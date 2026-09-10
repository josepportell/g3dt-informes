"""
Groq LLM Miner tests -- no API key needed, all external calls mocked.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.fileminer.miners.groq_miner import (
    GroqMiner,
    SYSTEM_PROMPT,
    TARGET_VARIABLES,
    EXTRACTION_SCHEMA,
    GROQ_PRIORITY,
    _G3_EXCLUSIONS,
)
from automation.fileminer.models import Signal, SignalType


@pytest.fixture
def project_path(tmp_path):
    return tmp_path / "test-project"


@pytest.fixture
def sample_pdf(project_path):
    project_path.mkdir(parents=True, exist_ok=True)
    pdf = project_path / "PRESSUPOST.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake content for testing")
    return pdf


@pytest.fixture
def sample_xlsx(project_path):
    project_path.mkdir(parents=True, exist_ok=True)
    xlsx = project_path / "DADES.xlsx"
    xlsx.write_bytes(b"PK\x03\x04 fake xlsx")
    return xlsx


@pytest.fixture
def cache_dir(tmp_path):
    d = tmp_path / "cache" / "groq"
    d.mkdir(parents=True)
    return d


def _mock_groq_response(extractions: list[dict]) -> dict:
    """Build a mock Groq API JSON response."""
    return {
        "choices": [{
            "message": {
                "content": json.dumps({"extractions": extractions})
            }
        }]
    }


# ============================================================
# 1. Feature flag tests
# ============================================================

class TestFeatureFlags:

    def test_groq_miner_disabled_without_env(self, project_path, sample_pdf):
        """GroqMiner.can_mine returns False when G3DT_USE_GROQ not set."""
        with patch.dict("os.environ", {}, clear=True):
            miner = GroqMiner(project_path)
            assert miner.can_mine(sample_pdf) is False

    def test_groq_miner_disabled_without_api_key(self, project_path, sample_pdf):
        """can_mine returns False when GROQ_API_KEY not set."""
        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1"}, clear=True):
            miner = GroqMiner(project_path)
            assert miner.can_mine(sample_pdf) is False

    def test_groq_miner_enabled_with_both_vars(self, project_path, sample_pdf):
        """can_mine returns True when both env vars set and file is supported."""
        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            miner = GroqMiner(project_path)
            assert miner.can_mine(sample_pdf) is True

    def test_groq_miner_rejects_unsupported_extension(self, project_path):
        """can_mine returns False for unsupported file types."""
        project_path.mkdir(parents=True, exist_ok=True)
        txt_file = project_path / "notes.txt"
        txt_file.write_text("some text")
        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            miner = GroqMiner(project_path)
            assert miner.can_mine(txt_file) is False


# ============================================================
# 2. Prompt construction
# ============================================================

class TestPromptConstruction:

    def test_prompt_contains_missing_variables(self, project_path):
        """User prompt includes only the requested missing variables."""
        miner = GroqMiner(
            project_path,
            missing_variables=["client_name", "municipality"],
        )
        prompt = miner._build_user_prompt("file content here", "PRESSUPOST.pdf")
        assert "client_name" in prompt
        assert "municipality" in prompt
        # Should not include variables not in missing list
        assert "lab_company" not in prompt

    def test_prompt_includes_file_content(self, project_path):
        miner = GroqMiner(project_path)
        text = "PROMOTOR: Joan Garcia"
        prompt = miner._build_user_prompt(text, "DADES.xlsx")
        assert "PROMOTOR: Joan Garcia" in prompt
        assert "DADES.xlsx" in prompt

    def test_prompt_truncates_long_text(self, project_path):
        miner = GroqMiner(project_path)
        long_text = "A" * 10000
        prompt = miner._build_user_prompt(long_text, "big.pdf")
        assert "[TRUNCATED]" in prompt
        assert len(prompt) < 10000 + 500  # text + prompt overhead


# ============================================================
# 3. Excel section annotation
# ============================================================

class TestExcelSectionAnnotation:

    def test_detect_section_sollicitant(self):
        assert GroqMiner._detect_section("DADES DEL SOL·LICITANT") is not None
        assert "G3 internal" in GroqMiner._detect_section("DADES DEL SOL·LICITANT")

    def test_detect_section_obra(self):
        section = GroqMiner._detect_section("DADES DE L'OBRA")
        assert section is not None
        assert "project data" in section

    def test_detect_section_pressupost(self):
        assert GroqMiner._detect_section("PRESSUPOST NÚM. 4001679") == "PRESSUPOST"

    def test_detect_section_none(self):
        assert GroqMiner._detect_section("Random row content") is None


# ============================================================
# 4. Response parsing
# ============================================================

class TestResponseParsing:

    def test_response_parsing_creates_signals(self, project_path):
        """Mock Groq response is correctly parsed into Signal objects."""
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {
                    "variable": "client_name",
                    "value": "Joan Garcia SL",
                    "confidence": 0.95,
                    "source_quote": "PROMOTOR: Joan Garcia SL",
                },
                {
                    "variable": "municipality",
                    "value": "Lleida",
                    "confidence": 0.9,
                    "source_quote": "Municipi: Lleida",
                },
            ]
        }
        signals = miner._parse_extractions(response, "ENCÀRREC.pdf")
        assert len(signals) == 2
        assert signals[0].maps_to == "client_name"
        assert signals[0].value == "Joan Garcia SL"
        assert signals[0].confidence == 0.95
        assert signals[0].priority == GROQ_PRIORITY
        assert signals[0].extraction_method == "groq_llm"
        assert signals[1].maps_to == "municipality"

    def test_empty_values_skipped(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "client_name", "value": "", "confidence": 0.5, "source_quote": ""},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 0

    def test_numeric_signal_type(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "superficie_parcela", "value": "350", "confidence": 0.8, "source_quote": "350 m2"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert signals[0].type == SignalType.NUMERIC

    def test_date_signal_type(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "field_date", "value": "15/03/2026", "confidence": 0.9, "source_quote": "Data: 15/03/2026"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert signals[0].type == SignalType.DATE

    def test_lab_company_not_in_target_variables(self):
        """Fix C (2026-08-31): el lab es resol pel NIF (gtl_lab_identity), Groq només hi aportava soroll."""
        assert "lab_company" not in TARGET_VARIABLES

    def test_lab_company_response_produces_no_signal(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "lab_company", "value": "Lab. Valdemoro", "confidence": 0.8, "source_quote": "Lab. Valdemoro"},
            ]
        }
        signals = miner._parse_extractions(response, "PLAN_COST.xlsx")
        assert signals == []

    def test_unrequested_variable_produces_no_signal(self, project_path):
        """El model no pot tornar variables que no s'han demanat (guarda `variable not in TARGET_VARIABLES`)."""
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "some_variable_not_in_the_schema", "value": "x", "confidence": 0.5, "source_quote": "x"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert signals == []


# ============================================================
# 5. G3 internal data exclusion
# ============================================================

class TestG3DataExclusion:

    def test_g3_nif_excluded(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "client_nif", "value": "B25364589", "confidence": 0.95, "source_quote": "NIF: B25364589"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 0

    def test_g3_email_excluded(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "client_email", "value": "info@g3dt.com", "confidence": 0.9, "source_quote": "email"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 0

    def test_g3_phone_excluded(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "client_phone", "value": "974551273", "confidence": 0.9, "source_quote": "tel"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 0

    def test_g3_municipality_excluded(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "municipality", "value": "Els Omells de Na Gaia", "confidence": 0.9, "source_quote": "loc"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 0

    def test_real_client_data_passes(self, project_path):
        miner = GroqMiner(project_path)
        response = {
            "extractions": [
                {"variable": "client_nif", "value": "12345678A", "confidence": 0.9, "source_quote": "NIF client"},
                {"variable": "client_email", "value": "joan@example.com", "confidence": 0.9, "source_quote": "email"},
                {"variable": "municipality", "value": "Lleida", "confidence": 0.9, "source_quote": "loc"},
            ]
        }
        signals = miner._parse_extractions(response, "test.pdf")
        assert len(signals) == 3


# ============================================================
# 6. Cache tests
# ============================================================

class TestCache:

    def test_cache_hit(self, project_path, sample_pdf, cache_dir):
        """Cached result is returned without API call."""
        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            miner = GroqMiner(project_path)
            file_hash = miner._file_hash(sample_pdf)

            # Pre-populate cache
            cached_data = {
                "_cached_at": "2026-03-20T10:00:00",
                "response": {
                    "extractions": [
                        {"variable": "client_name", "value": "Cached Client", "confidence": 0.9, "source_quote": "test"},
                    ]
                },
            }
            with patch.object(GroqMiner, '_file_hash', return_value=file_hash):
                cache_path = cache_dir / f"{file_hash[:12]}.json"
                cache_path.write_text(json.dumps(cached_data), encoding="utf-8")

                with patch(
                    "automation.fileminer.miners.groq_miner.CACHE_DIR", cache_dir
                ):
                    # mine() should use cache, not call API
                    with patch.object(miner, '_call_groq') as mock_api:
                        signals = miner.mine(sample_pdf)
                        mock_api.assert_not_called()
                        assert len(signals) == 1
                        assert signals[0].value == "Cached Client"

    def test_cache_miss(self, project_path, sample_pdf, cache_dir):
        """API is called when no cache exists."""
        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            miner = GroqMiner(project_path)

            mock_response = {
                "extractions": [
                    {"variable": "client_name", "value": "API Client", "confidence": 0.8, "source_quote": "test"},
                ]
            }

            with patch(
                "automation.fileminer.miners.groq_miner.CACHE_DIR", cache_dir
            ):
                with patch.object(miner, '_extract_text', return_value="some text"):
                    with patch.object(miner, '_call_groq', return_value=mock_response) as mock_api:
                        signals = miner.mine(sample_pdf)
                        mock_api.assert_called_once()
                        assert len(signals) == 1
                        assert signals[0].value == "API Client"


# ============================================================
# 7. mine_project_groq file selection
# ============================================================

class TestMineProjectGroq:

    def test_should_groq_mine_skips_dades(self, tmp_path):
        """dades_camp_excel files are skipped."""
        from automation.fileminer import mine_project_groq
        from automation.fileminer.models import Signal, SignalType

        project = tmp_path / "project"
        project.mkdir()
        dades = project / "DADES.xls"
        dades.write_bytes(b"fake xls content")

        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            signals = mine_project_groq(
                project,
                file_mapping={
                    "roles": {
                        "dpsh_excel": {"path": "DADES.xls", "confidence": 0.9, "detection": "pattern"},
                    }
                },
                missing_variables=["client_name"],
                existing_signals=[],
            )
            # DADES.xls with role dpsh_excel maps to dades_camp_excel -> should be skipped
            assert signals == []

    def test_should_groq_mine_sends_pressupost(self, tmp_path):
        """pressupost files with few signals are sent to Groq."""
        from automation.fileminer import mine_project_groq

        project = tmp_path / "project"
        project.mkdir()
        pressupost = project / "PRESSUPOST.pdf"
        pressupost.write_bytes(b"%PDF-1.4 pressupost content")

        mock_response = {
            "extractions": [
                {"variable": "client_name", "value": "Test SL", "confidence": 0.9, "source_quote": "promotor"},
            ]
        }

        with patch.dict("os.environ", {"G3DT_USE_GROQ": "1", "GROQ_API_KEY": "test-key"}):
            with patch(
                "automation.fileminer.miners.groq_miner.GroqMiner.mine",
                return_value=[
                    Signal(
                        type=SignalType.TEXT, label="client_name", value="Test SL",
                        maps_to="client_name", source_file="PRESSUPOST.pdf",
                        extraction_method="groq_llm", confidence=0.9, priority=42,
                    )
                ],
            ):
                signals = mine_project_groq(
                    project,
                    missing_variables=["client_name"],
                    existing_signals=[],
                )
                assert len(signals) == 1
                assert signals[0].value == "Test SL"


# ============================================================
# 8. Token counting & usage summary
# ============================================================

class TestTokenCounting:

    def setup_method(self):
        GroqMiner.reset_counters()

    def test_reset_counters(self):
        GroqMiner._total_input_tokens = 100
        GroqMiner._total_api_calls = 5
        GroqMiner._total_cache_hits = 3
        GroqMiner.reset_counters()
        assert GroqMiner._total_input_tokens == 0
        assert GroqMiner._total_output_tokens == 0
        assert GroqMiner._total_api_calls == 0
        assert GroqMiner._total_cache_hits == 0

    def test_usage_summary_structure(self):
        summary = GroqMiner.get_usage_summary()
        assert "model" in summary
        assert "api_calls" in summary
        assert "estimated_cost_usd" in summary
        assert "input_tokens" in summary
        assert "output_tokens" in summary
        assert "total_tokens" in summary
        assert "cache_hits" in summary

    def test_usage_summary_cost_calculation(self):
        """Cost is calculated correctly based on token counts and model pricing."""
        GroqMiner._total_input_tokens = 1000
        GroqMiner._total_output_tokens = 500
        GroqMiner._total_api_calls = 2
        with mock.patch.dict(os.environ, {"GROQ_MODEL": "qwen/qwen3.6-27b"}):
            summary = GroqMiner.get_usage_summary()
        # 1000 * 0.60 / 1M + 500 * 3.00 / 1M = 0.0006 + 0.0015 = 0.0021
        assert summary["estimated_cost_usd"] == 0.0021
        assert summary["total_tokens"] == 1500
        assert summary["model"] == "qwen/qwen3.6-27b"


# ============================================================
# 9. Cache includes model in hash
# ============================================================

class TestCacheIncludesModel:

    def test_different_models_different_hashes(self):
        """File hash should differ when GROQ_MODEL changes."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"test content for hash")
            f.flush()
            path = Path(f.name)

        try:
            # Two LIVE models (retired ids collapse onto their successor and
            # would share a cache key on purpose — see config.RETIRED_GROQ_MODELS).
            with mock.patch.dict(os.environ, {"GROQ_MODEL": "qwen/qwen3.6-27b"}):
                hash1 = GroqMiner._file_hash(path)
            with mock.patch.dict(os.environ, {"GROQ_MODEL": "openai/gpt-oss-20b"}):
                hash2 = GroqMiner._file_hash(path)
            assert hash1 != hash2
            # and a retired id keys the same as its successor
            with mock.patch.dict(os.environ, {"GROQ_MODEL": "qwen/qwen3-32b"}):
                assert GroqMiner._file_hash(path) == hash1
        finally:
            path.unlink()

    def test_same_model_same_hash(self):
        """Same file + same model = same hash."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"test content for hash")
            f.flush()
            path = Path(f.name)

        try:
            with mock.patch.dict(os.environ, {"GROQ_MODEL": "llama-3.3-70b-versatile"}):
                hash1 = GroqMiner._file_hash(path)
                hash2 = GroqMiner._file_hash(path)
            assert hash1 == hash2
        finally:
            path.unlink()
