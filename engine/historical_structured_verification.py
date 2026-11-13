"""Conservative, atomic proof from structured product-alternative lists.

Only explicit named products within a matching Gartner product alternatives
page qualify. A 200 response, keyword mention or a generic market listing
does NOT constitute proof. No inferred distribution/channel relationships.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlparse

from engine.model import canonical

SUPPORTED_PRODUCT = {
    "attackiq-platform": "attackiq",
    "efficientip-solidserver-ddi": "efficientip",
    "avaya-aura-ucaas": "avaya",
    "firemon-policy-manager": "firemon",
    "fortanix-data-security-manager": "fortanix",
    "xm-cyber-exposure-management-platform": "xm cyber",
    "the-anomali-platform": "anomali",
}
# Product names can change while the associated vendor name stays stable.
EXACT_ALIASES = {
    ("avaya", "ringcentral"): ("RingEX",),
    ("avaya", "cisco webex"): ("Webex Suite",),
    ("fortanix", "microsoft azure key vault"): ("Azure Key Vault",),
    ("fortanix", "aws kms"): ("AWS Key Management Service (KMS)",),
    ("xm cyber", "crowdstrike exposure management"): ("CrowdStrike Falcon Exposure Management",),
}
EXCLUDED_TOKENS = {"", "a", "it", "ai", "security", "cloud", "network", "platform"}


class _StructuredAlternatives(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.capture = None
        self.buffer = []
        self.title = []
        self.alternatives = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h5"):
            self.capture = tag
            self.buffer = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == self.capture:
            text = " ".join(" ".join(self.buffer).split())
            if tag == "h1":
                self.title.append(text)
            elif re.match(r"^\d+\.\s+", text):
                self.alternatives.append(re.sub(r"^\d+\.\s+", "", text).strip())
            self.capture = None
            self.buffer = []


def normalized(value: str) -> str:
    value = canonical(unescape(str(value or "")))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def source_entity(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.gartner.com":
        return None
    matched = re.fullmatch(r"/reviews/product/([^/]+)/alternatives/?", parsed.path)
    if not matched:
        return None
    return SUPPORTED_PRODUCT.get(matched.group(1))


def _product_match(entity: str, competitor: str, title: str) -> bool:
    candidate = normalized(competitor)
    product = normalized(title)
    if not candidate or candidate in EXCLUDED_TOKENS:
        return False
    variants = (competitor,) + EXACT_ALIASES.get((entity, candidate), ())
    for variant in variants:
        token = normalized(variant)
        if token and (product == token or product.startswith(token + " ")):
            return True
    return False


def verify_explicit_alternative(url: str, html: str, entity: str,
                                competitor: str) -> dict:
    expected_entity = source_entity(url)
    if not expected_entity or normalized(entity) != expected_entity:
        return {"verified": False, "reason": "SOURCE_ENTITY_OR_TYPE_MISMATCH"}
    doc = _StructuredAlternatives()
    doc.feed(html[:2_000_000])
    heading = " ".join(doc.title)
    if "alternatives" not in normalized(heading):
        return {"verified": False, "reason": "MISSING_PRODUCT_ALTERNATIVES_TITLE"}
    # Prove that the page is for the requested product, not merely a redirect
    # or interstitial that happens to list the requested competitor.
    required = expected_entity.replace(" ", "")
    if required not in normalized(heading).replace(" ", ""):
        return {"verified": False, "reason": "PRODUCT_PAGE_TITLE_MISMATCH"}
    for product in doc.alternatives:
        if _product_match(expected_entity, competitor, product):
            return {"verified": True, "reason": "EXPLICIT_PRODUCT_ALTERNATIVE",
                    "matched_product": product, "source_url": url}
    return {"verified": False, "reason": "NOT_IN_EXPLICIT_ALTERNATIVE_LIST"}
