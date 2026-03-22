"""Integration tests for progressive Cadastre address resolution.

These tests call the REAL Cadastre API -- not mocked.
Run with: pytest tests/test_cadastre_progressive.py -v
Mark: @pytest.mark.network (requires internet access)
"""

import pytest
import time

from automation.geocode_coordinates import (
    _consulta_municipio,
    _consulta_via,
    cadastre_progressive_lookup,
)

# Addresses from Eva's reference reports (real-world variance)
PROJECTS = [
    {
        "id": "4001612",
        "name": "BELL-LLOC",
        "street_name": "Mestre Ramon Ortiz",
        "house_number": "15",
        "municipality_hint": "Bell-Lloc",
        "province": "Lleida",
        "expected_municipality": "BELL-LLOC D'URGELL",
        "expected_rc_prefix": "4613172",
    },
    {
        "id": "4001679",
        "name": "ANCILES",
        "street_name": "Ferraz",
        "house_number": "20",
        "municipality_hint": "Benasque",
        "province": "Huesca",
        "expected_municipality": "BENASQUE",
        # Number 20 doesn't exist on CL DIRECTOR FERRAZ; API returns nearest (18)
        "expected_rc_prefix": "6803719",
    },
    {
        "id": "3001621",
        "name": "CASTELLAR DEL VALLES",
        "street_name": "Arbrells",
        "house_number": "18",
        "municipality_hint": "Castellar del Valles",
        "province": "Barcelona",
        "expected_municipality": "CASTELLAR DEL VALLES",
        "expected_rc_prefix": None,
    },
    {
        "id": "3001631",
        "name": "RUBI",
        "street_name": "Miranda",
        "house_number": "39",
        "municipality_hint": "Rubi",
        "province": "Barcelona",
        "expected_municipality": "RUBI",
        "expected_rc_prefix": None,
    },
    {
        "id": "4001607",
        "name": "LINYOLA",
        "street_name": "Clot de la Llacuna",
        "house_number": "16",
        "municipality_hint": "Linyola",
        "province": "Lleida",
        "expected_municipality": "LINYOLA",
        "expected_rc_prefix": None,
    },
    {
        "id": "4001670",
        "name": "ALCOLETGE",
        "street_name": "Girasols",
        "house_number": "7",
        "municipality_hint": "Alcoletge",
        "province": "Lleida",
        "expected_municipality": "ALCOLETGE",
        "expected_rc_prefix": None,
    },
    {
        "id": "4001671",
        "name": "VILANOVA DE SEGRIA",
        "street_name": "Sta. Gemma",
        "house_number": "4",
        "municipality_hint": "Vilanova de Segria",
        "province": "Lleida",
        "expected_municipality": "VILANOVA DE SEGRIA",
        "expected_rc_prefix": None,
    },
]


@pytest.mark.network
class TestConsultaMunicipio:
    """Test municipality fuzzy resolution against real Cadastre API."""

    @pytest.fixture(autouse=True)
    def _rate_limit(self):
        yield
        time.sleep(0.5)

    @pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p["name"])
    def test_municipality_found(self, project):
        result = _consulta_municipio(project["province"], project["municipality_hint"])
        assert result is not None, f"Municipality not found for hint: {project['municipality_hint']}"
        official_name, cp, cm = result
        assert official_name, "Empty official name"
        assert cp, "Empty province code"
        assert cm, "Empty municipality code"
        if project.get("expected_municipality"):
            assert official_name.upper() == project["expected_municipality"].upper(), \
                f"Expected {project['expected_municipality']}, got {official_name}"


@pytest.mark.network
class TestConsultaVia:
    """Test street fuzzy resolution against real Cadastre API."""

    @pytest.fixture(autouse=True)
    def _rate_limit(self):
        yield
        time.sleep(0.5)

    @pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p["name"])
    def test_street_found(self, project):
        if not project["street_name"]:
            pytest.skip("No street name for this project")
        # First resolve municipality
        muni = _consulta_municipio(project["province"], project["municipality_hint"])
        assert muni is not None, f"Municipality resolution failed: {project['municipality_hint']}"
        official_muni, _, _ = muni
        time.sleep(0.5)
        # Then resolve street
        result = _consulta_via(project["province"], official_muni, project["street_name"])
        assert result is not None, f"Street not found: '{project['street_name']}' in {official_muni}"
        street_name, tipo_via, cv = result
        assert street_name, "Empty street name"


@pytest.mark.network
class TestFullProgressiveLookup:
    """End-to-end progressive Cadastre lookup."""

    @pytest.fixture(autouse=True)
    def _rate_limit(self):
        yield
        time.sleep(1.0)

    @pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p["name"])
    def test_full_lookup(self, project):
        if not project["street_name"]:
            pytest.skip("No street name for this project")
        result = cadastre_progressive_lookup(
            street_name=project["street_name"],
            house_number=project["house_number"],
            municipality_hint=project["municipality_hint"],
            province=project["province"],
        )
        assert result is not None, f"Progressive lookup failed for {project['name']}"
        assert result.get("rc"), f"No RC for {project['name']}"
        if project.get("expected_rc_prefix"):
            assert result["rc"].startswith(project["expected_rc_prefix"]), \
                f"RC mismatch: got {result['rc']}, expected prefix {project['expected_rc_prefix']}"
        # Log for manual inspection
        print(f"\n  {project['name']}: RC={result['rc']}")
