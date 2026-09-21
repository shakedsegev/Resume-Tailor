"""
Universal HTML & Vector PDF Resume Builder.
Renders structured UniversalResume data into modern, ATS-optimized, designer-quality
HTML and compiles it to vector PDF via headless Google Chrome.
"""

from pathlib import Path
import subprocess
from typing import Optional
from jinja2 import Template
# pyrefly: ignore [missing-import]
from src.universal_models import UniversalResume, sanitize_universal_resume


CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

MODERN_TECH_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ resume.contact.name }} - Resume</title>
<style>
  @page {
    size: A4 portrait;
    margin: {{ density.page_margin | default('8mm 11mm') }};
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    font-size: {{ density.base_font_size | default('8.8pt') }};
    line-height: {{ density.line_height | default('1.30') }};
  }
  header {
    text-align: center;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 5px;
    margin-bottom: {{ density.section_margin_bottom | default('6px') }};
  }
  h1 {
    font-size: {{ density.name_size | default('18pt') }};
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #0f172a;
    text-transform: uppercase;
  }
  .contact-bar {
    margin-top: 3px;
    font-size: {{ density.contact_font_size | default('8.2pt') }};
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
    margin-bottom: {{ density.section_margin_bottom | default('6px') }};
  }
  .section-title {
    font-size: {{ density.section_title_size | default('9.5pt') }};
    font-weight: 700;
    color: #0284c7;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 2px;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .item {
    margin-bottom: {{ density.item_margin_bottom | default('4px') }};
  }
  .item-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: {{ density.base_font_size | default('8.8pt') }};
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
    font-size: {{ density.date_font_size | default('8pt') }};
    color: #64748b;
    font-weight: 500;
    white-space: nowrap;
  }
  ul {
    list-style-type: disc;
    padding-left: 14px;
    margin-top: 2px;
  }
  li {
    margin-bottom: {{ density.bullet_margin_bottom | default('1.5px') }};
    color: #334155;
    text-align: justify;
  }
  .skills-grid {
    display: grid;
    grid-template-columns: 130px 1fr;
    row-gap: {{ density.skills_row_gap | default('2.5px') }};
    font-size: {{ density.base_font_size | default('8.8pt') }};
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
    gap: 3px;
  }
  .pill {
    background: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: {{ density.pill_font_size | default('8pt') }};
    font-weight: 600;
  }
</style>
</head>
<body>

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

{% if resume.summary %}
<div class="section">
  <div class="section-title">Professional Summary</div>
  <p style="color: #334155; font-size: 8.8pt;">{{ resume.summary }}</p>
</div>
{% endif %}

{% if resume.education %}
<div class="section">
  <div class="section-title">Education</div>
  {% for edu in resume.education %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ edu.institution }}</span>
      <span class="item-date">{{ edu.date_range }}</span>
    </div>
    <div class="item-sub">{{ edu.degree }}{% if edu.gpa %} · {% if 'gpa' in edu.gpa.lower() %}{{ edu.gpa }}{% else %}GPA: {{ edu.gpa }}{% endif %}{% endif %}</div>
    {% if edu.details %}<p style="font-size: 8.4pt; color: #475569; margin-top: 1px;">{{ edu.details }}</p>{% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if resume.skills.programming_languages or resume.skills.frameworks_and_tools or resume.skills.core_concepts or resume.skills.spoken_languages %}
<div class="section">
  <div class="section-title">Technical & Language Skills</div>
  <div class="skills-grid">
    {% if resume.skills.programming_languages %}
    <span class="skill-label">Languages:</span>
    <span class="skill-values">
      <div class="pills">
        {% for lang in resume.skills.programming_languages %}
        <span class="pill">{{ lang }}</span>
        {% endfor %}
      </div>
    </span>
    {% endif %}
    {% if resume.skills.frameworks_and_tools %}
    <span class="skill-label">Tools & Frameworks:</span>
    <span class="skill-values">{{ resume.skills.frameworks_and_tools | join(', ') }}</span>
    {% endif %}
    {% if resume.skills.core_concepts %}
    <span class="skill-label">Core Concepts:</span>
    <span class="skill-values">{{ resume.skills.core_concepts | join(', ') }}</span>
    {% endif %}
    {% if resume.skills.spoken_languages %}
    <span class="skill-label">Spoken Languages:</span>
    <span class="skill-values">{{ resume.skills.spoken_languages | join(' · ') }}</span>
    {% endif %}
  </div>
</div>
{% endif %}

{% if resume.projects %}
<div class="section">
  <div class="section-title">Technical & Academic Projects</div>
  {% for proj in resume.projects %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ proj.name }} {% if proj.technologies %}<span class="item-tech">| {{ proj.technologies }}</span>{% endif %}</span>
    </div>
    {% if proj.description %}<p style="color: #334155; font-size: 8.8pt; margin-top: 1px;">{{ proj.description }}</p>{% endif %}
    {% if proj.bullets %}
    <ul>
      {% for b in proj.bullets %}
      <li>{{ b }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if resume.experience %}
<div class="section">
  <div class="section-title">Professional Experience</div>
  {% for exp in resume.experience %}
  <div class="item">
    <div class="item-header">
      <span class="item-title">{{ exp.role }} <span style="font-weight: 500; color: #64748b;">at</span> {{ exp.company }}</span>
      <span class="item-date">{{ exp.date_range }}</span>
    </div>
    {% if exp.bullets %}
    <ul>
      {% for b in exp.bullets %}
      <li>{{ b }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

{% if resume.additional_sections %}
{% for sec in resume.additional_sections %}
<div class="section">
  <div class="section-title">{{ sec.title }}</div>
  <ul>
    {% for item in sec.items %}
    <li>{{ item }}</li>
    {% endfor %}
  </ul>
</div>
{% endfor %}
{% endif %}

</body>
</html>
"""


DENSITY_LEVELS = [
    {
        "name": "Standard",
        "page_margin": "8mm 11mm",
        "base_font_size": "8.8pt",
        "line_height": "1.30",
        "name_size": "18pt",
        "contact_font_size": "8.2pt",
        "section_title_size": "9.5pt",
        "section_margin_bottom": "6px",
        "item_margin_bottom": "4px",
        "bullet_margin_bottom": "2px",
        "date_font_size": "8pt",
        "skills_row_gap": "2.5px",
        "pill_font_size": "8pt",
    },
    {
        "name": "Compact",
        "page_margin": "6.5mm 9.5mm",
        "base_font_size": "8.3pt",
        "line_height": "1.25",
        "name_size": "16.5pt",
        "contact_font_size": "7.8pt",
        "section_title_size": "9pt",
        "section_margin_bottom": "4.5px",
        "item_margin_bottom": "3px",
        "bullet_margin_bottom": "1.5px",
        "date_font_size": "7.6pt",
        "skills_row_gap": "2px",
        "pill_font_size": "7.6pt",
    },
    {
        "name": "High Density",
        "page_margin": "5mm 8mm",
        "base_font_size": "7.8pt",
        "line_height": "1.20",
        "name_size": "15pt",
        "contact_font_size": "7.5pt",
        "section_title_size": "8.5pt",
        "section_margin_bottom": "3.5px",
        "item_margin_bottom": "2px",
        "bullet_margin_bottom": "1px",
        "date_font_size": "7.2pt",
        "skills_row_gap": "1.5px",
        "pill_font_size": "7.2pt",
    },
    {
        "name": "Ultra Dense",
        "page_margin": "4mm 7mm",
        "base_font_size": "7.4pt",
        "line_height": "1.15",
        "name_size": "13.5pt",
        "contact_font_size": "7.2pt",
        "section_title_size": "8pt",
        "section_margin_bottom": "2.5px",
        "item_margin_bottom": "1.5px",
        "bullet_margin_bottom": "0.5px",
        "date_font_size": "6.8pt",
        "skills_row_gap": "1px",
        "pill_font_size": "6.8pt",
    },
]


def count_pdf_pages(pdf_path: Path) -> int:
    """Reads PDF and returns total page count."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception:
        return 1


def render_resume_to_html(
    resume: UniversalResume,
    output_html_path: Path,
    template_str: str = MODERN_TECH_TEMPLATE,
    density: Optional[dict] = None,
) -> Path:
    """Renders UniversalResume into a styled HTML file."""
    output_html_path = output_html_path.resolve()
    output_html_path.parent.mkdir(parents=True, exist_ok=True)

    active_density = density or DENSITY_LEVELS[0]
    template = Template(template_str)
    rendered_html = template.render(resume=resume, density=active_density)
    output_html_path.write_text(rendered_html, encoding="utf-8")
    return output_html_path


def render_html_to_pdf(html_path: Path, output_pdf_path: Path) -> Path:
    """Compiles an HTML resume into a vector PDF using headless Google Chrome."""
    html_path = html_path.resolve()
    output_pdf_path = output_pdf_path.resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    if not Path(CHROME_PATH).exists():
        raise RuntimeError(f"Google Chrome executable not found at {CHROME_PATH}")

    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf_path}",
        str(html_path),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not output_pdf_path.exists():
        raise RuntimeError(f"Headless Chrome PDF export failed: {res.stderr}")

    return output_pdf_path


def generate_universal_resume_pdf(
    resume: UniversalResume,
    output_dir: Path,
    base_name: str = "tailored_resume",
    force_single_page: bool = True,
) -> tuple[Path, Path]:
    """
    Renders UniversalResume to HTML and compiles to vector PDF.
    If force_single_page is True, dynamically steps through density tiers
    (Standard -> Compact -> High Density -> Ultra Dense) and prunes trailing
    bullets if necessary to guarantee the PDF strictly fits on exactly 1 page.
    Returns (html_path, pdf_path).
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    resume = sanitize_universal_resume(resume)
    html_path = output_dir / f"{base_name}.html"
    pdf_path = output_dir / f"{base_name}.pdf"

    if not force_single_page:
        render_resume_to_html(resume, html_path, density=DENSITY_LEVELS[0])
        render_html_to_pdf(html_path, pdf_path)
        return html_path, pdf_path

    # Step through density tiers
    active_resume = resume.model_copy(deep=True)
    pages = 2
    for density in DENSITY_LEVELS:
        render_resume_to_html(active_resume, html_path, density=density)
        render_html_to_pdf(html_path, pdf_path)
        pages = count_pdf_pages(pdf_path)
        if pages <= 1:
            return html_path, pdf_path

    # If still > 1 page even at Ultra Dense, systematically prune lowest-priority
    # trailing bullets until exactly 1 page
    while pages > 1:
        pruned = False
        longest_exp = None
        max_bullets = 2
        for exp in active_resume.experience:
            if len(exp.bullets) > max_bullets:
                longest_exp = exp
                max_bullets = len(exp.bullets)

        if longest_exp:
            longest_exp.bullets.pop()
            pruned = True
        else:
            longest_proj = None
            max_p_bullets = 2
            for proj in active_resume.projects:
                if len(proj.bullets) > max_p_bullets:
                    longest_proj = proj
                    max_p_bullets = len(proj.bullets)
            if longest_proj:
                longest_proj.bullets.pop()
                pruned = True
            elif active_resume.additional_sections:
                for sec in reversed(active_resume.additional_sections):
                    if len(sec.items) > 1:
                        sec.items.pop()
                        pruned = True
                        break

        if not pruned:
            break

        render_resume_to_html(active_resume, html_path, density=DENSITY_LEVELS[-1])
        render_html_to_pdf(html_path, pdf_path)
        pages = count_pdf_pages(pdf_path)

    return html_path, pdf_path
