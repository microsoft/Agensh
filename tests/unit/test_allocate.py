# Port and subnet allocation for team profiles.
# Run: python3 -m unittest discover -s tests/unit

import ipaddress
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agensh import allocate  # noqa: E402


def legacy_slot(idx, port_base, octet, workers):
    """Transcription of the former inline computation in scripts/pbench_gen_env.sh."""
    http = port_base + idx * 10
    prefix = 24
    need = 2 * workers + 8 + 6
    while (1 << (32 - prefix)) - 2 < need and prefix > 16:
        prefix -= 1
    units = 1 << (24 - prefix)
    stride = 3 if units == 1 else 2 * units
    sub = idx * stride
    if sub + units + 1 > 255:
        return None
    return {'EDGE_HTTP_PORT': http, 'EDGE_MM_PORT': http + 2,
            'AGENSH_SUBNET_DEFAULT': f'10.{octet}.{sub}.0/{prefix}',
            'AGENSH_SUBNET_EGRESS': f'10.{octet}.{sub + units}.0/24',
            'AGENSH_SUBNET_EDGE': f'10.{octet}.{sub + units + 1}.0/24'}


def always_free(_port):
    return True


class SlotTest(unittest.TestCase):
    def test_matches_legacy_layout(self):
        for workers in (1, 2, 8, 16, 120, 128, 1024):
            for idx in (0, 5, 19, 40, 84):
                with self.subTest(workers=workers, idx=idx):
                    self.assertEqual(allocate.slot(idx, 22000, 216, workers), legacy_slot(idx, 22000, 216, workers))

    def test_slot_subnets_do_not_overlap(self):
        for workers in (2, 128):
            networks = [ipaddress.ip_network(allocate.slot(i, 22000, 216, workers)[k])
                        for i in range(3) for k in ('AGENSH_SUBNET_DEFAULT', 'AGENSH_SUBNET_EGRESS', 'AGENSH_SUBNET_EDGE')]
            for a in range(len(networks)):
                for b in range(a + 1, len(networks)):
                    self.assertFalse(networks[a].overlaps(networks[b]), (workers, networks[a], networks[b]))


class ChooseSlotTest(unittest.TestCase):
    def test_first_free_slot_after_start(self):
        index, chosen = allocate.choose_slot(22000, 216, 2, set(), [], always_free, start=20)
        self.assertEqual(index, 20)
        self.assertEqual(chosen['EDGE_HTTP_PORT'], 22200)

    def test_skips_taken_ports_networks_and_busy_ports(self):
        taken_net = [ipaddress.ip_network('10.216.61.0/24')]   # slot 20's egress subnet
        index, _ = allocate.choose_slot(22000, 216, 2, set(), taken_net, always_free, start=20)
        self.assertEqual(index, 21)
        index, _ = allocate.choose_slot(22000, 216, 2, {22202}, [], always_free, start=20)
        self.assertEqual(index, 21)
        index, _ = allocate.choose_slot(22000, 216, 2, set(), [], lambda port: port != 22200, start=20)
        self.assertEqual(index, 21)

    def test_exhaustion_is_an_error(self):
        everything = [ipaddress.ip_network('10.216.0.0/16')]
        with self.assertRaises(ValueError):
            allocate.choose_slot(22000, 216, 2, set(), everything, always_free, start=20)


class ProfileClaimsTest(unittest.TestCase):
    def test_reads_other_profiles_only(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, '.env.a').write_text('EDGE_HTTP_PORT=22200\nEDGE_MM_PORT=22202\n'
                                                 'AGENSH_SUBNET_DEFAULT=10.216.60.0/24\nOTHER=x\n')
            mine = Path(directory, '.env.b')
            mine.write_text('EDGE_HTTP_PORT=22210\n')
            ports, networks = allocate.profile_claims(directory, str(mine))
        self.assertEqual(ports, {22200, 22202})
        self.assertEqual(networks, [ipaddress.ip_network('10.216.60.0/24')])


if __name__ == '__main__':
    unittest.main()
