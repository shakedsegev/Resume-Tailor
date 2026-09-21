# Resume-Tailor 🎯

An autonomous AI-powered pipeline that tailors a Canva-designed 1-page technical resume to any Job Description (JD) using Google Gemini AI, producing a ready-to-submit, high-resolution vector PDF while strictly preserving layout geometry and typography.

---

## Key Features

- **Full-Spectrum Substantive Tailoring**: Deeply reframes and optimizes every section of the resume:
  - **Academic Projects**: Aligns tech tags, networking protocols, concurrency architectures, and low-level details.
  - **Work Experience**: Elevates technical troubleshooting, R&D consulting, infrastructure automation, and systems reliability while preserving exact metrics.
  - **Programming Languages**: Dynamically reorders native Canva pill badges using flow coordinates so priority languages lead first (e.g. Python, C++, SQL).
  - **Tools & Platforms**: Formats developer environments and tooling across 4 neat lines without redundant programming languages.
  - **Core Concepts**: Prioritizes relevant architectural paradigms (Multithreading, Sockets, OOP, Memory Management).
  - **Education & Coursework**: Surfaces the most relevant coursework and verified grades first.
  - **Military Leadership**: Sharpens command and high-stakes operational execution bullets.
- **Zero Hallucination Guarantee**: Strict ground-truth guardrails grounded in `profile.json` ensure metrics (e.g., 40 min to <1 min, grades 91, 100, 90) and technologies are never fabricated.
- **Layout & Visual Collision Protection**:
  - Automatically calculates line budgets and applies `Pt(8.6)` font scaling.
  - Moves entire native Canva pill groups without text-swapping to eliminate word splits (like `pytho\nn`) and auto-kerning distortion.
  - Guarantees everything fits strictly on **1 single page** with zero overlapping sections.
- **Fast Vector PDF Export**: Uses Apple Keynote via AppleScript to export crisp vector PDFs in seconds on macOS.

---

## Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shakedsegev/Resume-Tailor.git
   cd Resume-Tailor
   ```

2. **Set up virtual environment & install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure API Key**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.8-flash  # optional override
   ```

4. **Ensure Base Template & Profile are present**:
   - `Shaked Segev - CV.pptx`: The Canva-exported PowerPoint template.
   - `profile.json`: The candidate's verified ground truth.

---

## Usage

### 1. Tailor via CLI Argument
Pass the job description directly in quotes:
```bash
python main.py --jd "Software Engineering Student position at a backend infrastructure team. Requirements: Python, C++, Docker, multithreading, socket networking."
```

### 2. Tailor via File
Save the target job description to a text file and run:
```bash
python main.py --jd-file path/to/job_description.txt --output-name "Google_SWE_Tailored_CV"
```

### 3. Interactive Mode
Run without arguments to paste the job description interactively:
```bash
python main.py
```

### Options & Flags
- `--jd <text>`: Target Job Description text string.
- `--jd-file <path>`: Path to file containing the Job Description.
- `--output-name <name>`: Custom base filename for output `.pptx` and `.pdf` (default: `Shaked_Segev_Tailored_CV`).
- `--output-dir <path>`: Output directory (default: `outputs/`).
- `--template <path>`: Custom template PPTX (default: `Shaked Segev - CV.pptx`).
- `--profile <path>`: Custom profile JSON (default: `profile.json`).
- `--no-open`: Skip automatically opening the generated PDF in the default viewer.

---

## Running Tests

Run the test suite with `pytest`:
```bash
pytest
```
