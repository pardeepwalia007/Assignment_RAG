# ingestion.py (STEP 1) — accept PDFs + CSVs, return (csv_paths, pdf_paths)
from pathlib import Path
from typing import List, Tuple
from pypdf import PdfReader

def ingest_files(paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    Splits input paths into CSVs + PDFs.
    Returns: (csv_paths, pdf_paths)
    """
    csv_paths: List[str] = []
    pdf_paths: List[str] = []

    for p in paths:
        ext = Path(p).suffix.lower()
        if ext == ".csv":
            csv_paths.append(str(p))
        elif ext == ".pdf":
            pdf_paths.append(str(p))
        else:
            raise ValueError(f"Unsupported file type: {ext} for path: {p}")

    if len(pdf_paths) > 6:
        raise ValueError("Maximum 6 PDFs allowed")

    # Validate PDFs (keep only usable ones)
    valid_pdfs, errors, is_usable = valid_pdf(pdf_paths)

    if not is_usable:
        raise ValueError(f"No usable PDFs found. Errors: {errors}")

    # return csvs as-is (we validate them later in sql_engine)
    return csv_paths, [str(p) for p in valid_pdfs]


def valid_pdf(pdf_paths: List[str], min_characters: int = 20):
    """
    Validates PDFs for extractable text and usability.
    """
    valid_pdfs = []
    errors = []

    for pdf_path in pdf_paths:
        pdf_path = Path(pdf_path)

        try:
            if pdf_path.stat().st_size == 0:
                raise ValueError("empty file (0 bytes)")

            reader = PdfReader(pdf_path)
            if len(reader.pages) == 0:
                raise ValueError("no pages")

            total_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    total_text += text

            if len(total_text.strip()) < min_characters:
                raise ValueError("no readable text (likely scanned PDF)")

            valid_pdfs.append(pdf_path)

        except Exception as e:
            errors.append({"file": str(pdf_path), "error": str(e)})

    is_usable = len(valid_pdfs) > 0
    return valid_pdfs, errors, is_usable


