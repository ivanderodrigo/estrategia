import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from v33.ecosystem_engine import _entity_rows

class T(unittest.TestCase):
    def test_country_in_name_overrides_conflicting_source_scope(self):
        d={"integrators":[
            {"name":"Bechtle Spain","country":"PT"},
            {"name":"Bechtle Spain","country":"ES"},
            {"name":"Bechtle Spain","scope":"GLOBAL"},
        ]}
        rows,report=_entity_rows(d,with_report=True)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["scope"],"ES")
        self.assertEqual(set(rows[0]["scope_variants"]),{"PT","ES","GLOBAL"})
        g=report["groups"][0]
        self.assertEqual(g["explicit_name_scope"],"ES")
        self.assertEqual(g["conflicting_scopes"],["PT"])
        self.assertTrue(g["name_scope_conflict_resolved"])
        self.assertEqual(report["summary"]["name_scope_conflicts_detected"],1)
        self.assertEqual(report["summary"]["name_scope_conflicts_resolved"],1)
        self.assertEqual(report["summary"]["unresolved_name_scope_conflicts"],0)

    def test_neutral_name_keeps_iberia_when_es_and_pt_exist(self):
        d={"integrators":[{"name":"Example SI","country":"ES"},{"name":"Example SI","country":"PT"}]}
        rows,report=_entity_rows(d,with_report=True)
        self.assertEqual(rows[0]["scope"],"IBERIA")
        self.assertEqual(report["summary"]["name_scope_conflicts_detected"],0)

    def test_spain_and_portugal_names_remain_separate(self):
        d={"integrators":[{"name":"NTT DATA Spain","country":"ES"},{"name":"NTT DATA Portugal","country":"PT"}]}
        rows,_=_entity_rows(d,with_report=True)
        self.assertEqual(len(rows),2)
        self.assertEqual({x["scope"] for x in rows},{"ES","PT"})

if __name__=="__main__": unittest.main()
