"""
Interactive Resume Diff & Changes Highlight Generator.
Renders a complete, beautifully-formatted resume matching the exact design and typography
of the clean output, but with every tailored element highlighted in soft marker green (#dcfce7).
Hovering over any highlighted text displays a rich tooltip revealing what was changed from what,
and why. The exported vector PDF remains 100% clean and pristine.
"""

from difflib import SequenceMatcher
import html
from pathlib import Path
import re
from typing import Any, Optional

from jinja2 import Template
# pyrefly: ignore [missing-import]
from src.universal_models import (
    AdditionalSection,
    ContactInfo,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    SkillCategories,
    UniversalResume,
    sanitize_universal_resume,
)


def _clean_text(val: str) -> str:
    """Normalizes whitespace and lowercase for reliable comparison."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val).strip().lower()


def _section_category(sec_name: str) -> str:
    """Categorizes a section name into standard buckets to prevent cross-section contamination."""
    s = (sec_name or "").lower()
    if any(k in s for k in ["exp", "work", "job", "career", "employ"]):
        return "experience"
    if any(k in s for k in ["proj", "academic"]):
        return "projects"
    if any(k in s for k in ["lang", "prog"]):
        return "languages"
    if any(k in s for k in ["tool", "framework", "tech", "librar"]):
        return "tools"
    if any(k in s for k in ["concept", "method", "course"]):
        return "concepts"
    if any(k in s for k in ["edu", "deg", "academ"]):
        return "education"
    if any(k in s for k in ["sum", "prof", "about", "object"]):
        return "summary"
    if any(k in s for k in ["mil", "lead", "addit", "extrac", "volunt"]):
        return "additional"
    return s.strip()


def find_matching_change(
    text: str,
    section: str,
    changes_log: list[Any],
    original_fallback: str = "",
) -> Optional[dict[str, str]]:
    """
    Finds a matching ChangeAnnotation in changes_log for the given text,
    or falls back to comparing against original_fallback.
    Strictly isolates section categories to prevent cross-section tooltip mismatch.
    Returns dict with keys: original, rationale, section.
    """
    cleaned_text = _clean_text(text)
    if not cleaned_text:
        return None

    cleaned_orig = _clean_text(original_fallback)
    # If original text is identical to current text, it was not changed
    if cleaned_orig and cleaned_orig == cleaned_text:
        return None

    sec_cat = _section_category(section)

    # 1. Programming Languages section handling
    if sec_cat == "languages":
        if not original_fallback:
            # Check if this specific language was logged as changed under languages
            for c in changes_log:
                c_sec = _section_category(getattr(c, "section", "") or (c.get("section", "") if isinstance(c, dict) else ""))
                if c_sec == "languages":
                    c_tailored = _clean_text(getattr(c, "tailored_text", "") or (c.get("tailored_text", "") if isinstance(c, dict) else ""))
                    if c_tailored == cleaned_text:
                        orig = getattr(c, "original_text", "") or (c.get("original_text", "") if isinstance(c, dict) else "")
                        rat = getattr(c, "rationale", "") or (c.get("rationale", "") if isinstance(c, dict) else "")
                        return {
                            "original": orig or "Not emphasized in original resume",
                            "rationale": rat or "Prioritized to match target role requirements.",
                            "section": "Programming Languages",
                        }
            return None
        else:
            # We have a specific fallback like "Rank #3 in original resume" or "Added from Master Profile"
            rat = ""
            for c in changes_log:
                c_sec = _section_category(getattr(c, "section", "") or (c.get("section", "") if isinstance(c, dict) else ""))
                if c_sec == "languages":
                    c_tailored = _clean_text(getattr(c, "tailored_text", "") or (c.get("tailored_text", "") if isinstance(c, dict) else ""))
                    if cleaned_text in c_tailored or c_tailored in cleaned_text:
                        rat = getattr(c, "rationale", "") or (c.get("rationale", "") if isinstance(c, dict) else "")
                        break
            if not rat:
                if "Master Profile" in original_fallback:
                    rat = f"Added '{text}' from Master Profile to satisfy core technical requirements in the job description."
                else:
                    rat = f"Prioritized '{text}' to the top of the technical stack to match target job requirements."
            return {
                "original": original_fallback,
                "rationale": rat,
                "section": "Programming Languages",
            }

    # 2. When original_fallback is provided and differs from text
    if original_fallback:
        # Guarantee that 'original' is strictly original_fallback
        matched_rat = ""
        best_r = 0.0
        for c in changes_log:
            c_sec = _section_category(getattr(c, "section", "") or (c.get("section", "") if isinstance(c, dict) else ""))
            if c_sec != sec_cat:
                continue
            c_tailored = _clean_text(getattr(c, "tailored_text", "") or (c.get("tailored_text", "") if isinstance(c, dict) else ""))
            c_orig = _clean_text(getattr(c, "original_text", "") or (c.get("original_text", "") if isinstance(c, dict) else ""))
            rat = getattr(c, "rationale", "") or (c.get("rationale", "") if isinstance(c, dict) else "")

            # Exact match
            if cleaned_text == c_tailored or (cleaned_orig and cleaned_orig == c_orig):
                matched_rat = rat
                break

            # Sequence similarity match within same section
            if c_tailored:
                r1 = SequenceMatcher(None, cleaned_text, c_tailored).ratio()
                if r1 > best_r and r1 >= 0.60:
                    best_r = r1
                    matched_rat = rat
            if cleaned_orig and c_orig:
                r2 = SequenceMatcher(None, cleaned_orig, c_orig).ratio()
                if r2 > best_r and r2 >= 0.60:
                    best_r = r2
                    matched_rat = rat

        if not matched_rat:
            if sec_cat == "experience":
                matched_rat = "Enhanced phrasing with quantifiable achievements, active verbs, and key technologies requested in the job description."
            elif sec_cat == "projects":
                matched_rat = "Emphasized relevant system architecture, tools, and technical delivery to align with target role requirements."
            elif sec_cat == "tools":
                matched_rat = "Updated frameworks and technologies to highlight key tools required for the position."
            elif sec_cat == "concepts":
                matched_rat = "Aligned core methodologies and domain concepts with the target job specifications."
            elif sec_cat == "education":
                matched_rat = "Highlighted relevant coursework and academic achievements pertinent to the position."
            elif sec_cat == "summary":
                matched_rat = "Reframed professional summary to highlight qualifications most relevant to the role."
            else:
                matched_rat = "Tailored phrasing to highlight qualifications and keywords relevant to the target job description."

        return {
            "original": original_fallback,
            "rationale": matched_rat,
            "section": section,
        }

    # 3. When original_fallback is NOT provided (fallback to changes_log within section category)
    best_c = None
    best_score = 0.0
    for c in changes_log:
        c_sec = _section_category(getattr(c, "section", "") or (c.get("section", "") if isinstance(c, dict) else ""))
        if c_sec != sec_cat:
            continue
        c_tailored = _clean_text(getattr(c, "tailored_text", "") or (c.get("tailored_text", "") if isinstance(c, dict) else ""))
        if not c_tailored:
            continue
        if cleaned_text == c_tailored:
            o_text = getattr(c, "original_text", "") or (c.get("original_text", "") if isinstance(c, dict) else "")
            rat = getattr(c, "rationale", "") or (c.get("rationale", "") if isinstance(c, dict) else "")
            return {
                "original": o_text or "Original phrasing",
                "rationale": rat or "Tailored to align with target job description requirements.",
                "section": section,
            }
        r = SequenceMatcher(None, cleaned_text, c_tailored).ratio()
        if r >= 0.75 and r > best_score:
            best_score = r
            best_c = c

    if best_c:
        o_text = getattr(best_c, "original_text", "") or (best_c.get("original_text", "") if isinstance(best_c, dict) else "")
        rat = getattr(best_c, "rationale", "") or (best_c.get("rationale", "") if isinstance(best_c, dict) else "")
        return {
            "original": o_text or "Original phrasing",
            "rationale": rat or "Tailored to align with target job description requirements.",
            "section": section,
        }

    return None


def highlight_text(
    text: str,
    section: str,
    changes_log: list[Any],
    original_fallback: str = "",
    inline_tag: str = "mark",
    extra_class: str = "",
) -> str:
    """
    Wraps text in an interactive highlight tag if matched in changes_log or changed from original_fallback.
    Returns safely escaped HTML.
    """
    if not text:
        return ""

    match = find_matching_change(text, section, changes_log, original_fallback)
    if match:
        safe_orig = html.escape(match["original"])
        safe_rat = html.escape(match["rationale"])
        safe_sec = html.escape(match["section"])
        safe_text = html.escape(text)
        classes = f"change-highlight {extra_class}".strip()

        return (
            f'<{inline_tag} class="{classes}" '
            f'data-section="{safe_sec}" '
            f'data-original="{safe_orig}" '
            f'data-rationale="{safe_rat}">{safe_text}</{inline_tag}>'
        )

    safe_text = html.escape(text)
    if extra_class:
        return f'<{inline_tag} class="{extra_class}">{safe_text}</{inline_tag}>'
    return safe_text


INTERACTIVE_RESUME_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ resume.contact.name }} - Interactive Changes Preview</title>
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    font-size: 9pt;
    line-height: 1.35;
    padding: 20px 24px 40px 24px;
  }
  /* Top Interactive Banner */
  .diff-banner {
    background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
    border: 1px solid #86efac;
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: #065f46;
    font-size: 8.5pt;
    line-height: 1.45;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }
  .diff-banner-icon {
    font-size: 16pt;
    flex-shrink: 0;
  }

  header {
    text-align: center;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 6px;
    margin-bottom: 8px;
  }
  h1 {
    font-size: 20pt;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #0f172a;
    text-transform: uppercase;
  }
  .contact-bar {
    margin-top: 3px;
    font-size: 8.5pt;
    color: #475569;
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .contact-bar a {
    color: #0284c7;
    text-decoration: none;
    font-weight: 500;
  }
  .section {
    margin-bottom: 8px;
  }
  .section-title {
    font-size: 10pt;
    font-weight: 700;
    color: #0284c7;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 2px;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .item {
    margin-bottom: 5px;
  }
  .item-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 9pt;
  }
  .item-title {
    font-weight: 700;
    color: #0f172a;
  }
  .item-sub {
    color: #334155;
    font-weight: 600;
  }
  .item-tech {
    font-weight: 500;
    color: #0369a1;
  }
  .item-date {
    font-size: 8pt;
    color: #64748b;
    font-weight: 500;
    white-space: nowrap;
  }
  ul {
    list-style-type: disc;
    padding-left: 16px;
    margin-top: 2px;
  }
  li {
    margin-bottom: 3px;
    color: #334155;
    text-align: justify;
    line-height: 1.4;
  }
  .skills-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    row-gap: 4px;
    font-size: 8.8pt;
  }
  .skill-label {
    font-weight: 700;
    color: #0f172a;
  }
  .skill-values {
    color: #334155;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .pill {
    background: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 8pt;
    font-weight: 600;
    display: inline-block;
  }

  /* Marker Green Highlight Style */
  .change-highlight {
    background-color: #dcfce7 !important; /* Soft marker green */
    border-bottom: 2px solid #22c55e !important;
    border-radius: 3px;
    padding: 1px 4px;
    cursor: help;
    display: inline;
    text-decoration: none;
    transition: background-color 0.15s ease, box-shadow 0.15s ease;
  }
  .change-highlight:hover {
    background-color: #bbf7d0 !important; /* Darker marker green on hover */
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.25);
  }
  .pill.change-highlight {
    background: #dcfce7 !important;
    border: 1px solid #4ade80 !important;
    color: #065f46 !important;
  }
  .pill.change-highlight:hover {
    background: #bbf7d0 !important;
  }

  /* Floating Popover Tooltip */
  #tooltip {
    position: fixed;
    display: none;
    z-index: 99999;
    width: 380px;
    max-width: calc(100vw - 32px);
    background: #0f172a;
    color: #f8fafc;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 8.5pt;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    pointer-events: none;
    border: 1px solid #334155;
    line-height: 1.45;
  }
  .tt-sec {
    font-size: 7.5pt;
    text-transform: uppercase;
    color: #38bdf8;
    font-weight: 800;
    letter-spacing: 0.8px;
    margin-bottom: 6px;
  }
  .tt-from {
    color: #cbd5e1;
    margin-bottom: 8px;
    border-left: 3px solid #ef4444;
    padding: 4px 8px;
    background: rgba(239, 68, 68, 0.12);
    border-radius: 0 4px 4px 0;
  }
  .tt-from strong {
    color: #fca5a5;
    display: block;
    font-size: 7.5pt;
    text-transform: uppercase;
    margin-bottom: 2px;
    letter-spacing: 0.5px;
  }
  .tt-from p {
    color: #e2e8f0;
    font-size: 8pt;
    word-break: break-word;
  }
  .tt-why {
    color: #f1f5f9;
    border-left: 3px solid #22c55e;
    padding: 4px 8px;
    background: rgba(34, 197, 94, 0.12);
    border-radius: 0 4px 4px 0;
  }
  .tt-why strong {
    color: #86efac;
    display: block;
    font-size: 7.5pt;
    text-transform: uppercase;
    margin-bottom: 2px;
    letter-spacing: 0.5px;
  }
  .tt-why p {
    color: #f8fafc;
    font-size: 8pt;
    word-break: break-word;
  }
</style>
</head>
<body>

<!-- Interactive Info Banner -->
<div class="diff-banner">
  <span class="diff-banner-icon">✨</span>
  <div>
    <strong>Interactive Tailoring Preview:</strong>
    All tailored additions, sharpened accomplishments, and prioritized skills are highlighted in <strong>soft marker green</strong>.
    <strong>Hover over any highlighted text</strong> to see what was changed from what and why.
    <em>Note: The exported PDF remains 100% clean and pristine for recruiter submission.</em>
  </div>
</div>

<header>
  <h1>{{ resume.contact.name }}</h1>
  <div class="contact-bar">
    {% if resume.contact.phone %}<span>📞 {{ resume.contact.phone }}</span>{% endif %}
    {% if resume.contact.email %}<span>✉️ <a href="mailto:{{ resume.contact.email }}">{{ resume.contact.email }}</a></span>{% endif %}
    {% if resume.contact.location %}<span>📍 {{ resume.contact.location }}</span>{% endif %}
    {% if resume.contact.linkedin %}<span>🔗 <a href="{{ resume.contact.linkedin }}" target="_blank">LinkedIn</a></span>{% endif %}
    {% if resume.contact.github %}<span>💻 <a href="{{ resume.contact.github }}" target="_blank">GitHub</a></span>{% endif %}
  </div>
</header>

{% if rendered_summary %}
<div class="section">
  <div class="section-title">Professional Summary</div>
  <p style="color: #334155; font-size: 8.8pt;">{{ rendered_summary | safe }}</p>
</div>
{% endif %}

{% if rendered_education %}
<div class="section">
  <div class="section-title">Education</div>
  {% for edu in rendered_education %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ edu.institution }}</span>
      <span class="item-date">{{ edu.date_range }}</span>
    </div>
    <div class="item-sub">{{ edu.degree }}{% if edu.gpa %} · {% if 'gpa' in edu.gpa.lower() %}{{ edu.gpa }}{% else %}GPA: {{ edu.gpa }}{% endif %}{% endif %}</div>
    {% if edu.rendered_details %}<p style="font-size: 8.4pt; color: #475569; margin-top: 1px;">{{ edu.rendered_details | safe }}</p>{% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if rendered_skills.programming_languages or rendered_skills.frameworks_and_tools or rendered_skills.core_concepts or rendered_skills.spoken_languages %}
<div class="section">
  <div class="section-title">Technical & Language Skills</div>
  <div class="skills-grid">
    {% if rendered_skills.programming_languages %}
    <span class="skill-label">Languages:</span>
    <span class="skill-values">
      <div class="pills">
        {% for pill_html in rendered_skills.programming_languages %}
        {{ pill_html | safe }}
        {% endfor %}
      </div>
    </span>
    {% endif %}
    {% if rendered_skills.frameworks_and_tools %}
    <span class="skill-label">Tools & Frameworks:</span>
    <span class="skill-values">{{ rendered_skills.frameworks_and_tools | safe }}</span>
    {% endif %}
    {% if rendered_skills.core_concepts %}
    <span class="skill-label">Core Concepts:</span>
    <span class="skill-values">{{ rendered_skills.core_concepts | safe }}</span>
    {% endif %}
    {% if rendered_skills.spoken_languages %}
    <span class="skill-label">Spoken Languages:</span>
    <span class="skill-values">{{ rendered_skills.spoken_languages | safe }}</span>
    {% endif %}
  </div>
</div>
{% endif %}

{% if rendered_projects %}
<div class="section">
  <div class="section-title">Technical & Academic Projects</div>
  {% for proj in rendered_projects %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ proj.name }} {% if proj.rendered_tech %}<span class="item-tech">| {{ proj.rendered_tech | safe }}</span>{% endif %}</span>
    </div>
    {% if proj.rendered_desc %}<p style="color: #334155; font-size: 8.8pt; margin-top: 1px;">{{ proj.rendered_desc | safe }}</p>{% endif %}
    {% if proj.rendered_bullets %}
    <ul>
      {% for b_html in proj.rendered_bullets %}
      <li>{{ b_html | safe }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if rendered_experience %}
<div class="section">
  <div class="section-title">Professional Experience</div>
  {% for exp in rendered_experience %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ exp.role }} <span style="font-weight: 500; color: #64748b;">at</span> {{ exp.company }}</span>
      <span class="item-date">{{ exp.date_range }}</span>
    </div>
    {% if exp.rendered_bullets %}
    <ul>
      {% for b_html in exp.rendered_bullets %}
      <li>{{ b_html | safe }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if rendered_additional %}
{% for sec in rendered_additional %}
<div class="section">
  <div class="section-title">{{ sec.title }}</div>
  <ul>
    {% for item_html in sec.rendered_items %}
    <li>{{ item_html | safe }}</li>
    {% endfor %}
  </ul>
</div>
{% endfor %}
{% endif %}

<!-- Floating Hover Tooltip -->
<div id="tooltip">
  <div class="tt-sec" id="ttSec"></div>
  <div class="tt-from">
    <strong>Changed from:</strong>
    <p id="ttOrig"></p>
  </div>
  <div class="tt-why">
    <strong>💡 Why this was changed:</strong>
    <p id="ttRat"></p>
  </div>
</div>

<script>
  const tooltip = document.getElementById('tooltip');
  const ttSec = document.getElementById('ttSec');
  const ttOrig = document.getElementById('ttOrig');
  const ttRat = document.getElementById('ttRat');

  document.querySelectorAll('.change-highlight').forEach(el => {
    el.addEventListener('mouseenter', (e) => {
      ttSec.textContent = e.currentTarget.getAttribute('data-section') || 'Tailored Section';
      ttOrig.textContent = e.currentTarget.getAttribute('data-original') || 'Original resume phrasing';
      ttRat.textContent = e.currentTarget.getAttribute('data-rationale') || 'Tailored to align with target job description requirements.';
      tooltip.style.display = 'block';
    });

    el.addEventListener('mousemove', (e) => {
      const x = e.clientX + 15;
      const y = e.clientY + 15;
      const ttWidth = tooltip.offsetWidth || 380;
      const ttHeight = tooltip.offsetHeight || 130;
      const posX = (x + ttWidth > window.innerWidth - 10) ? Math.max(10, e.clientX - ttWidth - 10) : x;
      const posY = (y + ttHeight > window.innerHeight - 10) ? Math.max(10, e.clientY - ttHeight - 10) : y;
      tooltip.style.left = posX + 'px';
      tooltip.style.top = posY + 'px';
    });

    el.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
  });
</script>

</body>
</html>
"""


def build_interactive_resume_diff_html(
    resume: UniversalResume,
    changes_log: list[Any],
    output_html_path: Path,
    original_resume: Optional[UniversalResume] = None,
) -> Path:
    """
    Renders the complete tailored resume as an interactive HTML preview
    where every modified bullet, reordered skill, and project tag is highlighted
    in light marker green, and hovering over it displays a rich tooltip with
    'Changed from' and 'Why this was changed'.
    """
    output_html_path = output_html_path.resolve()
    output_html_path.parent.mkdir(parents=True, exist_ok=True)

    resume = sanitize_universal_resume(resume)
    if original_resume:
        original_resume = sanitize_universal_resume(original_resume)

    # 1. Summary
    rendered_summary = ""
    if resume.summary:
        orig_sum = original_resume.summary if original_resume else ""
        rendered_summary = highlight_text(
            text=resume.summary,
            section="Summary",
            changes_log=changes_log,
            original_fallback=orig_sum,
        )

    # 2. Education
    rendered_education = []
    for idx, edu in enumerate(resume.education):
        orig_edu = (
            original_resume.education[idx]
            if original_resume and idx < len(original_resume.education)
            else None
        )
        orig_details = orig_edu.details if orig_edu else ""
        rendered_details = highlight_text(
            text=edu.details,
            section="Education & Coursework",
            changes_log=changes_log,
            original_fallback=orig_details,
        )
        rendered_education.append({
            "institution": edu.institution,
            "degree": edu.degree,
            "date_range": edu.date_range,
            "gpa": edu.gpa,
            "rendered_details": rendered_details,
        })

    # 3. Technical Skills
    # Check if languages were added, reordered or tailored
    orig_langs = (
        original_resume.skills.programming_languages
        if original_resume
        else []
    )
    rendered_pills = []
    for idx, lang in enumerate(resume.skills.programming_languages):
        is_new = bool(orig_langs and (lang not in orig_langs))
        is_prioritized = bool(
            orig_langs
            and lang in orig_langs
            and orig_langs.index(lang) > idx
        )
        if is_new:
            pill_fallback = "Not present in uploaded resume (added from Master Profile)"
        elif is_prioritized:
            pill_fallback = f"Rank #{orig_langs.index(lang) + 1} in original resume"
        else:
            pill_fallback = ""

        pill_html = highlight_text(
            text=lang,
            section="Programming Languages",
            changes_log=changes_log,
            original_fallback=pill_fallback,
            inline_tag="span",
            extra_class="pill",
        )
        rendered_pills.append(pill_html)

    # Tools & Frameworks
    tools_str = ", ".join(resume.skills.frameworks_and_tools)
    orig_tools = (
        ", ".join(original_resume.skills.frameworks_and_tools)
        if original_resume
        else ""
    )
    rendered_tools = highlight_text(
        text=tools_str,
        section="Tools & Frameworks",
        changes_log=changes_log,
        original_fallback=orig_tools,
    )

    # Core Concepts
    concepts_str = ", ".join(resume.skills.core_concepts)
    orig_concepts = (
        ", ".join(original_resume.skills.core_concepts)
        if original_resume
        else ""
    )
    rendered_concepts = highlight_text(
        text=concepts_str,
        section="Core Concepts",
        changes_log=changes_log,
        original_fallback=orig_concepts,
    )

    # Spoken Languages
    rendered_spoken = ""
    if hasattr(resume.skills, "spoken_languages") and resume.skills.spoken_languages:
        spoken_str = " · ".join(resume.skills.spoken_languages)
        orig_spoken = (
            " · ".join(original_resume.skills.spoken_languages)
            if original_resume and hasattr(original_resume.skills, "spoken_languages") and original_resume.skills.spoken_languages
            else ""
        )
        rendered_spoken = highlight_text(
            text=spoken_str,
            section="Spoken Languages",
            changes_log=changes_log,
            original_fallback=orig_spoken,
        )

    rendered_skills = {
        "programming_languages": rendered_pills,
        "frameworks_and_tools": rendered_tools,
        "core_concepts": rendered_concepts,
        "spoken_languages": rendered_spoken,
    }

    # 4. Projects
    rendered_projects = []
    for idx, proj in enumerate(resume.projects):
        orig_proj = None
        if original_resume and original_resume.projects:
            if idx < len(original_resume.projects) and SequenceMatcher(None, _clean_text(proj.name), _clean_text(original_resume.projects[idx].name)).ratio() >= 0.40:
                orig_proj = original_resume.projects[idx]
            else:
                best_p = None
                best_pr = 0.0
                for op in original_resume.projects:
                    r = SequenceMatcher(None, _clean_text(proj.name), _clean_text(op.name)).ratio()
                    if r > best_pr:
                        best_pr = r
                        best_p = op
                if best_pr >= 0.40:
                    orig_proj = best_p
                elif idx < len(original_resume.projects):
                    orig_proj = original_resume.projects[idx]

        rendered_tech = ""
        if proj.technologies:
            orig_tech = orig_proj.technologies if orig_proj else ""
            rendered_tech = highlight_text(
                text=proj.technologies,
                section=f"Project Tech: {proj.name}",
                changes_log=changes_log,
                original_fallback=orig_tech,
            )

        rendered_desc = ""
        if proj.description:
            orig_desc = orig_proj.description if orig_proj else ""
            rendered_desc = highlight_text(
                text=proj.description,
                section=f"Project Description: {proj.name}",
                changes_log=changes_log,
                original_fallback=orig_desc,
            )

        rendered_bullets = []
        for b_idx, bullet in enumerate(proj.bullets):
            orig_b = ""
            if orig_proj and orig_proj.bullets:
                if b_idx < len(orig_proj.bullets) and SequenceMatcher(None, _clean_text(bullet), _clean_text(orig_proj.bullets[b_idx])).ratio() >= 0.40:
                    orig_b = orig_proj.bullets[b_idx]
                else:
                    best_ob = ""
                    best_obr = 0.0
                    for ob in orig_proj.bullets:
                        r = SequenceMatcher(None, _clean_text(bullet), _clean_text(ob)).ratio()
                        if r > best_obr:
                            best_obr = r
                            best_ob = ob
                    if best_obr >= 0.40:
                        orig_b = best_ob
                    else:
                        orig_b = "New accomplishment bullet added to highlight relevant technical delivery"
            else:
                orig_b = "New project accomplishment added for target role"

            b_html = highlight_text(
                text=bullet,
                section=f"Project Accomplishment: {proj.name}",
                changes_log=changes_log,
                original_fallback=orig_b,
            )
            rendered_bullets.append(b_html)

        rendered_projects.append({
            "name": proj.name,
            "rendered_tech": rendered_tech,
            "rendered_desc": rendered_desc,
            "rendered_bullets": rendered_bullets,
        })

    # 5. Experience
    rendered_experience = []
    for idx, exp in enumerate(resume.experience):
        orig_exp = None
        if original_resume and original_resume.experience:
            if idx < len(original_resume.experience) and SequenceMatcher(None, _clean_text(exp.role), _clean_text(original_resume.experience[idx].role)).ratio() >= 0.40:
                orig_exp = original_resume.experience[idx]
            else:
                best_e = None
                best_er = 0.0
                for oe in original_resume.experience:
                    r = SequenceMatcher(None, _clean_text(f"{exp.role} {exp.company}"), _clean_text(f"{oe.role} {oe.company}")).ratio()
                    if r > best_er:
                        best_er = r
                        best_e = oe
                if best_er >= 0.40:
                    orig_exp = best_e
                elif idx < len(original_resume.experience):
                    orig_exp = original_resume.experience[idx]

        rendered_bullets = []
        for b_idx, bullet in enumerate(exp.bullets):
            orig_b = ""
            if orig_exp and orig_exp.bullets:
                if b_idx < len(orig_exp.bullets) and SequenceMatcher(None, _clean_text(bullet), _clean_text(orig_exp.bullets[b_idx])).ratio() >= 0.40:
                    orig_b = orig_exp.bullets[b_idx]
                else:
                    best_ob = ""
                    best_obr = 0.0
                    for ob in orig_exp.bullets:
                        r = SequenceMatcher(None, _clean_text(bullet), _clean_text(ob)).ratio()
                        if r > best_obr:
                            best_obr = r
                            best_ob = ob
                    if best_obr >= 0.40:
                        orig_b = best_ob
                    else:
                        orig_b = "New experience bullet added to demonstrate required expertise"
            else:
                orig_b = "New experience bullet added to demonstrate required expertise"

            b_html = highlight_text(
                text=bullet,
                section=f"Experience: {exp.role} at {exp.company}",
                changes_log=changes_log,
                original_fallback=orig_b,
            )
            rendered_bullets.append(b_html)

        rendered_experience.append({
            "role": exp.role,
            "company": exp.company,
            "date_range": exp.date_range,
            "rendered_bullets": rendered_bullets,
        })

    # 6. Additional Sections (Military, Soft Skills, Languages, etc.)
    rendered_additional = []
    for idx, sec in enumerate(resume.additional_sections):
        orig_sec = (
            original_resume.additional_sections[idx]
            if original_resume and idx < len(original_resume.additional_sections)
            else None
        )

        rendered_items = []
        for i_idx, item in enumerate(sec.items):
            orig_item = ""
            if orig_sec and orig_sec.items:
                if i_idx < len(orig_sec.items) and SequenceMatcher(None, _clean_text(item), _clean_text(orig_sec.items[i_idx])).ratio() >= 0.40:
                    orig_item = orig_sec.items[i_idx]
                else:
                    best_oi = ""
                    best_oir = 0.0
                    for oi in orig_sec.items:
                        r = SequenceMatcher(None, _clean_text(item), _clean_text(oi)).ratio()
                        if r > best_oir:
                            best_oir = r
                            best_oi = oi
                    if best_oir >= 0.40:
                        orig_item = best_oi
                    else:
                        orig_item = "New leadership accomplishment added"

            item_html = highlight_text(
                text=item,
                section=sec.title,
                changes_log=changes_log,
                original_fallback=orig_item,
            )
            rendered_items.append(item_html)

        rendered_additional.append({
            "title": sec.title,
            "rendered_items": rendered_items,
        })

    template = Template(INTERACTIVE_RESUME_TEMPLATE)
    html_content = template.render(
        resume=resume,
        rendered_summary=rendered_summary,
        rendered_education=rendered_education,
        rendered_skills=rendered_skills,
        rendered_projects=rendered_projects,
        rendered_experience=rendered_experience,
        rendered_additional=rendered_additional,
    )

    output_html_path.write_text(html_content, encoding="utf-8")
    return output_html_path


def build_interactive_pptx_diff_html(
    tailored_res: Any,
    original_data: dict[str, Any],
    output_html_path: Path,
    candidate_name: str = "",
) -> Path:
    """
    Constructs an interactive resume preview for PPTX design-preserving runs,
    converting PPTX extracted and tailored sections into a complete resume structure.
    """
    # Build projects
    projects = []
    for p in getattr(tailored_res, "academic_projects", []):
        name_clean = p.title_suffix.lstrip(" |").strip() if getattr(p, "title_suffix", "") else "Project"
        projects.append(
            ProjectItem(
                name=name_clean,
                technologies=p.title_suffix.strip() if getattr(p, "title_suffix", "") else "",
                description=p.description if getattr(p, "description", "") else "",
            )
        )

    # Build experience
    exp_bullets = getattr(tailored_res, "experience_bullets", [])
    experience = [
        ExperienceItem(
            role="Technical Experience",
            company="Engineering Accomplishments",
            bullets=exp_bullets,
        )
    ]

    # Build education
    coursework = getattr(tailored_res, "coursework_line", "")
    education = [
        EducationItem(
            degree="Academic Background & Studies",
            institution="University / Higher Education",
            details=coursework,
        )
    ]

    # Build skills
    skills = SkillCategories(
        programming_languages=getattr(tailored_res, "ordered_languages", []),
        frameworks_and_tools=getattr(tailored_res, "tools_lines", []),
        core_concepts=getattr(tailored_res, "core_concepts_lines", []),
    )

    # Additional sections (e.g. military bullets)
    additional = []
    mil_bullets = getattr(tailored_res, "military_bullets", [])
    if mil_bullets:
        additional.append(
            AdditionalSection(
                title="Leadership, Extracurricular & Military Experience",
                items=mil_bullets,
            )
        )

    tailored_resume = UniversalResume(
        contact=ContactInfo(name=candidate_name or "Tailored Resume Preview"),
        skills=skills,
        experience=experience,
        projects=projects,
        education=education,
        additional_sections=additional,
    )

    # Build original resume equivalent for precise fallback diffing
    orig_projects = []
    for op in original_data.get("academic_projects", []):
        orig_projects.append(
            ProjectItem(
                name=op.get("title_line", "Project"),
                description=op.get("description", ""),
            )
        )

    orig_resume = UniversalResume(
        contact=ContactInfo(name=candidate_name or "Original Resume"),
        skills=SkillCategories(
            programming_languages=original_data.get("programming_languages", []),
            frameworks_and_tools=original_data.get("tools_raw", []),
            core_concepts=original_data.get("concepts_raw", []),
        ),
        experience=[
            ExperienceItem(
                role="Technical Experience",
                company="Engineering Accomplishments",
                bullets=original_data.get("experience_bullets", []),
            )
        ],
        projects=orig_projects,
        education=[
            EducationItem(
                degree="Academic Background & Studies",
                institution="University / Higher Education",
                details=original_data.get("coursework", ""),
            )
        ],
        additional_sections=[
            AdditionalSection(
                title="Leadership, Extracurricular & Military Experience",
                items=original_data.get("military_bullets", []),
            )
        ] if original_data.get("military_bullets") else [],
    )

    changes_log = getattr(tailored_res, "changes_log", [])
    return build_interactive_resume_diff_html(
        resume=tailored_resume,
        changes_log=changes_log,
        output_html_path=output_html_path,
        original_resume=orig_resume,
    )


def build_interactive_diff_html(
    title: str,
    sections: list[dict[str, Any]],
    changes_log: list[Any],
    output_html_path: Path,
) -> Path:
    """
    Backward-compatible wrapper for raw section lists.
    Ensures every item is evaluated with fuzzy and substring matching.
    """
    rendered_sections = []
    for sec in sections:
        sec_title = sec.get("title", "Section")
        items_html = []
        for item in sec.get("items", []):
            item_text = item if isinstance(item, str) else item.get("text", "")
            highlighted = highlight_text(item_text, sec_title, changes_log)
            items_html.append(f"<li>{highlighted}</li>")

        rendered_sections.append(f"""
        <div class="section">
          <h2 class="section-title">{html.escape(sec_title)}</h2>
          <ul style="list-style-type: disc; padding-left: 20px;">
            {''.join(items_html)}
          </ul>
        </div>
        """)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1e293b;
    background: #ffffff;
    font-size: 9.5pt;
    line-height: 1.45;
    padding: 24px;
  }}
  .change-highlight {{
    background-color: #dcfce7 !important;
    border-bottom: 2px solid #22c55e !important;
    padding: 1px 4px;
    border-radius: 4px;
    cursor: help;
  }}
  .change-highlight:hover {{
    background-color: #bbf7d0 !important;
  }}
  #tooltip {{
    position: fixed;
    display: none;
    z-index: 9999;
    max-width: 380px;
    background: #0f172a;
    color: #f8fafc;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 8.5pt;
    border: 1px solid #334155;
    pointer-events: none;
  }}
  .tt-sec {{ color: #38bdf8; font-weight: 700; font-size: 7.5pt; text-transform: uppercase; margin-bottom: 4px; }}
  .tt-from {{ color: #cbd5e1; border-left: 2px solid #ef4444; padding-left: 6px; margin-bottom: 6px; }}
  .tt-why {{ color: #f1f5f9; border-left: 2px solid #22c55e; padding-left: 6px; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  {''.join(rendered_sections)}
  <div id="tooltip">
    <div class="tt-sec" id="ttSec"></div>
    <div class="tt-from"><strong>Changed from:</strong><p id="ttOrig"></p></div>
    <div class="tt-why"><strong>💡 Why:</strong><p id="ttRat"></p></div>
  </div>
  <script>
    const tooltip = document.getElementById('tooltip');
    const ttSec = document.getElementById('ttSec');
    const ttOrig = document.getElementById('ttOrig');
    const ttRat = document.getElementById('ttRat');
    document.querySelectorAll('.change-highlight').forEach(el => {{
      el.addEventListener('mouseenter', (e) => {{
        ttSec.textContent = e.currentTarget.getAttribute('data-section') || 'Section';
        ttOrig.textContent = e.currentTarget.getAttribute('data-original') || 'Original';
        ttRat.textContent = e.currentTarget.getAttribute('data-rationale') || 'Aligned with JD.';
        tooltip.style.display = 'block';
      }});
      el.addEventListener('mousemove', (e) => {{
        tooltip.style.left = (e.clientX + 15) + 'px';
        tooltip.style.top = (e.clientY + 15) + 'px';
      }});
      el.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
    }});
  </script>
</body>
</html>
"""
    output_html_path.write_text(full_html, encoding="utf-8")
    return output_html_path
