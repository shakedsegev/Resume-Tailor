#!/usr/bin/env python3
"""
Resume-Tailor CLI
AI-powered single-page resume tailoring pipeline.
Parses a Canva-designed PPTX resume, tailors all sections to a target Job Description
using Google Gemini AI without hallucinations, and compiles a ready-to-submit vector PDF.
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add project root to sys.path so imports work seamlessly
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from src.profile import load_profile
from src.parser import extract_resume_sections
from src.ai_engine import tailor_full_resume
from src.pdf_builder import build_full_tailored_resume


BANNER = r"""
======================================================================
  🎯 RESUME-TAILOR | AI-Powered 1-Page Precision Resume Optimizer
======================================================================
"""


def read_multiline_input(prompt: str) -> str:
    """Reads multiline input from stdin until EOF or 'EOF' marker."""
    print(prompt)
    print("  (Type or paste text. When done, type 'EOF' on a new line or press Ctrl+D):")
    lines = []
    try:
        while True:
            line = input()
            if line.strip() == "EOF":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


def print_fit_report(fit) -> None:
    """Prints a structured, readable Fit Analysis report to terminal."""
    print("\n" + "=" * 70)
    print("📊 JOB FIT & STRATEGY REPORT")
    print("=" * 70)

    print("\n🟢 Strong Matches:")
    for item in fit.match:
        print(f"   • {item}")

    if fit.partial:
        print("\n🟡 Partial Matches / Transferable Skills:")
        for item in fit.partial:
            print(f"   • {item}")

    if fit.gap:
        print("\n🔴 Gaps (Honest & Unfabricated):")
        for item in fit.gap:
            print(f"   • {item}")

    print("\n💡 Strategic Pitch Angle:")
    print(f"   {fit.pitch_angle}\n")
    print("=" * 70)


def print_tailoring_summary(tailored) -> None:
    """Prints a concise summary of the tailored sections."""
    print("\n🚀 TAILORING APPLIED ACROSS ALL SECTIONS:")
    print("-" * 70)
    print(f"🔤 Languages Order : {', '.join(tailored.ordered_languages)}")
    print("🛠 Academic Projects:")
    for i, proj in enumerate(tailored.academic_projects, 1):
        suffix = proj.title_suffix.strip()
        print(f"   {i}. Tags: {suffix}")
        print(f"      Desc: {proj.description}")
    print("💼 Experience:")
    for i, bullet in enumerate(tailored.experience_bullets[:3], 1):
        print(f"   {i}. {bullet}")
    if len(tailored.experience_bullets) > 3:
        print(f"   ... and {len(tailored.experience_bullets) - 3} more bullets")
    print(f"🎓 Coursework: {tailored.coursework_line}")
    print("-" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tailor your Canva-designed resume to any Job Description with AI."
    )
    parser.add_argument(
        "--jd",
        type=str,
        help="Target Job Description text string.",
    )
    parser.add_argument(
        "--jd-file",
        type=Path,
        help="Path to text file containing the target Job Description.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="Path to base PowerPoint template (.pptx).",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=project_root / "profile.json",
        help="Path to candidate profile JSON (default: 'profile.json').",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "outputs",
        help="Directory to save output files (default: 'outputs/').",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default="tailored_resume",
        help="Base filename for generated output files (default: 'tailored_resume').",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not automatically open the generated PDF in the default viewer.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the interactive web application interface in your browser.",
    )

    args = parser.parse_args()

    if args.web:
        from src.web_app import start_server
        start_server(auto_open=not args.no_open)
        return

    print(BANNER)

    # 1. Verify API Key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ ERROR: GEMINI_API_KEY environment variable is not set.")
        print("   Please create a .env file with GEMINI_API_KEY=your_key")
        sys.exit(1)

    # 2. Load Profile
    profile_path = args.profile.resolve()
    if not profile_path.exists():
        print(f"❌ ERROR: Profile file not found: {profile_path}")
        sys.exit(1)

    profile = load_profile(profile_path)
    if not profile:
        print(f"❌ ERROR: Failed to parse profile JSON from {profile_path}")
        sys.exit(1)
    print(f"✔️ Loaded profile for: {profile.get('personal', {}).get('name', 'Candidate')}")

    # 3. Load Template & Extract Sections
    template_path = args.template.resolve()
    if not template_path.exists():
        print(f"❌ ERROR: PowerPoint template not found: {template_path}")
        sys.exit(1)

    print(f"✔️ Loaded template: {template_path.name}")
    resume_data = extract_resume_sections(template_path)

    # 4. Get Job Description
    jd_text = ""
    if args.jd:
        jd_text = args.jd.strip()
    elif args.jd_file:
        jd_file_path = args.jd_file.resolve()
        if not jd_file_path.exists():
            print(f"❌ ERROR: JD file not found: {jd_file_path}")
            sys.exit(1)
        jd_text = jd_file_path.read_text(encoding="utf-8").strip()
    else:
        jd_text = read_multiline_input("\n📋 Paste target Job Description:")

    if not jd_text:
        print("❌ ERROR: Job Description cannot be empty.")
        sys.exit(1)

    print(f"✔️ Job Description received ({len(jd_text)} characters).")

    # 5. Tailor Resume with Gemini AI
    print("\n🧠 Tailoring resume with Gemini AI (Substantive Tailoring & Layout Protection)...")
    try:
        tailored = tailor_full_resume(profile, jd_text, resume_data)
    except Exception as err:
        print(f"❌ AI Tailoring failed: {err}")
        sys.exit(1)

    # 6. Display Fit Report & Summary
    print_fit_report(tailored.fit_analysis)
    print_tailoring_summary(tailored)

    # 7. Build Presentation and Vector PDF
    print("\n🎨 Injecting content, arranging language badges, and compiling PDF...")
    try:
        pptx_out, pdf_out = build_full_tailored_resume(
            template_pptx=template_path,
            output_dir=args.output_dir,
            tailored=tailored,
            base_name=args.output_name,
        )
    except Exception as err:
        print(f"❌ PDF generation failed: {err}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("✨ TAILORED RESUME GENERATED SUCCESSFULLY!")
    print("=" * 70)
    print(f"📄 PPTX: {pptx_out}")
    print(f"📄 PDF : {pdf_out}")
    print("=" * 70)

    # 8. Open PDF preview
    if not args.no_open:
        try:
            print("\n👀 Opening PDF in default viewer...")
            subprocess.run(["open", str(pdf_out)], check=False)
        except Exception:
            pass


if __name__ == "__main__":
    main()
