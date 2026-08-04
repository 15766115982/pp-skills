"""Unit + golden-file tests for pp-kb-builder (stdlib unittest, no pytest).

Run from the skill directory:
    python -m unittest discover -s tests -v
"""

import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
sys.path.insert(0, SCRIPTS)

import pp_common as pp  # noqa: E402
import export_metadata as em  # noqa: E402


def dircmp_exact(a: str, b: str) -> list:
    """Return list of differences between two directory trees (byte-level)."""
    diffs = []
    a_files, b_files = set(), set()
    for root, _d, files in os.walk(a):
        for f in files:
            a_files.add(os.path.relpath(os.path.join(root, f), a))
    for root, _d, files in os.walk(b):
        for f in files:
            b_files.add(os.path.relpath(os.path.join(root, f), b))
    for f in sorted(a_files | b_files):
        pa, pb = os.path.join(a, f), os.path.join(b, f)
        if f not in a_files:
            diffs.append(f"only in {b}: {f}")
        elif f not in b_files:
            diffs.append(f"only in {a}: {f}")
        elif not filecmp.cmp(pa, pb, shallow=False):
            diffs.append(f"content differs: {f}")
    return diffs


class TestRedaction(unittest.TestCase):
    def test_sensitive_keys_dropped_recursively(self):
        raw = {
            "name": "flow1",
            "clientdata": json.dumps({"ok": 1}),
            "connectionReferences": {
                "ref1": {"$authentication": {"type": "SecureObject", "value": "xyz"},
                         "apiId": "/providers/shared_commondataserviceforapps",
                         "connectionRuntimeUrl": "https://abc.flow.com/"},
            },
            "nested": [{"password": "hunter2", "ClientSecret": "abc", "fine": True}],
        }
        clean, findings = pp.redact(raw)
        self.assertNotIn("$authentication", clean["connectionReferences"]["ref1"])
        self.assertNotIn("connectionRuntimeUrl", clean["connectionReferences"]["ref1"])
        self.assertEqual(clean["connectionReferences"]["ref1"]["apiId"],
                         "/providers/shared_commondataserviceforapps")
        self.assertNotIn("password", clean["nested"][0])
        self.assertNotIn("ClientSecret", clean["nested"][0])
        self.assertTrue(clean["nested"][0]["fine"])
        self.assertGreaterEqual(len(findings), 4)

    def test_scan_catches_jwt_and_secret_assignment(self):
        jwt_text = "header eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig"
        self.assertTrue(pp.redaction_scan_text(jwt_text, "t"))
        self.assertTrue(pp.redaction_scan_text('"clientSecret": "x9f8e7d6c5"', "t"))
        self.assertFalse(pp.redaction_scan_text("nothing sensitive here", "t"))


class TestLabelsAndMatching(unittest.TestCase):
    def test_label_of_prefers_requested_language(self):
        obj = {"LocalizedLabels": [
            {"Label": "Auftrag", "LanguageCode": 1031},
            {"Label": "Sales Order", "LanguageCode": 1033}]}
        self.assertEqual(pp.label_of(obj, 1033), "Sales Order")
        self.assertEqual(pp.label_of(obj, 9999), "Auftrag")  # fallback: first
        self.assertEqual(pp.label_of(None, 1033), "")

    def test_dual_channel_table_matching(self):
        entities = [
            {"LogicalName": "contoso_salesorder",
             "DisplayName": {"LocalizedLabels": [{"Label": "Sales Order", "LanguageCode": 1033}]}},
            {"LogicalName": "contoso_orderline",
             "DisplayName": {"LocalizedLabels": [{"Label": "Order Line", "LanguageCode": 1033}]}},
        ]
        matched, warnings = em.match_tables(
            entities, ["contoso_salesorder", "Order Line", "no_such_thing"], 1033)
        self.assertEqual([e["LogicalName"] for e in matched],
                         ["contoso_salesorder", "contoso_orderline"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("no_such_thing", warnings[0])


class TestGoldenFiles(unittest.TestCase):
    """Rebuild kb/dataverse from fixtures; must byte-match tests/golden/kb/dataverse."""

    def test_rebuild_matches_golden(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(FIXTURES)) as tmp:
            kb = os.path.join(tmp, "kb")
            shutil.copytree(os.path.join(FIXTURES, "_raw"), os.path.join(kb, "_raw"))
            cfg_path = os.path.join(tmp, "pp-kb.config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"outputDir": kb, "labelLanguage": 1033}, f)
            r = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "parse_metadata.py"), "--config", cfg_path],
                capture_output=True, text=True, cwd=SKILL_DIR)
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            diffs = dircmp_exact(os.path.join(kb, "dataverse"),
                                 os.path.join(GOLDEN, "kb", "dataverse"))
            self.assertEqual(diffs, [], msg="\n".join(diffs))

    def test_rebuild_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(FIXTURES)) as tmp:
            kb = os.path.join(tmp, "kb")
            shutil.copytree(os.path.join(FIXTURES, "_raw"), os.path.join(kb, "_raw"))
            cfg_path = os.path.join(tmp, "pp-kb.config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"outputDir": kb, "labelLanguage": 1033}, f)
            cmd = [sys.executable, os.path.join(SCRIPTS, "parse_metadata.py"), "--config", cfg_path]
            subprocess.run(cmd, capture_output=True, cwd=SKILL_DIR, check=True)
            with open(os.path.join(kb, "dataverse", "er-overview.md"), "rb") as f:
                snap1 = f.read()
            subprocess.run(cmd, capture_output=True, cwd=SKILL_DIR, check=True)
            with open(os.path.join(kb, "dataverse", "er-overview.md"), "rb") as f:
                snap2 = f.read()
            self.assertEqual(snap1, snap2)


class TestRedactionScanIntegration(unittest.TestCase):
    def test_parser_fails_loudly_on_leaked_secret(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(FIXTURES)) as tmp:
            kb = os.path.join(tmp, "kb")
            shutil.copytree(os.path.join(FIXTURES, "_raw"), os.path.join(kb, "_raw"))
            # plant a leaked secret in a raw file
            leak = os.path.join(kb, "_raw", "metadata", "contoso_salesorder.json")
            with open(leak, encoding="utf-8") as f:
                data = json.load(f)
            data["Attributes"][0]["clientSecret"] = "x9f8e7d6c5"
            with open(leak, "w", encoding="utf-8") as f:
                json.dump(data, f)
            cfg_path = os.path.join(tmp, "pp-kb.config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"outputDir": kb, "labelLanguage": 1033}, f)
            r = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "parse_metadata.py"), "--config", cfg_path],
                capture_output=True, text=True, cwd=SKILL_DIR)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("redaction scan FAILED", r.stderr)


if __name__ == "__main__":
    unittest.main()
