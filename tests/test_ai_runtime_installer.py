from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path

from scripts.install_ai_runtime import UNITS, generate, install, unit_value


class InstallerTests(unittest.TestCase):
    def test_unit_builder_requires_valid_root_and_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "phd_agents").mkdir()
            (root / "phd_agents/server.py").write_text("")
            units = generate(root, Path("/usr/bin/python3"), root / "secret.env", 8765)
            self.assertEqual(set(units), set(UNITS))
            self.assertIn("scheduler-once", units["phd-atlas-ai-scheduler.service"])
            self.assertIn("OnCalendar=*-*-* 08,20:00:00", units["phd-atlas-ai-scheduler.timer"])
            self.assertIn("127.0.0.1", "127.0.0.1")
            with self.assertRaises(ValueError):
                generate(root, Path("/usr/bin/python3"), root / "secret.env", 80)
            with self.assertRaises(ValueError):
                unit_value("path\nmalicious")

    def test_install_keeps_credentials_file_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "systemd"
            envfile = root / "settings" / "provider.env"
            files = install({"unit.service": "example"}, folder, envfile, overwrite=False)
            self.assertEqual(len(files), 1)
            self.assertEqual(stat.S_IMODE(envfile.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                install({"unit.service": "changed"}, folder, envfile, overwrite=False)
            self.assertEqual(files[0].read_text(), "example")


if __name__ == "__main__":
    unittest.main()
