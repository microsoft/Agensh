#!/usr/bin/env python3
# Adapt docker exec stdio to the standalone worker's persistent ACP Unix socket.
# Preserve half-close on stdin EOF so remaining child output can still be drained.

import os
import socket
import threading
import time

connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
deadline = time.monotonic() + 60
while True:
    try:
        connection.connect('/opt/data/acp.sock')
        break
    except (FileNotFoundError, ConnectionRefusedError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.1)


def forward_input():
    try:
        while data := os.read(0, 65536):
            connection.sendall(data)
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass


threading.Thread(target=forward_input, daemon=True).start()
try:
    while data := connection.recv(65536):
        view = memoryview(data)
        # os.write may consume only part of a socket chunk.
        while view:
            view = view[os.write(1, view):]
finally:
    connection.close()
