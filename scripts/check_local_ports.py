"""Ensure localhost:3000 and the local Python API port are free."""
from __future__ import annotations

import socket
import sys

PORT_NAMES = {3000: "One-shot Next.js editor", 8100: "One-shot FastAPI backend"}


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
            print(f"[ERROR] 127.0.0.1:{port} is occupied ({name}).")
        print("[FIX] Close any existing one-shot editor terminals, then retry run.bat.")
        print("[FIX] PowerShell: Get-NetTCPConnection -State Listen -LocalPort 3000,8100")
        return 1
    print("[OK] Ports 3000 and 8100 are available for the one-shot editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
