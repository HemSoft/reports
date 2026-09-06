"""Run deterministic unit tests with empty GitHub credentials and network guards."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_real_run = subprocess.run


def guarded_run(*args, **kwargs):
    command = kwargs.get("args", args[0] if args else None)
    allowed = {"git", "git.exe", Path(sys.executable).name.lower()}
    if (
        not isinstance(command, (list, tuple))
        or not command
        or Path(command[0]).name.lower() not in allowed
        or kwargs.get("shell")
    ):
        raise AssertionError(f"Unexpected external command in unit test: {command}")
    return _real_run(*args, **kwargs)


def main():
    with tempfile.TemporaryDirectory() as config:
        environment = dict(os.environ, GH_CONFIG_DIR=config)
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
            environment.pop(key, None)
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("subprocess.run", side_effect=guarded_run),
            patch.object(
                socket, "create_connection", side_effect=AssertionError("Network in unit test")
            ),
            patch.object(
                socket.socket, "connect", side_effect=AssertionError("Network in unit test")
            ),
        ):
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
