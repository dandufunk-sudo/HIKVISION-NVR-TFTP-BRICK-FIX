#!/usr/bin/env python3
"""
Hikvision unbrick TFTP server – Python 3 / IDLE compatible
Original author: Scott Lamb
Modernised & fully debugged by Grok (2025)
"""

import argparse
import binascii
import errno
import os
import select
import socket
import struct
import sys
import time

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
HANDSHAKE_BYTES = struct.pack('20s', b'SWKH')
HANDSHAKE_PORT = 9978
TFTP_PORT = 69
TIME_FMT = '%c'
DEFAULT_BLOCK_SIZE = 512

# TFTP op-codes (RFC 1350)
OP_RRQ   = 1
OP_DATA  = 3
OP_ACK   = 4
OP_OACK  = 6
ACK_PREFIX = struct.pack('>H', OP_ACK)


class TFTPError(Exception):
    """Raised for controlled server-setup problems."""
    pass


class TFTPServer:
    def __init__(self, handshake_addr, tftp_addr, filename, data):
        self._data = data
        self._filename_bytes = filename.encode('utf-8')

        # Build the exact RRQ prefix the client sends (filename + \0octet\0)
        self._rrq_prefix = (
            struct.pack('>H', OP_RRQ) +
            self._filename_bytes + b'\x00octet\x00'
        )

        self._handshake_sock = self._bind(handshake_addr)
        self._tftp_sock      = self._bind(tftp_addr)

        self._set_block_size(DEFAULT_BLOCK_SIZE)

    # ------------------------------------------------------------------
    # Helper: bind a UDP socket with nice error messages
    # ------------------------------------------------------------------
    def _bind(self, addr):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(addr)
        except OSError as e:
            if e.errno == errno.EADDRNOTAVAIL:
                raise TFTPError(
                    f"IP {addr[0]} is not available on this machine.\n"
                    "  • Linux:   sudo ip addr add {addr[0]}/32 dev lo\n"
                    "  • macOS:   sudo ifconfig lo0 alias {addr[0]}\n"
                    "  • Windows: netsh interface ipv4 add address \"Loopback\" {addr[0]} 255.255.255.255"
                )
            if e.errno == errno.EADDRINUSE:
                raise TFTPError(f"Port {addr[1]} on {addr[0]} already in use.")
            if e.errno == errno.EACCES:
                raise TFTPError(f"Permission denied – run with sudo / Administrator.")
            raise
        return s

    # ------------------------------------------------------------------
    # Block size handling
    # ------------------------------------------------------------------
    def _set_block_size(self, size):
        print(f"Block size → {size} bytes")
        self._block_size = size
        self._total_blocks = (len(self._data) + size - 1) // size
        print(f"Serving {len(self._data)} bytes ({self._total_blocks} blocks)")

    def _check_limits(self):
        if self._total_blocks > 65535:
            raise TFTPError(f"File too large for block size {self._block_size}")

    # ------------------------------------------------------------------
    # TFTP option parsing (blksize only)
    # ------------------------------------------------------------------
    def _parse_options(self, pkt):
        # pkt = RRQ + filename + \0octet\0[option\0value\0...]
        try:
            after_mode = pkt.split(b'\x00octet\x00', 1)[1]
        except IndexError:
            return {}
        parts = after_mode.split(b'\x00')
        opts = {}
        i = 0
        while i < len(parts) - 1:
            key = parts[i].decode(errors='ignore').lower()
            val = parts[i + 1].decode(errors='ignore')
            if key:
                opts[key] = val
            i += 2
        print(f"Client options: {opts}")
        return opts

    # ------------------------------------------------------------------
    # Socket cleanup
    # ------------------------------------------------------------------
    def close(self):
        for s in (self._handshake_sock, self._tftp_sock):
            try:
                s.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Main event loop – 1-second timeout so Ctrl-C works instantly
    # ------------------------------------------------------------------
    def run(self):
        print("\n=== TFTP unbrick server STARTED ===")
        print(f"Listening on {self._tftp_sock.getsockname()}")
        print("Waiting for Hikvision handshake… (Ctrl-C to stop)\n")

        socks = [self._handshake_sock, self._tftp_sock]

        while True:
            try:
                readable, _, _ = select.select(socks, [], [], 1.0)
                for s in readable:
                    if s is self._handshake_sock:
                        self._handle_handshake()
                    else:
                        self._handle_tftp()
            except KeyboardInterrupt:
                print("\n\nInterrupted by user – shutting down.")
                break
            except Exception as e:
                print(f"\nUnexpected error: {e}")
                break

        self.close()
        print("Server stopped.")

    # ------------------------------------------------------------------
    # Handshake (SWKH magic)
    # ------------------------------------------------------------------
    def _handle_handshake(self):
        pkt, addr = self._handshake_sock.recvfrom(20)
        now = time.strftime(TIME_FMT)
        if pkt == HANDSHAKE_BYTES:
            self._handshake_sock.sendto(pkt, addr)
            print(f"{now} – Handshake OK from {addr[0]}")
        else:
            print(f"{now} – Bad handshake from {addr[0]}: {binascii.hexlify(pkt).decode()}")

    # ------------------------------------------------------------------
    # TFTP request / ACK handling
    # ------------------------------------------------------------------
    def _handle_tftp(self):
        pkt, addr = self._tftp_sock.recvfrom(65536)
        now = time.strftime(TIME_FMT)

        # ---- RRQ -------------------------------------------------------
        if pkt.startswith(self._rrq_prefix):
            opts = self._parse_options(pkt)

            if 'blksize' in opts:
                try:
                    sz = int(opts['blksize'])
                    if 8 <= sz <= 65464:
                        self._set_block_size(sz)
                        self._send_oack(addr)
                        return
                except ValueError:
                    pass

            self._check_limits()
            print(f"{now} – Starting transfer to {addr[0]}")
            self._send_block(0, addr)

        # ---- ACK -------------------------------------------------------
        elif pkt.startswith(ACK_PREFIX) and len(pkt) >= 4:
            block = struct.unpack('>H', pkt[2:4])[0]
            self._send_block(block, addr)

        # ---- Unknown ---------------------------------------------------
        else:
            print(f"{now} – Unexpected packet from {addr[0]}: {binascii.hexlify(pkt[:8]).decode()}...")

    # ------------------------------------------------------------------
    # Send OACK (option acknowledgement)
    # ------------------------------------------------------------------
    def _send_oack(self, addr):
        self._check_limits()
        oack = (
            struct.pack('>H', OP_OACK) +
            b'blksize\x00' + str(self._block_size).encode() + b'\x00'
        )
        self._tftp_sock.sendto(oack, addr)

    # ------------------------------------------------------------------
    # Send next DATA block (or finish)
    # ------------------------------------------------------------------
    def _send_block(self, prev_block, addr):
        block = prev_block + 1
        start = prev_block * self._block_size
        data = self._data[start:start + self._block_size]

        if not data:                                   # transfer finished
            now = time.strftime(TIME_FMT)
            print(f"\n{now} – DONE! {self._total_blocks} blocks sent.")
            if self._block_size != DEFAULT_BLOCK_SIZE:
                self._set_block_size(DEFAULT_BLOCK_SIZE)
            return

        pkt = struct.pack('>HH', OP_DATA, block) + data
        self._tftp_sock.sendto(pkt, addr)

        # ---- progress bar ------------------------------------------------
        width = 50
        filled = int(width * block / self._total_blocks)
        bar = '#' * filled + '-' * (width - filled)
        pct = block * 100 // self._total_blocks
        print(f"{time.strftime(TIME_FMT)} – {block:5d}/{self._total_blocks} [{bar}] {pct:3d}%", end='\r')

# ======================================================================
# Entry point
# ======================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Serve digicap.dav to unbrick a Hikvision device.'
    )
    parser.add_argument(
        '--filename', default='digicap.dav',
        help='Firmware file to serve (default: digicap.dav)'
    )
    parser.add_argument(
        '--server-ip', default='192.0.0.128',
        help='IP address the server binds to (default: 192.0.0.128)'
    )
    args = parser.parse_args()

    # ---- Load firmware ------------------------------------------------
    if not os.path.isfile(args.filename):
        print(f"\nFile not found: {args.filename}")
        print("   • Download digicap.dav and place it in the same folder.")
        sys.exit(1)

    try:
        with open(args.filename, 'rb') as f:
            firmware = f.read()
        if not firmware:
            raise ValueError("empty file")
    except Exception as e:
        print(f"\nCannot read '{args.filename}': {e}")
        sys.exit(1)

    # ---- Create server ------------------------------------------------
    server = None
    try:
        server = TFTPServer(
            (args.server_ip, HANDSHAKE_PORT),
            (args.server_ip, TFTP_PORT),
            args.filename,
            firmware
        )
    except TFTPError as e:
        print(f"\nSetup error:\n   {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected setup error: {e}")
        sys.exit(1)

    # ---- Run ----------------------------------------------------------
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.close()
        print("\nGoodbye!")
