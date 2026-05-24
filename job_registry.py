from __future__ import annotations

from typing import Any


class JobConfigError(ValueError):
    pass


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _safe_text(value).strip().lower() in {"1", "true", "yes", "sim", "y"}


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        tags = [value]
    elif isinstance(value, (list, tuple)):
        tags = [str(item) for item in value]
    else:
        tags = [str(value)]
    return [tag.strip() for tag in tags if str(tag).strip()]


def validate_configured_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_jobs = config.get("jobs", [])
    if raw_jobs is None:
        return []
    if not isinstance(raw_jobs, list):
        raise JobConfigError("config.yaml: 'jobs' precisa ser uma lista.")

    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_jobs, start=1):
        if not isinstance(entry, dict):
            raise JobConfigError(f"config.yaml: jobs[{index}] precisa ser um mapa.")

        job_id = _safe_text(entry.get("id")).strip()
        if not job_id:
            raise JobConfigError(f"config.yaml: jobs[{index}] precisa informar 'id'.")

        if job_id in seen_ids:
            raise JobConfigError(f"config.yaml: id duplicado em jobs: '{job_id}'.")
        seen_ids.add(job_id)

        url = _safe_text(entry.get("url")).strip()
        if not url:
            raise JobConfigError(f"config.yaml: jobs[{index}] precisa informar 'url'.")

        validated.append(entry)
    return validated


def collect_configured_jobs(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    configured_jobs = validate_configured_jobs(config)
    jobs: list[dict[str, Any]] = []

    for entry in configured_jobs:
        if not _safe_bool(entry.get("enabled"), default=True):
            continue

        job_id = _safe_text(entry.get("id")).strip()
        title = _safe_text(entry.get("title")).strip() or job_id
        company = _safe_text(entry.get("company")).strip()
        platform = _safe_text(entry.get("platform")).strip() or "manual"
        url = _safe_text(entry.get("url")).strip()
        tags = _normalize_tags(entry.get("tags"))
        notes = _safe_text(entry.get("notes")).strip()

        jobs.append(
            {
                "job_key": f"job:{job_id}",
                "origem": platform,
                "busca_keywords": ", ".join(tags),
                "titulo": title,
                "empresa": company,
                "localidade": "",
                "modalidade": "",
                "salario": "",
                "nivel": "",
                "regime_contratacao": "",
                "data_anuncio": "",
                "codigo_vaga": job_id,
                "link": url,
                "descricao": notes,
                "requisitos": "",
                "beneficios": "",
                "tags": tags,
                "score_bruto": 0,
                "score_aderencia": 0,
                "priority_rank": 0,
                "classificacao": "Ignorar",
                "motivos_score": "",
                "confianca_extracao": 1.0 if title and url else 0.5,
                "erro_extracao": "",
                "requer_login": False,
                "candidatura_automatica_disponivel": False,
                "status_candidatura": "não avaliada",
                "observacoes": "",
            }
        )

    metadata = {
        "name": "configured_jobs",
        "raw_count": len(jobs),
        "final_count": len(jobs),
        "start_urls": [],
        "detail_urls": [],
        "urls_acessadas": [],
        "listing_links": 0,
        "alerts": [],
    }
    return jobs, metadata
