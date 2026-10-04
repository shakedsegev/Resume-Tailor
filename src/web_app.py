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
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
import asyncio

import sys
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database import (
    upsert_user,
    create_session,
    get_user_by_session,
    delete_session,
    get_user_profile,
    save_user_profile,
    set_user_profile_active,
    delete_user_profile,
    get_user_base_resume,
    save_user_base_resume,
    set_user_base_resume_active,
    delete_user_base_resume,
    check_rate_limit,
    increment_daily_usage,
    check_deep_boost_limit,
    increment_deep_boost_usage,
    USER_RESUMES_DIR,
    verify_admin_secret_key,
    create_admin_session,
    list_all_users_with_daily_usage,
    list_active_guests_with_daily_usage,
    admin_reset_daily_usage,
    admin_add_daily_usage,
    admin_adjust_tailors,
    admin_reset_deep_boost,
    admin_adjust_deep_boost,
    get_system_stats,
    ADMIN_GOOGLE_ID,
    link_user_ip,
    record_tailor_run,
)

# pyrefly: ignore [missing-import]
from src.universal_parser import extract_text_from_file
# pyrefly: ignore [missing-import]
from src.universal_ai import parse_raw_resume_to_schema, tailor_universal_resume
# pyrefly: ignore [missing-import]
from src.universal_pdf_builder import generate_universal_resume_pdf
# pyrefly: ignore [missing-import]
from src.profile_manager import convert_document_to_profile, build_profile_from_questionnaire
# pyrefly: ignore [missing-import]
from src.ats_analyzer import analyze_resume_format, ATSFormatReport
# pyrefly: ignore [missing-import]
from src.sample_data import GENERIC_SAMPLE_PROFILE, GENERIC_SAMPLE_JD
# pyrefly: ignore [missing-import]
from src.models import CandidateProfile
# pyrefly: ignore [missing-import]
from src.universal_models import (
    UniversalResume,
    FitAnalysis,
    sanitize_universal_resume,
    compute_multi_metric_fit,
)

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "1057142254812-2pfj4d8dk8nsmfpm0k8pkg5043bpade1.apps.googleusercontent.com",
)

_google_auth_session = requests.Session()
_google_auth_request = google_requests.Request(session=_google_auth_session)


def get_session_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    token = request.headers.get("x-session-token")
    if token:
        return token.strip()
    return request.cookies.get("session_token")


def get_current_user_optional(request: Request) -> Optional[dict]:
    token = get_session_token_from_request(request)
    if not token:
        return None
    return get_user_by_session(token)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def get_client_device_id(request: Request) -> str:
    """
    Retrieves the unique device ID from 'X-Device-Id' header or 'rt_device_id' cookie.
    Falls back to sanitized client IP if not available.
    """
    dev_id = request.headers.get("x-device-id") or request.cookies.get("rt_device_id")
    if dev_id:
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "", str(dev_id).strip())
        if 4 <= len(clean) <= 64:
            return clean
    client_ip = get_client_ip(request)
    return f"ip_{client_ip.replace('.', '_').replace(':', '_')}"

app = FastAPI(
    title="Resume-Tailor 🎯",
    description="Universal AI-Powered Design-Preserving Resume Customizer",
    version="2.0.0",
)


def _prewarm_google_certs():
    try:
        _google_auth_session.get("https://www.googleapis.com/oauth2/v3/certs", timeout=4)
    except Exception:
        pass


@app.on_event("startup")
async def on_app_startup():
    asyncio.create_task(asyncio.to_thread(_prewarm_google_certs))

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


class GoogleAuthPayload(BaseModel):
    credential: str


class ToggleActivePayload(BaseModel):
    is_active: bool


class AdminLoginPayload(BaseModel):
    secret_key: str


class AdminIdentifierPayload(BaseModel):
    identifier: str


class AdminAddTailorsPayload(BaseModel):
    identifier: str
    count: int = 1


class AdminResetDeepBoostPayload(BaseModel):
    google_id: str


class AdminAdjustDeepBoostPayload(BaseModel):
    google_id: str
    count: int = 1


def require_admin_user(request: Request) -> dict[str, Any]:
    user = get_current_user_optional(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Admin access required."
        )
    return user


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_dashboard():
    """Serves the dedicated Admin Dashboard interface."""
    admin_file = TEMPLATES_DIR / "admin.html"
    if not admin_file.exists():
        raise HTTPException(status_code=404, detail="Admin template not found.")
    return HTMLResponse(content=admin_file.read_text(encoding="utf-8"))


@app.post("/api/admin/login")
async def admin_login(payload: AdminLoginPayload):
    """Authenticates admin using secret access key."""
    if not verify_admin_secret_key(payload.secret_key):
        raise HTTPException(status_code=401, detail="Invalid admin secret access key.")
    token, user = create_admin_session()
    return JSONResponse(
        content={
            "status": "success",
            "session_token": token,
            "user": user,
            "message": "Admin session authenticated successfully."
        }
    )


@app.get("/api/admin/users")
async def admin_get_users(request: Request):
    """Returns all registered users, active guests, and system KPIs for the admin dashboard."""
    require_admin_user(request)
    users = list_all_users_with_daily_usage()
    guests = list_active_guests_with_daily_usage()
    stats = get_system_stats()
    return JSONResponse(
        content={
            "status": "success",
            "users": users,
            "guests": guests,
            "stats": stats,
        }
    )


@app.post("/api/admin/user/reset-tailors")
async def admin_user_reset_tailors(payload: AdminIdentifierPayload, request: Request):
    """Resets daily tailoring count for a user or guest IP."""
    require_admin_user(request)
    admin_reset_daily_usage(payload.identifier)
    return JSONResponse(
        content={
            "status": "success",
            "message": f"Daily tailoring quota reset for {payload.identifier}."
        }
    )


@app.post("/api/admin/user/add-tailors")
async def admin_user_add_tailors(payload: AdminAddTailorsPayload, request: Request):
    """Adds bonus tailoring runs for a user or guest IP."""
    require_admin_user(request)
    new_count = admin_add_daily_usage(payload.identifier, payload.count)
    return JSONResponse(
        content={
            "status": "success",
            "message": f"Added {payload.count} tailors for {payload.identifier} (new usage: {new_count})."
        }
    )


@app.post("/api/admin/user/reset-deep-boost")
async def admin_user_reset_deep_boost(payload: AdminResetDeepBoostPayload, request: Request):
    """Unlocks another Deep Quality Boost for a registered user."""
    require_admin_user(request)
    admin_reset_deep_boost(payload.google_id)
    return JSONResponse(
        content={
            "status": "success",
            "message": f"Deep Quality Boost unlocked for user {payload.google_id}."
        }
    )


@app.post("/api/admin/user/adjust-deep-boost")
async def admin_user_adjust_deep_boost(payload: AdminAdjustDeepBoostPayload, request: Request):
    """Adjusts (adds or subtracts) bonus Deep Quality Boosts for a registered user."""
    require_admin_user(request)
    new_bonus = admin_adjust_deep_boost(payload.google_id, payload.count)
    return JSONResponse(
        content={
            "status": "success",
            "message": f"Adjusted Deep Quality Boost by {payload.count} for user {payload.google_id} (bonus: {new_bonus})."
        }
    )


@app.get("/api/auth/config")
async def get_auth_config():
    """Returns the Google Client ID configured for this instance."""
    return {"google_client_id": GOOGLE_CLIENT_ID}


@app.post("/api/auth/google")
async def auth_google(payload: GoogleAuthPayload, request: Request):
    """
    Verifies Google ID token from Google Identity Services and creates a persistent user session.
    """
    try:
        id_info = await asyncio.to_thread(
            id_token.verify_oauth2_token,
            payload.credential,
            _google_auth_request,
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
        google_id = id_info.get("sub")
        email = id_info.get("email")
        name = id_info.get("name")
        picture = id_info.get("picture")

        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Invalid Google token payload.")

        user = upsert_user(google_id, email, name, picture)
        session_token = create_session(google_id)

        saved_profile = get_user_profile(google_id)
        saved_base = get_user_base_resume(google_id)
        client_ip = get_client_ip(request)
        device_id = get_client_device_id(request)
        link_user_ip(google_id, client_ip)
        limit_info = check_rate_limit(f"user:{google_id}", is_authenticated=True, client_ip=client_ip)

        resp = JSONResponse(
            content={
                "status": "success",
                "session_token": session_token,
                "user": user,
                "rate_limit": limit_info,
                "has_profile": saved_profile is not None,
                "profile": saved_profile.get("profile") if saved_profile else None,
                "profile_is_active": saved_profile.get("is_active", True) if saved_profile else False,
                "has_base_resume": saved_base is not None,
                "base_resume": {
                    "filename": saved_base["filename"],
                    "is_active": saved_base["is_active"],
                    "file_ext": saved_base["file_ext"],
                } if saved_base else None,
            }
        )
        if "rt_device_id" not in request.cookies and device_id and not device_id.startswith("ip_"):
            resp.set_cookie("rt_device_id", device_id, max_age=31536000, httponly=False, samesite="lax")
        return resp
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Google authentication failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error during authentication: {e}")


@app.get("/api/auth/me")
async def get_current_user_info(request: Request):
    """
    Returns the current user profile, active base resume, and rate limit status.
    """
    user = get_current_user_optional(request)
    client_ip = get_client_ip(request)
    device_id = get_client_device_id(request)
    if user:
        if not user.get("is_admin"):
            link_user_ip(user["google_id"], client_ip)
        identifier = f"user:{user['google_id']}"
        limit_info = check_rate_limit(identifier, is_authenticated=True, client_ip=client_ip)
        saved_profile = get_user_profile(user["google_id"])
        saved_base = get_user_base_resume(user["google_id"])
        resp = JSONResponse(
            content={
                "is_authenticated": True,
                "user": user,
                "rate_limit": limit_info,
                "has_profile": saved_profile is not None,
                "profile": saved_profile.get("profile") if saved_profile else None,
                "profile_is_active": saved_profile.get("is_active", True) if saved_profile else False,
                "has_base_resume": saved_base is not None,
                "base_resume": {
                    "filename": saved_base["filename"],
                    "is_active": saved_base["is_active"],
                    "file_ext": saved_base["file_ext"],
                } if saved_base else None,
            }
        )
    else:
        identifier = f"dev:{device_id}"
        limit_info = check_rate_limit(identifier, is_authenticated=False)
        resp = JSONResponse(
            content={
                "is_authenticated": False,
                "rate_limit": limit_info,
                "has_profile": False,
                "profile": None,
                "profile_is_active": False,
                "has_base_resume": False,
                "base_resume": None,
            }
        )
    if "rt_device_id" not in request.cookies and device_id and not device_id.startswith("ip_"):
        resp.set_cookie("rt_device_id", device_id, max_age=31536000, httponly=False, samesite="lax")
    return resp


@app.post("/api/auth/logout")
async def logout_endpoint(request: Request):
    token = get_session_token_from_request(request)
    if token:
        delete_session(token)
    return JSONResponse(content={"status": "logged_out"})


# ---------------- USER PROFILE PERSISTENCE ----------------

@app.get("/api/user/profile")
async def get_user_profile_endpoint(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    prof = get_user_profile(user["google_id"])
    return JSONResponse(content=prof or {"profile": None, "is_active": False})


@app.post("/api/user/profile")
async def save_user_profile_endpoint(request: Request, payload: dict = Body(...)):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    profile_dict = payload.get("profile") if "profile" in payload else payload
    is_active = payload.get("is_active", True)
    save_user_profile(user["google_id"], profile_dict, is_active=is_active)
    return JSONResponse(content={"status": "saved", "is_active": is_active})


@app.post("/api/user/profile/toggle")
async def toggle_user_profile_endpoint(request: Request, payload: ToggleActivePayload):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    set_user_profile_active(user["google_id"], payload.is_active)
    return JSONResponse(content={"status": "updated", "is_active": payload.is_active})


@app.delete("/api/user/profile")
async def delete_user_profile_endpoint(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    delete_user_profile(user["google_id"])
    return JSONResponse(content={"status": "deleted"})


# ---------------- USER BASE RESUME PERSISTENCE ----------------

@app.get("/api/user/base-resume")
async def get_user_base_resume_endpoint(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    base = get_user_base_resume(user["google_id"])
    if not base:
        return JSONResponse(content={"has_base_resume": False})
    return JSONResponse(
        content={
            "has_base_resume": True,
            "filename": base["filename"],
            "file_ext": base["file_ext"],
            "is_active": base["is_active"],
            "updated_at": base["updated_at"],
        }
    )


@app.post("/api/user/base-resume")
async def upload_user_base_resume_endpoint(
    request: Request,
    base_file: UploadFile = File(...),
):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required to save base resume.")

    filename = base_file.filename or "base_resume.pdf"
    file_ext = Path(filename).suffix.lower()
    if file_ext not in [".pdf", ".pptx", ".ppt", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Supported formats: PDF, PPTX, DOCX, TXT")

    dest_path = USER_RESUMES_DIR / f"{user['google_id']}_base{file_ext}"
    content_bytes = await base_file.read()
    dest_path.write_bytes(content_bytes)

    save_user_base_resume(
        google_id=user["google_id"],
        filename=filename,
        file_path=str(dest_path),
        file_ext=file_ext,
        is_active=True,
        file_bytes=content_bytes,
    )
    return JSONResponse(
        content={
            "status": "success",
            "filename": filename,
            "file_ext": file_ext,
            "is_active": True,
        }
    )


@app.post("/api/user/base-resume/toggle")
async def toggle_user_base_resume_endpoint(request: Request, payload: ToggleActivePayload):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    set_user_base_resume_active(user["google_id"], payload.is_active)
    return JSONResponse(content={"status": "updated", "is_active": payload.is_active})


@app.delete("/api/user/base-resume")
async def delete_user_base_resume_endpoint(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    delete_user_base_resume(user["google_id"])
    return JSONResponse(content={"status": "deleted"})


@app.post("/api/profile/upload")
async def upload_profile_endpoint(
    request: Request,
    profile_files: list[UploadFile] = File(default=[]),
    profile_file: Optional[UploadFile] = File(None),
    notes_text: Optional[str] = Form(None),
):
    """
    Parses one or more background documents (notes, markdown, text, PDF, DOCX, JSON)
    and optional text notes, then synthesizes them into a unified standardized CandidateProfile.
    """
    all_files: list[UploadFile] = []
    if profile_files:
        for f in profile_files:
            if f and f.filename and f.filename.strip():
                all_files.append(f)
    if profile_file and profile_file.filename and profile_file.filename.strip():
        if profile_file not in all_files:
            all_files.append(profile_file)

    extracted_sections: list[str] = []

    # If exactly 1 file was provided and it's already a valid CandidateProfile JSON,
    # preserve the instant fast path without needing LLM synthesis:
    if len(all_files) == 1 and not (notes_text and notes_text.strip()):
        single_file = all_files[0]
        ext = Path(single_file.filename or "").suffix.lower()
        if ext == ".json":
            dest_path = UPLOADS_DIR / f"profile_{uuid.uuid4().hex[:8]}.json"
            content_bytes = await single_file.read()
            dest_path.write_bytes(content_bytes)
            try:
                data = json.loads(content_bytes.decode("utf-8"))
                profile = CandidateProfile.model_validate(data)
                # Auto-save to user profile if signed in
                user = get_current_user_optional(request)
                if user:
                    save_user_profile(user["google_id"], profile.model_dump(), is_active=True)
                return JSONResponse(content=profile.model_dump())
            except Exception:
                txt = content_bytes.decode("utf-8", errors="ignore")
                if txt.strip():
                    extracted_sections.append(f"=== Source Document: {single_file.filename} ===\n{txt.strip()}")

    # Extract text from all files
    for f in all_files:
        if extracted_sections and len(all_files) == 1:
            break
        file_ext = Path(f.filename or "notes.txt").suffix.lower()
        dest_path = UPLOADS_DIR / f"profile_{uuid.uuid4().hex[:8]}{file_ext}"
        content_bytes = await f.read()
        dest_path.write_bytes(content_bytes)

        txt = extract_text_from_file(dest_path, filename=f.filename)
        if txt.strip():
            extracted_sections.append(f"=== Source Document: {f.filename} ===\n{txt.strip()}")

    if notes_text and notes_text.strip():
        extracted_sections.append(f"=== Additional Background Notes ===\n{notes_text.strip()}")

    raw_content = "\n\n".join(extracted_sections).strip()
    if not raw_content:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one profile document or paste background notes."
        )

    try:
        profile = convert_document_to_profile(raw_content)
        # Auto-save to user profile if signed in
        user = get_current_user_optional(request)
        if user:
            save_user_profile(user["google_id"], profile.model_dump(), is_active=True)
        return JSONResponse(content=profile.model_dump())
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert document into master profile: {err}"
        )


@app.post("/api/profile/questionnaire")
async def questionnaire_profile_endpoint(request: Request, payload: dict[str, Any] = Body(...)):
    """
    Builds a structured CandidateProfile from questionnaire wizard responses.
    """
    if not payload:
        raise HTTPException(status_code=400, detail="Empty questionnaire data.")
    try:
        profile = build_profile_from_questionnaire(payload)
        user = get_current_user_optional(request)
        if user:
            save_user_profile(user["google_id"], profile.model_dump(), is_active=True)
        return JSONResponse(content=profile.model_dump())
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate profile from questionnaire: {err}"
        )


@app.post("/api/analyze-format")
async def analyze_format_endpoint(resume_file: UploadFile = File(...)):
    """
    Analyzes an uploaded resume file for ATS parser compatibility and layout risks.
    Returns ATS score, layout classification, risk items, and recommendations.
    """
    file_id = f"analyze_{uuid.uuid4().hex[:8]}"
    file_ext = Path(resume_file.filename or "resume.pdf").suffix.lower() or ".pdf"
    temp_path = UPLOADS_DIR / f"{file_id}{file_ext}"
    try:
        contents = await resume_file.read()
        temp_path.write_bytes(contents)
        report = analyze_resume_format(temp_path)
        return JSONResponse(content=report.model_dump())
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@app.post("/api/tailor")
async def tailor_resume_endpoint(
    request: Request,
    resume_file: Optional[UploadFile] = File(None),
    jd_text: str = Form(...),
    profile_json: Optional[str] = Form(None),
    format_strategy: str = Form("auto"),
    tournament_passes: int = Form(2),
    use_saved_base: bool = Form(False),
    existing_job_id: Optional[str] = Form(None),
):
    """
    Universal Tailoring Pipeline:
    - Enforces daily rate limits (2/day for guests, 5/day for authenticated users).
    - Supports 1-click tailoring with user's saved base resume.
    - Analyzes resume format for ATS parser risks.
    - If user chooses 'ats_optimized', outputs a 100% ATS-compliant single-column clean format.
    - If user chooses 'preserve_design', preserves visual layout (PPTX/Canva) and provides ATS version.
    - Substantively enriches accomplishments and skills with verified profile context.
    """
    if not jd_text or not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    user = get_current_user_optional(request)
    is_admin = bool(user and user.get("is_admin"))
    client_ip = get_client_ip(request)
    device_id = get_client_device_id(request)
    if user:
        identifier = f"user:{user['google_id']}"
        is_auth = True
    else:
        identifier = f"dev:{device_id}"
        is_auth = False

    # Enforce quota based on mode:
    # 5 passes = Deep Quality Boost (Exclusive to signed-in accounts, limit 1/day, separate counter)
    if is_admin:
        pass  # Admin has unlimited tailoring & unlimited Deep Quality Boost runs
    elif tournament_passes == 5:
        if not user or not is_auth:
            raise HTTPException(
                status_code=403,
                detail="Deep Quality Boost is exclusive to signed-in accounts. Sign in with Google to use it."
            )
        deep_limit = check_deep_boost_limit(user["google_id"])
        if not deep_limit["allowed"]:
            raise HTTPException(
                status_code=429,
                detail="You have used your 1 free Deep Quality Boost for today. Daily quota resets at midnight UTC."
            )
    else:
        limit_info = check_rate_limit(identifier, is_authenticated=is_auth, client_ip=client_ip)
        if not limit_info["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily tailoring limit reached ({limit_info['limit']} per day for {'signed-in users' if is_auth else 'guests'}). "
                    + ("Sign in with Google to get 5 daily tailors!" if not is_auth else "Your limit resets at midnight UTC.")
                ),
            )

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    dest_path = None
    file_ext = ".pdf"

    if resume_file and resume_file.filename and resume_file.filename.strip():
        file_ext = Path(resume_file.filename).suffix.lower() or ".pdf"
        dest_path = UPLOADS_DIR / f"{job_id}{file_ext}"
        contents = await resume_file.read()
        dest_path.write_bytes(contents)
    elif use_saved_base and user:
        saved_base = get_user_base_resume(user["google_id"])
        if saved_base and saved_base.get("file_path") and Path(saved_base["file_path"]).exists():
            file_ext = saved_base.get("file_ext", ".pdf")
            dest_path = UPLOADS_DIR / f"{job_id}{file_ext}"
            saved_content = Path(saved_base["file_path"]).read_bytes()
            dest_path.write_bytes(saved_content)
        else:
            raise HTTPException(
                status_code=400,
                detail="No active base resume found in your account. Please upload a resume file."
            )
    elif existing_job_id:
        existing_matches = list(UPLOADS_DIR.glob(f"{existing_job_id}.*"))
        if existing_matches and existing_matches[0].exists():
            existing_path = existing_matches[0]
            file_ext = existing_path.suffix.lower() or ".pdf"
            dest_path = UPLOADS_DIR / f"{job_id}{file_ext}"
            dest_path.write_bytes(existing_path.read_bytes())
        else:
            raise HTTPException(
                status_code=400,
                detail="Original resume file not found for this session. Please upload your resume file."
            )
    else:
        raise HTTPException(status_code=400, detail="Please upload your resume file.")

    # Analyze format compatibility
    format_report = analyze_resume_format(dest_path)
    effective_strategy = format_strategy
    if effective_strategy == "auto":
        effective_strategy = format_report.suggested_strategy
    if file_ext not in [".pptx", ".ppt"]:
        effective_strategy = "ats_optimized"

    # Load master profile context if provided or from user account
    profile_dict = None
    if profile_json and profile_json.strip():
        try:
            profile_dict = json.loads(profile_json)
        except Exception:
            profile_dict = None
    elif user:
        user_prof = get_user_profile(user["google_id"])
        if user_prof and user_prof.get("is_active"):
            profile_dict = user_prof.get("profile")

    # 1. Design-Preserving PPTX Tailoring (when requested or auto-suggested)
    if file_ext in [".pptx", ".ppt"] and effective_strategy != "ats_optimized":
        try:
            # pyrefly: ignore [missing-import]
            from src.parser import extract_resume_sections
            # pyrefly: ignore [missing-import]
            from src.ai_engine import tailor_full_resume
            # pyrefly: ignore [missing-import]
            from src.pdf_builder import build_full_tailored_resume
            # pyrefly: ignore [missing-import]
            from src.universal_models import (
                UniversalResume,
                ContactInfo,
                SkillCategories,
                ExperienceItem,
                ProjectItem,
                EducationItem,
                AdditionalSection,
            )

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
            # pyrefly: ignore [missing-import]
            from src.interactive_diff import build_interactive_pptx_diff_html
            diff_path = OUTPUTS_DIR / f"{base_filename}_diff.html"
            build_interactive_pptx_diff_html(
                tailored_res=tailored_res,
                original_data=resume_data,
                output_html_path=diff_path,
                candidate_name=profile_dict.get("name", "") if profile_dict else "",
            )

            # Also generate a pristine 100% ATS-compliant single-column PDF
            ats_base = f"{base_filename}_ATS"
            ats_resume = UniversalResume(
                contact=ContactInfo(
                    name=profile_dict.get("name", "") if profile_dict else "Candidate",
                    email=profile_dict.get("email", "") if profile_dict else "",
                    phone=profile_dict.get("phone", "") if profile_dict else "",
                    linkedin=profile_dict.get("linkedin", "") if profile_dict else "",
                    github=profile_dict.get("github", "") if profile_dict else "",
                ),
                skills=SkillCategories(
                    programming_languages=getattr(tailored_res, "ordered_languages", []),
                    frameworks_and_tools=getattr(tailored_res, "tools_lines", []),
                    core_concepts=getattr(tailored_res, "core_concepts_lines", []),
                    spoken_languages=resume_data.get("spoken_languages", []) or (profile_dict.get("skills", {}).get("spoken_languages", []) if profile_dict and isinstance(profile_dict.get("skills"), dict) else []),
                ),
                experience=[
                    ExperienceItem(
                        role="Technical Experience",
                        company="Engineering Accomplishments",
                        bullets=getattr(tailored_res, "experience_bullets", []),
                    )
                ],
                projects=[
                    ProjectItem(
                        name=p.title_suffix.lstrip(" |").strip() if getattr(p, "title_suffix", "") else "Project",
                        technologies=p.title_suffix.strip() if getattr(p, "title_suffix", "") else "",
                        description=p.description if getattr(p, "description", "") else "",
                    )
                    for p in getattr(tailored_res, "academic_projects", [])
                ],
                education=[
                    EducationItem(
                        degree="Academic Background & Studies",
                        institution="University / Higher Education",
                        details=getattr(tailored_res, "coursework_line", ""),
                    )
                ],
                additional_sections=[
                    sec for sec in [
                        AdditionalSection(
                            title="Military Service & Tactical Leadership",
                            items=getattr(tailored_res, "military_bullets", []) or resume_data.get("military_bullets", []),
                        ) if (getattr(tailored_res, "military_bullets", []) or resume_data.get("military_bullets", [])) else None,
                        AdditionalSection(
                            title="Volunteering & Mentorship",
                            items=resume_data.get("volunteering_bullets", []),
                        ) if resume_data.get("volunteering_bullets") else None,
                        AdditionalSection(
                            title="Sport Excellence",
                            items=resume_data.get("sport_bullets", []),
                        ) if resume_data.get("sport_bullets") else None,
                    ] if sec is not None
                ],
            )
            generate_universal_resume_pdf(
                resume=ats_resume,
                output_dir=OUTPUTS_DIR,
                base_name=ats_base,
                force_single_page=format_report.is_single_page,
            )

            # Save fit analysis, jd text, and parsed resume for live diff & live editor support
            (OUTPUTS_DIR / f"{base_filename}_fit.json").write_text(
                tailored_res.fit_analysis.model_dump_json(indent=2), encoding="utf-8"
            )
            (OUTPUTS_DIR / f"{base_filename}_jd.txt").write_text(jd_text.strip(), encoding="utf-8")
            (OUTPUTS_DIR / f"{base_filename}_orig_parsed.json").write_text(
                ats_resume.model_dump_json(indent=2), encoding="utf-8"
            )
            (OUTPUTS_DIR / f"{base_filename}_resume.json").write_text(
                ats_resume.model_dump_json(indent=2), encoding="utf-8"
            )

            if user and not is_admin:
                link_user_ip(user["google_id"], client_ip)

            if not is_admin:
                if tournament_passes == 5 and user:
                    increment_deep_boost_usage(user["google_id"])
                else:
                    increment_daily_usage(identifier)
                record_tailor_run(
                    identifier=identifier,
                    client_ip=client_ip,
                    google_id=user["google_id"] if user else None,
                    is_deep_boost=(tournament_passes == 5),
                )
            else:
                record_tailor_run(
                    identifier=f"user:{ADMIN_GOOGLE_ID}",
                    client_ip=client_ip,
                    google_id=ADMIN_GOOGLE_ID,
                    is_deep_boost=(tournament_passes == 5),
                )
            limit_status = check_rate_limit(identifier, is_authenticated=is_auth, client_ip=client_ip)
            resp = JSONResponse(
                content={
                    "status": "success",
                    "job_id": job_id,
                    "filename_base": base_filename,
                    "fit_analysis": tailored_res.fit_analysis.model_dump(),
                    "preview_url": f"/api/preview/{base_filename}",
                    "diff_url": f"/api/diff/{base_filename}",
                    "download_url": f"/api/download/{base_filename}",
                    "download_pptx_url": f"/api/download_pptx/{base_filename}",
                    "format_strategy": "preserve_design",
                    "ats_report": format_report.model_dump(),
                    "tailored_resume": ats_resume.model_dump(),
                    "rate_limit": limit_status,
                }
            )
            if "rt_device_id" not in request.cookies and device_id and not device_id.startswith("ip_"):
                resp.set_cookie("rt_device_id", device_id, max_age=31536000, httponly=False, samesite="lax")
            return resp
        except Exception as err:
            # If template-specific layout parsing encounters an unexpected layout,
            # log and proceed to universal fallback
            print(f"PPTX design-preserving engine notice: {err}. Falling back to universal builder.")

    # 2. Universal Parsing & Tailoring for PDF, DOCX, or ATS-Optimized Formats
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
        tournament_passes=tournament_passes,
    )

    candidate_name = tailored_output.tailored_resume.contact.name or "Tailored"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
    base_filename = f"{job_id}_{safe_name}_Tailored_CV"

    html_path, pdf_path = generate_universal_resume_pdf(
        resume=tailored_output.tailored_resume,
        output_dir=OUTPUTS_DIR,
        base_name=base_filename,
        force_single_page=format_report.is_single_page,
    )

    # Build interactive changes view with complete resume and green marker highlights
    # pyrefly: ignore [missing-import]
    from src.interactive_diff import build_interactive_resume_diff_html
    diff_path = OUTPUTS_DIR / f"{base_filename}_diff.html"
    build_interactive_resume_diff_html(
        resume=tailored_output.tailored_resume,
        changes_log=getattr(tailored_output, "changes_log", []),
        output_html_path=diff_path,
        original_resume=parsed_resume,
    )

    # Persist session state for instant Live Editor recompile (< 1s)
    (OUTPUTS_DIR / f"{base_filename}_orig_parsed.json").write_text(
        parsed_resume.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUTPUTS_DIR / f"{base_filename}_resume.json").write_text(
        tailored_output.tailored_resume.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUTPUTS_DIR / f"{base_filename}_fit.json").write_text(
        tailored_output.fit_analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUTPUTS_DIR / f"{base_filename}_jd.txt").write_text(
        jd_text.strip(), encoding="utf-8"
    )

    if user and not is_admin:
        link_user_ip(user["google_id"], client_ip)

    if not is_admin:
        if tournament_passes == 5 and user:
            increment_deep_boost_usage(user["google_id"])
        else:
            increment_daily_usage(identifier)
        record_tailor_run(
            identifier=identifier,
            client_ip=client_ip,
            google_id=user["google_id"] if user else None,
            is_deep_boost=(tournament_passes == 5),
        )
    else:
        record_tailor_run(
            identifier=f"user:{ADMIN_GOOGLE_ID}",
            client_ip=client_ip,
            google_id=ADMIN_GOOGLE_ID,
            is_deep_boost=(tournament_passes == 5),
        )
    limit_status = check_rate_limit(identifier, is_authenticated=is_auth, client_ip=client_ip)
    resp = JSONResponse(
        content={
            "status": "success",
            "job_id": job_id,
            "filename_base": base_filename,
            "fit_analysis": tailored_output.fit_analysis.model_dump(),
            "preview_url": f"/api/preview/{base_filename}",
            "diff_url": f"/api/diff/{base_filename}",
            "download_url": f"/api/download/{base_filename}",
            "format_strategy": effective_strategy,
            "ats_report": format_report.model_dump(),
            "tailored_resume": tailored_output.tailored_resume.model_dump(),
            "rate_limit": limit_status,
        }
    )
    if "rt_device_id" not in request.cookies and device_id and not device_id.startswith("ip_"):
        resp.set_cookie("rt_device_id", device_id, max_age=31536000, httponly=False, samesite="lax")
    return resp


class RecompileRequest(BaseModel):
    filename_base: str
    resume: UniversalResume
    jd_text: Optional[str] = None


@app.post("/api/recompile-pdf")
async def recompile_pdf_endpoint(payload: RecompileRequest):
    """
    Instantly recompiles the candidate's vector PDF with density protection (< 1s)
    after the user edits contact info, summary, skills, or bullets in the Live Editor.
    Re-evaluates 360° ATS match scores and updates the interactive highlighted diff.
    """
    safe_name = Path(payload.filename_base).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename_base.")

    # 1. Sanitize updated resume (ensuring https:// links, clean GPA, single section headers)
    updated_resume = sanitize_universal_resume(payload.resume)

    # 2. Recompile vector PDF using density guardian
    html_path, pdf_path = generate_universal_resume_pdf(
        resume=updated_resume,
        output_dir=OUTPUTS_DIR,
        base_name=safe_name,
        force_single_page=True,
    )

    # 3. Retrieve target JD for deterministic 360° scoring
    jd = payload.jd_text
    jd_file = OUTPUTS_DIR / f"{safe_name}_jd.txt"
    if not jd and jd_file.exists():
        jd = jd_file.read_text(encoding="utf-8")
    jd = jd or ""

    # 4. Calculate multi-metric fit using persisted fit analysis or fallback
    fit_file = OUTPUTS_DIR / f"{safe_name}_fit.json"
    fit_analysis = None
    if fit_file.exists():
        try:
            fit_analysis = FitAnalysis.model_validate_json(fit_file.read_text(encoding="utf-8"))
        except Exception:
            fit_analysis = None

    if not fit_analysis:
        fit_analysis = FitAnalysis(
            match=[],
            partial=[],
            gap=[],
            pitch_angle="Positioning candidate based on verified live edits.",
        )

    tailored_text_corpus = (
        (updated_resume.summary or "")
        + " "
        + " ".join(updated_resume.skills.programming_languages)
        + " "
        + " ".join(updated_resume.skills.frameworks_and_tools)
        + " "
        + " ".join(updated_resume.skills.core_concepts)
        + " "
        + " ".join(updated_resume.skills.spoken_languages)
        + " "
        + " ".join(b for exp in updated_resume.experience for b in exp.bullets)
        + " "
        + " ".join(
            (p.description or "")
            + " "
            + " ".join(p.bullets)
            + " "
            + (p.technologies or "")
            for p in updated_resume.projects
        )
        + " "
        + " ".join((edu.details or "") for edu in updated_resume.education)
    )
    fit_analysis = compute_multi_metric_fit(
        fit_analysis,
        resume_text=tailored_text_corpus,
        jd_text=jd,
    )
    try:
        fit_file.write_text(fit_analysis.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        pass

    # 5. Update interactive diff view if original parsed resume exists
    orig_parsed_path = OUTPUTS_DIR / f"{safe_name}_orig_parsed.json"
    orig_resume = None
    if orig_parsed_path.exists():
        try:
            orig_resume = UniversalResume.model_validate_json(
                orig_parsed_path.read_text(encoding="utf-8")
            )
        except Exception:
            orig_resume = None

    diff_path = OUTPUTS_DIR / f"{safe_name}_diff.html"
    from src.interactive_diff import build_interactive_resume_diff_html
    build_interactive_resume_diff_html(
        resume=updated_resume,
        changes_log=[],
        output_html_path=diff_path,
        original_resume=orig_resume,
    )

    # 6. Save updated resume to disk
    (OUTPUTS_DIR / f"{safe_name}_resume.json").write_text(
        updated_resume.model_dump_json(indent=2), encoding="utf-8"
    )

    return JSONResponse(
        content={
            "status": "success",
            "filename_base": safe_name,
            "preview_url": f"/api/preview/{safe_name}",
            "diff_url": f"/api/diff/{safe_name}",
            "download_url": f"/api/download/{safe_name}",
            "fit_analysis": fit_analysis.model_dump(),
            "tailored_resume": updated_resume.model_dump(),
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


@app.get("/api/download_pptx/{base_filename}")
async def download_pptx(base_filename: str):
    """Downloads the tailored presentation (.pptx) file with preserved visual layout."""
    safe_name = Path(base_filename).name
    pptx_path = OUTPUTS_DIR / f"{safe_name}.pptx"
    if not pptx_path.exists():
        raise HTTPException(status_code=404, detail="PPTX file not found.")
    return FileResponse(
        path=pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{safe_name}.pptx",
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
