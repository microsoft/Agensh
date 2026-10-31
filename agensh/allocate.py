# Choose host ports and Docker subnets for a team profile.
# Listed tasks keep their fixed slots; other tasks get the first slot whose ports
# and subnets are free on this host and unused by other profiles.

import glob
import ipaddress
import os
import socket
import subprocess


def subnet_layout(workers):
    """Prefix for the worker network, and how many /24 units one slot spans."""
    prefix = 24
    need = 2 * workers + 8 + 6
    while (1 << (32 - prefix)) - 2 < need and prefix > 16:
        prefix -= 1
    units = 1 << (24 - prefix)
    stride = 3 if units == 1 else 2 * units
    return prefix, units, stride


def slot(index, port_base, octet, workers):
    """Ports and subnets of slot `index`, as the profile generator has always laid them out."""
    prefix, units, stride = subnet_layout(workers)
    sub = index * stride
    if sub + units + 1 > 255:
        return None
    http = port_base + index * 10
    return {
        'EDGE_HTTP_PORT': http, 'EDGE_MM_PORT': http + 2,
        'AGENSH_SUBNET_DEFAULT': f'10.{octet}.{sub}.0/{prefix}',
        'AGENSH_SUBNET_EGRESS': f'10.{octet}.{sub + units}.0/24',
        'AGENSH_SUBNET_EDGE': f'10.{octet}.{sub + units + 1}.0/24',
    }


def overlaps(candidate, taken_networks):
    network = ipaddress.ip_network(candidate, strict=False)
    return any(network.overlaps(other) for other in taken_networks)


def choose_slot(port_base, octet, workers, taken_ports, taken_networks, port_free, start=0):
    """First slot from `start` whose ports are free and subnets do not overlap anything taken."""
    index = start
    while True:
        candidate = slot(index, port_base, octet, workers)
        if candidate is None:
            raise ValueError(f'no free slot in 10.{octet}.0.0/16 for {workers} workers from slot {start}')
        ports = (candidate['EDGE_HTTP_PORT'], candidate['EDGE_MM_PORT'])
        if candidate['EDGE_MM_PORT'] > 65535:
            raise ValueError('port range exhausted; choose a lower PORT_BASE')
        networks = [candidate[key] for key in ('AGENSH_SUBNET_DEFAULT', 'AGENSH_SUBNET_EGRESS', 'AGENSH_SUBNET_EDGE')]
        if (not any(port in taken_ports or not port_free(port) for port in ports)
                and not any(overlaps(network, taken_networks) for network in networks)):
            return index, candidate
        index += 1


# Host and profile inspection, best effort: anything unreadable is simply not counted.

def profile_claims(env_dir, exclude):
    ports, networks = set(), []
    for path in glob.glob(os.path.join(env_dir, '.env.*')):
        if os.path.abspath(path) == os.path.abspath(exclude):
            continue
        try:
            lines = open(path, encoding='utf-8').read().splitlines()
        except OSError:
            continue
        for line in lines:
            key, _, value = line.partition('=')
            if key in ('EDGE_HTTP_PORT', 'EDGE_MM_PORT') and value.isdigit():
                ports.add(int(value))
            elif key.startswith('AGENSH_SUBNET_') and value:
                try:
                    networks.append(ipaddress.ip_network(value, strict=False))
                except ValueError:
                    pass
    return ports, networks


def host_networks():
    networks = []
    commands = [['ip', '-4', 'route'],
                ['sh', '-c', 'sudo -n docker network inspect $(sudo -n docker network ls -q) '
                             '--format "{{range .IPAM.Config}}{{.Subnet}} {{end}}"']]
    for command in commands:
        try:
            text = subprocess.run(command, capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for token in text.split():
            if '/' in token:
                try:
                    network = ipaddress.ip_network(token, strict=False)
                except ValueError:
                    continue
                if network.version == 4 and network.prefixlen > 0:
                    networks.append(network)
    return networks


def port_is_free(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', port))
        except OSError:
            return False
    return True
