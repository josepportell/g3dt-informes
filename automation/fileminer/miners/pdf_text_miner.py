"""PDF text miner -- extracts signals from text-layer PDFs via PyMuPDF.

Only extracts the text layer. Vision-based extraction (scanned PDFs, planol,
sondeig, penetros) is handled separately in Phase 1.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..base import BaseMiner
from ..models import Signal, SignalType
from ._detection import run_all_detectors

logger = logging.getLogger(__name__)


class PdfTextMiner(BaseMiner):
    """Extract signals from PDF text content."""

    def can_mine(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.pdf'

    def mine(self, file_path: Path) -> list[Signal]:
        signals: list[Signal] = []

        text = self._extract_pdf_text(file_path)
        if text:
            rel_path = self._relative_path(file_path)
            # PDF text is noisier than plain text: -0.05 confidence
            signals.extend(run_all_detectors(
                text,
                rel_path,
                confidence_offset=-0.05,
                include_billing=True,
            ))

        try:
            signals.extend(self._extract_images_pdf(file_path))
        except Exception:
            logger.debug("Image extraction failed for %s", file_path.name)

        return signals

    _MAX_IMAGES_PER_FILE = 10  # Cap to avoid noise from vector PDFs

    def _extract_images_pdf(self, file_path: Path) -> list[Signal]:
        """Extract embedded images from PDF pages via PyMuPDF."""
        import fitz

        signals: list[Signal] = []
        rel = self._relative_path(file_path)
        out_dir = file_path.parent / "validation" / "mined_images"

        doc = fitz.open(str(file_path))
        try:
            img_idx = 0
            for page_num, page in enumerate(doc):
                for img_info in page.get_images(full=True):
                    if img_idx >= self._MAX_IMAGES_PER_FILE:
                        break
                    xref = img_info[0]
                    try:
                        img_data = doc.extract_image(xref)
                        if not img_data or not img_data.get("image"):
                            continue
                        ext = img_data.get("ext", "png")
                        # Skip small images (icons, decorations, vector fragments)
                        w = img_data.get("width", 0)
                        h = img_data.get("height", 0)
                        if w < 200 or h < 200:
                            continue
                        if len(img_data["image"]) < 5000:  # < 5KB
                            continue
                        out_dir.mkdir(parents=True, exist_ok=True)
                        stem = file_path.stem
                        dest = out_dir / f"{stem}_img{img_idx}.{ext}"
                        dest.write_bytes(img_data["image"])
                        signals.append(Signal(
                            type=SignalType.IMAGE,
                            label=f"embedded_image_{img_idx}",
                            value=str(dest),
                            source_file=rel,
                            source_location=f"page {page_num + 1}, image xref {xref} ({w}x{h}px)",
                            extraction_method="embedded_image",
                            confidence=0.30,
                        ))
                        img_idx += 1
                    except Exception:
                        logger.debug("Could not extract image xref %d from %s", xref, file_path.name)
                if img_idx >= self._MAX_IMAGES_PER_FILE:
                    break
        finally:
            doc.close()
        return signals

    @staticmethod
    def _extract_pdf_text(file_path: Path) -> str | None:
        """Extract text from all pages of a PDF using PyMuPDF.

        Returns None if PyMuPDF is not installed or the PDF has no text layer.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.debug("PyMuPDF (fitz) not installed, skipping PDF text extraction")
            return None

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            logger.debug("Could not open PDF %s: %s", file_path, exc)
            return None

        try:
            pages: list[str] = []
            for page in doc:
                page_text = page.get_text()
                if page_text and page_text.strip():
                    pages.append(page_text)
            return '\n'.join(pages) if pages else None
        except Exception as exc:
            logger.debug("Error extracting text from PDF %s: %s", file_path, exc)
            return None
        finally:
            doc.close()
