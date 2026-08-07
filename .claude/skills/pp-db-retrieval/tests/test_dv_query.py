"""Offline tests for pp-db-retrieval (stdlib unittest; no network).

Run from the skill directory:
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from unittest import mock

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

import dv_query as dq  # noqa: E402

FIXTURE_KB_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "fixtures", "contoso_salesorder.md")


def _cfg_with_kb(tmp):
    kb_tables = os.path.join(tmp, "kb", "dataverse", "tables")
    os.makedirs(kb_tables, exist_ok=True)
    with open(FIXTURE_KB_MD, encoding="utf-8") as f:
        content = f.read()
    with open(os.path.join(kb_tables, "contoso_salesorder.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return {"outputDir": os.path.join(tmp, "kb"), "dataverseUrl": "https://x.crm.dynamics.com"}


class TestSqlGuard(unittest.TestCase):
    def test_accepts_plain_select(self):
        self.assertEqual(dq.guard_sql("  SELECT name FROM account "), "SELECT name FROM account")
        self.assertTrue(dq.guard_sql("select top 5 a from b").startswith("select"))

    def test_rejects_writes(self):
        for bad in ("INSERT INTO account VALUES (1)",
                    "SELECT name INTO backup FROM account",
                    "UPDATE account SET name='x'",
                    "DELETE FROM account",
                    "SELECT 1; DROP TABLE account",
                    "SELECT 1 -- comment\nFROM account",
                    "SELECT /* x */ 1",
                    "EXEC sp_who",
                    "DROP TABLE account",
                    "SELECT * FROM xp_cmdshell"):
            with self.assertRaises(ValueError, msg=bad):
                dq.guard_sql(bad)

    def test_rejects_non_select_start(self):
        with self.assertRaises(ValueError):
            dq.guard_sql("WITH x AS (SELECT 1) SELECT * FROM x")


class TestFetchXmlGuard(unittest.TestCase):
    def test_accepts_plain_fetch(self):
        dq.guard_fetchxml('<fetch><entity name="account"><attribute name="name"/></entity></fetch>')

    def test_rejects_mutating_and_nonfetch(self):
        for bad in ('<insert><entity name="account"/></insert>',
                    '<fetch><entity name="a"/><delete/></fetch>',
                    '{"not":"xml"}'):
            with self.assertRaises(ValueError, msg=bad):
                dq.guard_fetchxml(bad)


class TestEntitySetResolution(unittest.TestCase):
    def test_local_kb_hit_by_filename(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg_with_kb(tmp)
            es, source = dq.resolve_entity_set("contoso_salesorder", cfg, token=None)
            self.assertEqual(es, "contoso_salesorders")
            self.assertEqual(source, "local kb")

    def test_local_kb_hit_by_display_name(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg_with_kb(tmp)
            es, source = dq.resolve_entity_set("Sales Order", cfg, token=None)
            self.assertEqual(es, "contoso_salesorders")

    def test_live_fallback_and_no_guess(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg_with_kb(tmp)
            with mock.patch.object(dq.pp, "api_get",
                                   return_value={"value": [{"EntitySetName": "widgets"}]}) as m:
                es, source = dq.resolve_entity_set("widget", cfg, token="t")
                self.assertEqual((es, source), ("widgets", "live EntityDefinitions"))
                self.assertIn("LogicalName+eq+'widget'", m.call_args[0][2])
            with mock.patch.object(dq.pp, "api_get", return_value={"value": []}):
                with self.assertRaises(ValueError):
                    dq.resolve_entity_set("nope", cfg, token="t")
            # no kb, no token -> refuse to guess
            with self.assertRaises(ValueError):
                dq.resolve_entity_set("anything", {"outputDir": tmp}, token=None)


class TestPagination(unittest.TestCase):
    def test_follows_next_link_and_stops(self):
        cfg = {"dataverseUrl": "https://x.crm.dynamics.com"}
        page1 = {"value": [{"a": 1}],
                 "@odata.nextLink": "https://x.crm.dynamics.com/api/data/v9.2/accounts?$skip=1"}
        page2 = {"value": [{"a": 2}]}
        calls = []

        def fake_get(_cfg, _token, path):
            calls.append(path)
            return page1 if len(calls) == 1 else page2

        with mock.patch.object(dq.pp, "api_get", side_effect=fake_get):
            rows, pages = dq.paged_get(cfg, "t", "accounts", max_pages=10)
        self.assertEqual(rows, [{"a": 1}, {"a": 2}])
        self.assertEqual(pages, 2)
        self.assertEqual(calls[1], "accounts?$skip=1")

    def test_max_pages_guard(self):
        cfg = {"dataverseUrl": "https://x.crm.dynamics.com"}
        page = {"value": [{"a": 1}],
                "@odata.nextLink": "https://x.crm.dynamics.com/api/data/v9.2/accounts?$skip=1"}
        with mock.patch.object(dq.pp, "api_get", return_value=page):
            rows, pages = dq.paged_get(cfg, "t", "accounts", max_pages=3)
        self.assertEqual(pages, 3)
        self.assertEqual(len(rows), 3)


class TestUrlBuilding(unittest.TestCase):
    def test_odata_query_params(self):
        args = mock.Mock(select="name,contoso_totalamount",
                         filter="contoso_status eq 100000002",
                         orderby="contoso_orderdate desc",
                         top="50", expand=None, apply=None, count=False)
        q = dq.build_odata_query(args)
        self.assertIn("$select=name,contoso_totalamount", q)
        self.assertIn("contoso_status+eq+100000002", q.replace("%20", "+"))
        self.assertIn("$orderby=contoso_orderdate", q)
        self.assertIn("$top=50", q)
        self.assertNotIn("$expand", q)

    def test_apply_and_count(self):
        args = mock.Mock(select=None, filter=None, orderby=None, top=None,
                         expand=None, apply="groupby((contoso_status),aggregate(contoso_totalamount with sum as total))",
                         count=True)
        q = dq.build_odata_query(args)
        self.assertIn("$apply=groupby", q)
        self.assertIn("$count=true", q)


class TestFormatting(unittest.TestCase):
    def test_table_output(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            dq.format_rows([{"a": 1, "b": "x"}, {"a": 22, "b": "yy"}], "table", None)
        out = buf.getvalue()
        self.assertIn("a", out) and self.assertIn("22", out)
        self.assertIn("-+-", out)

    def test_csv_requires_outfile(self):
        with self.assertRaises(SystemExit):
            dq.format_rows([{"a": 1}], "csv", None)

    def test_csv_and_json_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "o.csv")
            dq.format_rows([{"a": 1, "b": "x"}], "csv", csv_path)
            with open(csv_path, encoding="utf-8") as f:
                self.assertIn("a,b", f.read().replace("\r", ""))
            json_path = os.path.join(tmp, "o.json")
            dq.format_rows([{"a": 1}], "json", json_path)
            with open(json_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), [{"a": 1}])


if __name__ == "__main__":
    unittest.main()
