import contextlib
import io
import unittest
from unittest.mock import patch

import cli


class TestCli(unittest.TestCase):
    def test_invalid_dates_fail_before_generation(self):
        cases = [
            ["--start", "2026-01-01"],
            ["--end", "2026-01-01"],
            ["--start", "2026-01-02", "--end", "2026-01-01"],
            ["--start", "not-a-date", "--end", "2026-01-01"],
            ["--weeks", "0"],
            ["--weeks", "-1"],
        ]
        for args in cases:
            with self.subTest(args=args), patch("sys.argv", ["cli.py", *args]), \
                    patch("cli.generate_report") as generate, \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as error:
                    cli.main()
                self.assertEqual(error.exception.code, 2)
                self.assertIn("error:", stderr.getvalue())
                generate.assert_not_called()
