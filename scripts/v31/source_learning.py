from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict


@dataclass
class SourceStats:
    attempts: int = 0
    useful: int = 0
    corroborating: int = 0
    duplicates: int = 0
    false_positives: int = 0
    failures: int = 0
    avg_authority: float = 0.5
    avg_latency_ms: float = 0.0

    @property
    def utility_rate(self) -> float:
        return (self.useful + 1.5) / (self.attempts + 3.0)

    @property
    def reliability(self) -> float:
        return (self.attempts - self.failures + 2.0) / (self.attempts + 4.0)

    def priority(self, exploration: float = 0.18) -> float:
        exploitation = 0.45 * self.utility_rate + 0.25 * self.reliability + 0.20 * self.avg_authority
        penalty = 0.10 * ((self.false_positives + self.duplicates) / max(1, self.attempts))
        novelty = exploration / math.sqrt(self.attempts + 1)
        return max(0.02, exploitation - penalty + novelty)


class LearningStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: Dict[str, SourceStats] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    self.data[k] = SourceStats(**{x: v.get(x, getattr(SourceStats(), x)) for x in asdict(SourceStats())})
            except Exception:
                self.data = {}

    def get(self, source_id: str) -> SourceStats:
        return self.data.setdefault(source_id, SourceStats())

    def update(self, source_id: str, *, useful=False, corroborating=False, duplicate=False, false_positive=False, failed=False, authority=None, latency_ms=None, count_attempt=True):
        s = self.get(source_id)
        if count_attempt:
            s.attempts += 1
        s.useful += int(bool(useful))
        s.corroborating += int(bool(corroborating))
        s.duplicates += int(bool(duplicate))
        s.false_positives += int(bool(false_positive))
        s.failures += int(bool(failed))
        if authority is not None:
            s.avg_authority = round((s.avg_authority * max(0, s.attempts - 1) + float(authority)) / s.attempts, 4)
        if latency_ms is not None:
            s.avg_latency_ms = round((s.avg_latency_ms * max(0, s.attempts - 1) + float(latency_ms)) / s.attempts, 1)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: asdict(v) | {"priority": round(v.priority(), 4)} for k, v in sorted(self.data.items())}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
