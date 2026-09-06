import unittest
import os
import tempfile
from unittest.mock import patch
import test_analyzer
from src.generator import generate_report

class TestGenerator(unittest.TestCase):
    def test_generator_run(self):
        fixture = test_analyzer.TestAnalyzer()
        fixture.setUp()
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("src.generator.collect_all", return_value=fixture.sample_data):
            out_file = os.path.join(tmpdir, "test-report.html")
            out_path, analysis = generate_report(
                base_dir=r"D:\github\HemSoft",
                weeks=1,
                output_html=out_file
            )
            self.assertTrue(os.path.exists(out_file))
            self.assertGreater(os.path.getsize(out_file), 1000)
            
            with open(out_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Franz Hemmer", content)
            self.assertIn("Three.js", content)
            self.assertIn("chart-weekly-combo", content)

if __name__ == "__main__":
    unittest.main()
