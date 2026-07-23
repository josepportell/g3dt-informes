"""Groq LLM miner -- uses Llama 3.3 70B to extract data from underperforming files.

Phase 0.4: runs after Python regex miners, targets files where <3 mapped signals
were found. Requires G3DT_USE_GROQ=1 and GROQ_API_KEY env vars.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from automation import config
from ..base import BaseMiner
from ..models import Signal, SignalType

logger = logging.getLogger(__name__)

# === Configuration ===

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_DEFAULT = config.TEXT_MODEL_GROQ
GROQ_MAX_TOKENS = 2048
GROQ_TEMPERATURE = 0.0

CACHE_DIR = config.cache_dir("groq")
CACHE_TTL_DAYS = 90

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each retry

# === Pricing ($/Mtok in,out) ===
# Module-level so it can be re-exported via automation.llm_pricing without
# duplication. Source: groq.com/pricing observed 2026-04-18.
GROQ_PRICING: dict[str, tuple[float, float]] = {
    "llama-3.1-8b-instant": (0.05, 0.08),
    "qwen/qwen3-32b": (0.29, 0.59),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "meta-llama/llama-4-scout-17b-16e-instruct": (0.11, 0.34),  # retired 2026-07-17, kept for historical cost lookups
    "qwen/qwen3.6-27b": (0.60, 3.00),
}

# G3 internal data to exclude from results
_G3_EXCLUSIONS = {
    "client_nif": {"B25364589"},
    "client_email": {"@g3dt.com"},  # substring match
    "client_phone": {"974551273"},
    "client_address": {"C/ Vallbona, 22", "VALLBONA, 22"},
    "municipality": {"ELS OMELLS DE NA GAIA", "OMELLS DE NA GAIA"},
}

# === Prompts ===

SYSTEM_PROMPT = """\
You are a data extraction assistant for G3DT, a geotechnical engineering company \
(G3 Desenvolupament Territorial SL, NIF B25364589, based in Els Omells de Na Gaia).

Extract structured data from project files to auto-fill geotechnical reports.

CRITICAL RULES:
1. DISTINGUISH between G3's own data and the CLIENT/PROJECT data:
   - G3 INTERNAL (EXCLUDE): NIF B25364589, "ELS OMELLS DE NA GAIA", \
"C/ Vallbona, 22", any @g3dt.com email, phone 974551273
   - Extract the CLIENT/PROJECT data, NOT G3's internal data
2. When sections like "DADES DEL SOL·LICITANT" (= G3 internal) vs \
"DADES DE L'OBRA" (= project) exist, extract from PROJECT section only
3. Only extract values you are confident about. Use "" for uncertain values.
4. Languages: files may be in Catalan, Spanish, or mixed. Handle both.
5. For numeric values (surfaces, floors), extract the number only.

Respond with a JSON object: {"extractions": [{"variable": "...", "value": "...", \
"confidence": 0.0-1.0, "source_quote": "short quote from text"}]}
Only include variables you found. Do NOT include variables with empty values.\
"""

TARGET_VARIABLES: dict[str, str] = {
    "client_name": "Client or promoter name (person or company, NOT G3)",
    "client_nif": "Client's NIF/CIF tax ID (NOT B25364589)",
    "client_phone": "Client's phone number (NOT 974551273)",
    "client_email": "Client's email (NOT @g3dt.com)",
    "client_address": "Client's postal address (NOT C/ Vallbona, 22)",
    "architect_name": "Architect or project engineer name",
    "architect_company": "Architect's firm or studio name",
    "street_address": "Project site address (where the building will be)",
    "municipality": "Town/city where the project is located",
    "province": "Province (e.g. Lleida, Huesca, Barcelona)",
    "building_type": "Type of construction (e.g. 'Vivienda unifamiliar')",
    "num_floors": "Number of floors (e.g. 'PB+2', '3')",
    "superficie_parcela": "Plot/parcel surface area in m²",
    "superficie_construida": "Built surface area in m²",
    "has_basement": "Whether the building has a basement (true/false as string)",
    "has_retaining_walls": "Whether retaining walls are needed (true/false as string)",
    "expedient": "Project reference number (e.g. '4001679')",
    "field_date": "Date of field work (any format found)",
    "report_date": "Report issue date",
    "lab_company": "Laboratory company name (NOT G3)",
}

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "extractions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "variable": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "source_quote": {"type": "string"},
                },
                "required": ["variable", "value", "confidence", "source_quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["extractions"],
    "additionalProperties": False,
}

GROQ_PRIORITY = 42  # between geocode_nominatim=40 and content_pdf=45


class GroqMiner(BaseMiner):
    """LLM-based miner using Groq API (Llama 3.3 70B).

    Only active when G3DT_USE_GROQ=1 AND GROQ_API_KEY env vars are set.
    Targets files where Python regex miners found few signals.
    """

    # Class-level counters (reset per mine_project_groq invocation)
    _total_input_tokens: int = 0
    _total_output_tokens: int = 0
    _total_api_calls: int = 0
    _total_cache_hits: int = 0

    @classmethod
    def get_usage_summary(cls) -> dict:
        """Return usage stats and estimated costs for the current session."""
        model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)
        in_price, out_price = GROQ_PRICING.get(model, (0.59, 0.79))
        cost_usd = (
            cls._total_input_tokens * in_price
            + cls._total_output_tokens * out_price
        ) / 1_000_000
        return {
            "model": model,
            "api_calls": cls._total_api_calls,
            "cache_hits": cls._total_cache_hits,
            "input_tokens": cls._total_input_tokens,
            "output_tokens": cls._total_output_tokens,
            "total_tokens": cls._total_input_tokens + cls._total_output_tokens,
            "estimated_cost_usd": round(cost_usd, 6),
        }

    @classmethod
    def reset_counters(cls):
        cls._total_input_tokens = 0
        cls._total_output_tokens = 0
        cls._total_api_calls = 0
        cls._total_cache_hits = 0

    def __init__(
        self,
        project_path: Path,
        source_type: str = "groq_llm",
        *,
        missing_variables: list[str] | None = None,
    ) -> None:
        super().__init__(project_path, source_type)
        self.missing_variables = missing_variables or list(TARGET_VARIABLES.keys())
        self._api_key: str | None = os.environ.get("GROQ_API_KEY")

    def can_mine(self, file_path: Path) -> bool:
        if os.environ.get("G3DT_USE_GROQ", "1").strip() != "1":
            logger.debug("Groq: disabled (G3DT_USE_GROQ != 1)")
            return False
        if not os.environ.get("GROQ_API_KEY"):
            logger.debug("Groq: disabled (GROQ_API_KEY not set)")
            return False
        if file_path.suffix.lower() not in (".pdf", ".xls", ".xlsx", ".doc", ".docx"):
            logger.debug("Groq: skipping %s (unsupported extension)", file_path.name)
            return False
        return True

    def mine(self, file_path: Path) -> list[Signal]:
        rel_path = self._relative_path(file_path)

        # Check cache first
        file_hash = self._file_hash(file_path)
        cached = self._load_cache(file_hash)
        if cached is not None:
            logger.info("Groq cache HIT for %s (%s)", rel_path, file_hash[:12])
            GroqMiner._total_cache_hits += 1
            return self._parse_extractions(cached, rel_path)

        logger.info("Groq cache MISS for %s (%s)", rel_path, file_hash[:12])

        # Extract text from file
        text = self._extract_text(file_path)
        if not text:
            logger.debug("Groq: no text extracted from %s", rel_path)
            return []
        logger.debug("Groq: extracted %d chars from %s", len(text), rel_path)

        # Build prompt
        user_prompt = self._build_user_prompt(text, rel_path)

        # Call Groq API
        response = self._call_groq(user_prompt, rel_path)
        if response is None:
            return []

        # Cache result
        self._save_cache(file_hash, response)

        return self._parse_extractions(response, rel_path)

    # --- Text extraction ---

    def _extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".pdf":
                return self._extract_pdf_text(file_path)
            elif suffix in (".xls", ".xlsx"):
                return self._extract_excel_text(file_path)
            elif suffix in (".doc", ".docx"):
                return self._extract_docx_text(file_path)
        except Exception as exc:
            logger.warning("Groq: text extraction failed for %s: %s", file_path.name, exc)
        return ""

    def _extract_pdf_text(self, file_path: Path) -> str:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)

    def _extract_excel_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        lines: list[str] = []

        if suffix == ".xls":
            import xlrd

            wb = xlrd.open_workbook(str(file_path))
            for sheet in wb.sheets():
                lines.append(f"=== SHEET: {sheet.name} ===")
                current_section = None
                for row_idx in range(sheet.nrows):
                    row_vals = []
                    for col_idx in range(sheet.ncols):
                        cell = sheet.cell(row_idx, col_idx)
                        val = str(cell.value).strip() if cell.value else ""
                        if val:
                            row_vals.append(val)
                    row_text = " | ".join(row_vals)
                    if row_text:
                        # Annotate section headers
                        section = self._detect_section(row_text)
                        if section and section != current_section:
                            current_section = section
                            lines.append(f"=== SECTION: {section} ===")
                            logger.debug(
                                "Groq: annotated section %r in Excel %s",
                                section, file_path.name,
                            )
                        lines.append(row_text)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook

            wb = load_workbook(str(file_path), data_only=True, read_only=True)
            for ws in wb.worksheets:
                lines.append(f"=== SHEET: {ws.title} ===")
                current_section = None
                for row in ws.iter_rows():
                    row_vals = []
                    for cell in row:
                        val = str(cell.value).strip() if cell.value else ""
                        if val:
                            row_vals.append(val)
                    row_text = " | ".join(row_vals)
                    if row_text:
                        section = self._detect_section(row_text)
                        if section and section != current_section:
                            current_section = section
                            lines.append(f"=== SECTION: {section} ===")
                            logger.debug(
                                "Groq: annotated section %r in Excel %s",
                                section, file_path.name,
                            )
                        lines.append(row_text)
            wb.close()

        n_sections = sum(1 for l in lines if l.startswith("=== SECTION:"))
        if n_sections:
            logger.debug("Groq: annotated %d sections in Excel %s", n_sections, file_path.name)
        return "\n".join(lines)

    @staticmethod
    def _detect_section(row_text: str) -> str | None:
        upper = row_text.upper()
        if "SOL·LICITANT" in upper or "SOLICITANT" in upper:
            return "DADES SOL·LICITANT (G3 internal - ignore)"
        if "DADES DE L'OBRA" in upper or "DADES OBRA" in upper:
            return "DADES DE L'OBRA (project data)"
        if "PRESSUPOST" in upper:
            return "PRESSUPOST"
        if "FACTURA" in upper:
            return "FACTURA"
        return None

    @staticmethod
    def _is_cost_document(rel_path: str) -> bool:
        """Check if file is a cost/budget/internal planning document."""
        upper = rel_path.upper()
        return any(kw in upper for kw in ("PLAN_COST", "PRESSUPOST", "COMANDA", "FACTURA"))

    def _extract_docx_text(self, file_path: Path) -> str:
        try:
            from docx import Document
            doc = Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except Exception:
            if file_path.suffix.lower() == '.doc':
                from .docx_miner import DocxMiner
                return DocxMiner._extract_doc_legacy(file_path) or ""
            return ""

    # --- Prompt construction ---

    def _build_user_prompt(self, text: str, rel_path: str) -> str:
        # Focus on missing variables only
        vars_block = "\n".join(
            f"  - {var}: {TARGET_VARIABLES[var]}"
            for var in self.missing_variables
            if var in TARGET_VARIABLES
        )

        # Truncate text to ~8000 chars to stay within context limits
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [TRUNCATED]"

        return (
            f"File: {rel_path}\n\n"
            f"Extract ONLY these variables (leave out any you can't find):\n"
            f"{vars_block}\n\n"
            f"--- FILE CONTENT ---\n{text}\n--- END ---"
        )

    # --- Groq API ---

    def _call_groq(self, user_prompt: str, rel_path: str) -> dict | None:
        import httpx

        if not self._api_key:
            logger.debug("Groq: no API key, skipping")
            return None

        model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)

        # Qwen3 thinking mode: disable to get clean JSON
        if "qwen3" in model.lower():
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt + "\n\n/no_think"},
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": GROQ_TEMPERATURE,
            "max_tokens": GROQ_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }

        logger.debug(
            "Groq API call for %s: %d chars, model=%s",
            rel_path, len(user_prompt), model,
        )

        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        GROQ_API_URL,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                elapsed_ms = int((time.monotonic() - t0) * 1000)

                if resp.status_code == 429:
                    delay = 5  # Developer plan: higher limits, short retry
                    logger.warning(
                        "Groq: rate limited on %s, waiting %ds (attempt %d/%d)",
                        rel_path, delay, attempt, MAX_RETRIES,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(delay)
                        continue
                    return None

                if resp.status_code != 200:
                    logger.warning(
                        "Groq API error for %s: HTTP %d %s (attempt %d/%d)",
                        rel_path, resp.status_code, resp.text[:200], attempt, MAX_RETRIES,
                    )
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                        time.sleep(delay)
                        continue
                    return None

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                n_extractions = len(result.get("extractions", []))

                # Token usage tracking
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                GroqMiner._total_input_tokens += input_tokens
                GroqMiner._total_output_tokens += output_tokens
                GroqMiner._total_api_calls += 1

                logger.info(
                    "Groq API response for %s: %d extractions in %dms (%d in + %d out tokens)",
                    rel_path, n_extractions, elapsed_ms, input_tokens, output_tokens,
                )
                return result

            except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.warning(
                    "Groq API error for %s: %s (attempt %d/%d, %dms)",
                    rel_path, exc, attempt, MAX_RETRIES, elapsed_ms,
                )
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    time.sleep(delay)
                    continue
                return None

        return None

    # --- Response parsing ---

    def _parse_extractions(self, response: dict, rel_path: str) -> list[Signal]:
        signals: list[Signal] = []
        extractions = response.get("extractions", [])

        for item in extractions:
            variable = str(item.get("variable", ""))
            value = str(item.get("value", ""))
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            source_quote = str(item.get("source_quote", ""))

            if not variable or not value:
                continue

            # Check if this is G3 internal data
            if self._is_g3_internal(variable, value):
                logger.info(
                    "Groq: EXCLUDED G3 internal data: %s=%r", variable, value
                )
                continue

            # Exclude location/identity data from cost/budget documents
            # (province, municipality, architect_name in these refer to G3's office, not the project)
            if self._is_cost_document(rel_path) and variable in (
                "province", "municipality", "architect_name",
            ):
                logger.info(
                    "Groq: EXCLUDED %s=%r from cost document %s",
                    variable, value, rel_path,
                )
                continue

            # Determine signal type
            sig_type = SignalType.TEXT
            if variable in ("superficie_parcela", "superficie_construida", "num_floors"):
                sig_type = SignalType.NUMERIC
            elif variable in ("field_date", "report_date"):
                sig_type = SignalType.DATE

            # Remap variable names to match wizard field names
            _GROQ_MAPS_TO_REMAP = {
                "superficie_parcela": "superficie_parcela_m2",
                "superficie_construida": "superficie_construida_m2",
            }
            maps_to_key = _GROQ_MAPS_TO_REMAP.get(variable, variable)

            signal = Signal(
                type=sig_type,
                label=variable,
                value=value,
                raw_value=value,
                maps_to=maps_to_key if variable in TARGET_VARIABLES else None,
                source_file=rel_path,
                source_location=f"quote: {source_quote[:80]}",
                extraction_method="groq_llm",
                confidence=min(max(confidence, 0.0), 1.0),
                priority=GROQ_PRIORITY,
                source_type="groq_llm",
            )
            signals.append(signal)
            logger.info(
                "Groq: %s=%r (conf=%.2f, quote=%r) from %s",
                variable, value, confidence, source_quote[:60], rel_path,
            )

        return signals

    @staticmethod
    def _is_g3_internal(variable: str, value: str) -> bool:
        exclusions = _G3_EXCLUSIONS.get(variable)
        if not exclusions:
            return False
        upper_value = value.upper().strip()
        for pattern in exclusions:
            if pattern.startswith("@"):
                # Substring match for email domains
                if pattern.lower() in value.lower():
                    return True
            elif upper_value == pattern.upper() or pattern.upper() in upper_value:
                return True
        return False

    # --- Caching ---

    @staticmethod
    def _file_hash(file_path: Path) -> str:
        model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)
        h = hashlib.sha256()
        h.update(file_path.read_bytes())
        h.update(model.encode())
        return h.hexdigest()

    @staticmethod
    def _cache_path(file_hash: str) -> Path:
        return CACHE_DIR / f"{file_hash[:12]}.json"

    @staticmethod
    def _load_cache(file_hash: str) -> dict | None:
        if os.environ.get("G3DT_NO_CACHE") == "1":
            return None
        cache_path = CACHE_DIR / f"{file_hash[:12]}.json"
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            # Check TTL
            cached_at = data.get("_cached_at", "")
            if cached_at:
                cached_dt = datetime.fromisoformat(cached_at)
                if datetime.now() - cached_dt > timedelta(days=CACHE_TTL_DAYS):
                    logger.debug("Groq cache expired for %s", file_hash[:12])
                    return None
            return data.get("response", None)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.debug("Groq cache read error for %s: %s", file_hash[:12], exc)
            return None

    @staticmethod
    def _save_cache(file_hash: str, response: dict) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = CACHE_DIR / f"{file_hash[:12]}.json"
            data = {
                "_cached_at": datetime.now().isoformat(),
                "response": response,
            }
            fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                Path(temp_path).rename(cache_path)
                logger.debug("Groq: cached result at %s", cache_path)
            except Exception:
                Path(temp_path).unlink(missing_ok=True)
                raise
        except OSError as exc:
            logger.warning("Groq: failed to cache result: %s", exc)
