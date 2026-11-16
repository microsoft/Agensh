#!/usr/bin/env python3
"""Native MCP stdio adapter; fixed trusted env, no HTTP or executable proxy.

Run as the worker MCP executable. A failed control call ends this connection;
there is no retry or native backend restart. Diagnostics contain fixed codes
only. The host broker retains accepted side effects if this client disappears.
"""
import os,sys
from common import Refused,need,strict,wire
from native_mcp_policy import FRAME_CAP
from native_mcp_bridge import McpClient

def main():
    client=McpClient(os.environ['AGENSH_MCP_SOCKET'],os.environ['AGENSH_MCP_CAPABILITY'])
    while True:
        raw=sys.stdin.buffer.readline(FRAME_CAP+1)
        if not raw:return 0
        need(len(raw)<=FRAME_CAP and raw.endswith(b'\n'),'MCP_WORKER_FRAME_BOUND')
        message=strict(raw);response=client.call(message)
        if response is not None:sys.stdout.buffer.write(wire(response)+b'\n');sys.stdout.buffer.flush()
if __name__=='__main__':
    try:raise SystemExit(main())
    except Refused as e:sys.stderr.write(e.code+'\n');raise SystemExit(1)
    except Exception:sys.stderr.write('MCP_STDIO_CONTROL_UNKNOWN_NO_RETRY\n');raise SystemExit(1)
