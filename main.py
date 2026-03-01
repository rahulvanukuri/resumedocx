from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from docxtpl import DocxTemplate, RichText
from io import BytesIO
import base64
from pathlib import Path
import re

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"  # create a folder named templates in your repo


class GenerateRequest(BaseModel):
    context: dict


class GenerateResponse(BaseModel):
    filename: str
    docx_b64: str


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++ HELPER FUNCTION (Parses Markdown)
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def attempt_to_parse_markdown(text_value: str) -> RichText:
    """
    Tries to find valid **(.*?)** tags.
    If successful, returns a RichText object.
    If no valid tags are found, it returns a RichText object
    containing the original, plain string.
    """
    rt = RichText()
    last_index = 0

    matches = list(re.finditer(r"\*\*(.*?)\*\*", text_value))

    # If no valid pairs are found, return the entire string as plain RichText
    if not matches:
        rt.add(text_value, font="Calibri", size=24)
        return rt

    # If we find matches, build the RichText object
    for match in matches:
        start_of_match = match.start()
        if start_of_match > last_index:
            rt.add(text_value[last_index:start_of_match], font="Calibri", size=24)

        bold_text = match.group(1)
        if bold_text:
            rt.add(bold_text, bold=True, font="Calibri", size=24)

        last_index = match.end()

    if last_index < len(text_value):
        rt.add(text_value[last_index:], font="Calibri", size=24)

    return rt


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++ CONTEXT PROCESSOR
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def process_context_for_richtext(context_data: dict) -> dict:
    """
    Scans the context dict.
    Converts target string lists into RichText objects.
    Leaves TECHNICAL_SKILLS as plain strings for reliable table rendering.
    """
    processed_context = {}

    # Keys that are lists of bullet strings we want to convert to RichText
    richtext_list_keys = (
        "SUMMARY",
        "RESPONSIBILITES_CO",
        "RESPONSIBILITES_CI",
        "RESPONSIBILITES_CS",
    )

    for key, value in context_data.items():
        # Convert bullet lists (summary + responsibilities) into RichText objects
        if key in richtext_list_keys and isinstance(value, list):
            processed_list = []
            for item in value:
                if isinstance(item, str):
                    processed_list.append(attempt_to_parse_markdown(item))
                else:
                    processed_list.append(item)
            processed_context[key] = processed_list
            continue

        # Keep skills plain text (important for Word table cells)
        if key == "TECHNICAL_SKILLS" and isinstance(value, list):
            processed_context[key] = value
            continue

        # Default: keep as-is
        processed_context[key] = value

    return processed_context


@app.post("/generate-docx/{template_name}", response_model=GenerateResponse)
def generate_docx(payload: GenerateRequest, template_name: str):
    template_file = (TEMPLATES_DIR / template_name).with_suffix(".docx")

    if not template_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template file not found: {template_file}",
        )

    try:
        doc = DocxTemplate(str(template_file))

        final_context = process_context_for_richtext(payload.context)
        doc.render(final_context)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        docx_b64 = base64.b64encode(buffer.read()).decode("utf-8")

        return GenerateResponse(
            filename=f"{template_name}.docx",
            docx_b64=docx_b64,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating document: {str(e)}")


@app.get("/health")
def health():
    return {"ok": True}
