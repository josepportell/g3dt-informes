"""
FileMiner tests -- models, competition, label_map, integration with real projects.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.fileminer.models import Signal, SignalType, MiningResult, ResolvedValue
from automation.fileminer.competition import resolve_competition
from automation.fileminer.label_map import LABEL_TO_VARIABLE, get_priority, SOURCE_PRIORITY
from automation.fileminer import mine_project


REF_DIR = Path(__file__).resolve().parent.parent / 'reference-material'


def _project_exists(name: str) -> bool:
    return (REF_DIR / name).is_dir()


def _cleanup_mined_images(project_path: Path) -> None:
    """Remove mined_images directories created during mining."""
    for d in project_path.rglob("mined_images"):
        if d.is_dir():
            import shutil
            shutil.rmtree(d, ignore_errors=True)


# ============================================================
# 1. Unit tests for models
# ============================================================

class TestModels:
    """Verify Pydantic models for signals, results, resolved values."""

    def test_signal_creation_all_fields(self):
        sig = Signal(
            type=SignalType.TEXT,
            label="CLIENT",
            value="Test Company SL",
            raw_value="Test Company SL",
            maps_to="client_name",
            source_file="DADES.xlsx",
            source_location="Sheet 'fitxa', cell B3",
            extraction_method="label_adjacent",
            confidence=0.90,
            priority=35,
        )
        assert sig.type == SignalType.TEXT
        assert sig.label == "CLIENT"
        assert sig.value == "Test Company SL"
        assert sig.raw_value == "Test Company SL"
        assert sig.maps_to == "client_name"
        assert sig.source_file == "DADES.xlsx"
        assert sig.source_location == "Sheet 'fitxa', cell B3"
        assert sig.extraction_method == "label_adjacent"
        assert sig.confidence == 0.90
        assert sig.priority == 35

    def test_signal_defaults(self):
        sig = Signal(
            type=SignalType.TEXT,
            label="test",
            value="val",
            source_file="f.txt",
        )
        assert sig.raw_value == ""
        assert sig.maps_to is None
        assert sig.source_location == ""
        assert sig.extraction_method == ""
        assert sig.confidence == 0.5
        assert sig.priority == 50

    def test_signal_type_enum_values(self):
        assert SignalType.TEXT == "text"
        assert SignalType.NUMERIC == "numeric"
        assert SignalType.DATE == "date"
        assert SignalType.IMAGE == "image"
        assert SignalType.COORDS == "coords"
        assert SignalType.URL == "url"
        assert len(SignalType) == 6

    def test_mining_result_aggregation(self):
        result = MiningResult(
            project_path="/some/path",
            signals=[
                Signal(type=SignalType.TEXT, label="a", value="1", source_file="f1"),
                Signal(type=SignalType.TEXT, label="b", value="2", source_file="f2"),
            ],
            files_mined=5,
            files_skipped=3,
            errors=["error1"],
            duration_ms=1234,
        )
        assert result.project_path == "/some/path"
        assert len(result.signals) == 2
        assert result.files_mined == 5
        assert result.files_skipped == 3
        assert result.errors == ["error1"]
        assert result.duration_ms == 1234

    def test_mining_result_defaults(self):
        result = MiningResult(project_path="/p")
        assert result.signals == []
        assert result.files_mined == 0
        assert result.files_skipped == 0
        assert result.errors == []
        assert result.duration_ms == 0

    def test_resolved_value_with_alternatives(self):
        winner = Signal(
            type=SignalType.TEXT,
            label="CLIENT",
            value="Winner Inc",
            source_file="dades.xlsx",
            maps_to="client_name",
            confidence=0.90,
            priority=35,
        )
        loser = Signal(
            type=SignalType.TEXT,
            label="CLIENTE",
            value="Loser SA",
            source_file="report.pdf",
            maps_to="client_name",
            confidence=0.80,
            priority=45,
        )
        rv = ResolvedValue(
            variable="client_name",
            value="Winner Inc",
            source="dades.xlsx",
            confidence=0.90,
            signal=winner,
            alternatives=[loser],
        )
        assert rv.variable == "client_name"
        assert rv.value == "Winner Inc"
        assert len(rv.alternatives) == 1
        assert rv.alternatives[0].value == "Loser SA"


# ============================================================
# 2. Unit tests for competition.py
# ============================================================

class TestCompetition:
    """Verify signal competition resolution logic."""

    def _make_signal(self, maps_to, value, priority, confidence, source="file.txt"):
        return Signal(
            type=SignalType.TEXT,
            label="test",
            value=value,
            source_file=source,
            maps_to=maps_to,
            priority=priority,
            confidence=confidence,
        )

    def test_lower_priority_wins(self):
        """Lower priority number wins over higher."""
        signals = [
            self._make_signal("client_name", "From PDF", 45, 0.90, "report.pdf"),
            self._make_signal("client_name", "From Excel", 35, 0.90, "dades.xls"),
        ]
        resolved = resolve_competition(signals)
        assert resolved["client_name"].value == "From Excel"

    def test_same_priority_higher_confidence_wins(self):
        """Same priority: higher confidence wins."""
        signals = [
            self._make_signal("client_name", "Low conf", 35, 0.70, "a.xls"),
            self._make_signal("client_name", "High conf", 35, 0.95, "b.xls"),
        ]
        resolved = resolve_competition(signals)
        assert resolved["client_name"].value == "High conf"

    def test_maps_to_none_skipped(self):
        """Signals with maps_to=None should not appear in results."""
        signals = [
            self._make_signal(None, "unmapped", 45, 0.90),
            self._make_signal("client_name", "mapped", 35, 0.80),
        ]
        resolved = resolve_competition(signals)
        assert "client_name" in resolved
        assert len(resolved) == 1  # Only mapped signal

    def test_alternatives_populated(self):
        """Losers appear in alternatives list."""
        signals = [
            self._make_signal("municipality", "ANCILES", 35, 0.90, "comanda.xls"),
            self._make_signal("municipality", "ELS OMELLS", 45, 0.80, "report.pdf"),
            self._make_signal("municipality", "BENASQUE", 45, 0.70, "other.pdf"),
        ]
        resolved = resolve_competition(signals)
        rv = resolved["municipality"]
        assert rv.value == "ANCILES"
        assert len(rv.alternatives) == 2
        alt_values = [a.value for a in rv.alternatives]
        assert "ELS OMELLS" in alt_values
        assert "BENASQUE" in alt_values

    def test_multiple_variables_resolved(self):
        """Multiple variables are resolved independently."""
        signals = [
            self._make_signal("client_name", "Alice", 35, 0.90),
            self._make_signal("municipality", "Lleida", 35, 0.80),
        ]
        resolved = resolve_competition(signals)
        assert len(resolved) == 2
        assert resolved["client_name"].value == "Alice"
        assert resolved["municipality"].value == "Lleida"

    def test_empty_signals(self):
        resolved = resolve_competition([])
        assert resolved == {}

    def test_single_signal_no_alternatives(self):
        signals = [self._make_signal("client_nif", "12345678A", 35, 0.90)]
        resolved = resolve_competition(signals)
        assert resolved["client_nif"].value == "12345678A"
        assert resolved["client_nif"].alternatives == []


# ============================================================
# 3. Unit tests for label_map.py
# ============================================================

class TestLabelMap:
    """Verify label-to-variable mapping and source priorities."""

    @pytest.mark.parametrize("label,expected", [
        ("CLIENT", "client_name"),
        ("CLIENTE", "client_name"),
        ("NIF", "client_nif"),
        ("CIF", "client_nif"),
        ("ADREÇA OBRA", "street_address"),
        ("DIRECCIÓN OBRA", "street_address"),
        ("MUNICIPI", "municipality"),
        ("MUNICIPIO", "municipality"),
        ("ARQUITECTE", "architect_name"),
        ("TELÈFON", "client_phone"),
        ("EMAIL", "client_email"),
        ("ACCES A LA ZONA D'ESTUDI", "access_url"),
        ("EXPEDIENT", "expedient"),
        ("DATA", "field_date"),
    ])
    def test_label_to_variable_known_labels(self, label, expected):
        assert LABEL_TO_VARIABLE[label] == expected

    def test_label_to_variable_catalan_spanish_parity(self):
        """Key labels have both Catalan and Spanish variants."""
        # All these pairs should map to the same variable
        pairs = [
            ("CLIENT", "CLIENTE"),
            ("MUNICIPI", "MUNICIPIO"),
            ("TELÈFON", "TELÉFONO"),
            ("ADREÇA OBRA", "DIRECCIÓN OBRA"),
            ("ARQUITECTE", "ARQUITECTO"),
        ]
        for cat, es in pairs:
            assert LABEL_TO_VARIABLE[cat] == LABEL_TO_VARIABLE[es], (
                f"{cat} and {es} should map to same variable"
            )

    def test_get_priority_known_sources(self):
        # Global priority = minimum across all concepts for each source_type
        assert get_priority("user") == 10
        assert get_priority("dades_camp_excel") == 35
        # content_pdf global min lowered to 35 by client_name per-concept priority
        assert get_priority("content_pdf") <= 45
        assert get_priority("folder_name") == 15  # expedient: folder_name is most reliable
        assert get_priority("coordenades_txt") == 25

    def test_get_priority_unknown_returns_50(self):
        assert get_priority("totally_unknown_source") == 50
        assert get_priority("") == 50

    def test_source_priority_ordering(self):
        """User edits should always beat automated sources."""
        assert SOURCE_PRIORITY["user"] < SOURCE_PRIORITY["dades_camp_excel"]
        assert SOURCE_PRIORITY["dades_camp_excel"] <= SOURCE_PRIORITY["content_pdf"]
        # folder_name global min is 15 (expedient uses it as primary source)
        assert SOURCE_PRIORITY["user"] <= SOURCE_PRIORITY["folder_name"]


# ============================================================
# 4. Integration tests with real project files
# ============================================================

class TestIntegrationAnciles:
    """mine_project() on Anciles -- DADES, comanda lab, PDFs."""

    PROJECT = "4001679 ANCILES"

    @pytest.fixture(autouse=True)
    def _setup(self):
        if not _project_exists(self.PROJECT):
            pytest.skip(f"{self.PROJECT} not in reference-material")
        self.project_path = REF_DIR / self.PROJECT
        yield
        _cleanup_mined_images(self.project_path)

    @pytest.fixture()
    def mining_result(self):
        return mine_project(self.project_path)

    @pytest.fixture()
    def resolved(self, mining_result):
        return resolve_competition(mining_result.signals)

    def test_no_errors(self, mining_result):
        assert mining_result.errors == [], (
            f"Mining errors: {mining_result.errors}"
        )

    def test_at_least_4_mapped_signals(self, mining_result):
        mapped = [s for s in mining_result.signals if s.maps_to is not None]
        mapped_vars = set(s.maps_to for s in mapped)
        expected = {"client_name", "street_address", "access_url", "contact_name"}
        assert expected.issubset(mapped_vars), (
            f"Missing variables: {expected - mapped_vars}"
        )

    def test_municipality_is_anciles(self, resolved):
        """Competition should resolve municipality to ANCILES, not G3's office town."""
        assert "municipality" in resolved
        assert "ANCILES" in resolved["municipality"].value.upper()

    def test_client_nif_is_personal(self, resolved):
        """NIF should be the client's, not G3's CIF B25364589."""
        assert "client_nif" in resolved
        assert resolved["client_nif"].value == "18037382T"

    def test_performance_under_5s(self):
        t0 = time.monotonic()
        mine_project(self.project_path)
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0, f"Mining took {elapsed:.2f}s (limit: 10.0s)"


class TestIntegrationBellLloc:
    """mine_project() on Bell-Lloc -- DADES CLIENT.txt, COORDENADES.txt."""

    PROJECT = "4001612 BELL-LLOC"

    @pytest.fixture(autouse=True)
    def _setup(self):
        if not _project_exists(self.PROJECT):
            pytest.skip(f"{self.PROJECT} not in reference-material")
        self.project_path = REF_DIR / self.PROJECT
        yield
        _cleanup_mined_images(self.project_path)

    @pytest.fixture()
    def mining_result(self):
        return mine_project(self.project_path)

    def test_no_errors(self, mining_result):
        assert mining_result.errors == [], (
            f"Mining errors: {mining_result.errors}"
        )

    def test_finds_utm_coordinates(self, mining_result):
        utm_signals = [
            s for s in mining_result.signals
            if s.maps_to == "utm_coordinates"
        ]
        assert len(utm_signals) >= 1, "Should find UTM coordinates from COORDENADES.txt"
        # Check actual coordinate values from the file
        first = utm_signals[0]
        assert isinstance(first.value, dict)
        assert abs(first.value["x"] - 314418.9) < 1.0
        assert abs(first.value["y"] - 4611117.6) < 1.0

    def test_performance_under_5s(self):
        t0 = time.monotonic()
        mine_project(self.project_path)
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0, f"Mining took {elapsed:.2f}s (limit: 10.0s)"


class TestIntegrationRubi:
    """mine_project() on Rubi -- COORDENADES.txt with 3 points."""

    PROJECT = "3001631 RUBI"

    @pytest.fixture(autouse=True)
    def _setup(self):
        if not _project_exists(self.PROJECT):
            pytest.skip(f"{self.PROJECT} not in reference-material")
        self.project_path = REF_DIR / self.PROJECT
        yield
        _cleanup_mined_images(self.project_path)

    @pytest.fixture()
    def mining_result(self):
        return mine_project(self.project_path)

    def test_no_errors(self, mining_result):
        assert mining_result.errors == [], (
            f"Mining errors: {mining_result.errors}"
        )

    def test_finds_utm_coordinates(self, mining_result):
        utm_signals = [
            s for s in mining_result.signals
            if s.maps_to == "utm_coordinates"
        ]
        assert len(utm_signals) >= 1, "Should find UTM coordinates from COORDENADES.txt"

    def test_performance_under_5s(self):
        t0 = time.monotonic()
        mine_project(self.project_path)
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0, f"Mining took {elapsed:.2f}s (limit: 10.0s)"


# ============================================================
# 5. ExcelMiner unit tests
# ============================================================

class TestExcelMiner:
    """Unit tests for ExcelMiner edge cases."""

    def _make_miner(self, tmp_path, source_type="dades_camp_excel"):
        from automation.fileminer.miners.excel_miner import ExcelMiner
        return ExcelMiner(tmp_path, source_type)

    def test_phone_detection_skips_numeric_cells(self, tmp_path):
        """Phone regex must not fire on numeric cells (Vilanova MULTICA_61.xls bug)."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "content_excel")

        # Simulate a grid with a numeric cell that looks phone-like
        # e.g., 612345678 as a float (from Excel)
        grid = [
            [(612345678.0, "A")],  # pure numeric - should NOT trigger phone
            [("612 345 678", "A")],  # text string - SHOULD trigger phone
        ]

        signals = miner._mine_grid(grid, "test.xls", "Sheet1")

        # Gather phone signals from regex (not label-adjacent)
        phone_regex = [
            s for s in signals
            if s.extraction_method == "regex_phone"
        ]

        # Only the text cell should produce a phone signal
        assert len(phone_regex) == 1, (
            f"Expected 1 phone signal (from text), got {len(phone_regex)}: "
            f"{[(s.value, s.source_location) for s in phone_regex]}"
        )
        assert phone_regex[0].value == "612345678"

    def test_label_value_detection(self, tmp_path):
        """Label cells matching LABEL_TO_VARIABLE should extract adjacent values."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "dades_camp_excel")

        grid = [
            [("CLIENT", "A"), ("Empresa Test SL", "B")],
            [("MUNICIPI", "A"), ("LLEIDA", "B")],
        ]

        signals = miner._mine_grid(grid, "dades.xls", "fitxa")
        mapped = {s.maps_to: s.value for s in signals if s.extraction_method == "label_adjacent"}

        assert mapped.get("client_name") == "Empresa Test SL"
        assert mapped.get("municipality") == "LLEIDA"

    def test_g3_internal_nif_excluded(self, tmp_path):
        """G3's own CIF B25364589 must be filtered out."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "dades_camp_excel")

        grid = [
            [("NIF", "A"), ("B25364589", "B")],  # G3's CIF
        ]

        signals = miner._mine_grid(grid, "dades.xls", "Sheet1")
        nif_signals = [s for s in signals if s.maps_to == "client_nif"]

        # G3's CIF should be excluded from label-adjacent
        label_nifs = [s for s in nif_signals if s.extraction_method == "label_adjacent"]
        assert len(label_nifs) == 0, (
            f"G3 CIF should be excluded, got: {[s.value for s in label_nifs]}"
        )

    def test_g3_internal_municipality_excluded(self, tmp_path):
        """G3's office town 'ELS OMELLS DE NA GAIA' must be filtered out."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "dades_camp_excel")

        grid = [
            [("MUNICIPI", "A"), ("ELS OMELLS DE NA GAIA", "B")],
        ]

        signals = miner._mine_grid(grid, "dades.xls", "Sheet1")
        muni_signals = [
            s for s in signals
            if s.maps_to == "municipality" and s.extraction_method == "label_adjacent"
        ]
        assert len(muni_signals) == 0, (
            f"G3 office town should be excluded, got: {[s.value for s in muni_signals]}"
        )

    def test_cif_regex_excludes_g3(self, tmp_path):
        """CIF regex should skip G3's CIF B25364589."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "content_excel")

        # Text cell containing G3's CIF
        grid = [
            [("CIF: B25364589 company data", "A")],
        ]

        signals = miner._mine_grid(grid, "test.xls", "Sheet1")
        cif_signals = [s for s in signals if s.extraction_method == "regex_cif"]
        assert len(cif_signals) == 0, "G3 CIF should be excluded from regex detection"

    def test_url_field_requires_actual_url(self, tmp_path):
        """access_url field should only be set when value contains a URL."""
        from automation.fileminer.miners.excel_miner import ExcelMiner

        miner = ExcelMiner(tmp_path, "dades_camp_excel")

        grid = [
            [("ACCES A LA ZONA D'ESTUDI", "A"), ("just some text no url", "B")],
        ]

        signals = miner._mine_grid(grid, "dades.xls", "Sheet1")
        url_signals = [s for s in signals if s.maps_to == "access_url"]
        assert len(url_signals) == 0, (
            "access_url should not be set for non-URL values"
        )


class TestMineProjectEdgeCases:
    """Edge case tests for the mine_project entry point."""

    def test_nonexistent_path(self, tmp_path):
        result = mine_project(tmp_path / "does_not_exist")
        assert len(result.errors) > 0
        assert result.files_mined == 0

    def test_empty_directory(self, tmp_path):
        result = mine_project(tmp_path)
        assert result.errors == []
        assert result.files_mined == 0
        assert len(result.signals) == 0
