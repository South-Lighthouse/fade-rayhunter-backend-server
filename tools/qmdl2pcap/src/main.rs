mod gps;

use anyhow::Result;
use clap::Parser;
use rayhunter::gsmtap::parser as gsmtap_parser;
use rayhunter::pcap::GsmtapPcapWriter;
use rayhunter::qmdl::QmdlMessageReader;
use tokio::fs::File;

#[derive(Parser)]
struct Args {
    /// Path to the input .qmdl (or decompressed) file
    qmdl_path: String,
    /// Optional path to a Rayhunter GPS ndjson file to correlate and embed
    #[arg(long)]
    gps: Option<String>,
    /// Output .pcapng path
    #[arg(short, long)]
    output: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    let gps_records = match &args.gps {
        Some(path) => gps::load_gps_records(path).await?,
        None => Vec::new(),
    };
    if let Some(path) = &args.gps {
        eprintln!("loaded {} GPS record(s) from {path}", gps_records.len());
    }

    let qmdl_file = File::open(&args.qmdl_path).await?;
    let mut reader = QmdlMessageReader::new(qmdl_file).await?;

    let out_file = File::create(&args.output).await?;
    let mut pcap_writer = GsmtapPcapWriter::new(out_file).await?;
    pcap_writer.write_iface_header().await?;

    let mut count = 0;
    let mut gps_matched = 0;
    while let Some(maybe_msg) = reader.get_next_message().await? {
        if let Ok(msg) = maybe_msg {
            if let Some((timestamp, gsmtap_msg)) = gsmtap_parser::parse(msg)? {
                let packet_unix_ts = timestamp.to_datetime().timestamp();
                let gps_point = gps::find_nearest_gps(&gps_records, packet_unix_ts);
                if gps_point.is_some() {
                    gps_matched += 1;
                }
                pcap_writer
                    .write_gsmtap_message(gsmtap_msg, timestamp, gps_point.as_ref())
                    .await?;
                count += 1;
            }
        }
    }

    eprintln!(
        "wrote {count} GSMTAP message(s) to {} ({gps_matched} with GPS)",
        args.output
    );
    Ok(())
}
