// Our own reimplementation of Rayhunter's GPS-correlation behavior
// (daemon/src/gps.rs::load_gps_records + daemon/src/pcap.rs::find_nearest_gps
// in South-Lighthouse/rayhunter@lac-round-two), not a copy of their files --
// that logic lives in the daemon binary crate, not the reusable `lib` crate,
// so it isn't something we can depend on directly. Matching its exact
// behavior (same field names for direct deserialization from the real GPS
// ndjson format, same nearest-timestamp algorithm, same before/after
// tie-break) means a PCAP built here should carry the same GPS annotations
// the daemon's own /api/pcap endpoint would have produced for the same input.

use rayhunter::pcap::GpsPoint;
use serde::Deserialize;
use tokio::fs::File;
use tokio::io::{AsyncBufReadExt, BufReader};

#[derive(Deserialize)]
pub struct GpsRecord {
    pub latest_packet_timestamp: Option<i64>,
    #[allow(dead_code)]
    pub system_time: i64,
    pub lat: f64,
    pub lon: f64,
}

fn record_timestamp(r: &GpsRecord) -> i64 {
    r.latest_packet_timestamp.unwrap_or(i64::MIN)
}

// Rayhunter's own daemon/src/pcap.rs (South-Lighthouse/rayhunter@lac-round-two)
// reuses record_timestamp()'s i64::MIN sort sentinel to populate the emitted
// GpsPoint.unix_ts too -- confirmed directly against a real session: any
// packet near the start of a capture (before the first GPS fix has been
// correlated with a modem packet, so latest_packet_timestamp is still None)
// gets a GPS comment with unix_ts = -9223372036854775808, which crashes any
// downstream consumer that treats it as a real Unix timestamp. Keeping the
// sentinel for sorting/matching (same algorithm as upstream) but falling
// back to system_time -- always present, always a sane wall-clock value --
// rather than the sentinel for the value actually written out.
fn output_timestamp(r: &GpsRecord) -> i64 {
    r.latest_packet_timestamp.unwrap_or(r.system_time)
}

/// Reads GPS records from a Rayhunter `-gps.ndjson` file, sorted by
/// latest_packet_timestamp. Malformed lines are logged and skipped rather
/// than failing the whole file, matching the daemon's own tolerance for a
/// GPS log that wasn't always cleanly written.
pub async fn load_gps_records(path: &str) -> anyhow::Result<Vec<GpsRecord>> {
    let file = File::open(path).await?;
    let reader = BufReader::new(file);
    let mut lines = reader.lines();
    let mut records = Vec::new();

    while let Some(line) = lines.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<GpsRecord>(&line) {
            Ok(record) => records.push(record),
            Err(e) => eprintln!("skipping malformed GPS line: {e}"),
        }
    }

    records.sort_by_key(record_timestamp);
    Ok(records)
}

/// Nearest-timestamp match against a sorted GPS records list -- same
/// algorithm as the daemon's find_nearest_gps: binary search via
/// partition_point, ties prefer the earlier ("before") reading.
pub fn find_nearest_gps(records: &[GpsRecord], packet_timestamp: i64) -> Option<GpsPoint> {
    if records.is_empty() {
        return None;
    }

    let idx = records.partition_point(|r| record_timestamp(r) <= packet_timestamp);
    let record = if idx == 0 {
        &records[0]
    } else if idx >= records.len() {
        &records[records.len() - 1]
    } else {
        let (before, after) = (&records[idx - 1], &records[idx]);
        let before_delta = packet_timestamp - record_timestamp(before);
        let after_delta = record_timestamp(after) - packet_timestamp;
        if before_delta <= after_delta {
            before
        } else {
            after
        }
    };

    Some(GpsPoint {
        unix_ts: output_timestamp(record),
        latitude: record.lat,
        longitude: record.lon,
    })
}
