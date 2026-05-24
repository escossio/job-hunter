from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseSource


BASE_URL = "https://www.nerdin.com.br/"
START_URLS = (
    "https://www.nerdin.com.br/vagas.php",
    "https://www.nerdin.com.br/vagas-home-office.php",
    "https://www.nerdin.com.br/vagas-desenvolvedor-sistemas.php",
)
JOB_LINK_RE = re.compile(r"/?vaga_emprego/vaga-[^\"'#?\s]+-\d+\.php(?:\?[^\"'#\s]*)?$", re.IGNORECASE)
CODE_RE = re.compile(r"-(\d+)\.php$", re.IGNORECASE)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.replace("\xa0", " ").split())


def _text_from_node(node) -> str:
    if not node:
        return ""
    return _clean_text(node.get_text(" ", strip=True))


def _absolute_url(href: str) -> str:
    return urljoin(BASE_URL, href)


def _is_nerdin_job_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "www.nerdin.com.br":
        return False
    return bool(JOB_LINK_RE.search(parsed.path))


def extract_job_links(html: str, base_url: str = BASE_URL) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, anchor["href"])
        parsed = urlparse(absolute)
        normalized = parsed._replace(query="", fragment="").geturl()
        if not _is_nerdin_job_url(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)

    return links


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        text = _text_from_node(soup.select_one(selector))
        if text:
            return text
    return ""


def _company_text(soup: BeautifulSoup) -> str:
    company = _first_text(soup, ("main a.text-primary.fw-semibold", "main .mb-3 a.text-primary"))
    if not company:
        title_node = soup.select_one("main h2.h5, main h2")
        container = title_node.find_parent("div") if title_node else None
        sibling = container.find_next_sibling("div") if container else None
        while sibling:
            classes = sibling.get("class") or []
            text = _text_from_node(sibling)
            if "mb-3" in classes and text and not sibling.select_one(".badge-vaga-info"):
                company = text
                break
            sibling = sibling.find_next_sibling("div")
    company = re.sub(r"\s+-\s+\d+\s+Vagas?\s+Ativas?.*$", "", company, flags=re.IGNORECASE)
    return _clean_text(company)


def _badge_values(soup: BeautifulSoup) -> list[str]:
    values: list[str] = []
    for badge in soup.select("main .badge-vaga-info"):
        text = _clean_text(badge.get_text(" ", strip=True))
        if text and text not in values:
            values.append(text)
    return values


def _tab_panes(soup: BeautifulSoup) -> list[Any]:
    return soup.select("main .tab-content .tab-pane")


def _remove_unwanted_nodes(node) -> None:
    for selector in (
        "a.btn",
        ".btn-candidatar-vaga",
        ".d-lg-none",
        ".premium-card",
        ".shadow-sm",
        "script",
        "style",
    ):
        for found in node.select(selector):
            found.decompose()


def _pane_text(panes: list[Any], index: int) -> str:
    if index >= len(panes):
        return ""
    pane = BeautifulSoup(str(panes[index]), "lxml")
    _remove_unwanted_nodes(pane)
    text = _text_from_node(pane)
    blocked_phrases = (
        "Quero me Candidatar",
        "Desbloqueie o Contato Direto da Empresa.",
        "Não fique invisível no processo seletivo.",
        "Desbloquear contato",
        "Contato sem intermediação",
        "Aumente suas chances",
        "Vagas VIP exclusivas",
        "Quero Prioridade",
        "Seja Premium",
    )
    for phrase in blocked_phrases:
        text = text.replace(phrase, " ")
    return _clean_text(text)


def _salary_from_pane(pane) -> str:
    salary = _text_from_node(pane.select_one(".vaga-salario")) if pane else ""
    if salary:
        return salary
    text = _text_from_node(pane)
    match = re.search(r"(?:Até|De|R\$)\s*[\d\.,]+(?:\s*a\s*[\d\.,]+)?", text, flags=re.IGNORECASE)
    return _clean_text(match.group(0)) if match else ""


def _published_from_pane(pane) -> str:
    if not pane:
        return ""
    for item in pane.select(".text-muted.small"):
        text = _text_from_node(item)
        if "Publicada" in text:
            return text.split("|", 1)[0].strip()
    return ""


def _infer_level(badges: list[str], requirements: str) -> str:
    known = ("Estágio", "Junior", "Júnior", "Pleno", "Senior", "Sênior", "Especialista")
    for value in badges:
        if any(term.lower() in value.lower() for term in known):
            return value
    match = re.search(r"Nível:\s*([^\.]+)", requirements, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ""


def _infer_modality(badges: list[str], title: str, description: str) -> str:
    text = " ".join([*badges, title, description]).lower()
    if "home office" in text or "remoto" in text:
        return "Home Office"
    if "híbrido" in text or "hibrido" in text:
        return "Híbrido"
    if "presencial" in text:
        return "Presencial"
    return ""


def _infer_contract(badges: list[str], requirements: str) -> str:
    text = " ".join([*badges, requirements]).lower()
    contracts: list[str] = []
    for contract in ("CLT", "PJ", "Freelancer", "Cooperado"):
        if contract.lower() in text:
            contracts.append(contract)
    return ", ".join(contracts)


def _infer_location(title: str, badges: list[str], description: str) -> str:
    title_match = re.search(r"\s+-\s+(.+)$", title)
    if title_match:
        location = _clean_text(title_match.group(1))
        if location and not re.search(r"home office|remoto|h[ií]brido", location, flags=re.IGNORECASE):
            return location
    text = " ".join([*badges, description])
    match = re.search(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]+)/(?:[A-Z]{2}|HO|EX)\b", text)
    return _clean_text(match.group(0)) if match else ""


def _job_code(link: str) -> str:
    match = CODE_RE.search(urlparse(link).path)
    return match.group(1) if match else ""


def parse_job_detail(html: str, link: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    page_title = _first_text(soup, ("h1", "title"))
    title = _first_text(soup, ("main h2.h5", "main h2", "h1"))
    if not title and page_title:
        title = re.sub(r"^Vaga\s+", "", page_title, flags=re.IGNORECASE)
        title = re.sub(r"\s+-\s+Nerdin.*$", "", title, flags=re.IGNORECASE)

    company = _company_text(soup)
    badges = _badge_values(soup)
    panes = _tab_panes(soup)
    about_pane = panes[0] if panes else None
    description = _pane_text(panes, 0)
    requirements = _pane_text(panes, 1)
    benefits = _pane_text(panes, 2)
    tags = [value for value in badges if value.startswith("#")]
    tags.extend(_clean_text(tag.get_text(" ", strip=True)) for tag in soup.select("main a.btn-outline-secondary") if _clean_text(tag.get_text(" ", strip=True)).startswith("#"))
    tags = list(dict.fromkeys(tags))

    return {
        "origem": "nerdin",
        "busca_keywords": "nerdin_public",
        "titulo": title,
        "empresa": company,
        "localidade": _infer_location(page_title or title, badges, description),
        "modalidade": _infer_modality(badges, page_title or title, description),
        "salario": _salary_from_pane(about_pane),
        "nivel": _infer_level(badges, requirements),
        "regime_contratacao": _infer_contract(badges, requirements),
        "data_anuncio": _published_from_pane(about_pane),
        "codigo_vaga": _job_code(link),
        "link": link,
        "descricao": description,
        "requisitos": requirements,
        "beneficios": benefits,
        "tags": tags,
        "confianca_extracao": 0.78 if title and link else 0.35,
        "erro_extracao": "" if title and link else "detalhe_publico_incompleto",
        "requer_login": False,
        "candidatura_automatica_disponivel": False,
        "status_candidatura": "nao_iniciada",
        "observacoes": "Coleta publica Nerdin via requests/BeautifulSoup; nenhuma interacao de candidatura executada.",
    }


class NerdinSource(BaseSource):
    name = "nerdin"
    start_urls = START_URLS

    def __init__(self) -> None:
        self.stats: dict[str, Any] = {
            "start_urls": list(self.start_urls),
            "listing_links": 0,
            "detail_urls": [],
            "raw_collected": 0,
            "errors": [],
        }

    def _get(self, url: str, timeout: int = 25) -> requests.Response:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0; public Nerdin collector)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def collect(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        max_details = int(config.get("max_job_details") or config.get("max_details") or 30)
        delay_seconds = float(config.get("delay_seconds", 0.2))

        found_links: list[str] = []
        seen: set[str] = set()
        for url in self.start_urls:
            try:
                response = self._get(url)
            except requests.RequestException as exc:
                self.stats["errors"].append(f"{url}: {exc}")
                continue

            for link in extract_job_links(response.text, response.url):
                if link in seen:
                    continue
                seen.add(link)
                found_links.append(link)

        self.stats["listing_links"] = len(found_links)
        jobs: list[dict[str, Any]] = []
        for link in found_links[:max_details]:
            try:
                response = self._get(link)
                if not _is_nerdin_job_url(response.url):
                    self.stats["errors"].append(f"{link}: detalhe_publico_indisponivel ({response.url})")
                    continue
                self.stats["detail_urls"].append(response.url)
                jobs.append(parse_job_detail(response.text, response.url))
            except requests.RequestException as exc:
                self.stats["errors"].append(f"{link}: {exc}")
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        self.stats["raw_collected"] = len(jobs)
        self.stats["collected_at"] = datetime.now().isoformat(timespec="seconds")
        return jobs
