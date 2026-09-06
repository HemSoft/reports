"""Temporary negative check for issue 10; removed after CI proves merge blocking."""

import unittest


class TestRequiredStatusProbe(unittest.TestCase):
    def test_required_validation_rejects_failure(self):
        self.fail("Intentional issue-10 required-status probe; must not merge this revision")
