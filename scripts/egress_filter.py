#!/usr/bin/env python3
# Forward proxy for the `allowlist` network mode: workers and CI jobs reach the
# internet only through it, and only to a fixed list of package registries plus
# the project's ALLOW_DOMAINS (comma-separated). HTTPS goes through CONNECT; plain
# HTTP (for example apt) through absolute-URI requests. Every decision is logged
# as a JSON line to EGRESS_LOG. The model endpoint stays behind egress-proxy.

import asyncio
import json
import os
import sys
import time

# Hosts match exactly or as a subdomain of an entry.
REGISTRIES = (
    'pypi.org', 'files.pythonhosted.org',
    'registry.npmjs.org', 'registry.yarnpkg.com',
    'crates.io', 'index.crates.io', 'static.crates.io',
    'proxy.golang.org', 'sum.golang.org',
    'deb.debian.org', 'security.debian.org',
    'archive.ubuntu.com', 'security.ubuntu.com', 'ports.ubuntu.com',
)
PORTS = (80, 443)
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', '3128'))
LOG_PATH = os.environ.get('EGRESS_LOG', '')
HEADER_LIMIT = 64 * 1024


def allowed_domains(extra=''):
    domains = [*REGISTRIES, *(d.strip().lower().strip('.') for d in extra.split(','))]
    return tuple(dict.fromkeys(d for d in domains if d))


DOMAINS = allowed_domains(os.environ.get('ALLOW_DOMAINS', ''))


def is_allowed(host, port, domains=DOMAINS):
    host = host.lower().rstrip('.')
    if port not in PORTS or not host or host.replace('.', '').isdigit() or ':' in host:
        return False  # Registries are named; literal addresses would bypass the list.
    return any(host == d or host.endswith('.' + d) for d in domains)


def record(client, method, host, port, decision):
    entry = {'at': round(time.time(), 3), 'client': client, 'method': method, 'host': host,
             'port': port, 'decision': decision}
    print(json.dumps(entry), file=sys.stderr, flush=True)
    if LOG_PATH:
        try:
            with open(LOG_PATH, 'a') as stream:
                stream.write(json.dumps(entry) + '\n')
        except OSError:
            pass


def target(method, uri, headers):
    # CONNECT host:port, or an absolute http:// URI (a Host header as the fallback).
    if method == 'CONNECT':
        host, _, port = uri.rpartition(':')
        return host.strip('[]'), int(port) if port.isdigit() else 0, None
    if uri.startswith('http://'):
        rest = uri[len('http://'):]
        authority, slash, path = rest.partition('/')
        host, _, port = authority.rpartition(':') if ':' in authority else (authority, '', '80')
        return host, int(port) if port.isdigit() else 0, '/' + path if slash else '/'
    return headers.get('host', ''), 80, uri


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader, client_writer):
    client = (client_writer.get_extra_info('peername') or ('?',))[0]
    try:
        head = await client_reader.readuntil(b'\r\n\r\n')
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        client_writer.close()
        return
    lines = head.decode('latin-1').split('\r\n')
    try:
        method, uri, version = lines[0].split(' ', 2)
    except ValueError:
        client_writer.close()
        return
    headers = {}
    for line in lines[1:]:
        key, sep, value = line.partition(':')
        if sep:
            headers[key.strip().lower()] = value.strip()
    host, port, path = target(method, uri, headers)
    if not is_allowed(host, port):
        record(client, method, host, port, 'denied')
        body = (f'agensh egress-filter: {host}:{port} is not on the allowlist; '
                'add it to [environment] allow_domains in the project file\n').encode()
        client_writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\n'
                            b'Connection: close\r\nContent-Length: %d\r\n\r\n%s' % (len(body), body))
        await client_writer.drain()
        client_writer.close()
        return
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), 30)
    except (OSError, asyncio.TimeoutError) as error:
        record(client, method, host, port, f'error: {error.__class__.__name__}')
        client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
        await client_writer.drain()
        client_writer.close()
        return
    record(client, method, host, port, 'allowed')
    if method == 'CONNECT':
        client_writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
        await client_writer.drain()
    else:
        # Forward the request with an origin-form path; later requests on this
        # connection go to the same host.
        first = f'{method} {path} {version}\r\n'.encode('latin-1')
        upstream_writer.write(first + head.split(b'\r\n', 1)[1])
        await upstream_writer.drain()
    await asyncio.gather(pipe(client_reader, upstream_writer), pipe(upstream_reader, client_writer))


async def main():
    server = await asyncio.start_server(handle, '0.0.0.0', LISTEN_PORT, limit=HEADER_LIMIT)
    print(f'egress-filter listening on :{LISTEN_PORT}; allowed: {", ".join(DOMAINS)}', file=sys.stderr, flush=True)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
