"""
Resume-Tailor Web Application.
FastAPI backend providing a universal web interface to:
1. Ingest or build candidate ground-truth master profiles (via file upload or interactive questionnaire).
2. Substantively tailor resumes to target Job Descriptions with Gemini AI (Zero Hallucinations).
3. Preserve original designs (Canva/PPTX layout protection or universal modern ATS vector PDF).
"""

import os
import json
import uuid
import re
from pathlib import Path
from typing import Optional, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

import sys
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.universal_parser import extract_text_from_file
from src.universal_ai import parse_raw_resume_to_schema, tailor_universal_resume
from src.universal_pdf_builder import generate_universal_resume_pdf
from src.profile_manager import convert_document_to_profile, build_profile_from_questionnaire
from src.sample_data import GENERIC_SAMPLE_PROFILE, GENERIC_SAMPLE_JD
from src.models import CandidateProfile

app = FastAPI(
    title="Resume-Tailor 🎯",
    description="Universal AI-Powered Design-Preserving Resume Customizer",
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
    """Returns a realistic sample tech job description for instant testing."""
    return {"sample_jd": GENERIC_SAMPLE_JD}


@app.get("/api/sample-profile")
async def get_sample_profile():
    """Returns a realistic candidate master profile for testing."""
    return GENERIC_SAMPLE_PROFILE


@app.post("/api/profile/upload")
async def upload_profile_endpoint(
    profile_file: Optional[UploadFile] = File(None),
    notes_text: Optional[str] = Form(None),
):
    """
    Parses any background document (notes, markdown, text, PDF, DOCX, JSON)
    and converts it into a standardized CandidateProfile ground truth.
    """
    raw_content = ""
    if profile_file:
        file_ext = Path(profile_file.filename or "notes.txt").suffix
        dest_path = UPLOADS_DIR / f"profile_{uuid.uuid4().hex[:8]}{file_ext}"
        content_bytes = await profile_file.read()
        dest_path.write_bytes(content_bytes)

        if file_ext.lower() == ".json":
            try:
                data = json.loads(content_bytes.decode("utf-8"))
                profile = CandidateProfile.model_validate(data)
                return JSONResponse(content=profile.model_dump())
            except Exception:
                pass

        raw_content = extract_text_from_file(dest_path)
    elif notes_text and notes_text.strip():
        raw_content = notes_text.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide a profile document or paste background notes."
        )

    try:
        profile = convert_document_to_profile(raw_content)
        return JSONResponse(content=profile.model_dump())
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert document into master profile: {err}"
        )


@app.post("/api/profile/questionnaire")
async def questionnaire_profile_endpoint(payload: dict[str, Any] = Body(...)):
    """
    Builds a structured CandidateProfile from questionnaire wizard responses.
    """
    if not payload:
        raise HTTPException(status_code=400, detail="Empty questionnaire data.")
    try:
        profile = build_profile_from_questionnaire(payload)
        return JSONResponse(content=profile.model_dump())
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate profile from questionnaire: {err}"
        )


@app.post("/api/tailor")
async def tailor_resume_endpoint(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
    profile_json: Optional[str] = Form(None),
):
    """
    Universal Tailoring Pipeline:
    - Preserves design when a presentation (PPTX) is uploaded.
    - Compiles a vector PDF preserving native styles, fonts, and badge graphics.
    - Integrates unlisted context from the master profile if provided.
    """
    if not jd_text or not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    if not resume_file:
        raise HTTPException(status_code=400, detail="Please upload your resume file.")

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    file_ext = Path(resume_file.filename or "resume.pdf").suffix.lower()
    dest_path = UPLOADS_DIR / f"{job_id}{file_ext}"
    contents = await resume_file.read()
    dest_path.write_bytes(contents)

    # Load master profile context if provided
    profile_dict = None
    if profile_json:
        try:
            profile_dict = json.loads(profile_json)
        except Exception:
            profile_dict = None

    # 1. Design-Preserving PPTX Tailoring
    if file_ext in [".pptx", ".ppt"]:
        try:
            from src.parser import extract_resume_sections
            from src.ai_engine import tailor_full_resume
            from src.pdf_builder import build_full_tailored_resume

            resume_data = extract_resume_sections(dest_path)
            tailor_profile = profile_dict or resume_data

            tailored_res = tailor_full_resume(
                profile=tailor_profile,
                job_description=jd_text.strip(),
                original_data=resume_data,
            )

            base_filename = f"{job_id}_Tailored_Resume"
            pptx_out, pdf_out = build_full_tailored_resume(
                template_pptx=dest_path,
                output_dir=OUTPUTS_DIR,
                tailored=tailored_res,
                base_name=base_filename,
            )

            # Build interactive changes view with full resume and green marker highlights
            from src.interactive_diff import build_interactive_pptx_diff_html
            diff_path = OUTPUTS_DIR / f"{base_filename}_diff.html"
            build_interactive_pptx_diff_html(
                tailored_res=tailored_res,
                original_data=resume_data,
                output_html_path=diff_path,
                candidate_name=profile_dict.get("name", "") if profile_dict else "",
            )

            return JSONResponse(
                content={
                    "status": "success",
                    "job_id": job_id,
                    "filename_base": base_filename,
                    "fit_analysis": tailored_res.fit_analysis.model_dump(),
                    "preview_url": f"/api/preview/{base_filename}",
                    "diff_url": f"/api/diff/{base_filename}",
                    "download_url": f"/api/download/{base_filename}",
                }
            )
        except Exception as err:
            # If template-specific layout parsing encounters an unexpected layout,
            # log and proceed to universal fallback
            print(f"PPTX design-preserving engine notice: {err}. Falling back to universal builder.")

    # 2. Universal Parsing & Tailoring for PDF, DOCX, or other formats
    raw_text = extract_text_from_file(dest_path)
    if not raw_text.strip():
        raise HTTPException(
            status_code=422, detail="Could not extract readable text from uploaded document."
        )

    parsed_resume = parse_raw_resume_to_schema(raw_text)
    tailored_output = tailor_universal_resume(
        resume=parsed_resume,
        job_description=jd_text.strip(),
        profile=profile_dict,
    )

    candidate_name = tailored_output.tailored_resume.contact.name or "Tailored"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
    base_filename = f"{job_id}_{safe_name}_Tailored_CV"

    html_path, pdf_path = generate_universal_resume_pdf(
        resume=tailored_output.tailored_resume,
        output_dir=OUTPUTS_DIR,
        base_name=base_filename,
    )

    # Build interactive changes view with complete resume and green marker highlights
    from src.interactive_diff import build_interactive_resume_diff_html
    diff_path = OUTPUTS_DIR / f"{base_filename}_diff.html"
    build_interactive_resume_diff_html(
        resume=tailored_output.tailored_resume,
        changes_log=getattr(tailored_output, "changes_log", []),
        output_html_path=diff_path,
        original_resume=parsed_resume,
    )

    return JSONResponse(
        content={
            "status": "success",
            "job_id": job_id,
            "filename_base": base_filename,
            "fit_analysis": tailored_output.fit_analysis.model_dump(),
            "preview_url": f"/api/preview/{base_filename}",
            "diff_url": f"/api/diff/{base_filename}",
            "download_url": f"/api/download/{base_filename}",
        }
    )


@app.get("/api/diff/{base_filename}")
async def preview_diff(base_filename: str):
    """Renders the interactive HTML diff with green marker highlights and hover tooltips."""
    safe_name = Path(base_filename).name
    diff_path = OUTPUTS_DIR / f"{safe_name}_diff.html"
    if not diff_path.exists():
        raise HTTPException(status_code=404, detail="Interactive diff document not found.")
    return HTMLResponse(content=diff_path.read_text(encoding="utf-8"))


@app.get("/api/preview/{base_filename}")
async def preview_resume(base_filename: str):
    """Renders the actual vector PDF inline in the browser preview frame."""
    safe_name = Path(base_filename).name
    pdf_path = OUTPUTS_DIR / f"{safe_name}.pdf"
    if pdf_path.exists():
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=preview.pdf"},
        )

    html_path = OUTPUTS_DIR / f"{safe_name}.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail="Preview document not found.")


@app.get("/api/download/{base_filename}")
async def download_pdf(base_filename: str):
    """Downloads the compiled vector PDF."""
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
    """Starts the Uvicorn web server and optionally opens browser."""
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
