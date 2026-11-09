"""Reserve dedicated one-shot ports; legacy S3 editor may continue on 3000/8000."""
from __future__ import annotations

import socket
import sys

PORT_NAMES = {3100: "One-shot Next.js editor", 8100: "One-shot FastAPI backend"}


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
        print("[FIX] PowerShell: Get-NetTCPConnection -State Listen -LocalPort 3100,8100")
        return 1
    if port_is_busy(3000):
        print("[NOTE] Port 3000 still has another app (possibly the old S3 editor).")
        print("[NOTE] This is OK: the one-shot editor opens at http://127.0.0.1:3100")
    print("[OK] Dedicated ports 3100 and 8100 are available for the one-shot editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
