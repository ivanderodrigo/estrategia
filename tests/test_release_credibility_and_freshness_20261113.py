import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from engine.procurement_lifecycle import (
    deadline_date, public_tender_active, tender_lifecycle_report,
)
from scripts.revalidate_historical_sources import check_one


def notice(deadline="", status=""):
    return {"name":"Sample", "fields":{
        "milestone_date":{"value":deadline},
        "procurement_stage":{"value":status},
        "notice_id":{"value":"PROC-2026-0001"},
    }}


class ProcurementLifecycleTests(unittest.TestCase):
    def test_date_formats_and_unknowns(self):
        self.assertEqual(deadline_date("2026-11-10T10:00:00"),date(2026,11,10))
        self.assertEqual(deadline_date("10/11/2026"),date(2026,11,10))
        self.assertIsNone(deadline_date("not a date"))

    def test_active_vs_expired_or_awarded(self):
        today=date(2026,11,13)
        self.assertFalse(public_tender_active(notice("2026-11-12"),today))
        self.assertTrue(public_tender_active(notice("2026-11-13"),today))
        self.assertTrue(public_tender_active(notice(""),today))
        self.assertFalse(public_tender_active(notice("2026-12-15","Adjudicado"),today))
        self.assertFalse(public_tender_active(notice("2026-12-15","Cancelado"),today))
        self.assertTrue(public_tender_active(notice("2026-12-15","Abierto"),today))

    def test_non_notice_public_clients_do_not_become_expired_tenders(self):
        row = {"name": "Ayuntamiento como cliente", "fields": {
            "notice_id": {"value": "Por investigar"},
            "milestone_date": {"value": "2020-01-01"},
        }}
        tenders = [notice("2026-11-12"), notice("2026-11-20")]
        report = tender_lifecycle_report({"clients_public": [row, *tenders]},
                                         date(2026,11,13))
        self.assertEqual(report["total_public_rows"], 3)
        self.assertEqual(report["non_notice_public_rows"], 1)
        self.assertEqual(report["total_retained"], 2)
        self.assertEqual(report["closed_or_deadline_expired"], 1)
        self.assertEqual(report["currently_active_or_date_unknown"], 1)

    def test_counts_historical_records_not_deleted(self):
        rows=[notice("2026-11-12"),notice("2026-11-14"),
              notice(""),notice("2026-12-01","adjudicado")]
        data={"clients_public":rows}
        report=tender_lifecycle_report(data,date(2026,11,13))
        self.assertEqual(report["closed_or_deadline_expired"],2)
        self.assertEqual(report["currently_active_or_date_unknown"],2)
        self.assertEqual(report["total_retained"],4)
        self.assertEqual(report["total_public_rows"],4)
        self.assertEqual(len(data["clients_public"]),4)


class HistoricalSourceCheckSafety(unittest.TestCase):
    def test_web_success_not_mistaken_for_accredited_claim(self):
        class Response:
            status_code=200
            headers={"Content-Type":"text/html"}
            text="<html><body>Zero Trust Network Architecture explained by the NIST publication, discussing authentication authorization users devices applications access policies trusted resources and enterprise protection in extensive technical detail.</body></html>"
        class Session:
            def get(self,*args,**kwargs):
                return Response()
        # An HTTP success proves page reachability only, not atomic fact.
        with patch("scripts.revalidate_historical_sources.validate_public_url",side_effect=lambda u:u):
            result=check_one("https://example.org/zero-trust",[{
                "section":"architectures","entity":"Zero Trust",
                "field":"context","value":"Zero Trust Network Architecture"}],
                session=Session())
        self.assertEqual(result["accreditation"],"NOT_ACCREDITED")
        self.assertEqual(result["status"],"REACHABLE_TEXT_MATCH")


class PublicationContracts(unittest.TestCase):
    def test_all_periodic_publications_include_historical_and_tender_reports(self):
        text=(Path(__file__).resolve().parents[1]/"scripts/publish_research_update.py").read_text(encoding='utf-8')
        self.assertIn('data/public/historical/current/architectures.json',text)
        self.assertIn('data/public/historical/current/source_checks.json',text)
        self.assertIn('data/public/procurement_lifecycle.json',text)
        app=(Path(__file__).resolve().parents[1]/"assets/app/intelligence.js").read_text(encoding='utf-8')
        self.assertIn("sourceArchaeology(field,item)",app)
        self.assertNotIn("${historicalTrail(view,row,col.id)}",app)
        self.assertIn("publicTenderCurrent(row)",app)


if __name__=="__main__":
    unittest.main()
