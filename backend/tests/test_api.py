import time

from tests.conftest import make_pdf


def test_health(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200


def test_config_hides_key(client):
    body = client.get("/api/v1/config").json()
    assert body["llm_configured"] is True
    assert "test-key" not in str(body)


def test_rejects_non_pdf(client):
    r = client.post("/api/v1/analyses", data={"doc_type": "filing", "mode": "local"},
                    files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415


def test_rejects_oversize(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    r = client.post("/api/v1/analyses", data={"doc_type": "filing", "mode": "local"},
                    files={"file": ("x.pdf", b"%PDF-1.4" + b"0" * 100, "application/pdf")})
    assert r.status_code == 413


def test_filing_local_job_completes(client):
    pdf = make_pdf("There is substantial doubt about going concern. No assurance of results.")
    r = client.post("/api/v1/analyses", data={"doc_type": "filing", "mode": "local"},
                    files={"file": ("f.pdf", pdf, "application/pdf")})
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(50):
        job = client.get(f"/api/v1/analyses/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "completed", job
    assert job["result"]["red_flags"]["score"] < 100


def test_unknown_job_404(client):
    assert client.get("/api/v1/analyses/nope").status_code == 404
