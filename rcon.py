"""Minimal Source RCON client (the game's built-in remote console).

Testscript-Pad uses it to talk to a running TF2: send commands and read
what they print. The protocol is plain TCP on the game's port:

    int32 size, int32 id, int32 type, body (NUL-terminated), NUL
    type 3 = auth, 2 = exec command / auth reply, 0 = command output
"""

import socket
import struct

AUTH, AUTH_RESPONSE, EXEC, RESPONSE = 3, 2, 2, 0


class RconError(Exception):
    pass


class Rcon:
    def __init__(self, host='127.0.0.1', port=27015, password='', timeout=3.0):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout
        self.sock = None
        self._id = 0

    # -- connection -------------------------------------------------------
    def connect(self):
        self.close()
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            self.sock = None
            raise RconError(f"can't connect to {self.host}:{self.port} ({e.strerror or e})") from None
        rid = self._send(AUTH, self.password)
        # the server answers with an empty RESPONSE packet, then the AUTH_RESPONSE
        while True:
            pid, ptype, _ = self._recv()
            if ptype == AUTH_RESPONSE:
                if pid == -1:
                    self.close()
                    raise RconError('wrong rcon password')
                if pid == rid:
                    return self

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    @property
    def connected(self):
        return self.sock is not None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # -- commands ---------------------------------------------------------
    def command(self, cmd):
        """Run a console command and return everything it printed."""
        if self.sock is None:
            self.connect()
        try:
            rid = self._send(EXEC, cmd)
            # an empty follow-up packet marks the end of a long, multi-packet reply
            end = self._send(RESPONSE, '')
            out = []
            while True:
                pid, ptype, body = self._recv()
                if pid == end:
                    break
                if pid == rid and ptype == RESPONSE:
                    out.append(body)
            return ''.join(out)
        except (OSError, RconError) as e:
            self.close()
            raise RconError(f'connection lost ({e})') from None

    # -- packets ----------------------------------------------------------
    def _send(self, ptype, body):
        self._id = self._id % 2_000_000_000 + 1
        data = struct.pack('<ii', self._id, ptype) + body.encode('utf-8', 'replace') + b'\x00\x00'
        self.sock.sendall(struct.pack('<i', len(data)) + data)
        return self._id

    def _recv_exact(self, n):
        buf = b''
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except socket.timeout:
                raise RconError('the game stopped answering') from None
            if not chunk:
                raise RconError('the game closed the connection')
            buf += chunk
        return buf

    def _recv(self):
        size = struct.unpack('<i', self._recv_exact(4))[0]
        if not 10 <= size <= 1_000_000:
            raise RconError(f'bad packet size {size}')
        data = self._recv_exact(size)
        pid, ptype = struct.unpack_from('<ii', data)
        return pid, ptype, data[8:-2].decode('utf-8', 'replace')
