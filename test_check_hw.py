"""Unit tests for the parts of check_hw.py that need no hardware:
the LiDAR CRC-8 check and packet parsing. Run: python3 test_check_hw.py
"""
import unittest

import check_hw


def _make_packet(distance_mm, intensity=200):
    # Minimal fake LD06/LD19 packet: header, speed, start_angle, then one
    # real point followed by filler points, end_angle, timestamp, crc.
    body = bytearray(check_hw._LIDAR_HEADER)
    body += (1000).to_bytes(2, "little")   # speed
    body += (0).to_bytes(2, "little")      # start_angle
    body += distance_mm.to_bytes(2, "little") + bytes([intensity])
    body += bytes(3 * 11)                  # 11 more empty points
    body += (0).to_bytes(2, "little")      # end_angle
    body += (0).to_bytes(2, "little")      # timestamp
    crc = check_hw._crc8(bytes(body))
    return bytes(body) + bytes([crc])


class LidarCrcTests(unittest.TestCase):
    def test_valid_packet_is_accepted(self):
        packet = _make_packet(distance_mm=1234)
        self.assertTrue(check_hw._packet_valid(packet))
        self.assertEqual(check_hw._packet_first_distance_mm(packet), 1234)

    def test_corrupted_byte_is_rejected(self):
        packet = bytearray(_make_packet(distance_mm=1234))
        packet[10] ^= 0xFF  # flip a data byte, crc byte untouched
        self.assertFalse(check_hw._packet_valid(bytes(packet)))

    def test_wrong_length_is_rejected(self):
        packet = _make_packet(distance_mm=1234)[:-1]
        self.assertFalse(check_hw._packet_valid(packet))


if __name__ == "__main__":
    unittest.main()
