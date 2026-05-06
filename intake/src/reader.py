"""
reader.py
---------
Extracts raw text from any dropped file.
Supports: .txt, .md, .py, .json, .pdf, and anything else as raw text.
"""

from pathlib import Path
from loguru import logger


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        try:
            from pdfminer.high_level import extract_text as pdf_extract
            return pdf_extract(str(file_path))
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return ""

    # Everything else — just read as text
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Failed to read {file_path.name}: {e}")
        return ""
