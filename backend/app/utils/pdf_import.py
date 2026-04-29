"""
PDF import utility — converts a .pdf file to structured HTML for TipTap.

Uses pdfplumber for character-level extraction with font-size and font-name
data, enabling reliable detection of headings (h2/h3) vs body text without
pure-text heuristics.

The algorithm:
  1. Extract words per page with 'size' and 'fontname' attributes.
  2. Group words into visual text lines by vertical proximity.
  3. Group consecutive lines into paragraphs by vertical gap size.
  4. Compute the median body font size across the document.
  5. Single-line paragraphs whose font is ≥14% larger than the median
     (or bold at body size) are mapped to h2/h3; the rest become <p>.

Output tags: h2, h3, p, ul, ol, li.

Functions:
    pdf_bytes_to_import_result — convert raw .pdf bytes to structured content.
"""

from __future__ import annotations

import html as _html
import re
import statistics
from dataclasses import dataclass
from io import BytesIO

import pdfplumber


MAX_BYTES = 10 * 1024 * 1024  # 10 MB hard limit

_GENERIC_TITLES = {"untitled", "document", "pdf", "scan", "microsoft word"}

_BULLET_RE = re.compile(
    r"^[•\-\*\u2013\u2014\u25E6\u25AA\u25B8\u25BA]\s+(.+)$"
)
_NUMBERED_RE = re.compile(r"^\d+[\.\)]\s+(.+)$")
_PAGE_NUMBER_RE = re.compile(
    r"^(?:page\s+)?\d+(?:\s*(?:/|of)\s*\d+)?$",
    flags=re.IGNORECASE,
)
_FOOTNOTE_START_RE = re.compile(r"^(?:\d+[\.\)]|[\*\u2020\u2021])\s+\S+")


@dataclass(slots=True)
class PdfImportResult:
    """Structured result returned by the PDF import pipeline."""

    html: str
    title: str | None = None
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


def pdf_bytes_to_import_result(file_bytes: bytes) -> PdfImportResult:
    """
    Convert raw .pdf bytes to structured HTML plus an optional title.

    Headings are detected using per-character font-size data from pdfplumber.
    Image-only (scanned) PDFs will produce empty content gracefully.

    Parameters:
        file_bytes: Raw bytes of a .pdf file.

    Returns:
        PdfImportResult with extracted HTML and an optional title.

    Raises:
        ValueError: If the file is too large or cannot be parsed as a PDF.
    """
    if len(file_bytes) > MAX_BYTES:
        raise ValueError("Fichier trop volumineux. Taille maximale : 10 Mo.")

    try:
        pdf_file = pdfplumber.open(BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(
            "Could not parse the uploaded file as a PDF document."
        ) from exc

    with pdf_file:
        title = _metadata_title(pdf_file.metadata)
        warnings: list[str] = []

        # Phase 1: extract raw text lines from every page.
        raw_page_lines: list[tuple[float, list[dict]]] = []
        has_tables = False

        for page in pdf_file.pages:
            if not has_tables:
                try:
                    tables = page.extract_tables()
                    if tables:
                        has_tables = True
                except Exception:
                    pass
            words = page.extract_words(
                extra_attrs=["size", "fontname"],
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
            )
            if not words:
                raw_page_lines.append((page.height, []))
                continue

            lines = _words_to_lines(words)
            raw_page_lines.append((page.height, lines))

        repeated_footer_keys = _detect_repeated_footer_keys(raw_page_lines)

        # Phase 2: strip edge artefacts and group the remaining lines into paragraphs.
        page_paragraphs: list[list[dict]] = []
        all_sizes: list[float] = []

        for page_height, raw_lines in raw_page_lines:
            lines = _filter_noise_lines(raw_lines, page_height, repeated_footer_keys)
            paragraphs = _lines_to_paragraphs(lines)
            page_paragraphs.append(paragraphs)

            for para in paragraphs:
                for line in para["lines"]:
                    if line["text"].strip():
                        all_sizes.append(line["avg_size"])

        # Phase 3: determine font-size thresholds.
        body_size = statistics.median(all_sizes) if all_sizes else 11.0
        heading_min = body_size * 1.14  # ≥14% larger → heading candidate

        heading_sizes = sorted(
            {round(s, 1) for s in all_sizes if s >= heading_min},
            reverse=True,
        )
        # Largest heading size maps to h2; anything below it (but still above
        # heading_min) maps to h3.
        h2_size = heading_sizes[0] if heading_sizes else heading_min + 4

        # When the entire document uses a single uniform font size (e.g. PDFs
        # generated programmatically without styling), fall back to text-pattern
        # heuristics for title and heading detection.
        uniform_font = len(heading_sizes) == 0

        # Phase 4: emit HTML.
        html_parts: list[str] = []
        first_para = True

        for page_idx, paragraphs in enumerate(page_paragraphs):
            for para in paragraphs:
                text = para["text"]
                if not text:
                    continue

                max_size = para["max_size"]
                is_bold = para["bold"]
                is_single_line = len(para["lines"]) == 1

                # Title detection — first content block only.
                if first_para:
                    first_para = False
                    if title is None:
                        # Reliable: explicit font size or bold marker.
                        if is_single_line and (max_size >= heading_min or is_bold):
                            title = text[:500]
                            continue
                        # Fallback for uniform-font PDFs: text-pattern heuristic.
                        elif uniform_font:
                            first_line_text = para["lines"][0]["text"].strip()
                            if is_single_line and _looks_like_title(first_line_text):
                                title = first_line_text[:500]
                                continue
                            elif not is_single_line and _looks_like_title(first_line_text):
                                # First line of multi-line block looks like a title;
                                # split it out and emit the remainder as a paragraph.
                                title = first_line_text[:500]
                                rest = " ".join(
                                    ln["text"].strip()
                                    for ln in para["lines"][1:]
                                    if ln["text"].strip()
                                )
                                if rest:
                                    html_parts.append(f"<p>{_html.escape(rest)}</p>")
                                continue
                    elif title and _same_text(text, title):
                        continue

                # Heading detection: single short line, large or bold font.
                if is_single_line and (
                    max_size >= heading_min
                    or (is_bold and max_size >= body_size * 0.9)
                ):
                    tag = "h2" if max_size >= h2_size * 0.95 else "h3"
                    html_parts.append(f"<{tag}>{_html.escape(text)}</{tag}>")
                else:
                    list_html = _try_list_html(para["lines"])
                    if list_html:
                        html_parts.append(list_html)
                    else:
                        html_parts.append(f"<p>{_html.escape(text)}</p>")


        if has_tables:
            warnings.append("tables_ignored")

        return PdfImportResult(
            html="".join(html_parts) or "<p></p>",
            title=title,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _words_to_lines(words: list[dict]) -> list[dict]:
    """
    Group pdfplumber word dicts into text lines by vertical proximity.

    Words whose `top` values differ by ≤5 pt are considered the same line.

    Parameters:
        words: List of word dicts from pdfplumber extract_words().

    Returns:
        Ordered list of line summary dicts.
    """
    lines: list[dict] = []
    bucket: list[dict] = []
    bucket_top: float | None = None

    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        top = word["top"]
        if bucket_top is None or abs(top - bucket_top) <= 5:
            bucket.append(word)
            if bucket_top is None:
                bucket_top = top
        else:
            lines.append(_summarise_line(bucket))
            bucket = [word]
            bucket_top = top

    if bucket:
        lines.append(_summarise_line(bucket))

    return lines


def _summarise_line(words: list[dict]) -> dict:
    """
    Collapse a list of pdfplumber word dicts into a single line summary.

    Parameters:
        words: Words that belong to the same visual line.

    Returns:
        Dict with keys: text, avg_size, bold, top.
    """
    text = " ".join(w["text"] for w in words)
    sizes = [w["size"] for w in words if w.get("size") is not None]
    avg_size = sum(sizes) / len(sizes) if sizes else 11.0
    fontnames = [w.get("fontname", "") for w in words]
    bold = any(
        "bold" in fn.lower()
        or fn.endswith("-B")
        or fn.endswith(",B")
        or "BD" in fn
        or fn.endswith("-Bold")
        for fn in fontnames
    )
    return {
        "text": text,
        "avg_size": avg_size,
        "bold": bold,
        "top": words[0]["top"],
    }


def _filter_noise_lines(
    lines: list[dict],
    page_height: float,
    repeated_footer_keys: set[str],
) -> list[dict]:
    """
    Remove footer artefacts such as page numbers, repeated footers, and bottom footnotes.

    The import pipeline should keep the document body only. PDFs often expose
    visual footers as ordinary text lines, so this helper strips:
      - isolated page number markers near the page edges
      - repeated footer strings that recur across multiple pages
      - small-font footnotes anchored near the bottom of the page

    Parameters:
        lines: Ordered line summary dicts for a single page.
        page_height: Height of the current PDF page in points.
        repeated_footer_keys: Canonical footer markers detected across pages.

    Returns:
        Filtered list of body-content lines.
    """
    if not lines:
        return []

    line_sizes = [line["avg_size"] for line in lines if line["text"].strip()]
    body_size = statistics.median(line_sizes) if line_sizes else 11.0
    filtered: list[dict] = []
    skipping_footnote_block = False

    for line in lines:
        text = re.sub(r"\s+", " ", line["text"]).strip()
        if not text:
            continue

        if _is_page_number_line(text, line["top"], page_height):
            continue

        footer_key = _footer_candidate_key(text, line["top"], page_height)
        if footer_key and footer_key in repeated_footer_keys:
            continue

        if _is_footnote_start_line(text, line["avg_size"], line["top"], page_height, body_size):
            skipping_footnote_block = True
            continue

        if skipping_footnote_block and _is_footnote_continuation_line(
            text,
            line["avg_size"],
            line["top"],
            page_height,
            body_size,
        ):
            continue

        skipping_footnote_block = False
        filtered.append(line)

    return filtered


def _detect_repeated_footer_keys(
    pages: list[tuple[float, list[dict]]],
) -> set[str]:
    """
    Detect footer lines that repeat across multiple pages.

    Parameters:
        pages: Tuples of (page_height, raw line summaries) for the document.

    Returns:
        Set of canonical footer keys that should be removed during import.
    """
    counts: dict[str, int] = {}

    for page_height, lines in pages:
        seen_on_page: set[str] = set()
        for line in lines:
            text = re.sub(r"\s+", " ", line["text"]).strip()
            if not text:
                continue
            key = _footer_candidate_key(text, line["top"], page_height)
            if key:
                seen_on_page.add(key)

        for key in seen_on_page:
            counts[key] = counts.get(key, 0) + 1

    return {key for key, count in counts.items() if count >= 2}


def _lines_to_paragraphs(lines: list[dict]) -> list[dict]:
    """
    Group consecutive text lines into paragraph blocks.

    A vertical gap significantly larger than the typical inter-line spacing
    signals a paragraph break.  Negative gaps (column layout, artefacts) also
    trigger a new paragraph.

    Parameters:
        lines: Ordered list of line summary dicts from _words_to_lines().

    Returns:
        List of paragraph summary dicts, each with: text, max_size, bold, lines.
    """
    if not lines:
        return []

    gaps = []
    for i in range(1, len(lines)):
        gap = lines[i]["top"] - lines[i - 1]["top"]
        if 0 < gap < 50:
            gaps.append(gap)

    typical_gap = statistics.median(gaps) if gaps else lines[0]["avg_size"] * 1.4
    new_para_threshold = typical_gap * 1.7

    groups: list[list[dict]] = [[lines[0]]]
    for i in range(1, len(lines)):
        gap = lines[i]["top"] - lines[i - 1]["top"]
        if gap > new_para_threshold or gap < 0:
            groups.append([lines[i]])
        else:
            groups[-1].append(lines[i])

    return [_summarise_paragraph(group) for group in groups]


def _is_page_number_line(text: str, top: float, page_height: float) -> bool:
    """
    Return True when a line looks like a standalone page number marker.

    Parameters:
        text: Normalized line text.
        top: Vertical position of the line from the top of the page.
        page_height: Height of the current PDF page in points.

    Returns:
        True when the line matches common page-number patterns near page edges.
    """
    near_page_edge = top <= page_height * 0.08 or top >= page_height * 0.88
    compact_marker = len(text) <= 18
    return near_page_edge and compact_marker and _PAGE_NUMBER_RE.match(text) is not None


def _footer_candidate_key(text: str, top: float, page_height: float) -> str | None:
    """
    Canonicalize repeated footer text so it can be removed across pages.

    Parameters:
        text: Normalized line text.
        top: Vertical position of the line from the top of the page.
        page_height: Height of the current PDF page in points.

    Returns:
        Canonical footer key, or None when the line should not be treated as a footer.
    """
    in_footer_zone = top >= page_height * 0.82
    compact_text = 3 <= len(text) <= 140 and len(text.split()) <= 16
    has_letters = re.search(r"[A-Za-zÀ-ÿ]", text) is not None
    if not in_footer_zone or not compact_text or not has_letters:
        return None

    canonical = re.sub(r"\d+", "#", text.casefold())
    canonical = re.sub(r"\s+", " ", canonical)
    canonical = canonical.strip(" -|/•·")
    return canonical or None


def _is_footnote_start_line(
    text: str,
    avg_size: float,
    top: float,
    page_height: float,
    body_size: float,
) -> bool:
    """
    Return True when a bottom-of-page line looks like a footnote entry.

    Parameters:
        text: Normalized line text.
        avg_size: Average font size of the line.
        top: Vertical position of the line from the top of the page.
        page_height: Height of the current PDF page in points.
        body_size: Median body font size estimated for the current page.

    Returns:
        True when the line matches footnote markers in a footer-sized font.
    """
    in_footer_zone = top >= page_height * 0.72
    small_font = avg_size <= body_size * 0.9
    return in_footer_zone and small_font and _FOOTNOTE_START_RE.match(text) is not None


def _is_footnote_continuation_line(
    text: str,
    avg_size: float,
    top: float,
    page_height: float,
    body_size: float,
) -> bool:
    """
    Return True for wrapped continuation lines that belong to a footnote block.

    Parameters:
        text: Normalized line text.
        avg_size: Average font size of the line.
        top: Vertical position of the line from the top of the page.
        page_height: Height of the current PDF page in points.
        body_size: Median body font size estimated for the current page.

    Returns:
        True when the line remains in the bottom footer area with a footnote-like font.
    """
    if not text:
        return False
    in_footer_zone = top >= page_height * 0.72
    small_font = avg_size <= body_size * 0.9
    return in_footer_zone and small_font


def _summarise_paragraph(lines: list[dict]) -> dict:
    """
    Collapse a list of line dicts into a single paragraph summary.

    Parameters:
        lines: Lines that belong to the same paragraph block.

    Returns:
        Dict with keys: text, max_size, bold, lines.
    """
    text = " ".join(line["text"].strip() for line in lines if line["text"].strip())
    max_size = max(line["avg_size"] for line in lines)
    bold = any(line["bold"] for line in lines)
    return {"text": text, "max_size": max_size, "bold": bold, "lines": lines}


def _try_list_html(lines: list[dict]) -> str | None:
    """
    Convert a paragraph whose lines are bullet or numbered list items to HTML.

    Returns None if the lines do not uniformly match a single list type.

    Parameters:
        lines: Lines of the paragraph to inspect.

    Returns:
        HTML string (<ul> or <ol>) or None.
    """
    list_type: str | None = None
    items: list[str] = []

    for line in lines:
        text = line["text"].strip()
        bullet = _BULLET_RE.match(text)
        numbered = _NUMBERED_RE.match(text)

        if bullet:
            if list_type == "ol":
                return None
            list_type = "ul"
            items.append(bullet.group(1).strip())
        elif numbered:
            if list_type == "ul":
                return None
            list_type = "ol"
            items.append(numbered.group(1).strip())
        else:
            return None

    if not list_type or not items:
        return None

    inner = "".join(f"<li>{_html.escape(item)}</li>" for item in items)
    return f"<{list_type}>{inner}</{list_type}>"


def _normalize_title(value: object) -> str | None:
    """Return a cleaned title candidate or None for empty/generic values."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in _GENERIC_TITLES:
        return None
    return text[:500]


def _metadata_title(metadata: dict | None) -> str | None:
    """
    Extract a usable title from a pdfplumber metadata dict.

    Parameters:
        metadata: The pdf.metadata dict returned by pdfplumber.

    Returns:
        Title string or None.
    """
    if not metadata:
        return None
    for key in ("/Title", "Title", "title"):
        title = _normalize_title(metadata.get(key))
        if title:
            return title
    return None


def _looks_like_title(text: str) -> bool:
    """
    Heuristic: return True when a text string looks like a document title.

    Used as a fallback for PDFs where all text shares the same font size
    (no typographic heading signals are available).  A title candidate is
    short and lacks terminal sentence punctuation.

    The capitalisation condition has been removed because it is too fragile
    for French and other languages where titles may not be title-cased.

    Parameters:
        text: Collapsed single-line text to evaluate.

    Returns:
        True when the text matches title-like patterns.
    """
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if not text or len(text) > 200 or len(words) > 20:
        return False
    if text.endswith((".", "?", "!", ";")):
        return False
    return True


def _same_text(left: str, right: str) -> bool:
    """Return True when two strings are equal ignoring whitespace and case."""
    def norm(v: str) -> str:
        return re.sub(r"\s+", " ", v).strip().casefold()

    return norm(left) == norm(right)
