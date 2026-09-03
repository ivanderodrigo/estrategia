from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.intelligence_store import audit_store, load_intelligence, migrate_legacy, write_intelligence


class IntelligenceStoreV420(unittest.TestCase):
    def _dataset(self):
        return {
            "meta": {"version": "4.1.0", "note": "preserve me"},
            "manufacturers": [
                {"id": f"m{i}", "name": f"Vendor {i}", "blob": "x" * 3000}
                for i in range(30)
            ],
            "clients_public": [
                {"id": f"c{i}", "name": f"Client {i}", "blob": "y" * 2500}
                for i in range(25)
            ],
            "source_catalog": [{"url": f"https://example.com/{i}"} for i in range(40)],
            "research_seed_registry": {"a": {"value": 1}, "b": {"value": 2}},
            "future_unknown_key": {"nested": [1, 2, 3]},
        }

    def test_legacy_migration_roundtrips_every_top_level_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "data/current/intelligence.json"
            path.parent.mkdir(parents=True)
            original = self._dataset()
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            report = migrate_legacy(root=root, target_bytes=16_000)
            self.assertTrue(report["migrated"])
            self.assertEqual(load_intelligence(root=root), original)
            stub = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stub["storage_format"], "westcon-sharded-v1")
            self.assertLess(path.stat().st_size, 4096)
            audit = audit_store(root=root, max_shard_bytes=40_000)
            self.assertEqual(audit["status"], "PASS", audit.get("errors"))
            self.assertGreater(audit["shards"], 1)

    def test_updates_remain_sharded_and_semantically_exact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = self._dataset()
            write_intelligence(data, root=root, target_bytes=14_000)
            data["manufacturers"].append({"id": "new", "name": "New", "blob": "z" * 1000})
            write_intelligence(data, root=root, target_bytes=14_000)
            self.assertEqual(load_intelligence(root=root), data)
            audit = audit_store(root=root, max_shard_bytes=40_000)
            self.assertEqual(audit["status"], "PASS", audit.get("errors"))

    def test_manifest_hash_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_intelligence(self._dataset(), root=root, target_bytes=18_000)
            manifest = json.loads((root / "data/current/intelligence_store/manifest.json").read_text(encoding="utf-8"))
            part = root / manifest["entries"]["manufacturers"]["parts"][0]
            part.write_text("[]", encoding="utf-8")
            audit = audit_store(root=root, max_shard_bytes=40_000)
            self.assertEqual(audit["status"], "FAIL")
            self.assertTrue(any("hash mismatch" in error for error in audit["errors"]))


if __name__ == "__main__":
    unittest.main()
