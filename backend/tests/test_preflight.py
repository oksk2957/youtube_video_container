"""Make sure a running old server on port 3000 can be detected."""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_local_ports import port_is_busy


class PortTests(unittest.TestCase):
    def test_listener_is_detected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            self.assertTrue(port_is_busy(server.getsockname()[1]))

    def test_port_is_available_after_close(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            port = server.getsockname()[1]
        self.assertFalse(port_is_busy(port))


if __name__ == "__main__":
    unittest.main()
