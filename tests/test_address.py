"""addrbook.address 的基线行为，锁定地址与网段的文本语义。"""

import unittest

from addrbook.address import (
    ADDR_MAX,
    block_size,
    broadcast_of,
    format_addr,
    format_cidr,
    network_of,
    parse_addr,
    parse_cidr,
    usable_bounds,
)


class ParseAddrTest(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(parse_addr("0.0.0.0"), 0)
        self.assertEqual(parse_addr("10.0.0.1"), 0x0A000001)
        self.assertEqual(parse_addr("255.255.255.255"), ADDR_MAX)

    def test_round_trip(self):
        for text in ("0.0.0.0", "10.0.0.1", "172.16.31.9", "255.255.255.255"):
            self.assertEqual(format_addr(parse_addr(text)), text)

    def test_bad_shapes(self):
        for text in ("", "10.0.0", "10.0.0.1.2", "10.0.0.", ".0.0.1", "10.0.0.256", "10.0.0.a"):
            with self.assertRaises(ValueError, msg=text):
                parse_addr(text)

    def test_leading_zero_rejected(self):
        with self.assertRaises(ValueError):
            parse_addr("010.0.0.1")
        with self.assertRaises(ValueError):
            parse_addr("10.0.0.01")

    def test_non_string_rejected(self):
        with self.assertRaises(TypeError):
            parse_addr(0x0A000001)


class FormatAddrTest(unittest.TestCase):
    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            format_addr(-1)
        with self.assertRaises(ValueError):
            format_addr(ADDR_MAX + 1)

    def test_non_int_rejected(self):
        with self.assertRaises(TypeError):
            format_addr("10.0.0.1")


class BlockTest(unittest.TestCase):
    def test_block_size(self):
        self.assertEqual(block_size(32), 1)
        self.assertEqual(block_size(31), 2)
        self.assertEqual(block_size(24), 256)
        self.assertEqual(block_size(0), 1 << 32)

    def test_block_size_rejects_bad_prefix(self):
        for prefix in (-1, 33, True):
            with self.assertRaises((ValueError, TypeError), msg=prefix):
                block_size(prefix)

    def test_network_and_broadcast(self):
        addr = parse_addr("192.168.7.130")
        self.assertEqual(format_addr(network_of(addr, 24)), "192.168.7.0")
        self.assertEqual(format_addr(broadcast_of(addr, 24)), "192.168.7.255")
        self.assertEqual(format_addr(network_of(addr, 26)), "192.168.7.128")
        self.assertEqual(format_addr(broadcast_of(addr, 26)), "192.168.7.191")


class ParseCidrTest(unittest.TestCase):
    def test_host_bits_normalized(self):
        network, prefix = parse_cidr("10.0.0.5/24")
        self.assertEqual(prefix, 24)
        self.assertEqual(network, parse_addr("10.0.0.0"))
        self.assertEqual(format_cidr(network, prefix), "10.0.0.0/24")

    def test_keeps_network_when_aligned(self):
        network, prefix = parse_cidr("192.168.4.0/22")
        self.assertEqual((format_addr(network), prefix), ("192.168.4.0", 22))

    def test_rejects_bad_text(self):
        for text in ("10.0.0.0", "10.0.0.0/33", "10.0.0.0/-1", "10.0.0.0/", "10.0.0.0/x", "10.0.0.0/2a"):
            with self.assertRaises(ValueError, msg=text):
                parse_cidr(text)


class UsableBoundsTest(unittest.TestCase):
    def test_slash_30_drops_edges(self):
        network, prefix = parse_cidr("10.0.0.0/30")
        first, last = usable_bounds(network, prefix)
        self.assertEqual((format_addr(first), format_addr(last)), ("10.0.0.1", "10.0.0.2"))

    def test_slash_31_keeps_both(self):
        network, prefix = parse_cidr("10.0.0.0/31")
        first, last = usable_bounds(network, prefix)
        self.assertEqual((format_addr(first), format_addr(last)), ("10.0.0.0", "10.0.0.1"))

    def test_slash_32_keeps_single(self):
        network, prefix = parse_cidr("10.0.0.7/32")
        first, last = usable_bounds(network, prefix)
        self.assertEqual((format_addr(first), format_addr(last)), ("10.0.0.7", "10.0.0.7"))


if __name__ == "__main__":
    unittest.main()
