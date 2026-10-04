from __future__ import annotations

import unittest

from backend.auth import hash_password, verify_password


class PasswordTest(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self) -> None:
        first = hash_password("secure123")
        second = hash_password("secure123")
        self.assertNotEqual(first, second)
        self.assertNotIn("secure123", first)
        self.assertTrue(verify_password("secure123", first))
        self.assertFalse(verify_password("wrong-password", first))

    def test_short_password_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("123")


if __name__ == "__main__":
    unittest.main()
