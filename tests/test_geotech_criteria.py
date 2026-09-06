"""P3 — paràmetres geomecànics per criteri, com a candidats amb procedència.

Veritat: les 11 files de la taula de característiques geotècniques dels 7 informes signats
(`docs/golden-read-taules/_eva_truth/*.json`). Per a cada cel·la, o bé el DEFECTE coincideix amb el signat,
o bé el signat és entre els candidats (llista explícita `KNOWN_MISSES`: si un dia el defecte l'encerta, la
prova ho diu i s'actualitza la llista; si deixa de ser candidat, falla). Cap valor s'inventa.
"""

from __future__ import annotations

import pytest

from automation.geotech_criteria import (
    Candidate, alternatives_for_wizard, d23_band_E, geotech_by_criteria, lith_flags, regime_for,
    rock_kind, round_E, seismic_type_for,
)

# (nom, descripció, soil_type, Nb, rebuig, signat: γ, c, φ, E imprès)
SIGNED = [
    ("bell-lloc-1", "Graves en matriu sorrenca carbonatades", "grava", 25, True, (2.00, 0.00, 38, "650")),
    ("castellar-1", "Bretxes amb intercalacions de lutites i gresos vermells. Substrat rocós.", "rock", 17, True, (2.20, 1.00, 35, ">500")),
    ("rubi-1", "Graves i sorres, carbonatades", "granular", 47, True, (2.00, 0.05, 39, "450")),
    ("linyola-1", "Llims argilosos i sorrencs", "limo", 13, False, (1.90, 0.05, 28, "100")),
    ("linyola-2", "Lutites i sorrenques alterades, substrat", "rock", 31, True, (2.20, 1.00, 30, ">800")),
    ("alcoletge-1", "Sorres argiloses de rebliment", "arena", 5, False, (1.80, 0.00, 28, "50")),
    ("alcoletge-2", "Lutites i sorrenques alterades", "rock", 100, True, (2.00, 1.00, 30, ">400")),
    ("vilanova-1", "Arcilla limosa y arenosa con algunas gravas", "arcilla", 9, False, (1.90, 0.10, 25, "50")),
    ("vilanova-2", "Areniscas, arenas, sustrato", "rock", 57, True, (2.20, 0.50, 34, "550")),
    ("anciles-1", "Arcillas arenosas con gravitas", "arcilla", 5, False, (1.90, 0.10, 28, "90")),
    ("anciles-2", "Bolos y gravas de granito en matriz arenosa y arcillosa", "grava", 15, True, (2.00, 0.00, 38, ">350")),
]

# Cel·les que el defecte NO encerta (el signat hi és com a candidat amb la seva font).
KNOWN_MISSES = {
    ("bell-lloc-1", "E"),     # 450 defecte; 650 = ajust carbonatades (Rubí, també carbonatat, signa 450)
    ("rubi-1", "cohesion"),   # 0,00 defecte; 0,05 = granular carbonatat
    ("linyola-2", "E"),       # >500 defecte; >800 lutites
    ("alcoletge-2", "gamma"), # 2,20 defecte; 2,00 roca alterada
    ("alcoletge-2", "E"),     # >500 defecte; >400 lutites alterades
    ("vilanova-2", "cohesion"),  # 1,00 defecte; 0,50 roca tova (sorrenques)
    ("vilanova-2", "E"),      # >500 defecte; 550 gresos/sorrenques
    ("anciles-1", "E"),       # 50 defecte; 90 argila sorrenca (Anciles)
    ("anciles-2", "E"),       # 450 defecte; >350 bolos
}


def _display(param: str, value) -> str:
    if param == "E":
        return str(value)
    if param == "phi":
        return str(int(value))
    return f"{float(value):.2f}"


@pytest.mark.parametrize("name, desc, st, nb, refusal, signed", SIGNED, ids=[r[0] for r in SIGNED])
@pytest.mark.parametrize("param, idx", [("gamma", 0), ("cohesion", 1), ("phi", 2), ("E", 3)])
def test_signed_cell_is_default_or_candidate(name, desc, st, nb, refusal, signed, param, idx):
    crit = geotech_by_criteria(nb, nb * 0.83, st, desc, refusal)
    target = _display(param, signed[idx])
    got = crit.E_display if param == "E" else _display(param, getattr(crit, param))
    cands = [c.display for c in crit.candidates[param]]
    assert cands[0] == got, "el primer candidat és el defecte"
    if (name, param) in KNOWN_MISSES:
        assert got != target, f"{name} {param}: el defecte ja encerta el signat; treu-lo de KNOWN_MISSES"
        assert target in cands, f"{name} {param}: el signat {target} ha de ser candidat ({cands})"
        src = next(c.source for c in crit.candidates[param] if c.display == target)
        assert src, "cada candidat porta procedència"
    else:
        assert got == target, f"{name} {param}: defecte {got} ≠ signat {target} (candidats {cands})"


def test_every_candidate_has_provenance():
    for name, desc, st, nb, refusal, _ in SIGNED:
        crit = geotech_by_criteria(nb, nb * 0.83, st, desc, refusal)
        for param, cands in crit.candidates.items():
            assert cands, f"{name} {param}: sense candidats"
            for c in cands:
                assert isinstance(c, Candidate) and c.source.strip(), f"{name} {param}: candidat sense font"
            assert len({c.display for c in cands}) == len(cands), f"{name} {param}: candidats repetits"


# ------------------------------------------------------------------ criteris de règim i sísmica


@pytest.mark.parametrize("nb, refusal, rock, expected", [
    (5, False, False, "fluix"), (9.9, False, False, "fluix"), (10, False, False, "mitja"), (29, False, False, "mitja"),
    (30, False, False, "dens"), (15, True, False, "dens"), (5, True, False, "dens"), (60, False, True, "roca"),
])
def test_regime(nb, refusal, rock, expected):
    assert regime_for(nb, refusal, rock) == expected


def test_seismic_type_follows_regime_not_raw_n20():
    """Castellar (roca, N20 22) i Bell-lloc (25-R) signen Tipus II; abans sortien III pels llindars d'N20."""
    assert seismic_type_for("roca") == ("Tipus II", "1.3")
    assert seismic_type_for("dens") == ("Tipus II", "1.3")
    assert seismic_type_for("mitja", "grava") == ("Tipus III", "1.6")
    assert seismic_type_for("mitja", "transicional") == ("Tipus IV", "2.0")   # Linyola 1: llims, Nb 13 → IV
    assert seismic_type_for("fluix", "grava") == ("Tipus IV", "2.0")
    for name in ("castellar-1", "bell-lloc-1", "rubi-1", "linyola-2"):
        row = next(r for r in SIGNED if r[0] == name)
        assert geotech_by_criteria(row[3], row[3] * 0.83, row[2], row[1], row[4]).seismic_type == "Tipus II", name
    for name in ("linyola-1", "alcoletge-1", "vilanova-1", "anciles-1"):
        row = next(r for r in SIGNED if r[0] == name)
        assert geotech_by_criteria(row[3], row[3] * 0.83, row[2], row[1], row[4]).seismic_type == "Tipus IV", name


# ------------------------------------------------------------------ E: arrodoniment, sòl, rebuig, roca


@pytest.mark.parametrize("raw, expected", [
    (8, 10), (49, 50), (54, 50), (56, 60), (94, 90), (99.9, 100), (114, 100), (126, 150), (469, 450), (653, 650), (714, 700),
])
def test_round_E(raw, expected):
    assert round_E(raw) == expected


def test_E_never_below_50_for_soil():
    c = geotech_by_criteria(3, 2.5, "arcilla", "Argiles", False)
    assert c.E == 50 and c.E_display == "50"
    assert any(x.display == "8" for x in c.candidates["E"]), "la fórmula anterior queda com a candidat, no s'amaga"


def test_E_refusal_in_gravel_lifts_to_medios_band():
    without = geotech_by_criteria(20, 16.6, "grava", "Graves", False)
    with_r = geotech_by_criteria(20, 16.6, "grava", "Graves", True)
    assert without.E == 100 and with_r.E == 450
    assert "medios" in with_r.candidates["E"][0].source


def test_E_rock_prints_greater_than_and_keeps_numeric_value():
    c = geotech_by_criteria(17, 14, "rock", "Bretxes", True)
    assert c.E == 500 and c.E_display == ">500"


def test_E_carbonatades_candidate_is_the_40pct_band_point():
    c = geotech_by_criteria(25, 20.75, "grava", "Graves carbonatades", True)
    carb = next(x for x in c.candidates["E"] if "carbonatades" in x.source)
    assert carb.display == "650" == str(round_E(d23_band_E(25, 0.4)))
    assert c.candidates["E"][0].display == "450", "el defecte no aplica l'ajust: Rubí, carbonatat, signa 450"


# ------------------------------------------------------------------ φ per litologia


def test_phi_gravel_dense_band_38_or_39():
    assert geotech_by_criteria(25, 20.75, "grava", "Graves", True).phi == 38
    assert geotech_by_criteria(47, 39, "granular", "Graves i sorres", True).phi == 39
    assert geotech_by_criteria(15, 12.5, "grava", "Bolos y gravas", True).phi == 38
    assert geotech_by_criteria(20, 16.6, "grava", "Graves", False).phi == 33   # Crespo «media», sense rebuig


def test_phi_transitional_anchor_28_and_clayey_silt_25():
    assert geotech_by_criteria(13, 11, "limo", "Llims argilosos i sorrencs", False).phi == 28
    assert geotech_by_criteria(5, 4, "arena", "Sorres argiloses de rebliment", False).phi == 28
    assert geotech_by_criteria(5, 4, "arcilla", "Arcillas arenosas", False).phi == 28
    assert geotech_by_criteria(9, 7.5, "arcilla", "Arcilla limosa y arenosa", False).phi == 25


def test_phi_rock_by_lithology():
    assert geotech_by_criteria(17, 14, "rock", "Bretxes amb lutites", True).phi == 35
    assert geotech_by_criteria(31, 26, "rock", "Lutites i sorrenques", True).phi == 30
    assert geotech_by_criteria(57, 47, "rock", "Areniscas, arenas, sustrato", True).phi == 34
    assert rock_kind(lith_flags("Bretxes amb intercalacions de lutites")) == "bretxes"


# ------------------------------------------------------------------ senyals i wizard


def test_lith_flags_ca_es_without_accents():
    f = lith_flags("Graves en matriu sorrenca carbonatades")
    assert f["carbonatat"] and f["grava"] and f["sorra"] and not f["argila"]
    f = lith_flags("Sorres argiloses de rebliment")
    assert f["rebliment"] and f["argila"] and f["sorra"]
    f = lith_flags("Rebliment antròpic")
    assert f["rebliment"]
    assert lith_flags("Bolos y gravas de granito")["bolos"]
    assert lith_flags("Lutites alterades")["alterat"]


def test_alternatives_for_wizard_excludes_the_default_and_uses_prefill_keys():
    c = geotech_by_criteria(47, 39, "granular", "Graves i sorres, carbonatades", True)
    alts = alternatives_for_wizard(c)
    assert set(alts) <= {"geomech_gamma", "geomech_cohesion", "geomech_phi", "geomech_E"}
    assert all(a["source"] for k in alts for a in alts[k])
    assert 0.05 in [a["value"] for a in alts["geomech_cohesion"]]
    assert c.E not in [a["value"] for a in alts["geomech_E"]]
