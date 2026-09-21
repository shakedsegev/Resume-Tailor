from pathlib import Path
from fastapi.testclient import TestClient
from src.ats_analyzer import analyze_resume_format, ATSFormatReport
from src.web_app import app

client = TestClient(app)
TEMPLATE_PATH = Path("template.pptx") if Path("template.pptx").exists() else Path("Shaked Segev - CV.pptx")


def test_analyze_pptx_format(tmp_path):
    """Verifies that PPTX presentation templates are flagged for ATS layout risks."""
    if TEMPLATE_PATH.exists():
        report = analyze_resume_format(TEMPLATE_PATH)
    else:
        dummy_pptx = tmp_path / "resume.pptx"
        dummy_pptx.write_bytes(b"PK\x03\x04")
        report = analyze_resume_format(dummy_pptx)

    assert isinstance(report, ATSFormatReport)
    assert report.ats_score < 80
    assert report.needs_format_change is True
    assert "Canva" in report.layout_type or "Presentation" in report.layout_type
    assert len(report.risks) >= 2
    assert report.suggested_strategy == "ats_optimized"


def test_analyze_plain_text(tmp_path):
    """Verifies that plain text formats pass as ATS compliant."""
    txt_file = tmp_path / "resume.txt"
    txt_file.write_text("John Doe\nExperience\nSoftware Engineer\nEducation\nSkills\n", encoding="utf-8")

    report = analyze_resume_format(txt_file)
    assert report.is_ats_compliant is True
    assert report.needs_format_change is False
    assert report.ats_score >= 90


def test_api_analyze_format_endpoint(tmp_path):
    """Verifies that the /api/analyze-format endpoint inspects uploaded files correctly."""
    txt_file = tmp_path / "test_cv.txt"
    txt_file.write_text("Candidate Resume Content\nExperience\nEducation\nSkills", encoding="utf-8")

    with open(txt_file, "rb") as f:
        res = client.post("/api/analyze-format", files={"resume_file": ("test_cv.txt", f, "text/plain")})

    assert res.status_code == 200
    data = res.json()
    assert "ats_score" in data
    assert "needs_format_change" in data
    assert "layout_type" in data
    assert "risks" in data
    assert "recommendations" in data
    assert "suggested_strategy" in data


def test_pdf_always_suggests_ats_optimized(tmp_path):
    """Verifies that PDF files always report ats_optimized since preserve_design is strictly for PPTX."""
    from src.ats_analyzer import analyze_pdf_format
    dummy_pdf = tmp_path / "resume.pdf"
    # Create a minimal valid PDF
    dummy_pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n163\n%%EOF"
    )
    report = analyze_pdf_format(dummy_pdf)
    assert report.suggested_strategy == "ats_optimized"


def test_docx_always_suggests_ats_optimized(tmp_path):
    """Verifies that DOCX files always report ats_optimized."""
    from src.ats_analyzer import analyze_docx_format
    import docx
    doc = docx.Document()
    doc.add_paragraph("Candidate Resume\nExperience\nEducation\nSkills")
    docx_file = tmp_path / "resume.docx"
    doc.save(str(docx_file))

    report = analyze_docx_format(docx_file)
    assert report.suggested_strategy == "ats_optimized"

