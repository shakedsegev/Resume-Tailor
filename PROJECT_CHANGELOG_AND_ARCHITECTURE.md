# Resume Tailor — Complete Project Architecture, Features & Evolution Log

**Repository:** `Resume-Tailor`  
**Latest Verification:** 2026-09-22  
**Status:** Production Ready · 22/22 Automated Tests Passing · Clean Git History

---

## 1. System Architecture Overview

```mermaid
flowchart TD
    subgraph INGESTION["1. Document Ingestion & ATS Audit"]
        InputDoc["Uploaded Resume\n(.pptx, .pdf, .docx, .txt)"]
        Parser["Universal Parser\n(PyPDF / python-docx / python-pptx)"]
        ATSScan["ATS Layout Inspector\n(Column counting, coordinate check, 0-100 score)"]
        InputDoc --> Parser
        InputDoc --> ATSScan
    end

    subgraph GROUND_TRUTH["2. Master Profile (Ground Truth Database)"]
        NotesUpload["Candidate Background Notes\n(.pdf, .docx, .md, .txt)"]
        Wizard["4-Step Interactive Wizard"]
        MasterProfile["Candidate Master Profile\n(Verified architectures, metrics & unlisted nuances)"]
        NotesUpload --> MasterProfile
        Wizard --> MasterProfile
    end

    subgraph TAILOR_ENGINE["3. Intelligent Tailoring Engine (Gemini 2.5)"]
        JD["Target Job Description"]
        AntiHallucination["Zero-Fabrication Anchor\n(Strict factual validation)"]
        ProactiveMandate["Proactive Optimization Mandate\n(Sharpen verbs, elevate metrics, reorder skills)"]
        Normalization["Sanitization Pipeline\n(GPA isolation, course grades preservation, section deduplication)"]
        Parser --> TAILOR_ENGINE
        MasterProfile --> TAILOR_ENGINE
        JD --> TAILOR_ENGINE
    end

    subgraph DUAL_PIPELINE["4. Dual Rendering Pipeline"]
        PPTXBranch{"Format Strategy"}
        PPTXPreserver["Canva PPTX Preserver\n(Coordinate bounding guards, pill reflow, LibreOffice PDF)"]
        ATSPDF["Universal 100% ATS PDF\n(Semantic HTML -> Chromium Playwright -> Single-column vector PDF)"]
        DensityGuardian["1-Page Density Guardian\n(Dynamic margin/font compaction loop)"]

        TAILOR_ENGINE --> PPTXBranch
        PPTXBranch -->|"PPTX only + preserve_design"| PPTXPreserver
        PPTXBranch -->|"ats_optimized (Default / PDF / Word)"| ATSPDF
        ATSPDF --> DensityGuardian
    end

    subgraph REVIEW["5. Interactive Review & UI"]
        DiffView["Interactive Visual Diff\n(Green highlighter badges + scoped rationale tooltips)"]
        FinalPDF["Clean Final PDF\n(Print & application ready)"]
        Multilingual["Multilingual UI\n(EN, HE, ES, FR, DE, AR, ZH)"]
        DensityGuardian --> DiffView
        DensityGuardian --> FinalPDF
        PPTXPreserver --> DiffView
        PPTXPreserver --> FinalPDF
    end
```

---

## 2. Comprehensive Inventory of Changes, Features & Fixes

Below is the exhaustive chronological and functional inventory of every feature developed, every bug fixed, and why each change was implemented.

### A. Document Ingestion & ATS Parser Compatibility
1. **Multi-Format Ingestion Engine (`src/universal_parser.py`)**
   - **Problem:** The tool originally only supported PowerPoint PPTX templates. Real candidates frequently upload Word (`.docx`), exported PDFs, or plain text.
   - **Solution:** Integrated `pypdf`, `python-docx`, `python-pptx`, and text codecs with fallback handling to parse any resume into the structured `UniversalResume` model.
2. **ATS Parser Risk Inspector (`src/ats_analyzer.py`)**
   - **Problem:** Multi-column layouts, floating Canva shapes, and graphical text boxes often get scrambled by Applicant Tracking Systems like Workday, Taleo, Greenhouse, and Lever. Candidates had no visibility into why their resumes failed parsing.
   - **Solution:** Built layout analysis algorithms evaluating column splits, coordinate frames, and standard header presence. Outputs an ATS score (0–100), layout classification, and specific parsing risks.
3. **Strict Format Strategy Gating for PPTX Only (`templates/index.html`, `src/web_app.py`, `src/ats_analyzer.py`)**
   - **Problem:** The UI allowed users uploading PDFs to select "Preserve Original Visual Design". However, PDF coordinates cannot be altered in-place while keeping arbitrary graphic styling. Selecting this option on a PDF gave the false impression that original visual shapes were preserved.
   - **Solution:** The format strategy chooser and `"Preserve Original Visual Design"` option now appear **exclusively** for `.pptx` and `.ppt` uploads. All other formats (PDF, DOCX, TXT) automatically compile into the 100% ATS-compliant clean vector layout. The backend enforces `effective_strategy = "ats_optimized"` for any non-presentation input.
4. **Score 92 Tailoring Unblock & Clear Guidance (`templates/index.html`)**
   - **Problem:** Resumes with clean single-column formatting received an ATS score of 92/100, but the interface previously disabled the tailor button because `needs_format_change` was false.
   - **Solution:** Decoupled format compliance from role tailoring. A score of 92 displays a green checkmark explaining that the layout is already ATS-friendly, keeps the Tailor button active, and guides the candidate to tailor their bullet points and skills for the specific job description.

---

### B. Candidate Master Profile & Zero-Fabrication Architecture
1. **Master Profile Ground Truth Database (`src/profile.py`, `src/profile_manager.py`)**
   - **Problem:** AI tailoring models are notorious for hallucinations (inventing degrees, jobs, or metrics). Concurrently, candidates possess verified achievements, unlisted project architectures, and metrics that don't fit on their 1-page CV.
   - **Solution:** Designed a Master Profile ground-truth database. Candidates can upload background notes (PDF, Word, Markdown, JSON, TXT) or complete an interactive 4-step wizard. The AI synthesizes verified facts without inventing information.
2. **Zero Fabrication & Anti-Hallucination Protocol (`src/universal_ai.py`, `src/ai_engine.py`)**
   - **Problem:** Adding unverified skills or inventing metrics poses a severe risk in technical interviews.
   - **Solution:** Implemented strict multi-tier prompt instructions: the AI is strictly bound to verified facts in the candidate's original resume or Master Profile. Any skill, technology, or metric not grounded in these sources is prohibited from appearing.

---

### C. Substantive Content Tailoring & Anti-Duplication
1. **Proactive Optimization Mandate (`src/universal_ai.py`)**
   - **Problem:** Early versions occasionally passed original bullet points through unchanged if the resume already had high keyword match.
   - **Solution:** Mandated proactive optimization across every bullet: leading with strong engineering action verbs, emphasizing quantifiable impact, prioritizing JD-relevant technologies, and elevating verified achievements.
2. **Spoken Languages vs. Programming Languages Separation (`src/universal_models.py`)**
   - **Problem:** Spoken/natural languages were either omitted during tailoring or placed into an arbitrary "Languages" section that conflicted with "Programming Languages".
   - **Solution:** Integrated `spoken_languages` into `SkillCategories`. Spoken languages are rendered as a dedicated line inside Technical Skills, eliminating duplicate headers.
3. **Universal Candidate-Agnostic Philosophy (`src/universal_ai.py`, `src/universal_models.py`)**
   - **Problem:** Code previously contained hardcoded assumptions (such as assuming Hebrew and English as default spoken languages).
   - **Solution:** Purged all regional and personal assumptions. Spoken languages and backgrounds are dynamically extracted from what the candidate actually wrote.
4. **Coursework Grades Preservation (`src/universal_models.py`, `src/universal_ai.py`)**
   - **Problem:** When reordering courses by JD priority, parenthesized grades like `Computer Architecture (91)` were sometimes dropped by the AI.
   - **Solution:** Built `restore_course_grades` to cross-reference the original coursework list, automatically re-attaching grades to matching courses.
5. **GPA Isolation & Deduplication (`src/universal_models.py`, `src/universal_pdf_builder.py`, `src/interactive_diff.py`)**
   - **Problem:** GPA appeared in both the Professional Summary and Education section, creating duplicate mentions and repetitive labels like `GPA: GPA: 85`.
   - **Solution:** Built `clean_summary_gpa` to purge GPA from the summary, and `clean_gpa_val` to eliminate redundant prefixes, restricting GPA exclusively to the Education section.
6. **Section Title Normalization & Header Deduplication (`src/universal_models.py`)**
   - **Problem:** Uploaded documents with fragmented sections (e.g. two separate "Experience" blocks) resulted in repeated headers in the output.
   - **Solution:** Built `normalize_section_title` and `sanitize_universal_resume` to group and merge sections sharing the same normalized title under a single unified header.

---

### D. Dual Rendering & Density Protection
1. **In-Place PPTX Design Protection (`src/pdf_builder.py`)**
   - **Problem:** Editing text inside Canva presentations frequently caused text boxes to collide, overflow, or break line wrapping.
   - **Solution:** Implemented bounding-box guards, line-budget calculations, font auto-scaling, and pill group reflowing to preserve the original visual presentation without overlap.
2. **Universal 100% ATS Vector PDF Builder (`src/universal_pdf_builder.py`)**
   - **Problem:** Non-presentation resumes require a clean typography layout optimized for ATS parsers.
   - **Solution:** Created semantic HTML/CSS templates compiled via headless Chromium (Playwright), generating single-column vector PDFs with selectable text, standard margins, and clear typographic hierarchy.
3. **1-Page Density Guardian (`src/universal_pdf_builder.py`)**
   - **Problem:** Dense resumes occasionally spilled onto a second page, violating the standard 1-page rule.
   - **Solution:** Implemented an automated compaction loop that checks the compiled PDF page count. If page count exceeds 1, it progressively adjusts margins (20px -> 14px), font sizes (9.5pt -> 8.2pt), and line heights until the content fits on one page.

---

### E. User Interface & Interactive Review
1. **Interactive Visual Diff Inspector (`src/interactive_diff.py`)**
   - **Problem:** Candidates could not see what the AI changed or understand why changes were made.
   - **Solution:** Generates a side-by-side view with green highlighter badges on tailored bullets. Hovering reveals a tooltip showing original text, tailored text, and the strategic ATS rationale.
2. **Strict Section Tooltip Isolation (`src/interactive_diff.py`)**
   - **Problem:** Hovering over an item in one section occasionally triggered tooltips belonging to another section.
   - **Solution:** Scoped tooltip IDs strictly by section type and item index, eliminating cross-section hover bleed.
3. **Multilingual UI Support (`templates/index.html`)**
   - **Problem:** The tool was originally English-only.
   - **Solution:** Built a client-side localization system supporting English, Hebrew (RTL), Spanish, French, German, Arabic (RTL), and Chinese.

---

## 3. Privacy Audit & Cleanup Confirmation

| Check | Status | Details |
| :--- | :---: | :--- |
| **PDF/PPTX Git History** | Clean | `git log --all --full-history -- "*.pptx" "*.pdf"` is empty. Zero resumes committed. |
| **Tracked Code Data** | Clean | All tracked files contain only synthetic placeholders (`Alex Morgan`, `Jane Doe`). |
| **Test Fixtures** | Clean | Removed all local resume fallback filenames from tests, using generic `template.pptx`. |
| **Outputs Directory** | Clean | Cleared all temporary files from `outputs/` and `outputs/uploads/`; kept `.gitkeep`. |
| **Git Working Tree** | Clean | Synchronized with `origin/main` at commit `cdf72c4`. |
| **Test Suite** | Passing | 22/22 unit and integration tests passing. |
