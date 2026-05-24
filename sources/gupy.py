from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .base import BaseSource


API_BASE = "https://employability-portal.gupy.io/api/v1/jobs"
BLOCK_STATUSES = {403, 429}
DEFAULT_KEYWORDS = (
    "observabilidade",
    "monitoramento",
    "infraestrutura",
    "redes",
    "noc",
    "suporte",
    "suporte ti",
    "analista de ti",
    "devops",
    "sre",
    "linux",
    "python",
)
DEFAULT_WORKPLACE_TYPES = ("remote", "hybrid")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(html.unescape(value), "lxml")
    return _clean_text(soup.get_text(" ", strip=True))


def _payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _infer_modality(item: dict[str, Any]) -> str:
    text = " ".join(
        _clean_text(part)
        for part in (
            item.get("workplaceType"),
            "remote" if item.get("isRemoteWork") else "",
            item.get("description"),
        )
    ).lower()
    if "remote" in text or "home office" in text or "100% remoto" in text or item.get("isRemoteWork"):
        return "Home Office"
    if "hybrid" in text or "hibrido" in text or "híbrido" in text:
        return "Híbrido"
    if "presential" in text or "on-site" in text or "presencial" in text:
        return "Presencial"
    return ""


def _infer_location(item: dict[str, Any]) -> str:
    parts = [
        _clean_text(item.get("city")),
        _clean_text(item.get("state")),
        _clean_text(item.get("country")),
    ]
    location = " - ".join(part for part in parts if part)
    if location:
        return location
    if _infer_modality(item) == "Home Office":
        return "Remoto"
    return ""


def _infer_level(text: str) -> str:
    lowered = text.lower()
    for level in ("estágio", "trainee", "treinee", "júnior", "junior", "pleno", "sênior", "senior", "especialista"):
        if level in lowered:
            return level.title()
    return ""


def _infer_contract(description: str, type_name: str) -> str:
    text = f"{description} {type_name}".lower()
    contracts: list[str] = []
    for contract in ("CLT", "PJ", "Cooperado", "Freelancer"):
        if contract.lower() in text:
            contracts.append(contract)
    return ", ".join(dict.fromkeys(contracts))


def _infer_tags(item: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for skill in item.get("skills") or []:
        if isinstance(skill, dict):
            name = _clean_text(skill.get("name") or skill.get("label"))
        else:
            name = _clean_text(skill)
        if name:
            tags.append(name)
    if _infer_modality(item):
        tags.append(_infer_modality(item))
    if item.get("isRemoteWork"):
        tags.append("remoto")
    return list(dict.fromkeys(tags))


def _extract_section(description: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(
            rf"{pattern}\s*[:\-]?\s*(.+?)(?=(?:Benef[ií]cios?|Responsibilities?|Atribui[cç][oõ]es|Requisitos?|Qualifications?|Sobre|$))",
            description,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return _strip_html(match.group(1))
    return ""


def _normalize_job_item(item: dict[str, Any], search_keyword: str = "") -> dict[str, Any]:
    title = _clean_text(item.get("name"))
    description = _strip_html(item.get("description"))
    company = _clean_text(item.get("careerPageName"))
    link = _clean_text(item.get("jobUrl"))
    modality = _infer_modality(item)
    location = _infer_location(item)
    tags = _infer_tags(item)
    combined_text = f"{title} {description} {' '.join(tags)}"

    return {
        "origem": "gupy",
        "busca_keywords": search_keyword,
        "titulo": title,
        "empresa": company,
        "localidade": location,
        "modalidade": modality,
        "salario": "",
        "nivel": _infer_level(combined_text),
        "regime_contratacao": _infer_contract(description, _clean_text(item.get("type"))),
        "data_anuncio": _clean_text(item.get("publishedDate"))[:10],
        "codigo_vaga": str(item.get("id") or ""),
        "link": link,
        "descricao": description,
        "requisitos": _extract_section(description, ("Requisitos", "Qualifications", "Requirements", "Requisitos e qualificações")),
        "beneficios": _extract_section(description, ("Benefícios", "Benefits")),
        "tags": tags,
        "score_aderencia": 0,
        "classificacao": "Ignorar",
        "motivos_score": "",
        "confianca_extracao": 0.84 if title and link and description else 0.6 if title and link else 0.35,
        "erro_extracao": "" if title and link else "gupy_pagina_incompleta",
        "requer_login": False,
        "candidatura_automatica_disponivel": bool(link),
        "status_candidatura": "não avaliada",
        "observacoes": "Coleta pública Gupy via API sem login; link de candidatura público detectado e não acessado.",
    }


def parse_jobs_payload(payload: Any, search_keyword: str = "") -> list[dict[str, Any]]:
    return [_normalize_job_item(item, search_keyword) for item in _payload_items(payload)]


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


class GupySource(BaseSource):
    name = "gupy"

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
            "User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0; public Gupy collector)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }

    def _request_json(self, session: requests.Session, params: dict[str, Any]) -> Any:
        url = f"{API_BASE}?{urlencode(params)}"
        self.stats["start_urls"].append(url)
        response = session.get(API_BASE, params=params, headers=self._headers(), timeout=20)
        if response.status_code in BLOCK_STATUSES:
            raise RuntimeError(f"gupy_bloqueio_http_{response.status_code}")
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
                for workplace_type in DEFAULT_WORKPLACE_TYPES:
                    if len(jobs) >= max_jobs:
                        break
                    for page in range(max_pages):
                        params = {
                            "jobName": keyword,
                            "workplaceType": workplace_type,
                            "limit": page_limit,
                            "offset": page * page_limit,
                        }
                        payload = self._request_json(session, params)
                        parsed = parse_jobs_payload(payload, keyword)
                        if not parsed and page == 0:
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
        except Exception as exc:
            self.stats.setdefault("errors", []).append(str(exc))
            if "bloqueio_http" in str(exc):
                self.stats["raw_collected"] = len(jobs)
                self.stats["urls_acessadas"] = list(dict.fromkeys(self.stats["start_urls"]))
                return jobs
            if not jobs:
                return []

        self.stats["raw_collected"] = len(jobs)
        self.stats["urls_acessadas"] = list(dict.fromkeys(self.stats["start_urls"]))
        return jobs
