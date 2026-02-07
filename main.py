from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from docxtpl import DocxTemplate, RichText  # <--- Make sure RichText is imported
from io import BytesIO
import base64
import os
import re

app = FastAPI()



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
    
    matches = list(re.finditer(r'\*\*(.*?)\*\*', text_value))
    
    # If no valid pairs are found, return the *entire* string
    # as a single, plain RichText object.
    if not matches:
        rt.add(text_value, font='Calibri', size=24)
        return rt
        
    # If we find matches, build the RichText object
    for match in matches:
        start_of_match = match.start()
        if start_of_match > last_index:
            rt.add(text_value[last_index:start_of_match], font='Calibri',
                  size=24)
        
        bold_text = match.group(1)
        if bold_text:
            rt.add(bold_text, bold=True,font='Calibri',
                  size=24)
        
        last_index = match.end()
        
    if last_index < len(text_value):
        rt.add(text_value[last_index:], font='Calibri',
                  size=24)
        
    return rt

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++ CONTEXT PROCESSOR (WITH THE FINAL FIX)
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def process_context_for_richtext(context_data: dict) -> dict:
    """
    Recursively scans the context dict.
    Converts *all* target strings into RichText objects.
    """
    processed_context = {}
    for key, value in context_data.items():
        # --- Handle target fields: RESPONSIBILITES (lists) ---
        if key in ("SUMMARY","RESPONSIBILITES_AL", "RESPONSIBILITES_FD", "RESPONSIBILITES_SM") and isinstance(value, list):
            processed_list = []
            for item in value:
                if isinstance(item, str):
                    # Always append a RichText object
                    processed_list.append(attempt_to_parse_markdown(item))
                else:
                    processed_list.append(item) # for nulls, etc.
            processed_context[key] = processed_list
        
        
        # --- Keep all other fields as-is ---
        else:
            processed_context[key] = value
            
    return processed_context
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

@app.post("/generate-docx/{template_path}", response_model=GenerateResponse)
def generate_docx(payload: GenerateRequest, template_path: str):
    template_path = f"./{template_path}".strip() + ".docx"
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail=f"Template file not found: {template_path}")

    try:
        doc = DocxTemplate(template_path)
        
        # We must process the *entire* context object
        final_context = process_context_for_richtext(payload.context)

        # Render with the *new* context
        doc.render(final_context)
        doc.save("Ganesh_Gouru_Resume.docx")

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        docx_b64 = base64.b64encode(buffer.read()).decode("utf-8")

        return GenerateResponse(
            filename="Ganesh_Gouru_Resume.docx",
            docx_b64=docx_b64
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating document: {str(e)}")

@app.get("/health")
def health():
    return {"ok": True}