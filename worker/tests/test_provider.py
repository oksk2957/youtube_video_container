import base64
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provider import decrypt_api_key, validate_base_url
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ProviderTests(unittest.TestCase):
    def test_aes256gcm_round_trip_compatible_with_node_format(self):
        key, iv = b"0" * 32, b"1" * 12
        ciphertext = AESGCM(key).encrypt(iv, b"secret-token", None)
        encoded = ".".join(base64.b64encode(x).decode() for x in
                           [iv, ciphertext[-16:], ciphertext[:-16]])
        old = os.getenv("AI_CONFIG_ENCRYPTION_KEY")
        try:
            os.environ["AI_CONFIG_ENCRYPTION_KEY"] = key.hex()
            self.assertEqual(decrypt_api_key(encoded), "secret-token")
        finally:
            if old is None:
                os.environ.pop("AI_CONFIG_ENCRYPTION_KEY", None)
            else:
                os.environ["AI_CONFIG_ENCRYPTION_KEY"] = old

    def test_base_url_host_allowlist(self):
        old = os.getenv("AI_ALLOWED_HOSTS")
        try:
            os.environ["AI_ALLOWED_HOSTS"] = "api.openai.com"
            self.assertEqual(validate_base_url("https://api.openai.com/v1"), "https://api.openai.com/v1")
            with self.assertRaises(ValueError):
                validate_base_url("http://169.254.169.254/latest")
            with self.assertRaises(ValueError):
                validate_base_url("https://internal.example/v1")
        finally:
            if old is None:
                os.environ.pop("AI_ALLOWED_HOSTS", None)
            else:
                os.environ["AI_ALLOWED_HOSTS"] = old

if __name__ == "__main__":
    unittest.main()
