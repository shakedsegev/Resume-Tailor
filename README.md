# Resume-Tailor 🎯

An autonomous AI-powered pipeline and modern web application that tailors any technical or professional resume to any Job Description (JD) using Google Gemini AI, producing a ready-to-submit, high-resolution vector PDF while strictly preserving layout geometry and typography.

---

## Key Features

- **Universal Multi-Format Support**:
  - Upload Canva PPTX presentations, Microsoft Word DOCX, or PDFs.
  - Automatically parses structure, headers, experience, projects, skills, and education.
- **Full-Spectrum Substantive Tailoring**:
  - **Academic & Side Projects**: Aligns tech tags, networking protocols, concurrency architectures, and systems nuances.
  - **Work Experience**: Elevates technical troubleshooting, architectural impact, and systems reliability while preserving exact metrics.
  - **Programming Languages**: Dynamically reorders skill pills using flow coordinates so priority languages lead first.
  - **Tools & Platforms**: Formats developer environments and tooling neatly without clutter.
  - **Core Concepts**: Prioritizes relevant architectural paradigms (Multithreading, Sockets, OOP, Memory Management).
  - **Education & Coursework**: Surfaces the most relevant coursework and verified grades first.
  - **Leadership & Service**: Sharpens command, discipline, and high-stakes operational execution bullets.
- **Interactive Changes Preview with Hover Rationale**:
  - Live preview in the browser where all tailored changes are highlighted in soft marker green (`#dcfce7`).
  - Hovering over any highlighted text reveals an explanation tooltip showing what was changed from what and why.
  - **Zero Pollution on Export**: The downloaded PDF remains 100% clean and pristine for recruiter submission.
- **Candidate Master Profile (Ground Truth)**:
  - Guided 4-step wizard or document upload to establish ground truth for unlisted technical accomplishments.
  - Guarantees zero hallucinations and preserves all factual numbers and metrics without alteration.
- **Fast Vector PDF Export**:
  - Compiles crisp, ATS-ready vector PDFs via headless Chrome or native Apple Keynote.

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
   GEMINI_MODEL=gemini-2.5-flash  # optional override
   ```

---

## Usage

### 1. Launch the Web Application (Recommended)
Run the web application server:
```bash
python app.py
```
Or with CLI flag:
```bash
python main.py --web
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser:
- Upload any resume file (Canva PPTX, Word DOCX, or PDF).
- Paste your target Job Description.
- Click **Tailor & Preserve Design**.
- View the interactive preview with marker green highlights and hover tooltips, or toggle to the clean vector PDF.

### 2. Tailor via CLI
Pass the job description directly in quotes:
```bash
python main.py --template "resume_template.pptx" --jd "Backend Infrastructure Engineer. Requirements: Python, C++, Docker, multithreading, socket networking."
```

### Options & Flags
- `--web`: Launch the interactive browser web application.
- `--jd <text>`: Target Job Description text string.
- `--jd-file <path>`: Path to file containing the Job Description.
- `--output-name <name>`: Custom base filename for output `.pptx` and `.pdf` (default: `tailored_resume`).
- `--output-dir <path>`: Output directory (default: `outputs/`).
- `--template <path>`: Custom template PPTX (default: `None`).
- `--profile <path>`: Custom profile JSON (default: `profile.json`).
- `--no-open`: Skip automatically opening the generated PDF in the default viewer.

---

## Running Tests

Run the test suite with `pytest`:
```bash
pytest
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
