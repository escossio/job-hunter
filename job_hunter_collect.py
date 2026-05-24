from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml
from rich.console import Console

from dedupe import dedupe_jobs
from exporters import export_csv, export_incremental_report, export_xlsx
from normalizer import normalize_job
from job_panel_server import job_key_for, latest_csv_file, _load_status_file, _merge_status
from run_jobs import SOURCE_CLASSES, _source_metadata, load_source
from scoring import score_job


PROJECT_DIR = Path(__file__).resolve().parent
STATE_FILE = PROJECT_DIR / "data" / "state" / "known_jobs.json"


def load_config(project_dir: Path = PROJECT_DIR) -> dict[str, Any]:
    with (project_dir / "config.yaml").open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _truthy_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _state_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = dict(job)
    payload.pop("status_candidatura", None)
    payload.pop("observacoes", None)
    payload.pop("is_new_in_run", None)
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _backup_existing_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def _read_csv_jobs(csv_file: Path | None) -> list[dict[str, Any]]:
    if not csv_file or not csv_file.exists():
        return []

    jobs: list[dict[str, Any]] = []
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            job = dict(row)
            job["job_key"] = _safe_text(job.get("job_key")).strip() or job_key_for(job)
            job["first_seen_at"] = _safe_text(job.get("first_seen_at")).strip() or _safe_text(job.get("coletado_em")).strip()
            job["last_seen_at"] = _safe_text(job.get("last_seen_at")).strip() or _safe_text(job.get("coletado_em")).strip()
            job["collection_run_id"] = _safe_text(job.get("collection_run_id")).strip()
            job["is_new_in_run"] = False
            jobs.append(job)
    return jobs


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _load_known_jobs(state_file: Path, bootstrap_csv: Path | None, started_at: str) -> dict[str, dict[str, Any]]:
    state_data = _load_json(state_file)
    jobs = state_data.get("jobs")
    if isinstance(jobs, dict) and jobs:
        normalized: dict[str, dict[str, Any]] = {}
        for job_key, job in jobs.items():
            if not isinstance(job, dict):
                continue
            payload = _state_job_payload(job)
            payload["job_key"] = _safe_text(payload.get("job_key")).strip() or _safe_text(job_key).strip()
            payload["first_seen_at"] = _safe_text(payload.get("first_seen_at")).strip() or started_at
            payload["last_seen_at"] = _safe_text(payload.get("last_seen_at")).strip() or payload["first_seen_at"]
            payload["collection_run_id"] = _safe_text(payload.get("collection_run_id")).strip()
            payload.setdefault("seen_count", 1)
            normalized[payload["job_key"]] = payload
        if normalized:
            return normalized

    if bootstrap_csv and bootstrap_csv.exists():
        bootstrap_jobs = _read_csv_jobs(bootstrap_csv)
        normalized = {}
        for job in bootstrap_jobs:
            payload = _state_job_payload(job)
            payload["job_key"] = job["job_key"]
            payload["first_seen_at"] = job.get("first_seen_at") or started_at
            payload["last_seen_at"] = job.get("last_seen_at") or payload["first_seen_at"]
            payload["collection_run_id"] = f"bootstrap:{started_at}"
            payload["seen_count"] = 1
            normalized[payload["job_key"]] = payload
        return normalized

    return {}


def _save_known_jobs(state_file: Path, jobs: dict[str, dict[str, Any]], started_at: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        _backup_existing_file(state_file)
    payload = {
        "version": 1,
        "updated_at": started_at,
        "jobs": {job_key: jobs[job_key] for job_key in sorted(jobs)},
    }
    temp_file = state_file.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_file.replace(state_file)


def _collect_public_jobs(config: dict[str, Any], load_source_func: Callable[[str], Any] = load_source) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "started_at": _now_iso(),
        "sources": {},
        "raw_total": 0,
        "deduped_total": 0,
    }

    for source_name, source_config in (config.get("sources") or {}).items():
        if not source_config or not source_config.get("enabled", False):
            continue
        source = load_source_func(source_name)
        try:
            collected = list(source.collect(source_config))
        except Exception as exc:  # pragma: no cover - defensive guard for isolated source failure
            collected = []
            stats = getattr(source, "stats", {}) or {}
            errors = list(stats.get("errors") or [])
            errors.append(f"{source_name}_collect_error: {exc}")
            stats["errors"] = errors
            setattr(source, "stats", stats)
        metadata["sources"][source_name] = _source_metadata(source_name, len(collected), source)
        metadata["raw_total"] += len(collected)
        for job in collected:
            jobs.append(source.normalize_job(job))

    normalized = [normalize_job(job) for job in jobs]
    unique_jobs = dedupe_jobs(normalized)
    metadata["deduped_total"] = len(unique_jobs)
    scored_jobs = [normalize_job(score_job(job, config)) for job in unique_jobs]

    final_by_source: dict[str, int] = {}
    for job in scored_jobs:
        source_name = str(job.get("origem") or "")
        final_by_source[source_name] = final_by_source.get(source_name, 0) + 1
    for source_name, source_meta in metadata["sources"].items():
        source_meta["final_count"] = final_by_source.get(source_name, 0)

    return scored_jobs, metadata


def _merge_fresh_job(existing: dict[str, Any] | None, fresh: dict[str, Any], started_at: str, run_id: str) -> dict[str, Any]:
    merged = dict(existing or {})
    for field, value in fresh.items():
        if field in {"status_candidatura", "observacoes"}:
            continue
        if _truthy_value(value):
            merged[field] = value
    merged["job_key"] = fresh["job_key"]
    if not merged.get("first_seen_at"):
        merged["first_seen_at"] = fresh.get("coletado_em") or started_at
    merged["last_seen_at"] = started_at
    merged["collection_run_id"] = run_id
    merged["seen_count"] = int(existing.get("seen_count", 0)) + 1 if existing else 1
    return merged


def build_incremental_collection(
    project_dir: Path = PROJECT_DIR,
    *,
    now: datetime | None = None,
    collected_jobs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    load_source_func: Callable[[str], Any] = load_source,
) -> dict[str, Any]:
    started_at = _now_iso(now)
    run_id = datetime.fromisoformat(started_at).strftime("%Y%m%d_%H%M%S")
    data_dir = project_dir / "data" / "output"
    report_dir = project_dir / "data" / "reports"
    state_file = project_dir / "data" / "state" / "known_jobs.json"
    latest_csv = latest_csv_file(data_dir)

    if collected_jobs is None or metadata is None:
        config = load_config(project_dir)
        collected_jobs, metadata = _collect_public_jobs(config, load_source_func=load_source_func)

    known_before = len(_load_known_jobs(state_file, latest_csv, started_at))
    known_jobs = _load_known_jobs(state_file, latest_csv, started_at)
    status_map = _load_status_file(project_dir / "data" / "status" / "job_status.json").get("jobs", {})

    seen_keys: set[str] = set()
    new_jobs = 0
    updated_jobs = 0
    reencontradas = 0

    for job in collected_jobs:
        fresh = dict(job)
        fresh["job_key"] = _safe_text(fresh.get("job_key")).strip() or job_key_for(fresh)
        existing = known_jobs.get(fresh["job_key"])
        if existing is None:
            known_jobs[fresh["job_key"]] = _merge_fresh_job(None, fresh, started_at, run_id)
            new_jobs += 1
        else:
            merged = _merge_fresh_job(existing, fresh, started_at, run_id)
            if any(existing.get(field) != merged.get(field) for field in ("score_bruto", "score_aderencia", "priority_rank", "classificacao", "motivos_score", "confianca_extracao", "erro_extracao", "requer_login", "candidatura_automatica_disponivel")):
                updated_jobs += 1
            known_jobs[fresh["job_key"]] = merged
            reencontradas += 1
        seen_keys.add(fresh["job_key"])

    for job_key, job in list(known_jobs.items()):
        job.setdefault("job_key", job_key)
        job.setdefault("first_seen_at", started_at)
        job.setdefault("last_seen_at", job.get("first_seen_at", started_at))
        job.setdefault("collection_run_id", run_id)
        job.setdefault("seen_count", 1)

    final_jobs = [_merge_status(dict(job), status_map) for job in known_jobs.values()]
    for job in final_jobs:
        job["is_new_in_run"] = job.get("job_key") in seen_keys and job["collection_run_id"] == run_id and int(known_jobs.get(job["job_key"], {}).get("seen_count", 0)) == 1

    final_jobs = [normalize_job(job) for job in final_jobs]

    stamp = datetime.fromisoformat(started_at).strftime("%Y%m%d_%H%M%S")
    csv_path = data_dir / f"jobs_{stamp}.csv"
    xlsx_path = data_dir / f"jobs_{stamp}.xlsx"
    report_path = report_dir / f"jobs_incremental_report_{stamp}.md"

    export_csv(final_jobs, csv_path)
    export_xlsx(final_jobs, xlsx_path, metadata)
    export_incremental_report(
        final_jobs,
        report_path,
        {
            "started_at": started_at,
            "run_id": run_id,
            "known_before": known_before,
            "raw_total": int((metadata or {}).get("raw_total", len(collected_jobs or []))),
            "deduped_total": int((metadata or {}).get("deduped_total", len(collected_jobs or []))),
            "new_jobs": new_jobs,
            "known_jobs": reencontradas,
            "updated_jobs": updated_jobs,
            "final_total": len(final_jobs),
            "snapshot_csv": str(csv_path),
            "snapshot_xlsx": str(xlsx_path),
            "state_file": str(state_file),
            "report_csv": str(csv_path),
        },
        metadata,
    )

    _save_known_jobs(state_file, known_jobs, started_at)

    return {
        "started_at": started_at,
        "run_id": run_id,
        "known_before": known_before,
        "raw_total": int((metadata or {}).get("raw_total", len(collected_jobs or []))),
        "deduped_total": int((metadata or {}).get("deduped_total", len(collected_jobs or []))),
        "new_jobs": new_jobs,
        "known_jobs": reencontradas,
        "updated_jobs": updated_jobs,
        "final_total": len(final_jobs),
        "snapshot_csv": csv_path,
        "snapshot_xlsx": xlsx_path,
        "report_path": report_path,
        "state_file": state_file,
        "metadata": metadata,
        "jobs": final_jobs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta incremental do job-hunter")
    parser.add_argument("--project-dir", default=str(PROJECT_DIR), help="Diretorio raiz do projeto")
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).resolve()
    console = Console()
    result = build_incremental_collection(project_dir)
    console.print(f"Coleta incremental executada: {result['final_total']} vagas consolidadas.")
    console.print(f"CSV: {result['snapshot_csv']}")
    console.print(f"XLSX: {result['snapshot_xlsx']}")
    console.print(f"Relatorio: {result['report_path']}")
    console.print(f"Base historica: {result['state_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
