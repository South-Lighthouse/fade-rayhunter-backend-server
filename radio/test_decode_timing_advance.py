import unittest

from radio.decode_timing_advance import (
    PAYLOAD_TAG,
    RNTI_TYPE_RA,
    TA_SENTINEL,
    decode_timing_advance,
    decode_timing_advance_hex,
)


def build_payload(tac, ul_grant=0, tc_rnti=0, rnti_type=RNTI_TYPE_RA, tag=PAYLOAD_TAG):
    """Constructs a valid 11-byte RACH-response payload for a given TA (inverse of decode)."""
    rach_bits = (tac << 36) | (ul_grant << 16) | tc_rnti  # pad bit is implicitly 0
    rach_bytes = rach_bits.to_bytes(6, "big")
    return bytes([1, 1, rnti_type, tag, 0x00]) + rach_bytes


class TestDecodeTimingAdvance(unittest.TestCase):
    def test_real_sample_from_production_capture(self):
        # Real packet observed in sensor "bre" session 1788277141, manually
        # decoded by hand and cross-checked against 2298 packets total.
        payload = bytes.fromhex("01" "01" "02" "01" "57" "00" "41" "3c" "4c" "58" "9f")
        self.assertEqual(decode_timing_advance(payload), 4)

    def test_hex_string_wrapper_matches_bytes_version(self):
        hex_str = "01:01:02:01:57:00:41:3c:4c:58:9f"
        self.assertEqual(decode_timing_advance_hex(hex_str), 4)

    def test_round_trip_small_value(self):
        payload = build_payload(tac=42)
        self.assertEqual(decode_timing_advance(payload), 42)

    def test_round_trip_zero(self):
        payload = build_payload(tac=0)
        self.assertEqual(decode_timing_advance(payload), 0)

    def test_round_trip_max_valid_value(self):
        # 11 bits max is 2047, but that's the sentinel -- 2046 is the largest
        # value that should still decode as real.
        payload = build_payload(tac=2046)
        self.assertEqual(decode_timing_advance(payload), 2046)

    def test_sentinel_value_returns_none(self):
        payload = build_payload(tac=TA_SENTINEL)
        self.assertIsNone(decode_timing_advance(payload))

    def test_wrong_length_returns_none(self):
        self.assertIsNone(decode_timing_advance(b"\x01\x01\x02\x01"))
        self.assertIsNone(decode_timing_advance(b"\x00" * 12))

    def test_wrong_rnti_type_returns_none(self):
        # rnti_type=3 (C-RNTI) instead of 2 (RA-RNTI) -- not a RACH response
        payload = build_payload(tac=10, rnti_type=3)
        self.assertIsNone(decode_timing_advance(payload))

    def test_wrong_tag_returns_none(self):
        payload = build_payload(tac=10, tag=0x02)
        self.assertIsNone(decode_timing_advance(payload))

    def test_ul_grant_and_tc_rnti_do_not_disturb_tac(self):
        payload = build_payload(tac=7, ul_grant=0xFFFFF, tc_rnti=0xFFFF)
        self.assertEqual(decode_timing_advance(payload), 7)


if __name__ == "__main__":
    unittest.main()
