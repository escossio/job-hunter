from __future__ import annotations

from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from dedupe import dedupe_jobs
from exporters import export_csv, export_markdown_report, export_xlsx
from normalizer import normalize_job
from scoring import score_job


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_CLASSES = {
    "nerdin": "NerdinSource",
    "apinfo": "ApinfoSource",
    "remotar": "RemotarSource",
    "gupy": "GupySource",
    "programathor": "ProgramathorSource",
    "geekhunter": "GeekhunterSource",
    "trampos": "TramposSource",
    "indeed": "IndeedSource",
    "infojobs": "InfojobsSource",
    "manual_urls": "ManualUrlsSource",
    "linkedin": "LinkedinSource",
    "revelo": "ReveloSource",
    "catho": "CathoSource",
    "glassdoor": "GlassdoorSource",
    "company_careers": "CompanyCareersSource",
}


def load_config() -> dict[str, Any]:
    with (PROJECT_DIR / "config.yaml").open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_source(name: str):
    module = import_module(f"sources.{name}")
    return getattr(module, SOURCE_CLASSES[name])()


def _source_metadata(source_name: str, raw_count: int, source: Any) -> dict[str, Any]:
    stats = getattr(source, "stats", {}) or {}
    errors = list(stats.get("errors") or [])
    alerts: list[dict[str, str]] = []
    for error in errors:
        message = str(error)
        alert_type = "erro_detalhe"
        if "premium_necessario.php" in message or "detalhe_publico_indisponivel" in message:
            alert_type = "detalhe_nao_publico"
        elif "blocked" in message.lower() or "bloque" in message.lower():
            alert_type = "bloqueio"
        alerts.append({"tipo": alert_type, "mensagem": message})

    if raw_count == 0:
        alerts.append({"tipo": "fonte_vazia", "mensagem": "Fonte executada sem vagas coletadas."})

    start_urls = list(stats.get("start_urls") or [])
    detail_urls = list(stats.get("detail_urls") or [])
    urls_acessadas = list(stats.get("urls_acessadas") or [*start_urls, *detail_urls])
    return {
        "name": source_name,
        "raw_count": raw_count,
        "final_count": 0,
        "start_urls": start_urls,
        "detail_urls": detail_urls,
        "urls_acessadas": urls_acessadas,
        "listing_links": stats.get("listing_links", 0),
        "alerts": alerts,
    }


def main() -> int:
    console = Console()
    config = load_config()
    jobs: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {},
        "raw_total": 0,
        "deduped_total": 0,
    }

    for source_name, source_config in (config.get("sources") or {}).items():
        if not source_config or not source_config.get("enabled", False):
            continue
        source = load_source(source_name)
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
    max_total = int((config.get("limits") or {}).get("max_jobs_total") or 0)
    if max_total > 0 and len(unique_jobs) > max_total:
        unique_jobs = unique_jobs[:max_total]
    metadata["deduped_total"] = len(unique_jobs)
    scored_jobs = [normalize_job(score_job(job, config)) for job in unique_jobs]
    final_by_source: dict[str, int] = {}
    for job in scored_jobs:
        source_name = str(job.get("origem") or "")
        final_by_source[source_name] = final_by_source.get(source_name, 0) + 1
    for source_name, source_meta in metadata["sources"].items():
        source_meta["final_count"] = final_by_source.get(source_name, 0)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = PROJECT_DIR / "data" / "output" / f"jobs_{stamp}.csv"
    xlsx_path = PROJECT_DIR / "data" / "output" / f"jobs_{stamp}.xlsx"
    report_path = PROJECT_DIR / "data" / "reports" / f"jobs_report_{stamp}.md"

    export_csv(scored_jobs, csv_path)
    export_xlsx(scored_jobs, xlsx_path, metadata)
    export_markdown_report(scored_jobs, report_path, metadata)

    if scored_jobs:
        console.print(f"Pipeline executado com coleta real: {len(scored_jobs)} vagas apos deduplicacao.")
    else:
        console.print("Pipeline executado sem vagas coletadas.")
    console.print(f"CSV: {csv_path}")
    console.print(f"XLSX: {xlsx_path}")
    console.print(f"Relatorio: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
