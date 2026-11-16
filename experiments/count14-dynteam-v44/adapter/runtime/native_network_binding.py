"""Trusted cold network metadata -> original relay listen/Compose binding.

No Docker call, network creation, FORWARD/policy/sysctl/NAT or daemon change.
Only the launcher's fixed public network-inspect projection is consumed. A
fresh real network/kernel proof remains required before scientific activation.
"""
from dataclasses import dataclass
from pathlib import Path
import ipaddress

from common import need, digest


@dataclass(frozen=True)
class NativeNetworkBinding:
    trajectory: str
    experiment_root: str
    daemon_data_root: str
    network_id: str
    network_name: str
    gateway: str
    subnet: str
    contract_sha256: str
    qualification_only: bool

    def checked(self, *, contract, row, qualification_only):
        need(self.qualification_only is qualification_only and type(qualification_only) is bool and
             self.trajectory==row['trajectory_id'] and self.experiment_root==row['root'] and
             self.contract_sha256==digest(contract), 'DYNTEAM_EXACT_COLD_NATIVE_NETWORK_BINDING')
        root,daemon=Path(self.experiment_root),Path(self.daemon_data_root)
        need(root.is_absolute() and daemon.is_absolute() and '..' not in root.parts+daemon.parts,
             'DYNTEAM_NATIVE_NETWORK_CANONICAL_ROOT_METADATA')
        if qualification_only:
            need(any(p.startswith('OWN-') for p in root.parts) and
                 any(p.startswith('OWN-') for p in daemon.parts), 'DYNTEAM_OWN_NETWORK_EXPLICIT_ONLY')
        else:
            need((str(root).startswith('/mnt/ptb-scratch2/count14-dynteam') or (contract.get('mode')=='production' and digest(contract)=='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391' and row in contract['trajectories'] and str(root) in ('/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/u/b1', '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/u/b2', '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/u/b3', '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/r/b1', '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/r/b2', '/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/r/b3'))) and
                 (daemon.is_relative_to('/mnt/ptb-scratch2') or daemon.is_relative_to('/mnt/ptb-scratch')),
                 'DYNTEAM_NATIVE_DAEMON_AND_NEW_DATA_OFF_ROOT_DISK')
        need(type(self.network_id) is str and len(self.network_id)==64 and
             all(c in '0123456789abcdef' for c in self.network_id) and
             self.network_name=='ct14-dyn-c4-'+digest(self.trajectory)[:12],
             'DYNTEAM_EXACT_REGISTERED_NATIVE_NETWORK_ID_NAME')
        address=ipaddress.IPv4Address(self.gateway)
        subnet=ipaddress.IPv4Network(self.subnet, strict=True)
        private=(ipaddress.IPv4Network('10.0.0.0/8'),ipaddress.IPv4Network('172.16.0.0/12'),
                 ipaddress.IPv4Network('192.168.0.0/16'))
        need(address in subnet and address not in (subnet.network_address,subnet.broadcast_address) and
             (any(subnet.subnet_of(p) for p in private) or
              qualification_only and subnet.subnet_of(ipaddress.IPv4Network('127.0.0.0/8'))),
             'DYNTEAM_NATIVE_RELAY_BINDS_ONLY_EXACT_PRIVATE_BRIDGE_GATEWAY')
        return self

    @classmethod
    def from_public_inspect(cls, inspected, *, daemon_data_root, contract, row, qualification_only=False):
        need(type(inspected) is dict and inspected.get('Driver')=='bridge' and inspected.get('Scope')=='local' and
             inspected.get('Internal') is False and inspected.get('EnableIPv6') is False,
             'DYNTEAM_NATIVE_ORIGINAL_LOCAL_IPV4_BRIDGE_REQUIRED')
        labels=inspected.get('Labels')
        need(type(labels) is dict and labels.get('count14.root')==row['root'] and
             labels.get('count14.trajectory-sha256')==digest(row['trajectory_id']) and
             labels.get('count14.contract-sha256')==digest(contract),
             'DYNTEAM_NETWORK_LABELS_BIND_EXACT_NEW_SCOPE')
        ipam=inspected.get('IPAM')
        need(type(ipam) is dict and ipam.get('Driver')=='default' and
             type(ipam.get('Config')) is list and len(ipam['Config'])==1 and
             type(ipam['Config'][0]) is dict, 'DYNTEAM_ONE_NATIVE_IPV4_IPAM_CONFIG')
        config=ipam['Config'][0]
        return cls(row['trajectory_id'],row['root'],str(daemon_data_root),inspected.get('Id'),
                   inspected.get('Name'),config.get('Gateway'),config.get('Subnet'),digest(contract),
                   qualification_only).checked(contract=contract,row=row,qualification_only=qualification_only)
