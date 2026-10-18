from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import engine.enrichment as enrichment
from engine.enrichment import normalize_fields
from engine.model import canonical
from engine.provenance import evidence_for_item, evidence_for_relationship


TARGETS = [
    ("Ericsson Cradlepoint", "4G/5G"),
    ("Palo Alto Networks", "XDR"),
    ("Stratus / Penguin Solutions", "HPC"),
    ("Zscaler", "SASE/SSE"),
]

RELATION_FIELDS = {
    "vendor_relations",
    "distributors",
    "integrators",
    "westcon_overlap",
    "competitor_vendor_overlap",
}


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def manufacturers():
    return json.loads(
        (
            root()
            / "data"
            / "current"
            / "intelligence_store"
            / "02-manufacturers.part-0000.json"
        ).read_text(encoding="utf-8")
    )


def item_for(field, value):
    for item in field.get("items") or []:
        if (
            isinstance(item, dict)
            and canonical(item.get("value")) == canonical(value)
        ):
            return item
    return None


def support_for(row, field_id, value):
    field = (row.get("fields") or {}).get(field_id) or {}
    item = item_for(field, value)
    item_rows = [
        ev for ev in ((item or {}).get("evidence") or [])
        if isinstance(ev, dict)
    ]
    field_rows = [
        ev for ev in (field.get("evidence") or [])
        if isinstance(ev, dict)
    ]

    selected = evidence_for_item(
        item_rows,
        row.get("name"),
        value,
        field_id=field_id,
    )
    if not selected:
        selected = evidence_for_item(
            field_rows,
            row.get("name"),
            value,
            field_id=field_id,
        )
    return selected


class HF6R16TypedAtomicDocumentBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = manufacturers()
        cls.by_name = {
            canonical(row.get("name")): row
            for row in cls.rows
            if isinstance(row, dict)
        }

    def test_dedupe_keeps_typed_atomic_document_even_if_complete_filter_rejects(self):
        ev = {
            "source": "Westcon Comstor España",
            "title": "FY2027 slide 23",
            "description": "Atomic documentary support for XDR.",
            "url": "",
            "field": "capabilities",
            "item_value": "XDR",
            "atomic": True,
            "accrediting": True,
            "source_binding": "claim-specific",
            "provenance_origin": "WESTCON_DOCUMENT_CURRENT",
            "source_type": "westcon-document-current",
        }

        with patch.object(
            enrichment,
            "_complete_evidence",
            return_value=None,
        ):
            self.assertEqual(
                enrichment._dedupe_evidence([ev]),
                [ev],
            )

    def test_dedupe_does_not_bypass_completion_for_ordinary_web_rows(self):
        ev = {
            "source": "example.test",
            "title": "Example",
            "description": "Example evidence.",
            "field": "capabilities",
            "item_value": "XDR",
            "atomic": True,
            "accrediting": True,
            "source_binding": "claim-specific",
            "provenance_origin": "PUBLIC_PRIMARY",
            "source_type": "web",
        }

        with patch.object(
            enrichment,
            "_complete_evidence",
            return_value=None,
        ):
            self.assertEqual(
                enrichment._dedupe_evidence([ev]),
                [],
            )

    def test_atomic_item_value_mismatch_cannot_be_rescued_by_text(self):
        ev = {
            "source": "Palo Alto Networks",
            "title": "Palo Alto Networks XDR",
            "description": "Palo Alto Networks provides XDR.",
            "url": "https://example.test/xdr",
            "field": "capabilities",
            "item_value": "Cortex XDR",
            "atomic": True,
            "accrediting": True,
            "source_binding": "claim-specific",
            "provenance_origin": "PUBLIC_PRIMARY",
            "source_type": "web",
        }

        self.assertEqual(
            evidence_for_item(
                [ev],
                "Palo Alto Networks",
                "XDR",
                field_id="capabilities",
            ),
            [],
        )

    def test_atomic_exact_item_value_is_accepted(self):
        ev = {
            "source": "Westcon Comstor España",
            "title": "FY2027 slide 23",
            "description": "Atomic documentary support for XDR.",
            "field": "capabilities",
            "item_value": "XDR",
            "atomic": True,
            "accrediting": True,
            "source_binding": "claim-specific",
            "provenance_origin": "WESTCON_DOCUMENT_CURRENT",
            "source_type": "westcon-document-current",
        }

        self.assertEqual(
            evidence_for_item(
                [ev],
                "Palo Alto Networks",
                "XDR",
                field_id="capabilities",
            ),
            [ev],
        )

    def test_relationship_path_is_not_forced_to_item_value_equality(self):
        ev = {
            "source": "example.test",
            "title": "Integrator and Vendor partnership",
            "description": "Integrator partners with Vendor.",
            "url": "https://example.test/partner",
            "item_value": "historical-orientation",
            "atomic": True,
            "accrediting": True,
        }

        # Relationship selector has no field_id and therefore does not use
        # the non-relationship exact-item guard.
        self.assertIsInstance(
            evidence_for_relationship(
                [ev],
                "Integrator",
                "Vendor",
            ),
            list,
        )

    def test_four_daily65_claims_survive_normalization_with_exact_metadata(self):
        chosen = [
            copy.deepcopy(self.by_name[canonical(vendor)])
            for vendor, _ in TARGETS
        ]

        data = {"manufacturers": chosen}
        normalize_fields(data)

        after = {
            canonical(row.get("name")): row
            for row in data["manufacturers"]
        }

        for vendor, value in TARGETS:
            row = after[canonical(vendor)]
            field = row["fields"]["capabilities"]
            item = item_for(field, value)
            self.assertIsNotNone(item, f"{vendor}/{value}")

            evidence = item.get("evidence") or []
            self.assertTrue(
                evidence,
                f"empty evidence: {vendor}/{value}",
            )

            self.assertTrue(
                evidence_for_item(
                    evidence,
                    vendor,
                    value,
                    field_id="capabilities",
                ),
                f"support does not bind: {vendor}/{value}",
            )

            for ev in evidence:
                if (
                    isinstance(ev, dict)
                    and ev.get("atomic")
                    and ev.get("item_value") not in (None, "")
                ):
                    self.assertEqual(
                        canonical(ev.get("item_value")),
                        canonical(value),
                        f"cross metadata: {vendor}/{value}",
                    )

    def test_normalization_preserves_all_strict_manufacturer_capability_support(self):
        supported_before = set()

        for row in self.rows:
            field = (row.get("fields") or {}).get("capabilities") or {}
            values = field.get("value")
            if not isinstance(values, list):
                continue
            for value in values:
                if support_for(row, "capabilities", value):
                    supported_before.add(
                        (canonical(row.get("name")), canonical(value))
                    )

        data = {"manufacturers": copy.deepcopy(self.rows)}
        normalize_fields(data)
        after = {
            canonical(row.get("name")): row
            for row in data["manufacturers"]
            if isinstance(row, dict)
        }

        lost = []
        for owner_key, value_key in sorted(supported_before):
            row = after.get(owner_key)
            if not row:
                lost.append((owner_key, value_key, "row"))
                continue

            field = (row.get("fields") or {}).get("capabilities") or {}
            actual = next(
                (
                    value
                    for value in (field.get("value") or [])
                    if canonical(value) == value_key
                ),
                None,
            )
            if actual is None:
                lost.append((owner_key, value_key, "value"))
                continue

            item = item_for(field, actual)
            evidence = (
                item.get("evidence") or []
                if isinstance(item, dict)
                else []
            )

            if not evidence_for_item(
                evidence,
                row.get("name"),
                actual,
                field_id="capabilities",
            ):
                lost.append((owner_key, value_key, "support"))

        self.assertEqual(
            lost,
            [],
            "strict support lost by normalization: " + repr(lost[:30]),
        )

    def test_no_crossed_atomic_metadata_after_normalization(self):
        data = {"manufacturers": copy.deepcopy(self.rows)}
        normalize_fields(data)
        bad = []

        for row in data["manufacturers"]:
            for field_id, field in (row.get("fields") or {}).items():
                if field_id in RELATION_FIELDS:
                    continue
                if not isinstance(field.get("value"), list):
                    continue

                for item in field.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("value")
                    for ev in item.get("evidence") or []:
                        if not isinstance(ev, dict):
                            continue
                        if (
                            ev.get("atomic") is True
                            and ev.get("item_value") not in (None, "")
                            and canonical(ev.get("item_value"))
                            != canonical(value)
                        ):
                            bad.append((
                                row.get("name"),
                                field_id,
                                value,
                                ev.get("item_value"),
                            ))

        self.assertEqual(
            bad,
            [],
            "crossed atomic metadata remains: " + repr(bad[:30]),
        )


if __name__ == "__main__":
    unittest.main()
