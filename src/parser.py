
from dataclasses import asdict
from src.models import TextBlock
from src.models import ResumeShape
from src.models import ResumeContent
from pathlib import Path
import json

# pyrefly: ignore [missing-import]
from pptx import Presentation


def parse_resume(resume_path: Path) -> ResumeContent:
    prs = Presentation(resume_path)
    resume_content = ResumeContent()
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                resume_shape = ResumeShape(name=shape.name)
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text.strip():
                            text_block = TextBlock(
                                text=run.text,
                                bold=run.font.bold or False,
                                font_size=(run.font.size or 0) / 12700,
                            )
                            resume_shape.blocks.append(text_block)
                if resume_shape.blocks:
                    resume_content.shapes.append(resume_shape)
    return resume_content


def save_resume(resume_content: ResumeContent, output_path: Path) -> None:
    """
    Saves the resume content to a JSON file.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(resume_content), f, indent=4, ensure_ascii=False)