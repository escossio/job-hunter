from __future__ import annotations

import re
import unicodedata
from typing import Any


TITLE_TERMS: tuple[tuple[str, int, str], ...] = (
    ("analista de tecnologia da informacao ti", 28, "Titulo relevante: Analista de TI"),
    ("analista de ti", 28, "Titulo relevante: Analista de TI"),
    ("analista tecnologia da informacao ti", 28, "Titulo relevante: Analista TI"),
    ("analista ti", 28, "Titulo relevante: Analista TI"),
    ("suporte tecnologia da informacao ti", 24, "Titulo relevante: suporte TI"),
    ("suporte de tecnologia da informacao ti", 24, "Titulo relevante: suporte TI"),
    ("tecnico de suporte", 22, "Titulo relevante: tecnico de suporte"),
    ("analista de suporte", 24, "Titulo relevante: Analista de suporte"),
    ("suporte ti", 24, "Titulo relevante: suporte TI"),
    ("infraestrutura", 24, "Titulo menciona infraestrutura"),
    ("redes", 24, "Titulo menciona redes"),
    ("noc", 26, "Titulo menciona NOC"),
    ("monitoramento", 26, "Titulo menciona monitoramento"),
    ("observabilidade", 28, "Titulo menciona observabilidade"),
    ("telecom", 22, "Titulo menciona telecom"),
)
TECH_TERMS: tuple[tuple[str, int, str], ...] = (
    ("zabbix", 14, "menciona Zabbix"),
    ("grafana", 14, "menciona Grafana"),
    ("prometheus", 12, "menciona Prometheus"),
    ("linux", 10, "menciona Linux"),
    ("python", 10, "menciona Python"),
    ("postgresql", 6, "menciona PostgreSQL"),
    ("bgp", 10, "menciona BGP"),
    ("ospf", 10, "menciona OSPF"),
    ("vlan", 8, "menciona VLAN"),
    ("wireshark", 8, "menciona Wireshark"),
)
DOMAIN_TERMS: tuple[tuple[str, int, str], ...] = (
    ("infraestrutura", 16, "menciona infraestrutura"),
    ("redes", 16, "menciona redes"),
    ("rede", 10, "menciona rede"),
    ("telecom", 16, "menciona telecom"),
    ("monitoramento", 16, "menciona monitoramento"),
    ("observabilidade", 18, "menciona observabilidade"),
    ("noc", 16, "menciona NOC"),
    ("suporte", 10, "menciona suporte"),
    ("incidentes", 10, "menciona incidentes"),
    ("troubleshooting", 10, "menciona troubleshooting"),
    ("sustentacao", 10, "menciona sustentacao"),
    ("operacao", 10, "menciona operacao"),
)
REMOTE_TERMS = ("home office", "remoto", "remota", "100% remoto", "100 remoto")
HYBRID_TERMS = ("hibrido", "hybrid")
PRESENTIAL_TERMS = ("presencial",)
PROGRAMMING_TERMS = ("programador", "desenvolvedor", "fullstack", "full stack", "frontend", "front end", "backend", "back end")
INFRA_CONTEXT_TERMS = ("rede", "redes", "infra", "infraestrutura", "observabilidade", "monitoramento", "noc", "telecom", "linux", "zabbix", "grafana", "prometheus")
PRIMARY_FIT_TERMS = (
    "observabilidade",
    "monitoramento",
    "noc",
    "redes",
    "rede",
    "telecom",
    "infraestrutura",
    "suporte tecnologia da informacao ti",
    "suporte de tecnologia da informacao ti",
    "suporte ti",
    "analista de tecnologia da informacao ti",
    "analista tecnologia da informacao ti",
    "analista de ti",
    "analista ti",
    "tecnico de redes",
    "analista de redes",
    "comunicacao de dados",
    "sustentacao",
    "operacao",
    "operacoes",
    "incidentes",
    "troubleshooting",
    "soc",
    "siem",
    "qradar",
    "itom",
    "servicenow",
    "zabbix",
    "grafana",
    "prometheus",
    "elastic",
)
TITLE_PRIMARY_EXCEPTIONS = (
    "observabilidade",
    "monitoramento",
    "noc",
    "redes",
    "rede",
    "infraestrutura",
    "analista de ti",
    "analista ti",
    "analista de tecnologia da informacao ti",
    "analista tecnologia da informacao ti",
    "suporte ti",
    "suporte de ti",
    "suporte tecnologia da informacao ti",
    "suporte de tecnologia da informacao ti",
    "tecnico de suporte",
    "analista de suporte",
    "soc",
    "siem",
    "qradar",
    "tecnico de redes",
    "analista de redes",
)
SECONDARY_TECH_TERMS = ("linux", "python", "postgresql", "wireshark", "bgp", "ospf", "vlan", "cloud", "aws", "azure", "api", "shell", "automacao", "devops", "sre")
GENERIC_SOFTWARE_TERMS = (
    "backend",
    "back end",
    "frontend",
    "front end",
    "fullstack",
    "full stack",
    "desenvolvedor",
    "software engineer",
    "engenharia de software",
    "arquiteto de software",
    "arquitetura de software",
    "integracao e apis",
    "integracoes e apis",
    "data engineer",
    "cientista de dados",
    "testes",
    "qa",
    "java",
    "kotlin",
    "node",
    "react",
)
DISTANT_FOCUS_TERMS = ("inteligencia artificial", " ai ", "llm", "mlops", "llmops", "appsec", "devsecops", "seguranca de aplicacoes", "seguranca de aplicacao")
ADHERENT_TOOL_TERMS = ("zabbix", "grafana", "prometheus", "linux", "python", "postgresql", "wireshark", "bgp", "ospf", "vlan")
DISTANT_TECH_TERMS = (
    " ia ",
    " inteligencia artificial",
    " ai ",
    "llm",
    "mlops",
    "llmops",
    "appsec",
    "devsecops",
    "seguranca de aplicacoes",
    "seguranca de aplicacao",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_text(text: str, *, modality: bool = False) -> str:
    normalized = _strip_accents(str(text or "").lower())
    normalized = normalized.replace("home-office", "home office").replace("homeoffice", "home office")
    normalized = normalized.replace("phyton", "python")
    normalized = normalized.replace("front-end", "front end").replace("back-end", "back end")
    normalized = re.sub(r"\bti\b", "tecnologia da informacao ti", normalized)
    if modality:
        normalized = re.sub(r"\bho\b", "home office", normalized)
    normalized = re.sub(r"[^\w#+./% ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _add_once(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _classify(score: int) -> str:
    if score >= 70:
        return "Alta"
    if score >= 45:
        return "Média"
    if score >= 25:
        return "Baixa"
    return "Ignorar"


def _max_classification(current: str, maximum: str) -> str:
    order = {"Ignorar": 0, "Baixa": 1, "Média": 2, "Alta": 3}
    if order[current] <= order[maximum]:
        return current
    return maximum


def _classification_cap(classification: str) -> int:
    caps = {"Alta": 100, "Média": 69, "Baixa": 44, "Ignorar": 24}
    return caps.get(classification, 24)


def _priority_rank(classification: str, score: int) -> int:
    weights = {"Alta": 4, "Média": 3, "Baixa": 2, "Ignorar": 1}
    return weights.get(classification, 1) * 1000 + max(0, min(100, score))


def _preferences(config: dict[str, Any] | None) -> dict[str, Any]:
    defaults = {"remote_first": True, "allow_presential": False, "allow_hybrid": True}
    configured = (config or {}).get("preferences") or {}
    return {**defaults, **configured}


def _has_remote(modality_text: str, location_text: str) -> bool:
    return _contains_any(modality_text, REMOTE_TERMS) or "home office" in _normalize_text(location_text, modality=True)


def _has_hybrid(modality_text: str, location_text: str) -> bool:
    text = f"{modality_text} {_normalize_text(location_text)}"
    return _contains_any(text, HYBRID_TERMS)


def _has_presential(modality_text: str, location_text: str, full_text: str) -> bool:
    text = f"{modality_text} {_normalize_text(location_text)} {full_text}"
    return _contains_any(text, PRESENTIAL_TERMS)


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def _format_evidence_label(term: str) -> str:
    labels = {
        "suporte tecnologia da informacao ti": "suporte TI",
        "suporte de tecnologia da informacao ti": "suporte TI",
        "suporte ti": "suporte TI",
        "analista de tecnologia da informacao ti": "analista de TI",
        "analista tecnologia da informacao ti": "analista TI",
        "analista de ti": "analista de TI",
        "analista ti": "analista TI",
        "tecnico de redes": "técnico de redes",
        "analista de redes": "analista de redes",
        "comunicacao de dados": "comunicação de dados",
        "sustentacao": "sustentação",
        "operacao": "operação",
        "operacoes": "operações",
        "software engineer": "software engineer",
        "engenharia de software": "engenharia de software",
        "arquiteto de software": "arquiteto de software",
        "arquitetura de software": "arquitetura de software",
        "integracao e apis": "integração e APIs",
        "integracoes e apis": "integrações e APIs",
        "data engineer": "data engineer",
        "cientista de dados": "cientista de dados",
        "backend": "backend",
        "back end": "back-end",
        "frontend": "frontend",
        "front end": "front-end",
        "fullstack": "fullstack",
        "full stack": "full stack",
        "estagio": "estágio",
        "trainee": "trainee",
        "treinee": "treinee",
        "primeiro emprego": "primeiro emprego",
        "qradar": "QRadar",
        "itom": "ITOM",
        "servicenow": "ServiceNow",
    }
    return labels.get(term, term)


def score_job(job: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    title = str(job.get("titulo") or "").lower()
    description = str(job.get("descricao") or "").lower()
    requirements = str(job.get("requisitos") or "").lower()
    modality = str(job.get("modalidade") or "").lower()
    contract = str(job.get("regime_contratacao") or "").lower()
    level = str(job.get("nivel") or "").lower()
    location = str(job.get("localidade") or "").lower()
    origin = str(job.get("origem") or "").strip().lower()
    prefs = _preferences(config)

    title_norm = _normalize_text(title)
    description_norm = _normalize_text(description)
    requirements_norm = _normalize_text(requirements)
    modality_norm = _normalize_text(modality, modality=True)
    contract_norm = _normalize_text(contract)
    level_norm = _normalize_text(level)
    location_norm = _normalize_text(location, modality=True)
    full_text = " ".join([title_norm, description_norm, requirements_norm, modality_norm, contract_norm, level_norm, location_norm])

    score = 0
    reasons: list[str] = []
    limits: list[str] = []

    for term, points, reason in TITLE_TERMS:
        if term in title_norm:
            score += points
            _add_once(reasons, reason)
            break

    tech_hits = 0
    for term, points, reason in TECH_TERMS:
        if term in full_text:
            score += points
            tech_hits += 1
            if len([item for item in reasons if item.startswith("menciona ")]) < 5:
                _add_once(reasons, reason)
    if tech_hits >= 3:
        score += 8
        _add_once(reasons, "conjunto tecnico aderente")

    domain_hits = 0
    for term, points, reason in DOMAIN_TERMS:
        if term in full_text:
            score += points
            domain_hits += 1
            if len(reasons) < 7:
                _add_once(reasons, reason)
    if domain_hits >= 3:
        score += 10
        _add_once(reasons, "forte contexto de infraestrutura/suporte")

    has_remote = _has_remote(modality_norm, location_norm)
    has_hybrid = _has_hybrid(modality_norm, location_norm)
    has_presential = _has_presential(modality_norm, location_norm, full_text)

    if has_remote:
        score += 15
        _add_once(reasons, "modalidade remota")
    elif has_hybrid:
        if prefs["allow_hybrid"]:
            score -= 10
            _add_once(reasons, "Penalidade: vaga hibrida tem peso menor que remoto.")
        else:
            score -= 25
            _add_once(reasons, "Penalidade: vaga hibrida fora da preferencia atual.")
    elif has_presential and not prefs["allow_presential"]:
        score -= 35
        _add_once(reasons, "Penalidade: vaga presencial e preferencia atual e remoto.")

    if "clt" in contract_norm:
        score += 8
        _add_once(reasons, "contratacao CLT")
    if _contains_any(full_text, ("cloud", "devops", "sre", "automacao", "shell", "api", "aws", "azure")):
        score += 6
        _add_once(reasons, "adjacencias tecnicas")

    if "presencial obrigatorio" in full_text:
        score -= 50 if not prefs["allow_presential"] else 30
        _add_once(reasons, "Penalidade: presencial obrigatorio.")
    if _contains_any(full_text, PROGRAMMING_TERMS) and not _contains_any(full_text, INFRA_CONTEXT_TERMS):
        score -= 24
        _add_once(reasons, "penalidade: programacao sem contexto de infra")
    if _contains_any(full_text, ("vendas", "comercial", "telemarketing", "estágio", "estagio")):
        score -= 30
        _add_once(reasons, "penalidade: area fora do alvo")
    if _contains_any(level_norm, ("senior", "especialista")) and _contains_any(full_text, ("growth", "gtm", "salesforce", "produto", "product owner")) and not _contains_any(full_text, INFRA_CONTEXT_TERMS):
        score -= 15
        _add_once(reasons, "penalidade: senioridade distante do perfil")

    primary_terms = _matched_terms(full_text, PRIMARY_FIT_TERMS)
    primary_title_terms = _matched_terms(title_norm, TITLE_PRIMARY_EXCEPTIONS)
    secondary_terms = _matched_terms(full_text, SECONDARY_TECH_TERMS)
    generic_software_terms = _matched_terms(full_text, GENERIC_SOFTWARE_TERMS)
    distant_focus_terms = _matched_terms(full_text, DISTANT_FOCUS_TERMS)

    if primary_terms:
        for term in primary_terms[:5]:
            _add_once(reasons, f"evidencia principal: {_format_evidence_label(term)}")
    elif primary_title_terms:
        for term in primary_title_terms[:5]:
            _add_once(reasons, f"titulo principal: {_format_evidence_label(term)}")

    for term in secondary_terms[:4]:
        _add_once(reasons, f"evidencia tecnica: {_format_evidence_label(term)}")

    if has_remote:
        _add_once(reasons, "modalidade aderente: remoto")
    elif has_hybrid:
        _add_once(reasons, "modalidade aderente: híbrido")

    title_primary_fit = bool(primary_title_terms)
    body_primary_fit = bool(primary_terms)
    secondary_fit = bool(secondary_terms)
    modality_fit = bool(has_remote or has_hybrid)
    title_direct_exception = title_primary_fit

    seniority_text = f"{title_norm} {level_norm}"

    if generic_software_terms and not title_primary_fit:
        score -= 20
        limits.append("Limite aplicado: vaga de software/dados/testes sem foco principal em rede, infra, NOC ou observabilidade.")
        _add_once(reasons, "Limite aplicado: vaga de software/dados/testes sem foco principal em rede, infra, NOC ou observabilidade.")
        _add_once(reasons, "Area interessante, mas distante do foco principal.")

    if origin == "remotar" and generic_software_terms and not title_primary_fit:
        limits.append("Limite aplicado: Remotar exige foco principal para software genérico.")

    if distant_focus_terms and not title_primary_fit:
        limits.append("Limite aplicado: vaga tecnica interessante, mas distante do foco principal.")
        _add_once(reasons, "Area interessante, mas distante do foco principal.")

    if _contains_any(seniority_text, ("senior", "especialista", "lead", "arquiteto")) and not _contains_any(full_text, ("observabilidade", "monitoramento", "noc", "redes", "rede", "infraestrutura", "suporte", "operacao", "sustentacao", "soc", "siem", "qradar", "itom")):
        score -= 10
        limits.append("Limite aplicado: senioridade fora do alvo sem foco principal.")
        _add_once(reasons, "Penalidade: senioridade fora do alvo.")

    if _contains_any(seniority_text, ("trainee", "treinee")):
        score -= 25
        limits.append("Limite aplicado: trainee/treinee no maximo Média.")
        _add_once(reasons, "Penalidade: trainee/treinee.")

    if _contains_any(seniority_text, ("estagio",)) or _contains_any(full_text, ("estagio", "estágio", "primeiro emprego")):
        score -= 40
        limits.append("Limite aplicado: estagio/primeiro emprego no maximo Baixa.")
        _add_once(reasons, "Penalidade: estágio/primeiro emprego.")

    requires_primary_fit = bool((config or {}).get("preferences", {}).get("alta_requires_primary_fit", True))
    software_without_primary_max = str((config or {}).get("preferences", {}).get("software_without_primary_max") or "Média")
    remotar_strict = bool((config or {}).get("preferences", {}).get("remotar_strict_software_filter", True))
    high_eligible = score >= 70 and (title_direct_exception or (title_primary_fit and (secondary_fit or modality_fit)))

    if requires_primary_fit and score >= 70 and not high_eligible:
        limits.append("Limite aplicado: score alto, mas faltou combinacao minima para Alta.")
        if not title_primary_fit:
            _add_once(reasons, "Limite aplicado: faltou grupo principal para Alta.")
        elif not (secondary_fit or modality_fit):
            _add_once(reasons, "Limite aplicado: faltou segunda evidencia para Alta.")

    if generic_software_terms and not title_primary_fit:
        limits.append(f"Limite aplicado: {software_without_primary_max} para vaga de software sem grupo principal.")

    if remotar_strict and origin == "remotar" and generic_software_terms and not title_primary_fit:
        limits.append("Limite aplicado: Remotar bloqueia Alta para software genérico sem foco principal.")

    score_bruto = score
    scored = dict(job)
    classification = _classify(score_bruto)
    if requires_primary_fit and classification == "Alta" and not high_eligible:
        classification = "Média"
    if generic_software_terms and not title_primary_fit:
        classification = _max_classification(classification, software_without_primary_max)
    if origin == "remotar" and generic_software_terms and not title_primary_fit:
        classification = _max_classification(classification, "Média")
    if _contains_any(seniority_text, ("senior", "especialista", "lead", "arquiteto")) and not title_primary_fit:
        classification = _max_classification(classification, "Média")
    if _contains_any(seniority_text, ("trainee", "treinee")):
        classification = _max_classification(classification, "Média")
    if _contains_any(seniority_text, ("estagio",)) or _contains_any(full_text, ("estagio", "estágio", "primeiro emprego")):
        classification = _max_classification(classification, "Baixa")
    if score >= 70 and not high_eligible:
        classification = _max_classification(classification, "Média")

    score_aderencia = max(0, min(score_bruto, _classification_cap(classification)))
    if score_bruto > 100:
        _add_once(reasons, "Score bruto original acima de 100 antes dos limites finais.")
        _add_once(reasons, "Score limitado ao maximo de 100.")
    if score_aderencia != score_bruto:
        _add_once(reasons, f"Score bruto original: {score_bruto}.")
        _add_once(reasons, f"Teto da classificacao final: {_classification_cap(classification)}.")
        _add_once(reasons, f"Score aderencia final ajustado para {score_aderencia}.")

    scored["score_bruto"] = score_bruto
    scored["score_aderencia"] = score_aderencia
    scored["priority_rank"] = _priority_rank(classification, score_aderencia)
    scored["classificacao"] = classification
    scored["motivos_score"] = "; ".join([*reasons, *limits])
    return scored
