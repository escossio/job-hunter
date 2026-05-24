from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .base import BaseSource


BASE_URL = "https://www.apinfo.com/apinfo/inc/list4.cfm"
BLOCK_STATUSES = {403, 429}
DEFAULT_KEYWORDS = ("observabilidade", "monitoramento", "redes", "noc", "infraestrutura")
FOCUS_TERMS = tuple(term.lower() for term in DEFAULT_KEYWORDS)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.replace("\xa0", " ").split())


def _node_text(node) -> str:
    if not node:
        return ""
    return _clean_text(node.get_text(" ", strip=True))


def _extract_label(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*\.{{2,}}\s*:\s*(.+?)(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]+\s*\.{{2,}}\s*:|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ""


def _extract_code(text: str, application_href: str = "") -> str:
    match = re.search(r"C[oó]digo\s*\.{2,}\s*:\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"[?&]codvaga=(\d+)", application_href, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_strong_value(text_node, label: str) -> str:
    if not text_node:
        return ""
    for strong in text_node.find_all("strong"):
        strong_text = _node_text(strong).lower()
        if label.lower() not in strong_text:
            continue
        parts: list[str] = []
        for sibling in strong.next_siblings:
            sibling_name = getattr(sibling, "name", None)
            if sibling_name == "strong":
                break
            if sibling_name == "a":
                break
            value = sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling)
            value = _clean_text(value)
            if value:
                parts.append(value)
        return _clean_text(" ".join(parts))
    return ""


def _extract_strong_code(text_node, application_href: str = "") -> str:
    value = _extract_strong_value(text_node, "Código")
    match = re.search(r"\d+", value)
    if match:
        return match.group(0)
    return _extract_code("", application_href)


def _canonical_link(code: str) -> str:
    if not code:
        return BASE_URL
    return f"{BASE_URL}?codvaga={code}"


def _split_info_date(value: str) -> tuple[str, str, str]:
    text = _clean_text(value)
    match = re.match(r"(.+?)\s+-\s+([A-Z]{2}|HO)\s+-\s+(\d{2}/\d{2}/\d{2})$", text)
    if match:
        location = f"{match.group(1)} - {match.group(2)}"
        state = match.group(2)
        return location, state, match.group(3)
    return text, "", ""


def _infer_modality(location: str, body: str) -> str:
    text = f"{location} {body}".lower()
    if "home office" in text or re.search(r"\bho\b", text) or "remot" in text:
        return "Home Office"
    if "híbrido" in text or "hibrido" in text:
        return "Híbrido"
    if "presencial" in text:
        return "Presencial"
    return ""


def _infer_contract(body: str) -> str:
    text = body.lower()
    contracts: list[str] = []
    for contract in ("CLT", "PJ", "Cooperado", "Freelancer"):
        if contract.lower() in text:
            contracts.append(contract)
    return ", ".join(contracts)


def _infer_level(title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    levels: list[str] = []
    for level in ("estágio", "trainee", "treinee", "júnior", "junior", "pleno", "sênior", "senior", "especialista"):
        if level in text:
            levels.append(level.title())
    return ", ".join(dict.fromkeys(levels))


def _infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for term in (
        "observabilidade",
        "monitoramento",
        "redes",
        "noc",
        "infraestrutura",
        "linux",
        "python",
        "zabbix",
        "grafana",
        "telecom",
        "cloud",
        "devops",
        "sre",
        "suporte",
    ):
        if term in lowered:
            tags.append(term)
    return tags


def _extract_requirements(body: str) -> str:
    match = re.search(r"(Requisitos(?: Obrigat[oó]rios)?[:\s].+)", body, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ""


def _matches_keywords(job: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(
        str(job.get(field) or "")
        for field in ("titulo", "descricao", "requisitos", "tags", "localidade", "modalidade")
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def parse_job_box(box, search_keyword: str = "") -> dict[str, Any]:
    info = _node_text(box.select_one(".info-data"))
    location, state, published = _split_info_date(info)
    title = _node_text(box.select_one(".cargo span, .cargo"))
    text_node = box.select_one(".texto")
    body = _node_text(text_node)
    application = box.select_one('a[href*="enviecv.cfm"]')
    application_href = application.get("href", "") if application else ""
    code = _extract_strong_code(text_node, application_href) or _extract_code(body, application_href)
    company = _extract_strong_value(text_node, "Empresa") or _extract_label(body, "Empresa")
    body_without_meta = re.sub(r"Empresa\s*\.{2,}\s*:\s*.+$", "", body, flags=re.IGNORECASE).strip()
    tags = _infer_tags(f"{title} {body_without_meta} {location}")

    return {
        "origem": "apinfo",
        "busca_keywords": search_keyword,
        "titulo": title,
        "empresa": company,
        "localidade": location,
        "modalidade": _infer_modality(location, body_without_meta),
        "salario": "",
        "nivel": _infer_level(title, body_without_meta),
        "regime_contratacao": _infer_contract(body_without_meta),
        "data_anuncio": published,
        "codigo_vaga": code,
        "link": _canonical_link(code),
        "descricao": body_without_meta,
        "requisitos": _extract_requirements(body_without_meta),
        "beneficios": "",
        "tags": tags,
        "confianca_extracao": 0.74 if title and code else 0.45,
        "erro_extracao": "" if title and code else "apinfo_bloco_incompleto",
        "requer_login": False,
        "candidatura_automatica_disponivel": bool(application_href),
        "status_candidatura": "não avaliada",
        "observacoes": "Coleta publica APInfo via requests/BeautifulSoup; link de envio de curriculo detectado mas nao acessado.",
    }


def parse_listing(html: str, search_keyword: str = "", filter_keywords: list[str] | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[dict[str, Any]] = []
    keywords = filter_keywords or []
    for box in soup.select(".box-vagas"):
        job = parse_job_box(box, search_keyword)
        if _matches_keywords(job, keywords):
            jobs.append(job)
    return jobs


class ApinfoSource(BaseSource):
    name = "apinfo"

    def __init__(self) -> None:
        self.stats: dict[str, Any] = {
            "start_urls": [],
            "detail_urls": [],
            "listing_links": 0,
            "raw_collected": 0,
            "errors": [],
        }

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0; public APInfo collector)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }

    def _post_search(self, session: requests.Session, keyword: str, page: int) -> requests.Response:
        data = {
            "tcv": "1",
            "pag": str(page),
            "keyw": keyword,
            "onde": "2",
            "andor": "2",
        }
        response = session.post(BASE_URL, data=data, headers=self._headers(), timeout=20)
        if response.status_code in BLOCK_STATUSES:
            raise RuntimeError(f"bloqueio_http_{response.status_code}")
        response.raise_for_status()
        return response

    def _get_listing(self, session: requests.Session) -> requests.Response:
        response = session.get(BASE_URL, headers=self._headers(), timeout=20)
        if response.status_code in BLOCK_STATUSES:
            raise RuntimeError(f"bloqueio_http_{response.status_code}")
        response.raise_for_status()
        return response

    def collect(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        searches = config.get("searches") or []
        keywords = [str(item.get("keywords") or "").strip() for item in searches if item.get("keywords")]
        keywords = keywords or list(DEFAULT_KEYWORDS)
        max_pages = max(1, min(int(config.get("max_pages") or 1), 2))
        max_jobs = int(config.get("max_jobs") or 30)
        delay_seconds = float(config.get("delay_seconds", 0.2))

        jobs: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        session = requests.Session()

        for keyword in keywords:
            for page in range(1, max_pages + 1):
                if len(jobs) >= max_jobs:
                    break
                url_marker = f"{BASE_URL}?{urlencode({'keyw': keyword, 'pag': page})}"
                self.stats["start_urls"].append(url_marker)
                try:
                    response = self._post_search(session, keyword, page)
                    parsed_jobs = parse_listing(response.text, keyword)
                except RuntimeError as exc:
                    self.stats["errors"].append(f"{url_marker}: {exc}")
                    self.stats["raw_collected"] = len(jobs)
                    return jobs
                except requests.RequestException as exc:
                    self.stats["errors"].append(f"{url_marker}: {exc}")
                    break

                if not parsed_jobs and page == 1:
                    try:
                        fallback = self._get_listing(session)
                        fallback_url = f"{BASE_URL}?fallback={keyword}"
                        self.stats["start_urls"].append(fallback_url)
                        parsed_jobs = parse_listing(fallback.text, keyword, keywords)
                    except RuntimeError as exc:
                        self.stats["errors"].append(f"{BASE_URL}: {exc}")
                        self.stats["raw_collected"] = len(jobs)
                        return jobs
                    except requests.RequestException as exc:
                        self.stats["errors"].append(f"{BASE_URL}: {exc}")
                        break

                for job in parsed_jobs:
                    code = str(job.get("codigo_vaga") or job.get("link") or "").lower()
                    if not code or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    jobs.append(job)
                    self.stats["detail_urls"].append(str(job.get("link") or ""))
                    if len(jobs) >= max_jobs:
                        break

                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            if len(jobs) >= max_jobs:
                break

        self.stats["listing_links"] = len(seen_codes)
        self.stats["raw_collected"] = len(jobs)
        self.stats["collected_at"] = datetime.now().isoformat(timespec="seconds")
        return jobs
