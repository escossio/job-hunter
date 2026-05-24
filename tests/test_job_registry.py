from __future__ import annotations

import pytest

from job_registry import JobConfigError, collect_configured_jobs, validate_configured_jobs


def _job_entry(**overrides):
    job = {
        "id": "analista-infra-exemplo",
        "title": "Analista de Infraestrutura",
        "company": "Empresa Exemplo A",
        "platform": "exemplo",
        "url": "https://example.com/vaga/123",
        "enabled": True,
        "tags": ["infraestrutura", "suporte", "redes"],
        "notes": "Vaga ficticia para exemplo.",
    }
    job.update(overrides)
    return job


def test_collect_configured_jobs_accepts_valid_entry_and_returns_expected_fields():
    jobs, metadata = collect_configured_jobs({"jobs": [_job_entry()]})

    assert metadata["raw_count"] == 1
    assert metadata["final_count"] == 1
    assert len(jobs) == 1

    job = jobs[0]
    assert job["job_key"] == "job:analista-infra-exemplo"
    assert job["origem"] == "exemplo"
    assert job["titulo"] == "Analista de Infraestrutura"
    assert job["empresa"] == "Empresa Exemplo A"
    assert job["link"] == "https://example.com/vaga/123"
    assert job["codigo_vaga"] == "analista-infra-exemplo"
    assert job["tags"] == ["infraestrutura", "suporte", "redes"]
    assert job["descricao"] == "Vaga ficticia para exemplo."


def test_job_key_is_stable_and_based_on_id():
    jobs, _ = collect_configured_jobs({"jobs": [_job_entry(id="analista-infra-exemplo", url="https://example.com/vaga/456")]})

    assert jobs[0]["job_key"] == "job:analista-infra-exemplo"


def test_enabled_false_is_ignored():
    jobs, metadata = collect_configured_jobs({"jobs": [_job_entry(enabled=False)]})

    assert jobs == []
    assert metadata["raw_count"] == 0
    assert metadata["final_count"] == 0


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"url": "https://example.com/vaga/123"}, "id"),
        ({"id": "vaga-sem-url"}, "url"),
    ],
)
def test_missing_required_fields_raise_clear_error(entry, message):
    with pytest.raises(JobConfigError, match=message):
        validate_configured_jobs({"jobs": [entry]})


def test_duplicate_ids_raise_error():
    jobs = [
        _job_entry(url="https://example.com/vaga/123"),
        _job_entry(url="https://example.com/vaga/456"),
    ]

    with pytest.raises(JobConfigError, match="duplicado"):
        validate_configured_jobs({"jobs": jobs})


def test_optional_fields_can_be_missing_without_breaking_validation():
    jobs, metadata = collect_configured_jobs(
        {
            "jobs": [
                {
                    "id": "sre-exemplo",
                    "title": "Site Reliability Engineer",
                    "company": "Empresa Exemplo B",
                    "platform": "exemplo",
                    "url": "https://example.com/vaga/456",
                    "enabled": True,
                }
            ]
        }
    )

    assert metadata["raw_count"] == 1
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_key"] == "job:sre-exemplo"
    assert job["tags"] == []
    assert job["descricao"] == ""
    assert job["busca_keywords"] == ""
