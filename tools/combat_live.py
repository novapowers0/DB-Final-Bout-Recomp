"""Bounded local combat investigation client; never starts a game or edits RAM.

Inputs are explicit active-low PS1 words (FFFF=released). Screenshots must use a
new file. Disc/RAM payloads are printed only on explicit read, not saved in repo.
"""
import argparse
import json
from pathlib import Path
import socket
import time


def query(command, tcp_port=4370, **params):
    request = {'id': 1, 'cmd': command, **params}
    with socket.create_connection(('127.0.0.1', tcp_port), timeout=10) as connection:
        connection.sendall((json.dumps(request) + '\n').encode('ascii'))
        buffer = bytearray()
        deadline = time.monotonic() + 15
        while b'\n' not in buffer:
            connection.settimeout(max(0.01, deadline - time.monotonic()))
            chunk = connection.recv(65536)
            if not chunk or len(buffer) + len(chunk) > 2 * 1024 * 1024:
                raise ValueError('Missing or oversized reply')
            buffer.extend(chunk)
        reply = json.loads(buffer.split(b'\n', 1)[0])
        if reply.get('ok') is not True:
            raise ValueError(reply)
        return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('read', 'press', 'shot', 'status', 'quit', 'release'))
    parser.add_argument('args', nargs='*')
    parser.add_argument('--port', type=int, default=4370)
    args = parser.parse_args()
    params = {}
    if args.command == 'read':
        address, size = (int(v, 0) for v in args.args)
        if not 1 <= size <= 4096:
            parser.error('Read limited to 4096 bytes')
        command, params = 'read_ram', {'addr': hex(address), 'len': size}
    elif args.command == 'press':
        word = int(args.args[0], 0)
        frames = int(args.args[1]) if len(args.args) > 1 else 6
        port = int(args.args[2]) if len(args.args) > 2 else 1
        if not 0 <= word <= 0xFFFF or not 1 <= frames <= 600 or port not in (1, 2):
            parser.error('Invalid pad word, duration or port')
        command, params = 'press', {'buttons': word, 'frames': frames, 'port': port, 'pad_type': 0}
    elif args.command == 'shot':
        path = Path(args.args[0]).resolve()
        if path.exists() or not path.parent.is_dir():
            parser.error('Screenshot requires a new file in an existing folder')
        command, params = 'screenshot_file', {'path': str(path)}
    elif args.command == 'status':
        command = 'frame'
    elif args.command == 'release':
        command = 'clear_input'
    else:
        command = args.command
    print(json.dumps(query(command, args.port, **params), indent=2))


if __name__ == '__main__':
    main()
