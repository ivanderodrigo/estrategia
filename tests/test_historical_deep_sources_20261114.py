"""Deep audit: bounded official subpages and text-based PDF evidence."""
from __future__ import annotations
import unittest
from io import BytesIO
from unittest.mock import patch

from scripts.revalidate_historical_sources import (
    check_one,deep_source_links,historical_pdf_text,
)
from scripts.accredit_semantic_historical_sources import classify

HOME="https://www.nunsys.com/"
PARTNERS="https://www.nunsys.com/personas/nosotros/partners/"
CLAIM={"section":"integrators","entity":"nunsys","field":"vendor_relations","value":"Cisco"}

class Response:
    status_code=200
    def __init__(self,text="",content_type="text/html",content=b""):
        self.text=text
        self.content=content
        self.headers={"Content-Type":content_type}

class Session:
    def __init__(self):
        self.visited=[]
    def get(self,url,*args,**kwargs):
        self.visited.append(url)
        if url==HOME:
            return Response('''<html><h1>Nunsys, integración tecnológica y servicios empresariales</h1>
                <p>Soluciones de redes, cloud y ciberseguridad para empresas de España.</p>
                <a href="/personas/nosotros/partners/">Nuestros partners tecnológicos</a>
                </html>''')
        if url==PARTNERS:
            return Response('''<html><h1>Partners tecnológicos Nunsys</h1>
                <p>Trabajamos con fabricantes líderes para integrar redes y servicios.</p>
                <div class="partner-logo"><img alt="Cisco" src="/logos/cisco.png"></div>
                <div class="partner-logo"><img alt="Extreme Networks" src="/logos/extreme.png"></div>
                </html>''')
        raise AssertionError(url)

class DeepHistoricalSourceTests(unittest.TestCase):
    def test_follow_official_partner_directory_and_bind_discovered_url(self):
        with patch("scripts.revalidate_historical_sources.validate_public_url",side_effect=lambda x:x):
            session=Session()
            result=check_one(HOME,[CLAIM],session=session)
        self.assertEqual(result["claim_hits"],1)
        self.assertEqual(result["deep_claim_hits"],1)
        self.assertEqual(result["deep_links_fetched"],1)
        item=result["claim_checks"][0]
        self.assertEqual(item["resolved_url"],PARTNERS)
        self.assertEqual(item["status"],"VALUE_PRESENT_REQUIRES_CONTEXT")
        self.assertEqual(classify(item,PARTNERS),"VERIFIED_EXPLICIT_PARTNER_CONTEXT")

    def test_external_links_are_never_crawled(self):
        html='''<a href="https://www.attacker-example.com/partner">Partners</a>
                 <a href="/servicios">Servicios empresariales</a>
                 <a href="mailto:test@example.com">E-mail</a>'''
        self.assertEqual(deep_source_links(html,HOME),["https://www.nunsys.com/servicios"])

    def test_pdf_is_scanned_as_text_when_extractable(self):
        url="https://www.fluidra.com/documents/2025-report.pdf"
        claim={"section":"clients_private","entity":"fluidra","field":"technology_signals",
               "value":"Centro de operaciones de seguridad 24x7"}
        class PdfSession:
            def get(self,*args,**kwargs):
                return Response(content_type="application/pdf",content=b"%PDF document bytes")
        with (patch("scripts.revalidate_historical_sources.validate_public_url",side_effect=lambda x:x),
              patch("scripts.revalidate_historical_sources.historical_pdf_text",
                    return_value=("El informe anual de Fluidra acredita su Centro de operaciones "
                                  "de seguridad 24x7 y cuenta con equipos de detección y "
                                  "respuesta continuada para sus instalaciones y activos."))):
            result=check_one(url,[claim],session=PdfSession())
        self.assertEqual(result["source_format"],"pdf")
        self.assertEqual(result["claim_hits"],1)

    def test_blank_pdf_does_not_invent_claims(self):
        from pypdf import PdfWriter
        pdf=PdfWriter()
        pdf.add_blank_page(width=595,height=842)
        blob=BytesIO()
        pdf.write(blob)
        self.assertEqual(historical_pdf_text(blob.getvalue()),"")

if __name__=="__main__":
    unittest.main()
