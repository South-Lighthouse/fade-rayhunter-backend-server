#!/usr/bin/env python3
"""
Regenerates the RadioPacket field classification from real tshark output.

Not run as part of the build/pipeline -- a one-off dev tool, kept in-repo so
the doc -> real-ek-path -> classified-column mapping is reproducible later
(e.g. when promoting a raw_fields entry to a real column, or re-deriving
against a larger sample).

Usage:
    python3 radio/scripts/generate_fields.py <dir-of-pcapng-files> <doc-field-list.txt>

Where <doc-field-list.txt> is one candidate field name per line (the `field`
column from docs/radio-field-inventory.md's tables).

Classifies each candidate into:
  - scalar:    occurs at most once per packet -> a real dedicated column
               (IntegerField if every observed value is numeric, else
               CharField(max_length=32))
  - repeating: can occur more than once within a single packet (e.g. TMSIs
               in a Paging message, per-neighbor-cell measurements in a
               MeasurementReport) -> NOT a dedicated column. Routed to
               raw_fields as a JSON array instead -- a single scalar column
               can't hold "up to 42 values", and this is architecturally
               normal, not a rare edge case (verified: ~38% of candidates
               fell into this bucket against a real 7-session sample).
  - not_found: didn't appear in this sample at all (may need a larger
               sample, or may genuinely be rare) -> falls to raw_fields
               like any other unmapped field until confirmed otherwise.

Also excludes fields found to be pure duplicates of already-structured data:
e.g. `dedicatedInfoNAS`/`DedicatedInfoNAS` (raw hex NAS PDU bytes, redundant
with the already-separately-decoded `nas.*` columns).

Known decisions baked into the classification logic, not rediscovered here:
- NAS fields merged across their two nesting paths (standalone `nas-eps`
  layer vs. embedded in `lte_rrc`'s `dedicatedInfoNAS`) -- verified
  empirically elsewhere that both paths are driven by the same dissector.
- Decoder-internal noise excluded (ASN.1 PER bookkeeping, "spare" capability
  bits, array-index labels).
"""
import csv
import json
import re
import subprocess
import sys
import pathlib
from collections import defaultdict

from radio.ek_flatten import flatten_packet, is_noise, short

EXCLUDE_DOC_NAMES = {"dedicatedInfoNAS", "DedicatedInfoNAS"}


def to_snake(name):
    name = name.replace("-", "_").replace(".", "_")
    s = re.sub(r'(?<!^)(?=[A-Z][a-z])', '_', name)
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', s)
    s = re.sub(r'_+', '_', s).strip('_').lower()
    return s


INT32_MAX = 2_147_483_647  # Django IntegerField -> MySQL signed INT range


class Stats:
    def __init__(self):
        self.total_occurrences = 0
        self.max_per_packet = 0
        self.all_numeric = True
        self.max_abs_value = 0

    def add_packet_occurrences(self, values):
        n = len(values)
        self.total_occurrences += n
        self.max_per_packet = max(self.max_per_packet, n)
        for v in values:
            if isinstance(v, bool):
                self.all_numeric = False
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                self.all_numeric = False
                continue
            self.max_abs_value = max(self.max_abs_value, abs(f))


def classify(pcap_dir, doc_names):
    fields = defaultdict(Stats)
    pcaps = sorted(pathlib.Path(pcap_dir).glob("*.pcapng"))
    for pcap in pcaps:
        proc = subprocess.run(["tshark", "-r", str(pcap), "-T", "ek"], capture_output=True, text=True, check=True)
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith('{"index"'):
                continue
            try:
                pkt = json.loads(line)
            except json.JSONDecodeError:
                continue
            packet_values = flatten_packet(pkt.get("layers", {}))
            for key, values in packet_values.items():
                fields[key].add_packet_occurrences(values)

    real = {k: v for k, v in fields.items() if not is_noise(k)}
    by_short = defaultdict(list)
    for raw_path in real:
        by_short[short(raw_path)].append(raw_path)

    scalar, repeating, not_found, collisions = [], [], [], []
    seen_django_names = {}
    for name in doc_names:
        if name in EXCLUDE_DOC_NAMES:
            continue
        raw_paths = by_short.get(name, [])
        if not raw_paths:
            not_found.append(name)
            continue
        if len(raw_paths) > 1:
            collisions.append((name, raw_paths))
            continue
        raw_path = raw_paths[0]
        s = real[raw_path]
        django_name = to_snake(name)
        entry = (django_name, name, raw_path, s)

        # Route repeating fields away first -- a django_name "collision"
        # between two repeating fields is moot, neither becomes a column.
        if s.max_per_packet > 1:
            repeating.append(entry)
            continue
        if django_name in seen_django_names:
            collisions.append((name, [raw_path, seen_django_names[django_name]]))
            continue
        seen_django_names[django_name] = raw_path
        scalar.append(entry)

    return scalar, repeating, not_found, collisions


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    pcap_dir, doc_field_list = sys.argv[1], sys.argv[2]
    with open(doc_field_list) as f:
        doc_names = [line.strip() for line in f if line.strip()]

    scalar, repeating, not_found, collisions = classify(pcap_dir, doc_names)

    print(f"scalar (dedicated columns): {len(scalar)}", file=sys.stderr)
    print(f"repeating (-> raw_fields): {len(repeating)}", file=sys.stderr)
    print(f"not found in this sample: {len(not_found)}", file=sys.stderr)
    print(f"collisions (needs manual resolution): {len(collisions)}", file=sys.stderr)

    with open("final_model_fields.tsv", "w", newline="") as out:
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["django_name", "doc_name", "raw_path", "field_type", "max_abs_value"])
        for django_name, doc_name, raw_path, s in scalar:
            if not s.all_numeric:
                field_type = "CharField"
            else:
                # BigIntegerField uniformly, not just for fields observed
                # exceeding signed INT32 in this sample: identity-type
                # fields (IMSI, some TMSI/auth-code encodings) routinely do,
                # and relying on a 7-session sample to have shown the true
                # max for all 125 numeric fields is fragile. Storage cost is
                # a non-issue now that real classification shrank this to
                # 161 columns total (well under MySQL's row-size limit).
                field_type = "BigIntegerField"
            if s.max_abs_value > INT32_MAX:
                print(f"  NOTE: {django_name} observed max {int(s.max_abs_value)} exceeds INT32 -- BigIntegerField confirmed necessary, not just precautionary", file=sys.stderr)
            writer.writerow([django_name, doc_name, raw_path, field_type, int(s.max_abs_value)])

    with open("raw_path_lookup.json", "w") as out:
        # django_name -> raw ek path, for the actual parsing pipeline to map
        # tshark output onto model fields at ingestion time.
        lookup = {django_name: raw_path for django_name, _, raw_path, _ in scalar}
        json.dump(lookup, out, indent=2, sort_keys=True)

    if collisions:
        print("\nCOLLISIONS NEED MANUAL RESOLUTION:", file=sys.stderr)
        for name, paths in collisions:
            print(f"  {name}: {paths}", file=sys.stderr)


if __name__ == "__main__":
    main()
