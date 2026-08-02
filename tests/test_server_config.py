from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.app.main import default_host


class ServerConfigTestCase(unittest.TestCase):
    def test_default_host_is_local_outside_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "", "RAILWAY_SERVICE_ID": ""}, clear=False):
            self.assertEqual("127.0.0.1", default_host())

    def test_default_host_binds_all_interfaces_on_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("0.0.0.0", default_host())

    def test_explicit_host_wins(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("127.0.0.1", default_host())


if __name__ == "__main__":
    unittest.main()
