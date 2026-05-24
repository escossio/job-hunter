from __future__ import annotations

from typing import Any


def _dedupe_key(job: dict[str, Any]) -> tuple[str, ...]:
    job_key = str(job.get("job_key") or "").strip().lower()
    if job_key:
        return ("job_key", job_key)

    link = str(job.get("link") or "").strip().lower()
    if link:
        return ("link", link)

    codigo = str(job.get("codigo_vaga") or "").strip().lower()
    if codigo:
        return ("codigo_vaga", codigo)

    return (
        "composite",
        str(job.get("titulo") or "").strip().lower(),
        str(job.get("empresa") or "").strip().lower(),
        str(job.get("localidade") or "").strip().lower(),
    )


def dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    unique_jobs: list[dict[str, Any]] = []

    for job in jobs:
        key = _dedupe_key(job)
        if key in seen:
            continue
        seen.add(key)
        unique_jobs.append(job)

    return unique_jobs
