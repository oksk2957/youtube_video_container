"""Detect stale Next.js / Python services before starting the new one-shot editor."""
from __future__ import annotations

import socket
import sys

PORT_NAMES = {3000: "Next.js frontend", 8000: "FastAPI backend"}


def port_is_busy(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.45):
            return True
    except OSError:
        return False


def main() -> int:
    occupied = [(port, name) for port, name in PORT_NAMES.items() if port_is_busy(port)]
    if occupied:
        for port, name in occupied:
            print(f"[ERROR] 127.0.0.1:{port} is already occupied by a service ({name}).")
        print("[FIX] Close older Next.js/Node.js/Python server terminals first.")
        print("[FIX] In PowerShell: Get-NetTCPConnection -State Listen -LocalPort 3000,8000")
        print("[INFO] The one-shot editor uses NO S3, MinIO, or database.")
        return 1
    print("[OK] Ports 3000 and 8000 are available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
