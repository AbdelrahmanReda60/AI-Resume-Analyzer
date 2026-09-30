import logging
import os
import re
import uuid
import pdfplumber
import docx
from fastapi import UploadFile, HTTPException, status
from app.config import settings

logger = logging.getLogger("ai_resume_analyzer.upload")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def sanitize_filename(raw: str) -> str:
    """Strip any directory components and dangerous characters from a client filename."""
    name = os.path.basename(raw or "").replace("\\", "/")
    name = os.path.basename(name)
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in (" ", "-", "_", ".", "(", ")"))
    cleaned = cleaned.strip().lstrip(".")
    return cleaned or "uploaded_resume.pdf"


def validate_and_parse_resume(file: UploadFile) -> tuple[str, str, str, int, str]:
    """
    Validates file extension, magic bytes, size limit, and extracts text content.
    Returns: (saved_path, original_filename, file_type, file_size, extracted_text)
    """
    filename = sanitize_filename(file.filename or "uploaded_resume.pdf")
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF (.pdf) and DOCX (.docx) files are supported."
        )

    # Read binary content to check magic bytes and size
    content = file.file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # Content Too Large (HTTP_413_REQUEST_ENTITY_TOO_LARGE is deprecated)
            detail="File size exceeds maximum limit of 5MB."
        )

    # Magic Bytes verification
    if ext == "pdf":
        if not content.startswith(b"%PDF"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header does not match valid PDF format."
            )
        # Encrypted/password-protected documents cannot be parsed without the
        # password — detect before handing to pdfminer so the user gets an
        # actionable message instead of a generic parser failure.
        if re.search(rb"/Encrypt\s+\d+\s+\d+\s+R", content):
            # No file has been written yet, so there is nothing to clean up.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The document is password-protected. "
                       "Please remove the password and upload it again."
            )
    elif ext == "docx":
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header does not match valid DOCX archive format."
            )

    # Save file securely with UUID (never trust the client-supplied name for the path)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(saved_path, "wb") as f:
        f.write(content)

    # Extract text content; never leave an orphan file behind if parsing fails
    try:
        extracted_text = extract_text_from_file(saved_path, ext)
    except HTTPException:
        _remove_quietly(saved_path)
        raise
    except Exception:
        _remove_quietly(saved_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process the uploaded document."
        )

    if not extracted_text or len(extracted_text.strip()) < 20:
        _remove_quietly(saved_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to extract text from document. Please ensure the file is not scanned, empty, or password-protected."
        )

    return saved_path, filename, ext, file_size, extracted_text


def _remove_quietly(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

def _friendly_pdf_error(exc: Exception) -> str:
    """Map low-level pdfplumber/pdfminer failures to a message a user can act on."""
    name = type(exc).__name__
    text = str(exc).lower()
    if "password" in name.lower() or "encrypt" in name.lower() or "password" in text or "encrypt" in text:
        return ("The document is password-protected. "
                "Please remove the password and upload it again.")
    if "syntax" in name.lower() or "xref" in text or "eof" in text or "cannot read" in text:
        return "The document appears to be corrupted or is not a valid PDF."
    return "Unable to process the uploaded document."


def extract_text_from_file(file_path: str, ext: str) -> str:
    """Extracts plain text from PDF or DOCX file."""
    text_chunks = []
    try:
        if ext == "pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        text_chunks.append(txt)
        elif ext == "docx":
            doc = docx.Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    text_chunks.append(paragraph.text)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - pdfminer raises many exception types
        message = _friendly_pdf_error(e) if ext == "pdf" else "Unable to process the uploaded document."
        logger.info("Resume extraction failed (%s): %s", ext, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return "\n".join(text_chunks)
