"""
Resume-Tailor Web Application.
FastAPI backend providing a modern web interface for uploading any resume,
tailoring it against any Job Description with Gemini AI, and exporting ready-to-submit vector PDFs.
"""

import os
import uuid
import re
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to sys.path
import sys
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.universal_parser import extract_text_from_file
from src.universal_ai import parse_raw_resume_to_schema, tailor_universal_resume
from src.universal_pdf_builder import generate_universal_resume_pdf

app = FastAPI(
    title="Resume-Tailor 🎯",
    description="Universal AI-Powered 1-Page Resume Customizer",
    version="2.0.0",
)

OUTPUTS_DIR = project_root / "outputs"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
TEMPLATES_DIR = project_root / "templates"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the single-page application frontend."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend template not found.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/api/sample-jd")
async def get_sample_jd():
    """Returns a realistic tech job description for 1-click testing."""
    sample = (
        "Backend Software Engineering Student position at high-performance cloud team.\n\n"
        "Requirements:\n"
        "- Currently pursuing B.Sc. in Computer Science or related degree.\n"
        "- Proficiency in Python, C++, or Java.\n"
        "- Solid grasp of multithreading, concurrency, socket networking, and memory management.\n"
        "- Experience working in Linux/Docker environments.\n"
        "- Strong problem-solving mindset, clean code principles, and passion for distributed systems.\n"
        "- Bonus: Familiarity with CI/CD, TypeScript, or low-latency communication protocols."
    )
    return {"sample_jd": sample}


@app.post("/api/tailor")
async def tailor_resume_endpoint(
    resume_file: Optional[UploadFile] = File(None),
    use_demo_resume: Optional[str] = Form(None),
    jd_text: str = Form(...),
):
    """
    Universal tailoring endpoint:
    1. Reads uploaded resume (PDF, DOCX, PPTX, TXT) or demo template.
    2. Parses raw text into standardized UniversalResume.
    3. Tailors all sections to the JD via Gemini AI without hallucinations.
    4. Compiles an ATS-optimized, designer-quality vector PDF.
    """
    if not jd_text or not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    file_to_parse: Optional[Path] = None

    if use_demo_resume and use_demo_resume.lower() == "true":
        demo_path = project_root / "Shaked Segev - CV.pptx"
        if not demo_path.exists():
            raise HTTPException(status_code=404, detail="Demo resume template not found.")
        file_to_parse = demo_path
    elif resume_file:
        file_ext = Path(resume_file.filename or "resume.pdf").suffix
        dest_path = UPLOADS_DIR / f"{job_id}{file_ext}"
        contents = await resume_file.read()
        dest_path.write_bytes(contents)
        file_to_parse = dest_path
    else:
        raise HTTPException(status_code=400, detail="Please provide a resume file.")

    # 1. Extract raw text
    try:
        raw_text = extract_text_from_file(file_to_parse)
    except Exception as err:
        raise HTTPException(
            status_code=422, detail=f"Failed to extract text from file: {err}"
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=422, detail="No readable text could be extracted from the uploaded document."
        )

    # 2. Parse into UniversalResume schema with AI
    try:
        parsed_resume = parse_raw_resume_to_schema(raw_text)
    except Exception as err:
        raise HTTPException(
            status_code=502, detail=f"AI Resume Parsing failed: {err}"
        )

    # 3. Substantively tailor with Gemini AI
    try:
        tailored_output = tailor_universal_resume(parsed_resume, jd_text.strip())
    except Exception as err:
        raise HTTPException(
            status_code=502, detail=f"AI Tailoring failed: {err}"
        )

    # 4. Compile HTML & Vector PDF
    try:
        candidate_name = tailored_output.tailored_resume.contact.name or "Tailored"
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
        base_filename = f"{job_id}_{safe_name}_Tailored_CV"

        html_path, pdf_path = generate_universal_resume_pdf(
            resume=tailored_output.tailored_resume,
            output_dir=OUTPUTS_DIR,
            base_name=base_filename,
        )
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"PDF rendering failed: {err}"
        )

    return JSONResponse(
        content={
            "status": "success",
            "job_id": job_id,
            "filename_base": base_filename,
            "fit_analysis": tailored_output.fit_analysis.model_dump(),
            "preview_url": f"/api/preview/{base_filename}",
            "download_url": f"/api/download/{base_filename}",
            "download_html_url": f"/api/download_html/{base_filename}",
        }
    )


@app.get("/api/preview/{base_filename}")
async def preview_resume(base_filename: str):
    """Renders the styled HTML resume inside the browser preview frame."""
    safe_name = Path(base_filename).name
    html_path = OUTPUTS_DIR / f"{safe_name}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Preview document not found.")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/download/{base_filename}")
async def download_pdf(base_filename: str):
    """Downloads the compiled high-resolution vector PDF."""
    safe_name = Path(base_filename).name
    pdf_path = OUTPUTS_DIR / f"{safe_name}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found.")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{safe_name}.pdf",
    )


@app.get("/api/download_html/{base_filename}")
async def download_html(base_filename: str):
    """Downloads the standalone HTML resume."""
    safe_name = Path(base_filename).name
    html_path = OUTPUTS_DIR / f"{safe_name}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="HTML file not found.")
    return FileResponse(
        path=html_path,
        media_type="text/html",
        filename=f"{safe_name}.html",
    )


def start_server(host: str = "127.0.0.1", port: int = 8000, auto_open: bool = True):
    """Starts the Uvicorn web server and opens browser."""
    import uvicorn
    import webbrowser
    import threading

    url = f"http://{host}:{port}"

    if auto_open:
        def open_browser():
            import time
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

    print(f"\n🚀 Resume-Tailor Web App is running at: {url}")
    print("Press Ctrl+C to stop the server.\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
