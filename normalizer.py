from __future__ import annotations

from datetime import datetime
from typing import Any


STANDARD_COLUMNS = [
    "coletado_em",
    "origem",
    "busca_keywords",
    "titulo",
    "empresa",
    "localidade",
    "modalidade",
    "salario",
    "nivel",
    "regime_contratacao",
    "data_anuncio",
    "codigo_vaga",
    "link",
    "descricao",
    "requisitos",
    "beneficios",
    "tags",
    "score_bruto",
    "score_aderencia",
    "priority_rank",
    "classificacao",
    "motivos_score",
    "confianca_extracao",
    "erro_extracao",
    "requer_login",
    "candidatura_automatica_disponivel",
    "status_candidatura",
    "observacoes",
    "job_key",
    "first_seen_at",
    "last_seen_at",
    "collection_run_id",
    "is_new_in_run",
]


DEFAULTS: dict[str, Any] = {
    "coletado_em": "",
    "origem": "",
    "busca_keywords": "",
    "titulo": "",
    "empresa": "",
    "localidade": "",
    "modalidade": "",
    "salario": "",
    "nivel": "",
    "regime_contratacao": "",
    "data_anuncio": "",
    "codigo_vaga": "",
    "link": "",
    "descricao": "",
    "requisitos": "",
    "beneficios": "",
    "tags": "",
    "score_bruto": 0,
    "score_aderencia": 0,
    "priority_rank": 0,
    "classificacao": "Ignorar",
    "motivos_score": "",
    "confianca_extracao": 0.0,
    "erro_extracao": "",
    "requer_login": False,
    "candidatura_automatica_disponivel": False,
    "status_candidatura": "nao_iniciada",
    "observacoes": "",
    "job_key": "",
    "first_seen_at": "",
    "last_seen_at": "",
    "collection_run_id": "",
    "is_new_in_run": False,
}


def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    normalized = {column: job.get(column, DEFAULTS[column]) for column in STANDARD_COLUMNS}
    if not normalized["coletado_em"]:
        normalized["coletado_em"] = datetime.now().isoformat(timespec="seconds")
    if isinstance(normalized["tags"], list):
        normalized["tags"] = ", ".join(str(tag) for tag in normalized["tags"])
    return normalized
