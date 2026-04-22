"""Tests for the G3 internal-address pre-filter inside resolve_competition."""

from __future__ import annotations

from automation.fileminer.competition import resolve_competition
from automation.fileminer.models import Signal, SignalType


def _make_signal(
    *,
    value,
    concept_id: str,
    source_file: str = "anon.xls",
    source_type: str = "dades_camp_excel",
    priority: int = 50,
    confidence: float = 0.8,
) -> Signal:
    return Signal(
        type=SignalType.TEXT,
        label="ADRECA OBRA",
        value=value,
        raw_value=str(value),
        maps_to=concept_id,
        concept_id=concept_id,
        source_file=source_file,
        extraction_method="cell_adjacent",
        confidence=confidence,
        priority=priority,
        source_type=source_type,
    )


class TestG3FilterPreCompetition:
    def test_g3_signal_dropped_non_g3_wins(self):
        g3 = _make_signal(
            value="C/ Vallbona, 22",
            concept_id="street_address",
            source_file="comanda_lab.xls",
            source_type="dades_camp_excel",
        )
        real = _make_signal(
            value="C. Santa Gemma, 4",
            concept_id="street_address",
            source_file="A.01.pdf",
            source_type="pressupost_pdf",
            confidence=0.9,
        )
        resolved = resolve_competition([g3, real])
        assert "street_address" in resolved
        assert resolved["street_address"].value == "C. Santa Gemma, 4"
        # The dropped G3 signal must not linger as an alternative.
        assert all(
            alt.value != "C/ Vallbona, 22"
            for alt in resolved["street_address"].alternatives
        )

    def test_only_g3_signal_means_concept_absent(self):
        g3 = _make_signal(
            value="C/ Vallbona, 22",
            concept_id="street_address",
        )
        resolved = resolve_competition([g3])
        assert "street_address" not in resolved

    def test_g3_value_on_non_address_concept_kept(self):
        """Filter scope is addresses only. A client_name that happens to
        contain "Vallbona 22" must NOT be filtered."""
        sig = _make_signal(
            value="Vallbona 22 SL",
            concept_id="client_name",
        )
        resolved = resolve_competition([sig])
        assert "client_name" in resolved
        assert resolved["client_name"].value == "Vallbona 22 SL"

    def test_non_string_address_value_not_crashed(self):
        """Filter must be a no-op on non-string address values."""
        sig = _make_signal(
            value=12345,  # nonsense but shouldn't crash
            concept_id="street_address",
        )
        resolved = resolve_competition([sig])
        assert "street_address" in resolved
        assert resolved["street_address"].value == 12345

    def test_site_address_also_filtered(self):
        g3 = _make_signal(value="Vallbona 22", concept_id="site_address")
        real = _make_signal(
            value="Av. Mestral 3", concept_id="site_address", source_file="memoria.pdf",
        )
        resolved = resolve_competition([g3, real])
        assert resolved["site_address"].value == "Av. Mestral 3"

    def test_client_address_also_filtered(self):
        g3 = _make_signal(value="C/ Vallbona, 22 — Rubi", concept_id="client_address")
        real = _make_signal(
            value="C. Gran Via 100",
            concept_id="client_address",
            source_file="fitxa_client.xlsx",
        )
        resolved = resolve_competition([g3, real])
        assert resolved["client_address"].value == "C. Gran Via 100"
