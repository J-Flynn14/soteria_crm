import logging, PyPDF2, pdfkit, gc, os, shutil
from typing import Optional, Tuple
from django.utils.crypto import get_random_string
from io import BytesIO

logger = logging.getLogger(__name__)

# Configure pdfkit (ensure the path to wkhtmltopdf is correct)
pdfkit_config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

def html_to_pdf_bytes(html_content: str) -> BytesIO:
    """
    Convert HTML content to PDF bytes wrapped in a BytesIO buffer.
    """
    try:
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=pdfkit_config)
    except Exception as e:
        logger.error(f"❌ Error converting HTML to PDF: {e}")
        raise
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)
    return buffer

def pdf_to_text(pdf_file) -> str:
    """
    Extract text from a PDF file.
    Accepts both file objects (with an 'open' method) and already-open file-like objects.
    """
    f = None
    text = ""
    file_name = getattr(pdf_file, "name", "unknown file")
    try:
        # Open the file if needed.
        f = pdf_file.open('rb') if hasattr(pdf_file, "open") else pdf_file
        pdf_reader = PyPDF2.PdfReader(f)
        text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        logger.info(f"✅ Successfully extracted text from file object")
    except Exception as e:
        logger.error(f"❌ Error extracting text from {file_name}: {e}")
    finally:
        if f is not None:
            try:
                if not f.closed:
                    f.close()
            except Exception:
                pass
            gc.collect()
    return text

def extract_body_html(html_content: str) -> str:
    start_tag = "<body>"
    end_tag = "</body>"
    
    start_index = html_content.find(start_tag)
    if start_index == -1:
        return ""
    
    end_index = html_content.find(end_tag, start_index)
    if end_index == -1:
        return ""
    
    return html_content[start_index:end_index + len(end_tag)].strip()

def is_file_locked(filepath: str) -> bool:
    try:
        with open(filepath, 'a'):
            return False
    except IOError:
        return True

def get_file_upload_to(candidate, filename:str) -> str:
        return f'{candidate.first_name}_{candidate.last_name}/{filename}'
def clean_ai_output(raw_output: str) -> str:
    """Remove markdown fences from AI output."""
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned

def clean_str(value) -> Optional[str]:
    if isinstance(value, str):
        val = value.strip()
        return val if val else None
    elif isinstance(value, list):
        joined = ", ".join(str(item).strip() for item in value if str(item).strip())
        return joined if joined else None
    return value

def clean_decimal(value) -> Optional[float]:
    if not value or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
    
def normalise_address_postcode(address:str, postcode:Optional[str]) -> Tuple[str, str]:
    normalized_address = " ".join(address.lower().split()) if address else ""
    normalized_postcode = " ".join(postcode.lower().split()) if postcode else ""
    return (normalized_address, normalized_postcode)