"""
Decodes Timing Advance (TA) from a GSMTAP type-15 (LteMacFramed) packet
payload, as written by tools/qmdl2pcap (which mirrors the exact byte layout
Rayhunter's lib/src/gsmtap/mac.rs constructs for a MAC RACH response).

tshark does not dispatch GSMTAP type 15 to a mac-lte sub-dissector, so TA
isn't available as an ordinary tshark field (`-T fields -e mac-lte.rar.ta`
returns nothing) -- it has to be unpacked from the raw payload bytes
directly, which is what this module does. The raw bytes themselves ARE
available via tshark as `data.data` on any `gsmtap.type==15` packet.

Verified against 2298 real packets across 27 sessions: 0 decode failures,
0% sentinel values, a physically plausible 0-134 range (see
docs/radio-field-inventory.md for the full verification writeup).
"""
from __future__ import annotations

# Qualcomm's sentinel meaning "RAR received but TA was not valid", which
# becomes exactly 2047 after the 11-bit mask below -- excluded rather than
# treated as a real measurement. Didn't appear in the 2298-packet sample,
# but the check is cheap defensive insurance against the rare case.
TA_SENTINEL = 2047

# RACH response payloads written by our GSMTAP conversion are always this
# many bytes: Header(3) + payload tag(1) + ETRAPIDSubheader(1) + RACHResponse(6).
EXPECTED_PAYLOAD_LEN = 11

RNTI_TYPE_RA = 2  # Random-access RNTI -- required for a RACH response
PAYLOAD_TAG = 0x01


def decode_timing_advance(payload: bytes) -> int | None:
    """
    Byte layout (mirrors lib/src/gsmtap/mac.rs's RACHResponse writer):
      byte0    radio_type   (enum, 1=FDD/2=TDD)
      byte1    direction    (enum, 0=Uplink/1=Downlink)
      byte2    rnti_type    (enum, 2=RA-RNTI -- required for a RACH response)
      byte3    payload tag  (always 0x01)
      byte4    ETRAPIDSubheader (extended:1b, type_field:1b, rapid:6b)
      byte5-10 RACHResponse: pad(1b) + tac(11b) + ul_grant(20b) + tc_rnti(16b),
               48 bits packed big-endian across the 6 bytes

    Returns None if the payload isn't this exact 11-byte RACH-response shape,
    isn't an RA-RNTI packet, or decodes to the sentinel (no valid TA).
    """
    if len(payload) != EXPECTED_PAYLOAD_LEN:
        return None

    rnti_type, tag = payload[2], payload[3]
    if tag != PAYLOAD_TAG or rnti_type != RNTI_TYPE_RA:
        return None

    rach_bits = int.from_bytes(payload[5:11], "big")
    # tc_rnti(16b) and ul_grant(20b) are unpacked here even though unused --
    # they're part of the same bitstream as tac and documented for anyone
    # who wants to extend this later (e.g. tc_rnti for RACH-attempt linkage).
    rach_bits >>= 16  # discard tc_rnti
    rach_bits >>= 20  # discard ul_grant
    tac = rach_bits & 0x7FF  # remaining 11 bits (pad bit already shifted off)

    if tac == TA_SENTINEL:
        return None

    return tac


def decode_timing_advance_hex(hex_str: str) -> int | None:
    """Convenience wrapper for tshark's `data.data` field format (colon-separated hex)."""
    return decode_timing_advance(bytes.fromhex(hex_str.replace(":", "")))
