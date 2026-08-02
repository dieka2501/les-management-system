from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.app.main import default_host, default_port, parse_host_value


class ServerConfigTestCase(unittest.TestCase):
    def test_default_host_is_local_outside_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "", "RAILWAY_SERVICE_ID": ""}, clear=False):
            self.assertEqual("127.0.0.1", default_host())

    def test_default_host_binds_all_interfaces_on_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("0.0.0.0", default_host())

    def test_railway_ignores_explicit_host_for_socket_bind(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("0.0.0.0", default_host())

    def test_explicit_host_wins_outside_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1", "RAILWAY_ENVIRONMENT": ""}, clear=False):
            self.assertEqual("127.0.0.1", default_host())

    def test_host_value_can_include_port_for_local_runs(self) -> None:
        self.assertEqual(("127.0.0.1", 9000), parse_host_value("127.0.0.1:9000"))

    def test_port_env_wins_over_host_port(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1:9000", "PORT": "7000"}, clear=False):
            self.assertEqual(7000, default_port())

    def test_default_port_can_fallback_to_host_port(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1:9000", "PORT": ""}, clear=False):
            self.assertEqual(9000, default_port())


if __name__ == "__main__":
    unittest.main()
