from __future__ import annotations

import argparse
import base64
import csv
import binascii
import hmac
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import yaml


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data" / "output"
DEFAULT_PANEL_DIR = PROJECT_DIR / "panel"
DEFAULT_STATUS_FILE = PROJECT_DIR / "data" / "status" / "job_status.json"
DEFAULT_CONFIG_FILE = PROJECT_DIR / "config.yaml"
AUTH_ENV_USER = "JOB_HUNTER_PANEL_USER"
AUTH_ENV_PASSWORD = "JOB_HUNTER_PANEL_PASSWORD"
AUTH_ENV_DISABLED = "JOB_HUNTER_PANEL_AUTH_DISABLED"
STATUS_OPTIONS = [
    "não avaliada",
    "revisar",
    "candidatura enviada",
    "não enviar",
    "aguardando retorno",
    "entrevista",
    "recusada",
]
STATUS_ALIASES = {
    "nao avaliada": "não avaliada",
    "não avaliada": "não avaliada",
    "nao enviar": "não enviar",
    "não enviar": "não enviar",
    "candidatura enviada": "candidatura enviada",
    "aguardando retorno": "aguardando retorno",
    "entrevista": "entrevista",
    "recusada": "recusada",
    "revisar": "revisar",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        if isinstance(value, float) and value != value:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_text(value).strip().lower() in {"1", "true", "yes", "sim", "y"}


def _env_truthy(value: Any) -> bool:
    return _safe_bool(value)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _date_part(value: Any) -> str:
    text = _safe_text(value).strip()
    if not text:
        return ""
    return text.split("T", 1)[0].split(" ", 1)[0]


def _collection_timestamp(run_id: Any) -> str:
    text = _safe_text(run_id).strip()
    if not text:
        return ""
    if ":" in text:
        return text.split(":", 1)[-1]
    return text


def normalize_status(value: Any) -> str:
    text = _safe_text(value).strip().lower()
    return STATUS_ALIASES.get(text, text)


def _normalized_job_text(job: dict[str, Any]) -> str:
    parts = [
        _safe_text(job.get("titulo")),
        _safe_text(job.get("empresa")),
        _safe_text(job.get("origem")),
        _safe_text(job.get("localidade")),
    ]
    return " | ".join(part.strip().lower() for part in parts)


def job_key_for(job: dict[str, Any]) -> str:
    explicit_key = _safe_text(job.get("job_key")).strip()
    if explicit_key:
        return explicit_key

    link = _safe_text(job.get("link")).strip()
    if link:
        return f"link:{link.lower()}"

    codigo = _safe_text(job.get("codigo_vaga")).strip()
    if codigo:
        return f"codigo:{codigo.lower()}"

    digest = hashlib.sha1(_normalized_job_text(job).encode("utf-8")).hexdigest()
    return f"hash:{digest[:16]}"


@dataclass(slots=True)
class PanelAuthConfig:
    auth_disabled: bool = False
    username: str = ""
    password: str = ""
    source: str = "env"


def load_panel_auth_config(
    project_dir: Path = PROJECT_DIR,
    environ: Mapping[str, str] | None = None,
) -> PanelAuthConfig:
    env = environ or os.environ
    if _env_truthy(env.get(AUTH_ENV_DISABLED)):
        return PanelAuthConfig(auth_disabled=True, source="env")

    env_user_present = AUTH_ENV_USER in env
    env_password_present = AUTH_ENV_PASSWORD in env
    if env_user_present or env_password_present:
        return PanelAuthConfig(
            username=_safe_text(env.get(AUTH_ENV_USER)).strip(),
            password=_safe_text(env.get(AUTH_ENV_PASSWORD)).strip(),
            source="env",
        )

    config = _load_yaml_file(project_dir / "config.yaml")
    panel_auth = config.get("panel_auth")
    if isinstance(panel_auth, dict):
        return PanelAuthConfig(
            username=_safe_text(panel_auth.get("username") or panel_auth.get("user")).strip(),
            password=_safe_text(panel_auth.get("password")).strip(),
            source="config",
        )

    return PanelAuthConfig()


def validate_panel_auth_config(auth_config: PanelAuthConfig) -> PanelAuthConfig:
    if auth_config.auth_disabled:
        return auth_config
    if not auth_config.username or not auth_config.password:
        raise RuntimeError(
            "Autenticacao do painel exigida. Defina JOB_HUNTER_PANEL_USER e JOB_HUNTER_PANEL_PASSWORD "
            "ou habilite JOB_HUNTER_PANEL_AUTH_DISABLED=true apenas em desenvolvimento local."
        )
    return auth_config


def check_basic_auth(authorization: str | None, username: str, password: str) -> bool:
    if not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "basic" or not token:
        return False
    try:
        decoded = base64.b64decode(token.encode("ascii"), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False
    if ":" not in decoded:
        return False
    provided_user, provided_password = decoded.split(":", 1)
    return hmac.compare_digest(provided_user, username) and hmac.compare_digest(provided_password, password)


def require_panel_auth(handler: BaseHTTPRequestHandler, auth_config: PanelAuthConfig) -> bool:
    if auth_config.auth_disabled:
        return True
    authorization = handler.headers.get("Authorization")
    if check_basic_auth(authorization, auth_config.username, auth_config.password):
        return True
    handler.send_response(HTTPStatus.UNAUTHORIZED)
    handler.send_header("WWW-Authenticate", 'Basic realm="job-hunter-panel", charset="UTF-8"')
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    body = b"Authentication required\n"
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return False


def latest_csv_file(data_dir: Path = DEFAULT_DATA_DIR) -> Path | None:
    csv_files = sorted(data_dir.glob("jobs_*.csv"), key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return csv_files[0] if csv_files else None


def _read_csv_jobs(csv_file: Path | None) -> list[dict[str, Any]]:
    if not csv_file or not csv_file.exists():
        return []

    jobs: list[dict[str, Any]] = []
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            job = dict(row)
            job["score_bruto"] = _safe_int(job.get("score_bruto"))
            job["score_aderencia"] = _safe_int(job.get("score_aderencia"))
            job["priority_rank"] = _safe_int(job.get("priority_rank"))
            job["confianca_extracao"] = float(job.get("confianca_extracao") or 0)
            job["status_candidatura"] = normalize_status(job.get("status_candidatura") or "não avaliada")
            job.setdefault("observacoes", "")
            job["job_key"] = _safe_text(job.get("job_key")).strip() or job_key_for(job)
            jobs.append(job)
    return jobs


def _load_status_file(status_file: Path = DEFAULT_STATUS_FILE) -> dict[str, Any]:
    if not status_file.exists():
        return {"jobs": {}}
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"jobs": {}}
    if not isinstance(data, dict):
        return {"jobs": {}}
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        data["jobs"] = {}
    return data


def _save_status_file(status_file: Path, payload: dict[str, Any]) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = status_file.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_file.replace(status_file)


def _merge_status(job: dict[str, Any], status_map: dict[str, Any]) -> dict[str, Any]:
    merged = dict(job)
    persisted = status_map.get(job["job_key"]) or {}
    if isinstance(persisted, dict):
        if persisted.get("status_candidatura"):
            merged["status_candidatura"] = normalize_status(persisted["status_candidatura"])
        if persisted.get("observacoes") is not None:
            merged["observacoes"] = persisted.get("observacoes", "")
        if persisted.get("updated_at"):
            merged["status_updated_at"] = persisted["updated_at"]
    merged.setdefault("status_candidatura", "não avaliada")
    merged.setdefault("observacoes", "")
    return merged


def _jobs_with_status(data_dir: Path = DEFAULT_DATA_DIR, status_file: Path = DEFAULT_STATUS_FILE) -> tuple[list[dict[str, Any]], Path | None]:
    csv_file = latest_csv_file(data_dir)
    jobs = _read_csv_jobs(csv_file)
    status_map = _load_status_file(status_file).get("jobs", {})
    merged = [_merge_status(job, status_map) for job in jobs]
    merged.sort(key=lambda job: (-_safe_int(job.get("priority_rank")), -_safe_int(job.get("score_aderencia")), _safe_text(job.get("titulo")).lower()))
    return merged, csv_file


def _counts_by_field(jobs: list[dict[str, Any]], field: str, ordered: list[str] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for job in jobs:
        key = _safe_text(job.get(field)).strip() or "sem informacao"
        counts[key] = counts.get(key, 0) + 1
    if ordered:
        return {key: counts.get(key, 0) for key in ordered}
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def build_summary(data_dir: Path = DEFAULT_DATA_DIR, status_file: Path = DEFAULT_STATUS_FILE) -> dict[str, Any]:
    jobs, csv_file = _jobs_with_status(data_dir, status_file)
    by_classification = _counts_by_field(jobs, "classificacao", ["Alta", "Média", "Baixa", "Ignorar"])
    by_origin = _counts_by_field(jobs, "origem")
    by_status = _counts_by_field(
        jobs,
        "status_candidatura",
        [
            "não avaliada",
            "revisar",
            "candidatura enviada",
            "não enviar",
            "aguardando retorno",
            "entrevista",
            "recusada",
        ],
    )
    today = date.today().isoformat()
    new_today = [job for job in jobs if _date_part(job.get("first_seen_at")) == today]
    new_last_run = [job for job in jobs if _safe_bool(job.get("is_new_in_run"))]
    collection_times = [_collection_timestamp(job.get("collection_run_id")) for job in jobs]
    collection_times = [value for value in collection_times if value]
    last_collection_at = max(collection_times) if collection_times else ""
    return {
        "total": len(jobs),
        "total_new_today": len(new_today),
        "total_new_last_run": len(new_last_run),
        "last_collection_at": last_collection_at,
        "current_snapshot": str(csv_file) if csv_file else "",
        "by_classification": by_classification,
        "by_origin": by_origin,
        "by_status": by_status,
        "data_file": str(csv_file) if csv_file else "",
        "data_file_mtime": datetime.fromtimestamp(csv_file.stat().st_mtime).isoformat(timespec="seconds") if csv_file else "",
        "updated_at": _now_iso(),
    }


def _health_payload(bind_host: str, data_dir: Path = DEFAULT_DATA_DIR, status_file: Path = DEFAULT_STATUS_FILE) -> dict[str, Any]:
    jobs, csv_file = _jobs_with_status(data_dir, status_file)
    return {
        "ok": True,
        "service": "job-hunter-panel",
        "bind": bind_host,
        "data_file": str(csv_file) if csv_file else "",
        "jobs_count": len(jobs),
    }


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _plain_response(handler: BaseHTTPRequestHandler, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


@dataclass(slots=True)
class PanelPaths:
    data_dir: Path = DEFAULT_DATA_DIR
    panel_dir: Path = DEFAULT_PANEL_DIR
    status_file: Path = DEFAULT_STATUS_FILE


class JobPanelHandler(BaseHTTPRequestHandler):
    server_version = "job-hunter-panel/1.0"

    @property
    def paths(self) -> PanelPaths:
        return getattr(self.server, "panel_paths")  # type: ignore[return-value]

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    @property
    def auth_config(self) -> PanelAuthConfig:
        return getattr(self.server, "panel_auth")  # type: ignore[return-value]

    def _serve_asset(self, relative_path: str) -> None:
        asset_path = (self.paths.panel_dir / relative_path).resolve()
        if not asset_path.exists() or self.paths.panel_dir.resolve() not in asset_path.parents and asset_path != self.paths.panel_dir.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }
        _plain_response(self, asset_path.read_bytes(), mime_types.get(asset_path.suffix.lower(), "application/octet-stream"))

    def do_GET(self) -> None:  # noqa: N802
        if not require_panel_auth(self, self.auth_config):
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._serve_asset("index.html")
        if parsed.path == "/app.js":
            return self._serve_asset("app.js")
        if parsed.path == "/style.css":
            return self._serve_asset("style.css")
        if parsed.path == "/api/health":
            bind_host = self.server.server_address[0]
            return _json_response(self, _health_payload(bind_host, self.paths.data_dir, self.paths.status_file))
        if parsed.path == "/api/jobs":
            jobs, _ = _jobs_with_status(self.paths.data_dir, self.paths.status_file)
            limit_value = parse_qs(parsed.query).get("limit", [""])[0]
            limit = _safe_int(limit_value, default=0)
            if limit > 0:
                jobs = jobs[:limit]
            return _json_response(self, {"jobs": jobs, "count": len(jobs), "updated_at": _now_iso()})
        if parsed.path == "/api/summary":
            return _json_response(self, build_summary(self.paths.data_dir, self.paths.status_file))
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not require_panel_auth(self, self.auth_config):
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/job-status":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "JSON invalido")
            return

        job_key = _safe_text(payload.get("job_key")).strip()
        status = normalize_status(payload.get("status_candidatura") or "não avaliada")
        if status not in STATUS_OPTIONS:
            self.send_error(HTTPStatus.BAD_REQUEST, "Status invalido")
            return
        notes = _safe_text(payload.get("observacoes"))
        if not job_key:
            self.send_error(HTTPStatus.BAD_REQUEST, "job_key obrigatoria")
            return

        current = _load_status_file(self.paths.status_file)
        jobs = current.setdefault("jobs", {})
        jobs[job_key] = {
            "status_candidatura": status,
            "observacoes": notes,
            "updated_at": _now_iso(),
        }
        _save_status_file(self.paths.status_file, current)
        _json_response(self, {"ok": True, "job_key": job_key, "status_candidatura": status, "observacoes": notes})


def create_server(
    host: str,
    port: int,
    data_dir: Path = DEFAULT_DATA_DIR,
    panel_dir: Path = DEFAULT_PANEL_DIR,
    status_file: Path = DEFAULT_STATUS_FILE,
    auth_config: PanelAuthConfig | None = None,
) -> ThreadingHTTPServer:
    resolved_auth = validate_panel_auth_config(auth_config or load_panel_auth_config())
    server = ThreadingHTTPServer((host, port), JobPanelHandler)
    server.panel_paths = PanelPaths(data_dir=data_dir, panel_dir=panel_dir, status_file=status_file)  # type: ignore[attr-defined]
    server.panel_auth = resolved_auth  # type: ignore[attr-defined]
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Painel local do job-hunter")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--panel-dir", default=str(DEFAULT_PANEL_DIR))
    parser.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    args = parser.parse_args()

    try:
        auth_config = load_panel_auth_config()
        if auth_config.auth_disabled:
            print("AVISO: autenticacao do painel desativada explicitamente para desenvolvimento local.")
        else:
            validate_panel_auth_config(auth_config)
    except RuntimeError as exc:
        print(f"Erro de configuracao de autenticacao: {exc}")
        return 1

    server = create_server(
        args.host,
        args.port,
        Path(args.data_dir),
        Path(args.panel_dir),
        Path(args.status_file),
        auth_config=auth_config,
    )
    print(f"job-hunter panel ouvindo em http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
