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
import export_flows as ef  # noqa: E402
import parse_flows as pf  # noqa: E402
import parse_canvas as pc  # noqa: E402
import build_crossrefs as bx  # noqa: E402

CANVAS_FIXTURE = os.path.join(FIXTURES, "canvas-src")


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
        """Full 5-script pipeline rebuild must byte-match tests/golden/kb."""
        with tempfile.TemporaryDirectory(dir=os.path.dirname(FIXTURES)) as tmp:
            kb = os.path.join(tmp, "kb")
            shutil.copytree(os.path.join(FIXTURES, "_raw"), os.path.join(kb, "_raw"))
            cfg_path = os.path.join(tmp, "pp-kb.config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"outputDir": kb, "labelLanguage": 1033,
                           "canvasSourcePath": CANVAS_FIXTURE,
                           "filters": {"screens": ["Order*"]}}, f)
            for script in ("parse_metadata.py", "parse_flows.py", "parse_canvas.py",
                           "build_crossrefs.py", "build_index.py"):
                env = dict(os.environ, PP_CANVAS_COMMIT="testcommit")
                r = subprocess.run(
                    [sys.executable, os.path.join(SCRIPTS, script), "--config", cfg_path],
                    capture_output=True, text=True, cwd=SKILL_DIR, env=env)
                self.assertEqual(r.returncode, 0, msg=f"{script}: {r.stderr}")
            diffs = dircmp_exact(kb, os.path.join(GOLDEN, "kb"))
            diffs = [d for d in diffs if not d.startswith("only in") or "_raw" not in d]
            diffs = [d for d in diffs if "_raw" not in d]
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


class TestFlows(unittest.TestCase):
    def _load_fixture(self, name):
        with open(os.path.join(FIXTURES, "_raw", "flows", name), encoding="utf-8") as f:
            return json.load(f)

    def test_decompress_gzip_clientdata(self):
        rec = self._load_fixture("8b4c1d3f-2222-4333-9444-fedcba654321.json")
        self.assertTrue(rec["clientdataiscompressed"])
        text = ef.decompress_clientdata(rec)
        obj = json.loads(text)
        self.assertIn("definition", obj)
        self.assertIn("Daily_recurrence", obj["definition"]["triggers"])

    def test_decompress_passthrough_when_uncompressed(self):
        rec = self._load_fixture("7f3a9c2e-1111-4222-8333-abcdef012345.json")
        self.assertEqual(ef.decompress_clientdata(rec), rec["clientdata"])

    def test_sanitize_flow_record_strips_embedded_secrets(self):
        rec = {
            "workflowid": "w1", "name": "Leak Test", "clientdataiscompressed": False,
            "clientdata": json.dumps({
                "connectionReferences": {"r1": {"apiId": "/apis/x",
                                                "$authentication": {"value": "secret-xyz"}}},
                "definition": {"triggers": {}, "actions": {}}}),
            "connectionreferences": json.dumps({"connectionReferences": {
                "r1": {"apiId": "/apis/x", "connectionName": "7f3a9c2e-real-guid", "id": "/conn/real"}}}),
        }
        clean, findings = ef.sanitize_flow_record(rec)
        cd = json.loads(clean["clientdata"])
        self.assertNotIn("$authentication", cd["connectionReferences"]["r1"])
        cr = json.loads(clean["connectionreferences"])
        self.assertEqual(cr["connectionReferences"]["r1"]["connectionName"], "<redacted-instance>")
        self.assertNotIn("real-guid", json.dumps(clean))
        self.assertGreaterEqual(len(findings), 2)

    def test_flow_wildcard_matching(self):
        records = [{"name": "Contoso Order Approval", "workflowid": "1"},
                   {"name": "Daily Order Digest", "workflowid": "2"},
                   {"name": "Invoice Sync", "workflowid": "3"}]
        matched, warnings = ef.match_flows(records, ["*order*"])
        self.assertEqual({r["workflowid"] for r in matched}, {"1", "2"})
        matched, warnings = ef.match_flows(records, ["Nothing*"])
        self.assertEqual(matched, [])
        self.assertEqual(len(warnings), 1)

    def test_runafter_graph_extraction(self):
        rec = self._load_fixture("7f3a9c2e-1111-4222-8333-abcdef012345.json")
        cd = json.loads(ef.decompress_clientdata(rec))
        rows, edges = [], []
        pf.walk_actions(cd["definition"]["actions"], rows, edges)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(len(rows), 5)
        self.assertEqual(by_name["Check_total_amount"]["type"], "If")
        self.assertEqual(by_name["Update_status_approved"]["branch"], "true")
        self.assertEqual(by_name["Send_approval_email"]["branch"], "false")
        graph = pf.build_graph("When_a_row_is_created", rows)
        self.assertIn('Check_total_amount{"Check_total_amount"}', graph)
        self.assertIn('Check_total_amount -- "true" --> Update_status_approved', graph)
        self.assertIn('Check_total_amount -- "false" --> Send_approval_email', graph)
        self.assertIn("Get_order_lines --> Check_total_amount", graph)


class TestCanvas(unittest.TestCase):
    def test_yaml_loader_no_bool_coercion(self):
        import yaml
        doc = yaml.load("a: On\nb: off\nc: yes\nd: =false\n", Loader=pc.PaLoader)
        self.assertEqual(doc["a"], "On")      # not True
        self.assertEqual(doc["b"], "off")     # not False
        self.assertEqual(doc["c"], "yes")
        self.assertEqual(doc["d"], "=false")  # formula untouched

    def test_merge_and_provenance(self):
        merged, provenance = pc.load_app(os.path.join(CANVAS_FIXTURE, "SalesHub", "Src"))
        self.assertEqual(set(merged["Screens"]),
                         {"OrderListScreen", "OrderDetailScreen", "SettingsScreen"})
        self.assertIn("HeaderBar", merged["ComponentDefinitions"])
        self.assertEqual(merged["DataSources"]["Sales Orders"]["Parameters"]["TableLogicalName"],
                         "contoso_salesorder")
        self.assertTrue(provenance[("Screens", "OrderListScreen")].endswith("OrderListScreen.pa.yaml"))

    def test_control_tree_and_formulas(self):
        merged, _ = pc.load_app(os.path.join(CANVAS_FIXTURE, "SalesHub", "Src"))
        rows = pc.screen_rows(merged["Screens"]["OrderListScreen"])
        self.assertEqual(len(rows), 7)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["lblOrderNumber"]["depth"], 1)
        self.assertEqual(by_name["galOrders"]["type"], "Gallery")
        fx = pc.formulas_of(rows, "OrderListScreen")
        nav = pc.nav_edges(fx)
        self.assertEqual({t for _c, _p, t in nav}, {"OrderDetailScreen"})
        self.assertIn("colOrders", pc.collection_names(fx))
        self.assertIn("Sales Orders", pc.table_refs(fx, set(merged["DataSources"])))

    def test_two_tier_screen_matching(self):
        names = ["OrderListScreen", "OrderDetailScreen", "SettingsScreen"]
        self.assertEqual(pc.match_screens(names, ["Order*"]),
                         {"OrderListScreen", "OrderDetailScreen"})
        self.assertEqual(pc.match_screens(names, []), set(names))  # no filter = all full


class TestCrossrefs(unittest.TestCase):
    def _kb_tables(self):
        return bx.load_kb_tables(os.path.join(FIXTURES, "_raw", "metadata"))

    def test_resolve_table_three_channels(self):
        kb = self._kb_tables()
        self.assertEqual(bx.resolve_table("contoso_salesorder", kb), "contoso_salesorder")   # logical
        self.assertEqual(bx.resolve_table("contoso_salesorders", kb), "contoso_salesorder")  # entity set
        self.assertEqual(bx.resolve_table("Sales Order", kb), "contoso_salesorder")          # display
        self.assertIsNone(bx.resolve_table("contoso_invoiceline", kb))                       # external

    def test_external_boundary_detection(self):
        kb = self._kb_tables()
        flows, ext = bx.collect_flow_refs(os.path.join(FIXTURES, "_raw", "flows"), kb)
        self.assertIn("contoso_invoiceline", ext)
        digest = flows["Daily Order Digest"]["tables"]
        self.assertIn("contoso_salesorder", digest)
        self.assertTrue(any(t.endswith(bx.EXTERNAL) for t in digest))

    def test_app_table_and_connector_refs(self):
        kb = self._kb_tables()
        cfg = {"canvasSourcePath": CANVAS_FIXTURE}
        apps, ext = bx.collect_app_refs(cfg, kb)
        self.assertEqual(set(apps["SalesHub"]["tables"]),
                         {"contoso_orderline", "contoso_salesorder"})
        self.assertIn("shared_office365", apps["SalesHub"]["connectors"])
        self.assertEqual(ext, set())

    def test_used_by_rewrite(self):
        with tempfile.TemporaryDirectory(dir=os.path.dirname(FIXTURES)) as tmp:
            kb = os.path.join(tmp, "kb")
            shutil.copytree(os.path.join(FIXTURES, "_raw"), os.path.join(kb, "_raw"))
            tdir = os.path.join(kb, "dataverse", "tables")
            os.makedirs(tdir)
            doc = "# Table: contoso_salesorder (Sales Order)\n\n## Used by\n\n_(populated by build_crossrefs — phase 4)_\n\n---\n*Snapshot: x*\n"
            with open(os.path.join(tdir, "contoso_salesorder.md"), "w", encoding="utf-8") as f:
                f.write(doc)
            kb_tables = self._kb_tables()
            apps, _ = bx.collect_app_refs({"canvasSourcePath": CANVAS_FIXTURE}, kb_tables)
            flows, _ = bx.collect_flow_refs(os.path.join(FIXTURES, "_raw", "flows"), kb_tables)
            bx.rewrite_used_by(kb, apps, flows, kb_tables)
            with open(os.path.join(tdir, "contoso_salesorder.md"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("[SalesHub](../../apps/SalesHub/overview.md)", text)
            self.assertIn("[Daily Order Digest](../../flows/daily-order-digest.md)", text)
            self.assertNotIn("phase 4", text)
            self.assertTrue(text.endswith("*Snapshot: x*\n"))


if __name__ == "__main__":
    unittest.main()
