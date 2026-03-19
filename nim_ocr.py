"""
nim_ocr.py — PDF text extraction with NIM OCR fallback.

Extracts text from provincial tracker PDFs, IAAC documents, municipal budgets.
Most government PDFs have embedded text — PyMuPDF handles those at zero API cost.
NIM OCR (nvidia/ocdrnet) is used only for scanned/image-only pages.

Strategy per page:
  1. PyMuPDF native text extraction (fast, free)
  2. If page has < 50 chars of text, render to image and send to NIM OCR
  3. Combine all page text
  4. Send to K2.5 for structured project extraction (via nim_client)

Pipeline works without this module — PDFs just remain unprocessed.

Usage:
    from nim_ocr import extract_text_from_pdf, extract_projects_from_pdf

    # Just get text
    pages = extract_text_from_pdf("https://example.com/report.pdf")

    # Full pipeline: fetch → extract text → K2.5 project extraction
    projects = extract_projects_from_pdf(
        "https://example.com/report.pdf",
        province="British Columbia", sector="infrastructure",
    )
"""

import base64
import io
import json
import logging
import re

import requests

from pipeline_config import (
    NIM_OCR_ENABLED,
    NIM_OCR_URL,
    NVIDIA_API_KEY,
)

logger = logging.getLogger(__name__)

# Try PyMuPDF import
try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False
    logger.info("PyMuPDF not installed — PDF text extraction unavailable")

MIN_TEXT_LENGTH = 50    # pages with less text trigger OCR
OCR_DPI = 200           # resolution for page rasterization
FETCH_TIMEOUT = 30      # seconds for PDF download
MAX_PAGES = 50          # skip PDFs longer than this
MAX_PDF_BYTES = 50_000_000  # 50 MB cap

_HEADERS = {
    "User-Agent": "SignalDispatch/1.0 (Canadian infrastructure pipeline)",
}


# ── PDF Source Registry ───────────────────────────────────────────────────
# Curated list of known government PDF sources for Canadian capital projects.
# URLs point to landing pages — actual PDF links change with each publication.
# The pipeline can periodically check these pages for new PDF publications.

PDF_SOURCES = [
    {
        "name": "BC Major Projects Inventory",
        "landing_url": "https://www2.gov.bc.ca/gov/content/data/statistics/economy/bc-major-projects-inventory",
        "province": "British Columbia",
        "frequency": "quarterly",
        "notes": "Published by BC Stats. Lists all major projects >$15M. PDF linked from landing page.",
    },
    {
        "name": "Alberta Major Projects",
        "landing_url": "https://majorprojects.alberta.ca/",
        "province": "Alberta",
        "frequency": "semi-annual",
        "notes": "Interactive site with downloadable PDF/Excel. Covers energy, infrastructure, commercial.",
    },
    {
        "name": "Saskatchewan Major Projects",
        "landing_url": "https://www.saskatchewan.ca/business/investment-and-economic-development/major-projects",
        "province": "Saskatchewan",
        "frequency": "annual",
        "notes": "Major project listings. Some data in PDF format.",
    },
    {
        "name": "Ontario Infrastructure Projects",
        "landing_url": "https://www.ontario.ca/page/building-ontario",
        "province": "Ontario",
        "frequency": "varies",
        "notes": "Infrastructure Ontario publishes project updates. Budget documents contain capital plans.",
    },
    {
        "name": "IAAC Environmental Assessments",
        "landing_url": "https://iaac-aeic.gc.ca/050/evaluations",
        "province": "National",
        "frequency": "ongoing",
        "notes": "Federal Impact Assessment Registry. Project documents include PDFs with cost/timeline data.",
    },
    {
        "name": "Infrastructure Canada Project Map",
        "landing_url": "https://www.infrastructure.gc.ca/plan/prog-proj-pc-eng.html",
        "province": "National",
        "frequency": "quarterly",
        "notes": "Federal infrastructure program project lists. Downloadable data.",
    },
    {
        "name": "Quebec Plan quebecois des infrastructures",
        "landing_url": "https://www.tresor.gouv.qc.ca/budget-de-depenses/plans-annuels-de-gestion-des-investissements-publics-en-infrastructures/",
        "province": "Quebec",
        "frequency": "annual",
        "notes": "Annual infrastructure investment plan. PDF with all major public projects.",
    },
]


# ── PDF download ──────────────────────────────────────────────────────────

def fetch_pdf(url: str) -> bytes | None:
    """Download a PDF from a URL.

    Returns:
        PDF bytes, or None on failure.
    """
    try:
        resp = requests.get(
            url, timeout=FETCH_TIMEOUT, headers=_HEADERS, stream=True,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            logger.warning(f"URL does not appear to be a PDF: {url} (Content-Type: {content_type})")

        content = resp.content
        if len(content) > MAX_PDF_BYTES:
            logger.warning(f"PDF too large ({len(content)} bytes), skipping: {url}")
            return None

        return content

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch PDF from {url}: {e}")
        return None


# ── Native text extraction (PyMuPDF — zero API cost) ─────────────────────

def _extract_text_native(pdf_bytes: bytes) -> list[dict]:
    """Extract embedded text from PDF pages using PyMuPDF.

    Most government PDFs have embedded text (generated from databases/Word).
    This is fast and free — no API calls needed.

    Returns:
        List of {page: int, text: str} dicts. Pages with no text have empty string.
    """
    if not _HAS_PYMUPDF:
        return []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"PyMuPDF failed to open PDF: {e}")
        return []

    if doc.page_count > MAX_PAGES:
        logger.warning(f"PDF has {doc.page_count} pages (max {MAX_PAGES}), truncating")

    pages = []
    for i in range(min(doc.page_count, MAX_PAGES)):
        try:
            page = doc[i]
            text = page.get_text("text").strip()
            pages.append({"page": i + 1, "text": text})
        except Exception as e:
            logger.debug(f"Failed to extract text from page {i+1}: {e}")
            pages.append({"page": i + 1, "text": ""})

    doc.close()
    return pages


def _render_page_to_png(pdf_bytes: bytes, page_num: int) -> bytes | None:
    """Render a single PDF page to a PNG image for OCR.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_num: 0-indexed page number.

    Returns:
        PNG image bytes, or None on failure.
    """
    if not _HAS_PYMUPDF:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num]
        # Render at OCR_DPI (default 200 — good balance of quality vs size)
        mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception as e:
        logger.debug(f"Failed to render page {page_num} to PNG: {e}")
        return None


# ── NIM OCR (for scanned/image pages only) ────────────────────────────────

def _ocr_image(image_bytes: bytes) -> str:
    """Send an image to NIM OCR (nvidia/ocdrnet) and return extracted text.

    Only called for pages that have no embedded text (scanned documents).

    Args:
        image_bytes: PNG image bytes.

    Returns:
        Extracted text string, or empty string on failure.
    """
    if not NVIDIA_API_KEY:
        logger.debug("NVIDIA_API_KEY not set, skipping OCR")
        return ""

    if not NIM_OCR_ENABLED:
        return ""

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "input": [f"data:image/png;base64,{b64_image}"],
    }

    try:
        resp = requests.post(
            NIM_OCR_URL, headers=headers, json=payload, timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract text from OCR response (format may vary by model version)
        texts = []
        for item in data.get("data", [data]):
            # nvidia/ocdrnet returns text_predictions or similar
            for pred in item.get("text_predictions", item.get("predictions", [])):
                if isinstance(pred, dict):
                    texts.append(pred.get("text", ""))
                elif isinstance(pred, str):
                    texts.append(pred)

            # Fallback: check for flat text field
            if not texts and item.get("text"):
                texts.append(item["text"])

        return " ".join(texts).strip()

    except requests.RequestException as e:
        logger.warning(f"NIM OCR request failed: {e}")
        return ""
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"NIM OCR response parse error: {e}")
        return ""


# ── Orchestrator ──────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_url_or_bytes, source_url: str = "") -> list[dict]:
    """Extract text from a PDF — native first, OCR fallback for image pages.

    Args:
        pdf_url_or_bytes: URL string or raw PDF bytes.
        source_url: Original URL (for logging, if pdf_url_or_bytes is bytes).

    Returns:
        List of {page: int, text: str, method: str} dicts.
        Empty list if extraction fails entirely.
    """
    if not _HAS_PYMUPDF:
        logger.warning("PyMuPDF not installed — cannot process PDFs")
        return []

    # Fetch if URL
    if isinstance(pdf_url_or_bytes, str):
        source_url = pdf_url_or_bytes
        pdf_bytes = fetch_pdf(pdf_url_or_bytes)
        if not pdf_bytes:
            return []
    else:
        pdf_bytes = pdf_url_or_bytes

    # Step 1: Native text extraction
    pages = _extract_text_native(pdf_bytes)
    if not pages:
        return []

    # Step 2: OCR fallback for pages with insufficient text
    ocr_count = 0
    for page_info in pages:
        if len(page_info["text"]) >= MIN_TEXT_LENGTH:
            page_info["method"] = "native"
            continue

        # Try OCR for this page
        png = _render_page_to_png(pdf_bytes, page_info["page"] - 1)
        if png:
            ocr_text = _ocr_image(png)
            if ocr_text:
                page_info["text"] = ocr_text
                page_info["method"] = "ocr"
                ocr_count += 1
                continue

        page_info["method"] = "empty"

    total_text = sum(len(p["text"]) for p in pages)
    label = source_url[:60] if source_url else "PDF"
    logger.info(
        f"PDF extraction: {label} — {len(pages)} pages, "
        f"{total_text} chars, {ocr_count} OCR pages"
    )

    return pages


def extract_projects_from_pdf(
    pdf_url: str,
    province: str = "",
    sector: str = "",
) -> list[dict]:
    """Full pipeline: fetch PDF → extract text → K2.5 project extraction.

    Args:
        pdf_url: URL of the PDF to process.
        province: Province hint for extraction prompt.
        sector: Sector hint for extraction prompt.

    Returns:
        List of extracted project dicts (same format as nim_deep_search).
    """
    pages = extract_text_from_pdf(pdf_url)
    if not pages:
        return []

    # Combine all page text
    combined = "\n\n".join(
        f"[Page {p['page']}]\n{p['text']}"
        for p in pages
        if p["text"]
    )

    if len(combined) < 100:
        logger.info(f"PDF has too little text to extract projects: {pdf_url[:60]}")
        return []

    # Truncate to fit K2.5 context (leave room for prompt)
    if len(combined) > 50000:
        combined = combined[:50000] + "\n\n[... truncated ...]"

    # Build K2.5 extraction prompt
    location_hint = ""
    if province:
        location_hint += f" in {province}, Canada"
    if sector:
        location_hint += f" ({sector} sector)"

    from nim_deep_search import JSON_INSTRUCTIONS, extract_json_array

    prompt = (
        f"Extract all capital projects{location_hint} from this government document. "
        f"Include project name, location, estimated cost, status, and proponent "
        f"for each project found.\n\n"
        f"{JSON_INSTRUCTIONS}\n\n"
        f"Document text:\n\n{combined}"
    )

    # Call K2.5 via nim_client
    try:
        from nim_client import get_client
        client = get_client()
        response = client.chat_sync(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research assistant specializing in Canadian capital projects. "
                        "Extract structured project data from the provided government document. "
                        "Only include projects clearly described in the document."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            thinking=True,
            max_tokens=8192,
            temperature=0.3,
        )
    except Exception as e:
        logger.error(f"K2.5 extraction failed for PDF {pdf_url[:60]}: {e}")
        return []

    projects = extract_json_array(response)
    logger.info(f"PDF extraction: {pdf_url[:60]} — {len(projects)} projects found")
    return projects
