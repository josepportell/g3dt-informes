"""Tests for _best_vision_address and its preference in geocode/adjacents phases."""

from __future__ import annotations

from automation.auto_extractor import AutoExtractionResult, _best_vision_address
from automation.concept_scout import ConceptMap, ConceptSource


def _result_with_vision_street(
    *sources: ConceptSource,
) -> AutoExtractionResult:
    r = AutoExtractionResult()
    r.concept_map = ConceptMap(
        concept_sources={"street_address": list(sources)},
    )
    return r


class TestBestVisionAddress:
    def test_returns_architect_plan_when_high_conf(self):
        r = _result_with_vision_street(
            ConceptSource(
                file="A.01.pdf",
                confidence=1.0,
                signal_preview="C. Santa Gemma, 4 Urb. La Serra",
                extraction_method="vision_probe:architect_plan",
            ),
        )
        assert (
            _best_vision_address(r) == "C. Santa Gemma, 4 Urb. La Serra"
        )

    def test_returns_none_when_only_projecte(self):
        r = _result_with_vision_street(
            ConceptSource(
                file="MEMORIA.pdf",
                confidence=1.0,
                signal_preview="Whatever Projecte Says",
                extraction_method="vision_probe:projecte",
            ),
        )
        assert _best_vision_address(r) is None

    def test_returns_none_when_below_confidence(self):
        r = _result_with_vision_street(
            ConceptSource(
                file="A.01.pdf",
                confidence=0.5,
                signal_preview="C. Santa Gemma, 4",
                extraction_method="vision_probe:architect_plan",
            ),
        )
        assert _best_vision_address(r) is None

    def test_picks_highest_confidence(self):
        r = _result_with_vision_street(
            ConceptSource(
                file="A.01.pdf",
                confidence=0.92,
                signal_preview="Candidate Low",
                extraction_method="vision_probe:architect_plan",
            ),
            ConceptSource(
                file="A.02.pdf",
                confidence=0.99,
                signal_preview="Candidate High",
                extraction_method="vision_probe:architect_plan",
            ),
        )
        assert _best_vision_address(r) == "Candidate High"

    def test_returns_none_when_no_concept_map(self):
        r = AutoExtractionResult()
        assert _best_vision_address(r) is None

    def test_returns_none_when_no_street_address_concept(self):
        r = AutoExtractionResult()
        r.concept_map = ConceptMap(concept_sources={})
        assert _best_vision_address(r) is None


class TestGeocodePrefersVision:
    def test_phase25_geocode_uses_vision_address_over_prefill(
        self, tmp_path, monkeypatch,
    ):
        """_phase25_geocode must prefer vision-extracted architect-plan
        address over whatever is in prefills."""
        from automation import auto_extractor

        r = AutoExtractionResult()
        r.concept_map = ConceptMap(
            concept_sources={
                "street_address": [
                    ConceptSource(
                        file="A.01.pdf",
                        confidence=1.0,
                        signal_preview="C. Santa Gemma, 4",
                        extraction_method="vision_probe:architect_plan",
                    ),
                ],
            },
        )
        # Pretend a stale prefill has a different (but non-G3) address.
        r.prefills["site_address"] = "Av. Outdated 99"

        existing_user_data = {"street_address": "Av. Outdated 99"}

        # Make a fake project folder so _extract_municipality resolves.
        proj = tmp_path / "1234567 VILANOVA"
        proj.mkdir()

        seen_address: dict[str, str] = {}

        def fake_geocode_project(*args, **kwargs):
            # geocode_project is called with the address as first positional.
            seen_address["addr"] = args[0] if args else kwargs.get("address", "")
            return None  # Force early return so we don't exercise Callejero

        def fake_callejero(address, municipality, province=""):
            seen_address["addr"] = address
            return None

        monkeypatch.setattr(
            auto_extractor, "geocode_project", fake_geocode_project, raising=False,
        )
        # callejero_address_to_rc is imported inside the function; patch at
        # the module where it lives.
        from automation import geocode_coordinates
        monkeypatch.setattr(
            geocode_coordinates,
            "callejero_address_to_rc",
            fake_callejero,
            raising=False,
        )
        monkeypatch.setattr(
            geocode_coordinates,
            "geocode_project",
            fake_geocode_project,
            raising=False,
        )

        # Run phase
        auto_extractor._phase25_geocode(existing_user_data, r, proj)

        # The address passed to the geocoder must be the vision one (cleaned)
        assert "Santa Gemma" in seen_address.get("addr", "")
        assert "Outdated" not in seen_address.get("addr", "")

    def test_phase3_adjacents_prepends_vision_address(self, tmp_path, monkeypatch):
        """_phase3_adjacents must add vision address as first candidate."""
        from automation import auto_extractor

        r = AutoExtractionResult()
        r.concept_map = ConceptMap(
            concept_sources={
                "street_address": [
                    ConceptSource(
                        file="A.01.pdf",
                        confidence=1.0,
                        signal_preview="C. Santa Gemma, 4",
                        extraction_method="vision_probe:architect_plan",
                    ),
                ],
            },
        )
        r.prefills["site_municipality"] = "Vilanova i la Geltru"
        r.prefills["street_address"] = "Av. Outdated 99"

        tried: list[str] = []

        def fake_geocode_for_adjacents(addr, muni, province=""):
            tried.append(addr)
            return None  # Force candidates exhaustion; we only care about order

        def fake_get_adjacents(*a, **kw):
            return {}

        def fake_get_ref(*a, **kw):
            return None

        monkeypatch.setattr(
            auto_extractor, "_geocode_for_adjacents", fake_geocode_for_adjacents,
        )
        from automation import cadastre_adjacents
        monkeypatch.setattr(
            cadastre_adjacents, "get_adjacent_parcels", fake_get_adjacents,
        )
        monkeypatch.setattr(
            cadastre_adjacents, "get_cadastral_reference", fake_get_ref,
        )

        auto_extractor._phase3_adjacents(
            utm_x=400000.0, utm_y=4500000.0,
            superficie=500.0, result=r,
            project_path=tmp_path, existing_user_data={},
        )

        assert tried, "geocode helper should have been called at least once"
        # Vision address must be attempted first.
        assert "Santa Gemma" in tried[0]


class TestCallejeroFastpathRemoved:
    """Callejero direct fast-path has been removed from auto_extractor; both
    call sites route through geocode_project exclusively (Callejero is still
    exercised internally inside geocode_project's pipeline)."""

    def test_phase25_geocode_uses_geocode_project_not_callejero_fastpath(
        self, tmp_path, monkeypatch,
    ):
        from automation import auto_extractor, geocode_coordinates

        r = AutoExtractionResult()
        r.prefills["site_address"] = "C. Santa Gemma, 4 Urb. La Serra"

        proj = tmp_path / "4001671 VILANOVA DE SEGRIA"
        proj.mkdir()

        gp_calls: list[tuple] = []
        cj_calls: list[tuple] = []

        def fake_geocode_project(*args, **kwargs):
            gp_calls.append((args, kwargs))
            return {
                "utm_x": 298594.78,
                "utm_y": 4620391.33,
                "rc": "8606709CG9280N",
                "source": "geocode:cartociudad",
            }

        def fake_callejero(*args, **kwargs):
            cj_calls.append((args, kwargs))
            return {"utm_x": 1.0, "utm_y": 2.0, "rc": "WRONG"}

        monkeypatch.setattr(
            auto_extractor, "geocode_project", fake_geocode_project, raising=False,
        )
        monkeypatch.setattr(
            geocode_coordinates, "geocode_project", fake_geocode_project,
            raising=False,
        )
        monkeypatch.setattr(
            geocode_coordinates, "callejero_address_to_rc", fake_callejero,
            raising=False,
        )

        utm_x, utm_y = auto_extractor._phase25_geocode({}, r, proj)

        assert gp_calls, "geocode_project must be called"
        assert not cj_calls, (
            f"callejero_address_to_rc must NOT be called from _phase25_geocode; "
            f"got {len(cj_calls)} call(s)"
        )
        assert utm_x == 298594.78 and utm_y == 4620391.33

    def test_geocode_for_adjacents_uses_geocode_project_not_callejero_fastpath(
        self, monkeypatch,
    ):
        from automation import auto_extractor, geocode_coordinates

        gp_calls: list[tuple] = []
        cj_calls: list[tuple] = []

        def fake_geocode_project(*args, **kwargs):
            gp_calls.append((args, kwargs))
            return {
                "utm_x": 298594.78,
                "utm_y": 4620391.33,
                "rc": "8606709CG9280N",
            }

        def fake_callejero(*args, **kwargs):
            cj_calls.append((args, kwargs))
            return {"utm_x": 1.0, "utm_y": 2.0, "rc": "WRONG"}

        monkeypatch.setattr(
            geocode_coordinates, "geocode_project", fake_geocode_project,
            raising=False,
        )
        monkeypatch.setattr(
            geocode_coordinates, "callejero_address_to_rc", fake_callejero,
            raising=False,
        )

        out = auto_extractor._geocode_for_adjacents(
            "C. Santa Gemma, 4 Urb. La Serra", "Vilanova de Segrià",
        )

        assert gp_calls, "geocode_project must be called"
        assert not cj_calls, (
            f"callejero_address_to_rc must NOT be called from "
            f"_geocode_for_adjacents; got {len(cj_calls)} call(s)"
        )
        assert out is not None
        assert out["rc"] == "8606709CG9280N"

    def test_phase25_geocode_handles_geocode_project_none(
        self, tmp_path, monkeypatch,
    ):
        from automation import auto_extractor, geocode_coordinates

        r = AutoExtractionResult()
        r.prefills["site_address"] = "Carrer Inexistent 999"

        proj = tmp_path / "9999999 NOWHERE"
        proj.mkdir()

        def fake_geocode_project(*args, **kwargs):
            return None

        monkeypatch.setattr(
            auto_extractor, "geocode_project", fake_geocode_project, raising=False,
        )
        monkeypatch.setattr(
            geocode_coordinates, "geocode_project", fake_geocode_project,
            raising=False,
        )

        utm_x, utm_y = auto_extractor._phase25_geocode({}, r, proj)

        assert utm_x is None and utm_y is None
