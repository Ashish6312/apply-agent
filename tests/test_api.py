from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body
    assert "model_name" in body


def test_analyze_rejects_empty_job_description():
    # A tiny valid PDF is enough - the empty job description should be
    # rejected before any parsing/LLM work happens.
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Python Developer")
    pdf_bytes = document.tobytes()
    document.close()

    response = client.post(
        "/analyze",
        files={"resume": ("resume.pdf", pdf_bytes, "application/pdf")},
        data={"job_description": "   "},
    )
    assert response.status_code == 400


def test_analyze_rejects_non_pdf_content_type():
    response = client.post(
        "/analyze",
        files={"resume": ("resume.txt", b"hello", "text/plain")},
        data={"job_description": "We need a Python developer."},
    )
    assert response.status_code == 400
