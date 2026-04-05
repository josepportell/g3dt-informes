"""Excel file miner (.xls, .xlsx) -- extracts signals from spreadsheet cells."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..base import BaseMiner
from ..label_map import LABEL_TO_VARIABLE, get_priority
from ..models import Signal, SignalType

logger = logging.getLogger(__name__)

# --- Regex patterns ---

_PHONE_RE = re.compile(r'[69]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}')
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_URL_RE = re.compile(r'https?://\S+')
_GMAPS_RE = re.compile(r'maps\.app\.goo\.gl|google\.com/maps', re.IGNORECASE)
_NIF_RE = re.compile(r'\b\d{8}[A-Z]\b')
_CIF_RE = re.compile(r'\b[A-Z]\d{7}[A-Z0-9]\b')
_G3_CIF = "B25364589"

# G3's own data — must be excluded from client-facing signals
_G3_INTERNAL_NIFS = {_G3_CIF}
_G3_INTERNAL_PLACES = {"ELS OMELLS DE NA GAIA"}  # G3 office town
_G3_INTERNAL_NAMES = {"G3 DESENVOLUPAMENT TERRITORIAL", "INTECSON"}  # G3 + lab subcontractor

# Excel epoch for serial date conversion
_EXCEL_EPOCH = datetime(1899, 12, 30)


class ExcelMiner(BaseMiner):
    """Extract signals from Excel files (.xls, .xlsx)."""

    def can_mine(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in ('.xls', '.xlsx')

    def mine(self, file_path: Path) -> list[Signal]:
        try:
            if file_path.suffix.lower() == '.xlsx':
                return self._mine_xlsx(file_path)
            else:
                return self._mine_xls(file_path)
        except Exception:
            logger.exception("ExcelMiner failed on %s", file_path)
            return []

    # ------------------------------------------------------------------
    # .xlsx via openpyxl
    # ------------------------------------------------------------------

    def _mine_xlsx(self, file_path: Path) -> list[Signal]:
        import openpyxl

        signals: list[Signal] = []
        rel = self._relative_path(file_path)

        wb = openpyxl.load_workbook(str(file_path), read_only=False, data_only=True)
        try:
            for ws in wb.worksheets:
                sheet_name = ws.title
                grid = self._xlsx_to_grid(ws)
                signals.extend(self._mine_grid(grid, rel, sheet_name))
                signals.extend(self._extract_images_xlsx(ws, file_path, rel, sheet_name))
        finally:
            wb.close()

        return signals

    @staticmethod
    def _xlsx_to_grid(ws) -> list[list[tuple[Any, str]]]:
        """Convert worksheet to list of rows, each row = list of (value, col_letter)."""
        rows: list[list[tuple[Any, str]]] = []
        for row in ws.iter_rows():
            cells = []
            for cell in row:
                col_letter = cell.column_letter if hasattr(cell, 'column_letter') else _col_letter(cell.column)
                cells.append((cell.value, col_letter))
            rows.append(cells)
        return rows

    def _extract_images_xlsx(
        self, ws, file_path: Path, rel: str, sheet_name: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        images = getattr(ws, '_images', [])
        if not images:
            return signals

        out_dir = file_path.parent / "validation" / "mined_images"
        out_dir.mkdir(parents=True, exist_ok=True)

        for idx, img in enumerate(images):
            stem = file_path.stem
            dest = out_dir / f"{stem}_img{idx}.png"
            try:
                blob = img._data() if callable(getattr(img, '_data', None)) else getattr(img, 'ref', b'')
                if not isinstance(blob, bytes) or not blob:
                    continue
                dest.write_bytes(blob)
            except Exception:
                logger.debug("Could not extract image %d from %s", idx, file_path.name)
                continue

            signals.append(Signal(
                type=SignalType.IMAGE,
                label=f"embedded_image_{idx}",
                value=str(dest),
                source_file=rel,
                source_location=f"Sheet '{sheet_name}', embedded image {idx}",
                extraction_method="embedded_image",
                confidence=0.30,
                priority=get_priority(self.source_type),
            ))

        return signals

    # ------------------------------------------------------------------
    # .xls via xlrd
    # ------------------------------------------------------------------

    def _mine_xls(self, file_path: Path) -> list[Signal]:
        import xlrd

        signals: list[Signal] = []
        rel = self._relative_path(file_path)

        wb = xlrd.open_workbook(str(file_path))
        for ws in wb.sheets():
            grid = self._xls_to_grid(ws)
            signals.extend(self._mine_grid(grid, rel, ws.name))
        return signals

    @staticmethod
    def _xls_to_grid(ws) -> list[list[tuple[Any, str]]]:
        rows: list[list[tuple[Any, str]]] = []
        for row_idx in range(ws.nrows):
            cells = []
            for col_idx in range(ws.ncols):
                val = ws.cell_value(row_idx, col_idx)
                col_letter = _col_letter(col_idx + 1)
                cells.append((val, col_letter))
            rows.append(cells)
        return rows

    # ------------------------------------------------------------------
    # Grid mining (shared logic for xlsx and xls)
    # ------------------------------------------------------------------

    def _mine_grid(
        self,
        grid: list[list[tuple[Any, str]]],
        rel: str,
        sheet_name: str,
    ) -> list[Signal]:
        signals: list[Signal] = []

        for row_idx, row in enumerate(grid):
            for col_idx, (cell_val, col_letter) in enumerate(row):
                if cell_val is None:
                    continue
                cell_str = str(cell_val).strip()
                if not cell_str:
                    continue

                row_num = row_idx + 1  # 1-based for display

                # 1) Label-value matching
                label_upper = cell_str.upper().strip()
                # Strip trailing dots/colons
                label_clean = label_upper.rstrip(":. ")

                if label_clean in LABEL_TO_VARIABLE:
                    maps_to = LABEL_TO_VARIABLE[label_clean]
                    value = self._find_adjacent_value(grid, row_idx, col_idx)
                    if value is not None:
                        value_str = self._normalize_value(value, maps_to)
                        # Skip if the "value" is itself a known label (below-
                        # cell fallback picked up the next label, not a value)
                        if value_str.upper().rstrip(":. ") in LABEL_TO_VARIABLE:
                            continue
                        # Validate URL fields actually contain URLs
                        if maps_to == "access_url" and not _URL_RE.search(value_str):
                            continue
                        # Filter out G3's own internal data
                        if maps_to == "client_nif" and value_str in _G3_INTERNAL_NIFS:
                            continue
                        if maps_to == "municipality" and value_str.upper() in _G3_INTERNAL_PLACES:
                            continue
                        if maps_to == "client_name" and any(
                            name in value_str.upper() for name in _G3_INTERNAL_NAMES
                        ):
                            continue
                        if value_str:
                            sig = Signal(
                                type=self._type_for(maps_to),
                                label=cell_str,
                                value=value_str,
                                raw_value=str(value),
                                maps_to=maps_to,
                                concept_id=maps_to,
                                source_file=rel,
                                source_location=f"Sheet '{sheet_name}', row {row_num}, col {col_letter}",
                                extraction_method="label_adjacent",
                                confidence=0.90,
                                priority=get_priority(self.source_type),
                            )
                            signals.append(sig)

                            # If the value contains an embedded phone, split it
                            if maps_to == "client_name":
                                extra = self._split_embedded_phone(value_str, rel, sheet_name, row_num, col_letter)
                                if extra:
                                    signals.append(extra[0])
                                    # Update client_name to strip the phone
                                    sig.value = extra[1]

                # 2) Regex scans — only on text cells, not pure numeric data
                if not isinstance(cell_val, (int, float)):
                    signals.extend(self._regex_scan(cell_str, rel, sheet_name, row_num, col_letter))

        return signals

    def _find_adjacent_value(
        self,
        grid: list[list[tuple[Any, str]]],
        row_idx: int,
        col_idx: int,
    ) -> Any | None:
        """Look for the value to the right (primary) or below (secondary)."""
        row = grid[row_idx]
        # Right: next non-empty cell in the same row
        for ci in range(col_idx + 1, len(row)):
            val, _ = row[ci]
            if val is not None and str(val).strip():
                return val
        # Below: same column, next row
        if row_idx + 1 < len(grid):
            below_row = grid[row_idx + 1]
            if col_idx < len(below_row):
                val, _ = below_row[col_idx]
                if val is not None and str(val).strip():
                    return val
        return None

    # ------------------------------------------------------------------
    # Regex scanning
    # ------------------------------------------------------------------

    def _regex_scan(
        self,
        text: str,
        rel: str,
        sheet_name: str,
        row_num: int,
        col_letter: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        loc = f"Sheet '{sheet_name}', row {row_num}, col {col_letter}"
        priority = get_priority(self.source_type)

        # Phones
        for m in _PHONE_RE.finditer(text):
            phone = re.sub(r'[\s.\-]', '', m.group())
            signals.append(Signal(
                type=SignalType.TEXT,
                label="phone_detected",
                value=phone,
                raw_value=m.group(),
                maps_to="client_phone",
                concept_id="client_phone",
                source_file=rel,
                source_location=loc,
                extraction_method="regex_phone",
                confidence=0.85,
                priority=priority,
            ))

        # Emails
        for m in _EMAIL_RE.finditer(text):
            signals.append(Signal(
                type=SignalType.TEXT,
                label="email_detected",
                value=m.group().lower(),
                raw_value=m.group(),
                maps_to="client_email",
                concept_id="client_email",
                source_file=rel,
                source_location=loc,
                extraction_method="regex_email",
                confidence=0.85,
                priority=priority,
            ))

        # URLs
        for m in _URL_RE.finditer(text):
            url = m.group()
            maps_to = "access_url" if _GMAPS_RE.search(url) else None
            signals.append(Signal(
                type=SignalType.URL,
                label="url_detected",
                value=url,
                raw_value=url,
                maps_to=maps_to,
                concept_id=maps_to,
                source_file=rel,
                source_location=loc,
                extraction_method="regex_url",
                confidence=0.80,
                priority=priority,
            ))

        # NIF
        for m in _NIF_RE.finditer(text):
            signals.append(Signal(
                type=SignalType.TEXT,
                label="nif_detected",
                value=m.group(),
                raw_value=m.group(),
                maps_to="client_nif",
                concept_id="client_nif",
                source_file=rel,
                source_location=loc,
                extraction_method="regex_nif",
                confidence=0.85,
                priority=priority,
            ))

        # CIF
        for m in _CIF_RE.finditer(text):
            cif = m.group()
            if cif == _G3_CIF:
                continue
            signals.append(Signal(
                type=SignalType.TEXT,
                label="cif_detected",
                value=cif,
                raw_value=cif,
                maps_to="client_nif",
                concept_id="client_nif",
                source_file=rel,
                source_location=loc,
                extraction_method="regex_cif",
                confidence=0.85,
                priority=priority,
            ))

        return signals

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_embedded_phone(
        self, name: str, rel: str, sheet_name: str, row_num: int, col_letter: str,
    ) -> tuple[Signal, str] | None:
        """If name contains an embedded phone, return (phone_signal, cleaned_name)."""
        m = _PHONE_RE.search(name)
        if not m:
            return None
        phone = re.sub(r'[\s.\-]', '', m.group())
        cleaned = name[:m.start()].strip()
        sig = Signal(
            type=SignalType.TEXT,
            label="phone_embedded_in_name",
            value=phone,
            raw_value=m.group(),
            maps_to="client_phone",
            concept_id="client_phone",
            source_file=rel,
            source_location=f"Sheet '{sheet_name}', row {row_num}, col {col_letter}",
            extraction_method="regex_phone_embedded",
            confidence=0.85,
            priority=get_priority(self.source_type),
        )
        return (sig, cleaned)

    @staticmethod
    def _normalize_value(value: Any, maps_to: str) -> str:
        """Convert raw cell value to a clean string."""
        if value is None:
            return ""

        # Excel serial date
        if maps_to == "field_date":
            if isinstance(value, (int, float)) and 30000 < value < 55000:
                dt = _EXCEL_EPOCH + timedelta(days=int(value))
                return dt.strftime("%Y-%m-%d")
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

        # Expedient often comes as float (4001679.0 -> "4001679")
        if maps_to == "expedient" and isinstance(value, float):
            if value == int(value):
                return str(int(value))

        return str(value).strip()

    @staticmethod
    def _type_for(maps_to: str) -> SignalType:
        if maps_to == "field_date":
            return SignalType.DATE
        if maps_to == "access_url":
            return SignalType.URL
        if maps_to in ("expedient", "num_floors", "superficie_parcela", "superficie_construida"):
            return SignalType.NUMERIC
        return SignalType.TEXT


def _col_letter(col_num: int) -> str:
    """Convert 1-based column number to Excel letter (1->A, 27->AA)."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result
