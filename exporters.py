from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from normalizer import STANDARD_COLUMNS


def _jobs_df(jobs: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(jobs, columns=STANDARD_COLUMNS)


def _sorted_jobs_df(jobs: list[dict[str, Any]]) -> pd.DataFrame:
    df = _jobs_df(jobs)
    if df.empty:
        return df
    if "priority_rank" in df.columns:
        return df.sort_values(["priority_rank", "score_aderencia", "titulo"], ascending=[False, False, True])
    return df.sort_values(["score_aderencia", "titulo"], ascending=[False, True])


def export_csv(jobs: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _sorted_jobs_df(jobs).to_csv(output_path, index=False)
    return output_path


def _source_items(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return (metadata or {}).get("sources") or {}


def _alerts_df(metadata: dict[str, Any] | None) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for source_name, source_meta in _source_items(metadata).items():
        for alert in source_meta.get("alerts") or []:
            rows.append({"origem": source_name, "tipo": alert.get("tipo", "alerta"), "mensagem": alert.get("mensagem", "")})
    return pd.DataFrame(rows, columns=["origem", "tipo", "mensagem"])


def export_xlsx(jobs: list[dict[str, Any]], output_path: Path, metadata: dict[str, Any] | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = _sorted_jobs_df(jobs)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Todas", index=False)
        df[df["classificacao"] == "Alta"].to_excel(writer, sheet_name="Alta aderência", index=False)
        df[df["classificacao"] == "Média"].to_excel(writer, sheet_name="Média aderência", index=False)
        df[df["classificacao"] == "Baixa"].to_excel(writer, sheet_name="Baixa aderência", index=False)
        df[df["classificacao"] == "Ignorar"].to_excel(writer, sheet_name="Ignorar", index=False)
        por_origem = df.groupby("origem").size().reset_index(name="total") if not df.empty else pd.DataFrame(columns=["origem", "total"])
        por_origem.to_excel(writer, sheet_name="Por origem", index=False)
        _alerts_df(metadata).to_excel(writer, sheet_name="Alertas", index=False)
    return output_path


def _table_value(value: Any) -> str:
    text = str(value or "").replace("|", "\\|")
    return " ".join(text.split())


def _int_table_value(value: Any) -> int:
    try:
        if value is None:
            return 0
        if pd.isna(value):
            return 0
    except TypeError:
        pass
    return int(value)


def _classification_counts(df: pd.DataFrame) -> dict[str, int]:
    return {classification: int((df["classificacao"] == classification).sum()) if not df.empty else 0 for classification in ("Alta", "Média", "Baixa", "Ignorar")}


def _sorted_jobs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "priority_rank" in df.columns:
        return df.sort_values(["priority_rank", "score_aderencia", "titulo"], ascending=[False, False, True])
    return df.sort_values(["score_aderencia", "titulo"], ascending=[False, True])


def export_markdown_report(jobs: list[dict[str, Any]], output_path: Path, metadata: dict[str, Any] | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = _sorted_jobs_df(jobs)
    sources = _source_items(metadata)
    raw_total = int((metadata or {}).get("raw_total", len(df)))
    deduped_total = int((metadata or {}).get("deduped_total", len(df)))
    real_collection = bool(len(df) > 0 or raw_total > 0)
    source_counts = df.groupby("origem").size().to_dict() if not df.empty else {}
    classification_counts = _classification_counts(df)

    lines = [
        "# Relatorio de vagas",
        "",
        "Coleta real executada." if real_collection else "Nenhuma vaga real coletada nesta execucao.",
        "",
        "## Resumo da coleta",
        "",
        f"- Total bruto: {raw_total}",
        f"- Total apos deduplicacao: {deduped_total}",
        f"- Total exportado: {len(df)}",
        "- score_aderencia: score final apos limites e teto da classificacao.",
        "- score_bruto: diagnostico interno antes dos limites finais.",
        "- Candidatura automatica: nao executada",
        "",
        "## Fontes executadas",
        "",
    ]
    if sources:
        for source_name, source_meta in sources.items():
            raw_count = int(source_meta.get("raw_count", 0))
            final_count = int(source_meta.get("final_count", source_counts.get(source_name, 0)))
            status = "com vagas" if final_count else "sem vagas"
            lines.append(f"- {source_name}: {status}; bruto={raw_count}; final={final_count}")
    else:
        lines.append("- Metadados de fontes nao informados.")

    lines.extend(["", "## Resultados por origem", ""])
    if source_counts:
        for source_name, total in sorted(source_counts.items()):
            raw_count = int((sources.get(source_name) or {}).get("raw_count", total))
            lines.append(f"- {source_name}: bruto={raw_count}; final={int(total)}")
    else:
        lines.append("- Nenhuma origem com vagas exportadas.")

    lines.extend(["", "## Resultados por classificacao", ""])
    for classification in ("Alta", "Média", "Baixa", "Ignorar"):
        total = classification_counts[classification]
        lines.append(f"- {classification}: {total}")

    lines.extend(["", "## Alertas por conector", ""])
    alerts = _alerts_df(metadata)
    if not alerts.empty:
        for _, alert in alerts.iterrows():
            lines.append(f"- {alert['origem']}: {alert['tipo']} - {alert['mensagem']}")
    else:
        lines.append("- Nenhum alerta registrado pelos conectores.")

    lines.extend(
        [
            "",
            "## Top vagas por aderencia",
            "",
            "| Score final | Score bruto | Classificacao | Titulo | Empresa | Origem | Modalidade | Link |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    top_jobs = _sorted_jobs_df(jobs).head(20) if jobs else df
    if top_jobs.empty:
        lines.append("|  |  |  | Nenhuma vaga exportada |  |  |  |  |")
    else:
        for _, job in top_jobs.iterrows():
            lines.append(
                "| {final_score} | {raw_score} | {classification} | {title} | {company} | {source} | {modality} | {link} |".format(
                    final_score=_int_table_value(job.get("score_aderencia")),
                    raw_score=_int_table_value(job.get("score_bruto")),
                    classification=_table_value(job.get("classificacao")),
                    title=_table_value(job.get("titulo")),
                    company=_table_value(job.get("empresa")),
                    source=_table_value(job.get("origem")),
                    modality=_table_value(job.get("modalidade")),
                    link=_table_value(job.get("link")),
                )
            )

    lines.extend(
        [
            "",
            "## Proximos passos",
            "",
            "- Revisar as vagas de maior aderencia antes de qualquer candidatura manual.",
            "- Ajustar pesos do scoring conforme feedback das vagas aceitas e rejeitadas.",
            "- Manter a politica de nao executar candidatura automatica.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def export_incremental_report(
    jobs: list[dict[str, Any]],
    output_path: Path,
    summary: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = _sorted_jobs_df(jobs)
    sources = _source_items(metadata)
    alerts = _alerts_df(metadata)
    source_counts = df.groupby("origem").size().to_dict() if not df.empty else {}
    known_before = int(summary.get("known_before", 0))
    raw_total = int(summary.get("raw_total", len(df)))
    deduped_total = int(summary.get("deduped_total", len(df)))
    new_jobs = int(summary.get("new_jobs", 0))
    known_jobs = int(summary.get("known_jobs", 0))
    updated_jobs = int(summary.get("updated_jobs", 0))
    final_total = int(summary.get("final_total", len(df)))
    run_id = str(summary.get("run_id", ""))
    snapshot_csv = str(summary.get("snapshot_csv", ""))
    snapshot_xlsx = str(summary.get("snapshot_xlsx", ""))
    state_file = str(summary.get("state_file", ""))
    report_csv = str(summary.get("report_csv", snapshot_csv))
    lines = [
        "# Relatorio incremental de vagas",
        "",
        f"- Coleta em: {summary.get('started_at', '')}",
        f"- Run ID: {run_id}",
        f"- Total conhecido antes: {known_before}",
        f"- Total bruto coletado: {raw_total}",
        f"- Total apos dedupe da coleta: {deduped_total}",
        f"- Vagas novas adicionadas: {new_jobs}",
        f"- Vagas conhecidas reencontradas: {known_jobs}",
        f"- Vagas atualizadas: {updated_jobs}",
        f"- Total final consolidado: {final_total}",
        "- Candidatura automatica: nao executada",
        "- Login externo: nao executado",
        "- Links externos de candidatura: nao acessados",
        "",
        "## Fontes consultadas",
        "",
    ]
    if sources:
        for source_name, source_meta in sources.items():
            raw_count = int(source_meta.get("raw_count", 0))
            final_count = int(source_meta.get("final_count", source_counts.get(source_name, 0)))
            lines.append(f"- {source_name}: bruto={raw_count}; final={final_count}")
    else:
        lines.append("- Metadados de fontes nao informados.")

    lines.extend(["", "## Alertas por fonte", ""])
    if not alerts.empty:
        for _, alert in alerts.iterrows():
            lines.append(f"- {alert['origem']}: {alert['tipo']} - {alert['mensagem']}")
    else:
        lines.append("- Nenhum alerta registrado pelos conectores.")

    lines.extend(
        [
            "",
            "## Artefatos gerados",
            "",
            f"- CSV: {snapshot_csv}",
            f"- XLSX: {snapshot_xlsx}",
            f"- Relatorio: {output_path}",
            f"- Base historica: {state_file}",
            f"- Snapshot CSV usado pelo painel: {report_csv}",
            "",
            "## Observacoes operacionais",
            "",
            "- A base historica e incremental e preserva as vagas antigas.",
            "- Status e observacoes continuam independentes em data/status/job_status.json.",
            "- Nenhuma candidatura, login ou automacao de envio foi executada.",
        ]
    )

    top_jobs = df.head(20) if not df.empty else df
    lines.extend(["", "## Top vagas da consolidacao", "", "| Score final | Classificacao | Titulo | Empresa | Origem | Link |", "| --- | --- | --- | --- | --- | --- |"])
    if top_jobs.empty:
        lines.append("|  |  | Nenhuma vaga consolidada |  |  |  |")
    else:
        for _, job in top_jobs.iterrows():
            lines.append(
                "| {score} | {classification} | {title} | {company} | {source} | {link} |".format(
                    score=_int_table_value(job.get("score_aderencia")),
                    classification=_table_value(job.get("classificacao")),
                    title=_table_value(job.get("titulo")),
                    company=_table_value(job.get("empresa")),
                    source=_table_value(job.get("origem")),
                    link=_table_value(job.get("link")),
                )
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
