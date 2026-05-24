from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseSource


BASE_URL = "https://www.remotar.com.br"
API_BASE = "https://api.remotar.com.br"
BLOCK_STATUSES = {403, 429}
DEFAULT_KEYWORDS = (
    "observabilidade",
    "monitoramento",
    "infraestrutura",
    "redes",
    "noc",
    "suporte",
    "suporte ti",
    "devops",
    "python",
    "linux",
    "dados",
    "tecnologia",
)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "lxml")
    return _clean_text(soup.get_text(" ", strip=True))


def _slugify(value: str) -> str:
    text = _clean_text(html.unescape(value)).lower()
    text = (
        text.replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("ä", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("í", "i")
        .replace("ì", "i")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ó", "o")
        .replace("ò", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ö", "o")
        .replace("ú", "u")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
    )
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "unknown"


def _payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _build_job_link(item: dict[str, Any]) -> str:
    company = item.get("company") or {}
    company_name = str(company.get("name") or item.get("companyDisplayName") or "unknown")
    title = str(item.get("title") or "vaga")
    return f"{BASE_URL}/job/{item.get('id')}/{_slugify(company_name)}/{_slugify(title)}"


def _format_salary(item: dict[str, Any]) -> str:
    salary = item.get("jobSalary") or {}
    if not isinstance(salary, dict):
        return ""
    lower = salary.get("from") or 0
    upper = salary.get("to") or 0
    currency = str(salary.get("currency") or "BRL").upper()
    if not lower and not upper:
        return ""

    def _format_value(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return ""
        integer = int(number)
        return f"R$ {integer:,.0f}".replace(",", ".")

    if lower and upper:
        return f"{_format_value(lower)} a {_format_value(upper)} / {currency}"
    if lower:
        return f"A partir de {_format_value(lower)} / {currency}"
    return f"Até {_format_value(upper)} / {currency}"


def _infer_level(text: str) -> str:
    lowered = text.lower()
    for level in ("estágio", "trainee", "treinee", "júnior", "junior", "pleno", "sênior", "senior", "especialista"):
        if level in lowered:
            return level.title()
    return ""


def _infer_modality(item: dict[str, Any]) -> str:
    text = " ".join(
        _clean_text(part)
        for part in (
            item.get("type"),
            item.get("subtitle"),
            item.get("description"),
            " ".join(tag.get("tag", {}).get("name", "") for tag in (item.get("jobTags") or []) if isinstance(tag, dict)),
        )
    ).lower()
    if "home office" in text or "100% remoto" in text or "remoto" in text or item.get("type") == "remote":
        return "Remoto"
    if "hibrido" in text or "híbrido" in text:
        return "Híbrido"
    if "presencial" in text:
        return "Presencial"
    return ""


def _infer_contract(item: dict[str, Any], description: str) -> str:
    text = " ".join(
        (
            str(item.get("type") or ""),
            description,
        )
    ).lower()
    contracts: list[str] = []
    for contract in ("CLT", "PJ", "Cooperado", "Freelancer"):
        if contract.lower() in text:
            contracts.append(contract)
    return ", ".join(dict.fromkeys(contracts))


def _infer_location(item: dict[str, Any]) -> str:
    city = _clean_text(item.get("city"))
    state = _clean_text(item.get("state"))
    country = _clean_text(item.get("country"))
    parts = [part for part in (city, state, country) if part]
    if parts:
        return " - ".join(parts)
    if _infer_modality(item) == "Remoto":
        return "Remoto"
    return ""


def _infer_tags(item: dict[str, Any], description: str) -> list[str]:
    tags: list[str] = []
    for entry in item.get("jobTags") or []:
        if not isinstance(entry, dict):
            continue
        tag = entry.get("tag") or {}
        name = _clean_text(tag.get("name"))
        if name:
            tags.append(name)
    for category in item.get("jobCategories") or []:
        if not isinstance(category, dict):
            continue
        value = category.get("category") or {}
        name = _clean_text(value.get("name"))
        if name:
            tags.append(name)
    text = f"{item.get('title') or ''} {description}".lower()
    for term in ("infraestrutura", "monitoramento", "observabilidade", "redes", "noc", "suporte", "devops", "python", "linux"):
        if term in text:
            tags.append(term)
    return list(dict.fromkeys(tags))


def _infer_requirements(item: dict[str, Any], description: str) -> str:
    requirements = item.get("jobRequirements") or []
    if isinstance(requirements, list) and requirements:
        values = []
        for entry in requirements:
            if isinstance(entry, dict):
                values.extend(str(value) for value in entry.values() if isinstance(value, str))
            elif isinstance(entry, str):
                values.append(entry)
        text = " ".join(values)
        if text:
            return _clean_text(text)
    match = re.search(
        r"(Requisitos?|Qualifications?|Requirements?)\s*[:\-]?\s*(.+?)(?=(?:Benef[ií]cios?|About the position|Responsibilities?|Atribui[cç][oõ]es|$))",
        description,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _strip_html(match.group(2)) if match else ""


def _infer_benefits(item: dict[str, Any], description: str) -> str:
    benefits = item.get("jobBenefits") or []
    if isinstance(benefits, list) and benefits:
        values = []
        for entry in benefits:
            if isinstance(entry, dict):
                values.extend(str(value) for value in entry.values() if isinstance(value, str))
            elif isinstance(entry, str):
                values.append(entry)
        text = " ".join(values)
        if text:
            return _clean_text(text)
    match = re.search(r"(Benef[ií]cios?)\s*[:\-]?\s*(.+)$", description, flags=re.IGNORECASE | re.DOTALL)
    return _strip_html(match.group(2)) if match else ""


def _normalize_job_item(item: dict[str, Any], search_keyword: str = "") -> dict[str, Any]:
    description = _strip_html(item.get("description"))
    title = _clean_text(item.get("title"))
    company = _clean_text((item.get("company") or {}).get("name")) or _clean_text(item.get("companyDisplayName"))
    link = _build_job_link(item)
    external_link = _clean_text(item.get("externalLink"))
    modality = _infer_modality(item)
    tags = _infer_tags(item, description)
    requirements = _infer_requirements(item, description)
    benefits = _infer_benefits(item, description)
    confidence = 0.82 if title and link and description else 0.58 if title and link else 0.35

    return {
        "origem": "remotar",
        "busca_keywords": search_keyword,
        "titulo": title,
        "empresa": company,
        "localidade": _infer_location(item),
        "modalidade": modality,
        "salario": _format_salary(item),
        "nivel": _infer_level(f"{title} {description}"),
        "regime_contratacao": _infer_contract(item, description),
        "data_anuncio": _clean_text(item.get("createdAt"))[:10],
        "codigo_vaga": str(item.get("id") or ""),
        "link": link,
        "descricao": description,
        "requisitos": requirements,
        "beneficios": benefits,
        "tags": tags,
        "score_aderencia": 0,
        "classificacao": "Ignorar",
        "motivos_score": "",
        "confianca_extracao": confidence,
        "erro_extracao": "" if title and link else "remotar_pagina_incompleta",
        "requer_login": False,
        "candidatura_automatica_disponivel": bool(external_link),
        "status_candidatura": "não avaliada",
        "observacoes": (
            "Coleta pública Remotar via API; link externo de candidatura detectado e não acessado."
            if external_link
            else "Coleta pública Remotar via API; nenhum link externo de candidatura acessado."
        ),
    }


def parse_jobs_payload(payload: Any, search_keyword: str = "") -> list[dict[str, Any]]:
    jobs = []
    for item in _payload_items(payload):
        jobs.append(_normalize_job_item(item, search_keyword))
    return jobs


def parse_job_item(item: dict[str, Any], search_keyword: str = "") -> dict[str, Any]:
    return _normalize_job_item(item, search_keyword)


def _matches_keywords(job: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(
        str(job.get(field) or "")
        for field in ("titulo", "descricao", "requisitos", "beneficios", "tags", "empresa", "modalidade", "localidade")
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


class RemotarSource(BaseSource):
    name = "remotar"

    def __init__(self) -> None:
        self.stats: dict[str, Any] = {
            "start_urls": [],
            "detail_urls": [],
            "urls_acessadas": [],
            "listing_links": 0,
            "raw_collected": 0,
            "errors": [],
        }

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0; public Remotar collector)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }

    def _request_json(self, session: requests.Session, url: str, params: dict[str, Any]) -> Any:
        self.stats["start_urls"].append(f"{url}?{urlencode(params)}")
        response = session.get(url, params=params, headers=self._headers(), timeout=20)
        if response.status_code in BLOCK_STATUSES:
            raise RuntimeError(f"remotar_bloqueio_http_{response.status_code}")
        response.raise_for_status()
        return response.json()

    def collect(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        searches = config.get("searches") or []
        keywords = [str(item.get("keywords") or "").strip() for item in searches if item.get("keywords")]
        keywords = [keyword for keyword in keywords if keyword] or list(DEFAULT_KEYWORDS)
        max_jobs = max(1, min(int(config.get("max_jobs_per_source") or 40), 40))
        page_limit = max(1, min(int(config.get("page_limit") or 10), max_jobs))
        max_pages = max(1, int(config.get("max_pages") or 1))

        jobs: list[dict[str, Any]] = []
        seen: set[str] = set()
        session = requests.Session()

        try:
            for keyword in keywords:
                if len(jobs) >= max_jobs:
                    break
                for page in range(1, max_pages + 1):
                    params = {"search": keyword, "page": page, "limit": page_limit}
                    payload = self._request_json(session, f"{API_BASE}/jobs", params)
                    parsed = parse_jobs_payload(payload, keyword)
                    if not parsed and page == 1:
                        continue
                    for job in parsed:
                        if not _matches_keywords(job, keywords):
                            continue
                        key = (
                            str(job.get("link") or "").strip().lower()
                            or str(job.get("codigo_vaga") or "").strip().lower()
                            or f"{job.get('titulo')}|{job.get('empresa')}|{job.get('localidade')}".lower()
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        jobs.append(job)
                        if len(jobs) >= max_jobs:
                            break
                    if len(jobs) >= max_jobs:
                        break

            if not jobs:
                params = {"limit": page_limit}
                self.stats["start_urls"].append(f"{API_BASE}/jobs/promoted?{urlencode(params)}")
                response = session.get(f"{API_BASE}/jobs/promoted", params=params, headers=self._headers(), timeout=20)
                if response.status_code in BLOCK_STATUSES:
                    raise RuntimeError(f"remotar_bloqueio_http_{response.status_code}")
                response.raise_for_status()
                for job in parse_jobs_payload(response.json(), "promovidas"):
                    if not _matches_keywords(job, keywords):
                        continue
                    key = (
                        str(job.get("link") or "").strip().lower()
                        or str(job.get("codigo_vaga") or "").strip().lower()
                        or f"{job.get('titulo')}|{job.get('empresa')}|{job.get('localidade')}".lower()
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append(job)
                    if len(jobs) >= max_jobs:
                        break
        except Exception as exc:
            self.stats.setdefault("errors", []).append(str(exc))
            if "bloqueio_http" in str(exc):
                return jobs
            if not jobs:
                return []

        self.stats["raw_collected"] = len(jobs)
        self.stats["urls_acessadas"] = list(dict.fromkeys(self.stats["start_urls"]))
        return jobs
