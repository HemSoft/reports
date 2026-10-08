"""Keep generated-workflow compatibility scoped while retaining other lint failures."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.check_workflows import check_workflows, MESSAGE


class WorkflowLintTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / ".sfl").mkdir()
        (self.root / ".github/workflows").mkdir(parents=True)
        self.workflow = self.root / ".github/workflows/sfl-pr-review-auto.yml"
        self.workflow.write_bytes(b"reviewed fixture bytes")
        self.manifest = {"version": "fixture", "sourceSha": "reviewed-source"}
        (self.root / ".sfl/sfl.json").write_text(json.dumps(self.manifest))
        self.contract = {
            "version": "fixture",
            "source_sha": "reviewed-source",
            "workflow_sha256": hashlib.sha256(self.workflow.read_bytes()).hexdigest(),
        }
        (self.root / ".sfl/lint-contract.json").write_text(json.dumps(self.contract))
        self.diagnostic = {
            "filepath": ".github/workflows/sfl-pr-review-auto.yml",
            "kind": "syntax-check",
            "message": MESSAGE,
            "line": 243,
            "column": 7,
        }

    def run_with(self, diagnostics, code=1, stderr="exit status 1"):
        result = subprocess.CompletedProcess([], code, json.dumps(diagnostics), stderr)
        with patch("scripts.check_workflows.subprocess.run", return_value=result):
            check_workflows(self.root)

    def test_only_exact_generated_workflow_diagnostic_is_compatible(self):
        self.run_with([self.diagnostic])
        self.run_with([], 0, "")
        for key, value in (
            ("filepath", "other.yml"),
            ("line", 1),
            ("column", 1),
            ("kind", "other"),
            ("message", "different finding"),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "Workflow lint finding"):
                    self.run_with([{**self.diagnostic, key: value}])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_with([self.diagnostic, self.diagnostic])

    def test_changed_deployment_cannot_reuse_the_contract(self):
        for changes in ({"version": "new"}, {"sourceSha": "new"}):
            (self.root / ".sfl/sfl.json").write_text(json.dumps({**self.manifest, **changes}))
            with self.assertRaisesRegex(ValueError, "reviewed lint contract"):
                self.run_with([])
        (self.root / ".sfl/sfl.json").write_text(json.dumps(self.manifest))
        self.workflow.write_bytes(b"changed workflow")
        with self.assertRaisesRegex(ValueError, "reviewed lint contract"):
            self.run_with([])

    def test_tool_failure_or_malformed_output_cannot_pass(self):
        with self.assertRaisesRegex(RuntimeError, "could not complete"):
            self.run_with([])
        with self.assertRaisesRegex(RuntimeError, "could not complete"):
            self.run_with([self.diagnostic], stderr="exit status 2")
        with self.assertRaisesRegex(ValueError, "diagnostic list"):
            self.run_with({})
