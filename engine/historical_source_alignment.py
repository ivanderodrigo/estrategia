"""Cautious identity checks on archived sources.

Historical URLs may be useful for discovery, but a source written for a DIFFERENT
vendor cannot substantiate a vendor-specific capability, product or service.
Quarantine these original links; do not delete the archival source registry.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .model import canonical

OWNER_DOMAINS = {
    "1password.com": "1password",
    "levelblue.com": "levelblue",
    "cloudflare.com": "cloudflare",
    "crowdstrike.com": "crowdstrike",
    "extremenetworks.com": "extreme networks",
    "zscaler.com": "zscaler",
    "checkpoint.com": "check point",
    "fortinet.com": "fortinet",
    "okta.com": "okta",
    "pingidentity.com": "ping identity",
    "uipath.com": "uipath",
    "f5.com": "f5",
    "paloaltonetworks.com": "palo alto networks",
    "sonarsource.com": "sonar",
    "sonarcloud.io": "sonar",
}
VENDOR_SPECIFIC_FIELDS = frozenset({
    "capabilities", "products_platforms", "products", "platforms",
    "services", "technology_stack", "subcategories", "certifications",
})


def source_alignment(section: str, entity: str, field: str, url: str) -> tuple[bool, str]:
    """The only automatic rejection is an identified other-vendor site.

    Independent analysts, general publications and unknown domains are kept as
    NON-ACCREDITED leads. No page is automatically promoted from this function.
    """
    if section != "manufacturers" or field not in VENDOR_SPECIFIC_FIELDS:
        return True, ""
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
    except ValueError:
        return False, "invalid-url"
    owner = next((name for domain, name in OWNER_DOMAINS.items()
                  if host == domain or host.endswith("." + domain)), "")
    if owner and canonical(entity) != canonical(owner):
        return False, "other-vendor-source:" + owner
    return True, ""
