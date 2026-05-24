from __future__ import annotations

from datetime import datetime
from typing import Any


class BaseSource:
    name = "base"

    def collect(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def normalize_job(self, job: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(job)
        normalized.setdefault("origem", self.name)
        normalized.setdefault("coletado_em", datetime.now().isoformat(timespec="seconds"))
        return normalized
