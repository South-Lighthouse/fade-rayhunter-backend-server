"""
Shared tshark `-T ek` field-flattening logic.

This normalization (SKIP_LAYERS, the dotted-path building, the nas-eps
merge, noise filtering) is the exact logic `radio/scripts/generate_fields.py`
used to build `radio/raw_path_lookup.json`. The pipeline (`radio/parsing.py`)
has to reproduce it bit-for-bit, or the raw_path keys in that lookup table
won't match what it computes at ingest time -- so both import this module
instead of each keeping their own copy.
"""
import re

SKIP_LAYERS = {"frame", "eth", "ip", "udp", "raw", "gsmtap", "pkt_comment"}
NOISE_PATTERNS = [
    re.compile(r"^per_per_"),
    re.compile(r"^text$"),
    re.compile(r"spare\d*$", re.IGNORECASE),
    re.compile(r"_ws_"),
]

NAS_MARKER = "nas-eps."


def is_noise(field_name):
    leaf = field_name.split(".")[-1]
    return any(p.search(leaf) for p in NOISE_PATTERNS)


def short(f):
    return (f.replace("lte_rrc.lte_rrc_lte-rrc_", "")
             # Wireshark's nas-eps dissector doubles its own prefix inside
             # the ek field name, but not consistently across versions --
             # tshark 4.6.4 emits "nas-eps_nas-eps_<leaf>", tshark 4.0.17
             # (the one actually shipped in the Docker image) emits
             # "nas-eps_nas_eps_<leaf>" for the same field. Strip both.
             .replace("nas-eps.nas-eps_nas-eps_", "nas.")
             .replace("nas-eps.nas-eps_nas_eps_", "nas.")
             .replace("nas-eps.", "nas.")
             .replace("lte_rrc.", ""))


def normalize_key(prefix, layer):
    idx = prefix.find(NAS_MARKER)
    if layer == "lte_rrc" and idx != -1:
        return prefix[idx:]
    return prefix


def flatten_packet(layers):
    """
    layers: the `pkt["layers"]` dict from one `-T ek` data line.
    Returns {raw_path: [value, ...]} across all non-skipped layers --
    matching generate_fields.py's packet_values accumulator for a single
    packet. Explicit `None` leaves are dropped (same as generate_fields.py):
    they're ASN.1 "element present" markers, not real values.
    """
    packet_values = {}

    def _flatten(prefix, obj, layer):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.startswith("_ws") or k.endswith("_raw"):
                    continue
                _flatten(f"{prefix}.{k}" if prefix else k, v, layer)
        elif isinstance(obj, list):
            for item in obj:
                _flatten(prefix, item, layer)
        elif obj is not None:
            key = normalize_key(prefix, layer)
            packet_values.setdefault(key, []).append(obj)

    for layer, content in layers.items():
        if layer in SKIP_LAYERS:
            continue
        _flatten(layer, content, layer)

    return packet_values
