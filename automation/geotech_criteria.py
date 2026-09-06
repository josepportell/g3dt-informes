"""Paràmetres geomecànics per CRITERI, com a candidats amb procedència (P3, 2026-09-06).

Regla d'or (`docs/METODOLOGIA-EVA.md` §0): l'Eva, com el sector, s'aparta de les fórmules amb criteris
pactats — règim de compacitat, ajust per litologia, arrodoniment professional, topalls — i l'E el declara
ella mateixa de judici («agafa la taula, ja ho ajustarem»). Cap correlació publicada sola reprodueix els seus
valors (`RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md` §4.3, repàs R 2026-09-03 negatiu per a l'E). Per tant aquest
mòdul NO és una fórmula nova: per a cada paràmetre dona una llista de candidats, el primer és el defecte
que s'imprimeix, i cadascun diu d'on surt. L'override expert del wizard (`geomech_params`) mana sempre.

Evidència (11 nivells signats, `docs/golden-read-taules/_eva_truth/*.json`, taula de característiques
geotècniques; Nb / γ / c / φ / E):
  Bell-lloc  graves carbonatades      25-R  2,0  0,0   38  650
  Castellar  bretxes (roca)           17-R  2,20 1,0   35  >500
  Rubí       graves i sorres carb.    47-R  2,0  0,05  39  450
  Linyola 1  llims argilosos sorrencs 13    1,90 0,05  28  100
  Linyola 2  lutites (roca)           31-R  2,20 1,0   30  >800
  Alcoletge 1 sorres argiloses rebl.  5-0   1,80 0,00  28  50
  Alcoletge 2 lutites alterades       R     2,00 1,00  30  >400
  Vilanova 1 arcilla limosa arenosa   9     1,90 0,10  25  50
  Vilanova 2 areniscas/arenas sustr.  57-R  2,20 0,50  34  550
  Anciles 1  arcillas arenosas        5     1,90 0,10  28  90
  Anciles 2  bolos y gravas           15-R  2,00 0,00  38  >350

Criteris que en surten (i que aquest mòdul codifica com a DEFECTE; els que no encaixen queden com a
candidats amb la seva font, mai com a valor inventat):
  1. Règim per Nb i rebuig: fluix (< 10), mitjà (10-30), dens (≥ 30 o «R»). El rebuig del DPSH en un nivell
     granular vol dir compacitat densa encara que la mitjana pre-rebuig sigui baixa (Bell-lloc 25-R → φ 38,
     E 650; Anciles 15-R → φ 38).
  2. φ per litologia amb Crespo Villalaz com a font declarada (7/7 informes): graves denses 38 (39 a la meitat
     alta de la banda), transicionals (llims, sorres/argiles amb l'altre component) 28 (àncora Tabla 11.2
     «muy floja», memòria `project_crespo_tabla_11_2`), argila llimosa 25 (nota de Crespo: −3°), roca
     35 (bretxes/conglomerats) / 30 (lutites, margues) / 34 (gresos, sorrenques).
  3. E: taula CTE D.23 banda baixa per als trams mitjos (Rubí 450, Linyola 100), MAI per sota de 50 (cap
     informe signa un mòdul d'un dígit: Alcoletge/Vilanova 50), rebuig granular ⇒ banda «medios» com a
     mínim, roca 500 amb el prefix «>» (Castellar), arrodoniment a desenes (< 100) o a 50 (≥ 100).
     L'ajust litològic ↑ per «carbonatades» (Bell-lloc 650) és CANDIDAT, no defecte: Rubí també és
     carbonatat i signa 450 (pregunta 6b a l'Eva).
  4. c i γ per tipus (com fins ara: 9/11): granular 0,0 / 2,0; transicional 0,05 / 1,90; argila 0,10 / 1,90;
     roca 1,0 / 2,20; rebliment 0,00 / 1,80. Candidats: c 0,05 (granular carbonatat, Rubí), 0,25 (grava
     cimentada, Crespo p.175), 0,50 (roca tova/alterada, Vilanova 2), Hunt c(N) per cohesius.
  5. Tipus de terreny sísmic (NCSE-02, taula sísmica): roca i granular dens → Tipus II (Castellar, Bell-lloc,
     Rubí, Linyola 2), granular mitjà → III, cohesius/transicionals no densos i fluixos → IV (Linyola 1 amb
     Nb 13, Alcoletge 1, Vilanova 1, Anciles 1). Abans era només per llindars d'N20 (Castellar roca sortia III).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any

from .cte_geomech import (
    TABLE_D23, crespo_phi_cohesive, crespo_phi_granular, hunt_cohesion_from_nspt, is_rock,
    nspt_to_E_kg_cm2, nspt_to_phi, rock_params_default, CRESPO_C_CEMENTED_GRAVEL_KGCM2,
)

MN_TO_KG_CM2 = 10.197


def d23_band_E(n: float, position: float) -> float:
    """E (kg/cm²) a la posició relativa `position` (0 = E_min, 1 = E_max) de la banda D.23 que conté N."""
    for n_min, n_max, _, _, _, e_min, e_max in TABLE_D23:
        if n_min <= n < n_max:
            return (e_min + position * (e_max - e_min)) * MN_TO_KG_CM2
    return 500 * MN_TO_KG_CM2


def rock_kind(flags: dict[str, bool]) -> str:
    """Litologia dominant de la roca: bretxes | lutites | gresos | roca (mateixa precedència per φ, c, γ i E)."""
    if flags["bretxes"]:
        return "bretxes"
    if flags["lutites"]:
        return "lutites"
    if flags["gresos"]:
        return "gresos"
    return "roca"

E_FLOOR_KG_CM2 = 50          # cap informe signa un mòdul d'un dígit (Alcoletge, Vilanova: 50)
E_ROCK_BASE_KG_CM2 = 500     # CTE D.23 roques toves, límit inferior; s'imprimeix «>500»
E_MEDIOS_MIN_N = 25          # banda «medios» de la D.23 comença a N = 25
GRANULAR_TYPES = frozenset({"granular", "grava", "arena"})
TRANSITIONAL_TYPES = frozenset({"limo", "arena_limosa", "cohesive"})


@dataclass
class Candidate:
    value: float
    display: str
    source: str
    kind: str = ""
    note: str = ""


@dataclass
class GeotechCriteria:
    gamma: float
    cohesion: float
    phi: float
    E: float
    E_display: str
    regime: str
    seismic_type: str
    seismic_C: str
    flags: dict[str, bool] = field(default_factory=dict)
    candidates: dict[str, list[Candidate]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------ utilitats


def _norm(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def lith_flags(description: Any) -> dict[str, bool]:
    """Senyals litològiques de la descripció (ca/es), sense accents."""
    d = _norm(description)
    return {
        "carbonatat": bool(re.search(r"carbonat|cimentat|cementad", d)),
        "rebliment": bool(re.search(r"rebl(i|e)ment|relleno|reblert|antropic", d)),
        "vegetal": bool(re.search(r"vegetal|terreny vegetal|tierra vegetal", d)),
        "bolos": bool(re.search(r"\bbolos?\b|bloc", d)),
        "lutites": bool(re.search(r"lutit|margu|marga|argil.?lit|limolit", d)),
        "bretxes": bool(re.search(r"bretx|brech|conglomer", d)),
        "gresos": bool(re.search(r"\bgres|sorrenq|arenisc", d)),
        "alterat": bool(re.search(r"alterad|alterat|meteorit", d)),
        "argila": bool(re.search(r"argil|arcill|clay", d)),
        "llim": bool(re.search(r"\bllim|limo|silt", d)),
        "sorra": bool(re.search(r"\bsorr|\baren|sand", d)),
        "grava": bool(re.search(r"\bgrav|gravel", d)),
    }


def round_E(value: float) -> int:
    """Arrodoniment professional de l'E: desenes per sota de 100, cinquantenes a partir de 100."""
    v = float(value)
    if v < 100:
        return int(round(v / 10.0) * 10)
    return int(round(v / 50.0) * 50)


def regime_for(nb: float, refusal: bool, rock: bool) -> str:
    if rock:
        return "roca"
    if refusal or nb >= 30:
        return "dens"
    if nb >= 10:
        return "mitja"
    return "fluix"


def seismic_type_for(regime: str, klass: str = "") -> tuple[str, str]:
    """(Tipus NCSE-02, coeficient C): roca i granular dens II (1,3); granular mitjà III (1,6);
    cohesius/transicionals no densos i tot el que és fluix IV (2,0) — Linyola 1 (llims, Nb 13) signa IV."""
    if regime in ("roca", "dens"):
        return "Tipus II", "1.3"
    if regime == "mitja" and klass in ("grava", "sorra"):
        return "Tipus III", "1.6"
    return "Tipus IV", "2.0"


def _classify(soil_type: str, flags: dict[str, bool], rock: bool) -> str:
    """Classe de criteri: roca | rebliment | grava | sorra | transicional | argila."""
    st = (soil_type or "").lower()
    if rock:
        return "roca"
    if flags["rebliment"] or flags["vegetal"]:
        return "rebliment"
    if st == "arcilla" or (flags["argila"] and not flags["sorra"] and not flags["llim"] and not flags["grava"]):
        return "argila"
    if st in TRANSITIONAL_TYPES:
        return "transicional"
    if st in GRANULAR_TYPES and (flags["argila"] or flags["llim"]) and not flags["grava"]:
        return "transicional"  # «sorres argiloses», «arena limosa»: l'àncora de 28° de l'Eva
    if flags["argila"] and (flags["sorra"] or flags["llim"]) and not flags["grava"]:
        return "transicional" if flags["sorra"] else "argila"
    if flags["grava"] or flags["bolos"] or st == "grava":
        return "grava"
    if st in GRANULAR_TYPES:
        return "sorra"
    if flags["argila"]:
        return "argila"
    return "grava" if st == "granular" else "transicional"


def _dedupe(cands: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in cands:
        key = c.display
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ------------------------------------------------------------------ criteri principal


def geotech_by_criteria(
    nb: float,
    n20: float,
    soil_type: str,
    description: str = "",
    refusal: bool = False,
) -> GeotechCriteria:
    """Candidats amb procedència per γ, c, φ, E (i tipus sísmic); el primer de cada llista és el defecte.

    Args:
        nb: Nb del nivell (N20/0,83), el que imprimeix la cel·la «Nb».
        n20: N20 mitjà del nivell (entrada de la D.23, com fins ara).
        soil_type: tipus del wizard o detectat (`granular|grava|arena|arena_limosa|limo|arcilla|rock|cohesive`).
        description: litologia del nivell (per als senyals: carbonatat, rebliment, lutites…).
        refusal: el DPSH ha rebutjat dins del nivell («-R» a la cel·la Nb).
    """
    nb = float(nb or 0.0)
    n20 = float(n20 or 0.0)
    flags = lith_flags(description)
    rock = (soil_type or "").lower() == "rock" or is_rock(n20, description or "")
    regime = regime_for(nb, refusal, rock)
    klass = _classify(soil_type, flags, rock)
    notes: list[str] = []
    st = (soil_type or "granular").lower()
    if st == "cohesive":
        st = "limo"

    # --- φ ----------------------------------------------------------------
    phi_c: list[Candidate] = []
    rk = rock_kind(flags) if klass == "roca" else ""
    if klass == "roca":
        if rk == "lutites":
            phi_c.append(Candidate(30, "30", "criteri Eva: lutites/margues (signat Linyola 2, Alcoletge 2)", "eva"))
        elif rk == "gresos":
            phi_c.append(Candidate(34, "34", "criteri Eva: gresos/sorrenques (signat Vilanova 2)", "eva"))
        else:
            phi_c.append(Candidate(35, "35", "criteri Eva: bretxes/conglomerats (signat Castellar); CTE roca tova", "eva"))
        phi_c.append(Candidate(rock_params_default()["phi"], "35", "CTE D.25 roca tova (defecte anterior)", "cte"))
    elif klass in ("grava", "sorra"):
        if refusal or nb >= 31:
            phi_default = 39 if nb >= 41 else 38
            phi_c.append(Candidate(phi_default, str(phi_default),
                                   "Crespo Tabla 11.2 banda «densa» (36-41): rebuig ⇒ dens; 38 (39 a la meitat alta, Nb ≥ 41). "
                                   "Signat: Bell-lloc 38 (25-R), Rubí 39 (47-R), Anciles 2 38 (15-R)", "crespo"))
        else:
            phi_c.append(Candidate(round(crespo_phi_granular(nb)), f"{round(crespo_phi_granular(nb))}",
                                   f"Crespo Tabla 11.2, punt mig de la banda per Nb={nb:.0f}", "crespo"))
        phi_c.append(Candidate(round(nspt_to_phi(nb, st)), f"{round(nspt_to_phi(nb, st))}",
                               f"CTE 4.1 + Schmertmann (n) amb Nb={nb:.0f} (fórmula anterior)", "cte"))
    elif klass == "argila":
        if flags["llim"]:
            phi_c.append(Candidate(25, "25", "criteri Eva: argila llimosa 25 (signat Vilanova 1; Crespo: argila limosa −3°)", "eva"))
        phi_c.append(Candidate(28, "28", "àncora Crespo Tabla 11.2 «muy floja» = 28° (signat Anciles 1, Alcoletge 1, Linyola 1)", "crespo"))
        phi_c.append(Candidate(round(crespo_phi_cohesive(nb)), f"{round(crespo_phi_cohesive(nb))}",
                               f"Crespo taula cohesius, punt mig per N={nb:.0f}", "crespo"))
        phi_c.append(Candidate(round(nspt_to_phi(nb, "arcilla")), f"{round(nspt_to_phi(nb, 'arcilla'))}",
                               "CTE 4.1 + Schmertmann n=1,0 (fórmula anterior)", "cte"))
    elif klass == "rebliment":
        phi_c.append(Candidate(28, "28", "àncora 28° per a sòls fluixos/transicionals (signat Alcoletge 1: rebliment)", "crespo"))
        phi_c.append(Candidate(round(nspt_to_phi(nb, st)), f"{round(nspt_to_phi(nb, st))}",
                               "CTE 4.1 + Schmertmann (fórmula anterior)", "cte"))
    else:  # transicional
        phi_c.append(Candidate(28, "28", "àncora Crespo Tabla 11.2 «muy floja» = 28° per a materials transicionals "
                                         "(signat Linyola 1, Alcoletge 1, Anciles 1)", "crespo"))
        phi_c.append(Candidate(round(crespo_phi_cohesive(nb)), f"{round(crespo_phi_cohesive(nb))}",
                               f"Crespo taula cohesius, punt mig per N={nb:.0f}", "crespo"))
        phi_c.append(Candidate(round(nspt_to_phi(nb, st)), f"{round(nspt_to_phi(nb, st))}",
                               "CTE 4.1 + Schmertmann (n) (fórmula anterior)", "cte"))
    phi_c = _dedupe(phi_c)

    # --- c ----------------------------------------------------------------
    c_c: list[Candidate] = []
    if klass == "roca":
        c_c.append(Candidate(1.0, "1.00", "roca (CTE D.25 / signat Castellar, Linyola 2, Alcoletge 2)", "cte"))
        if flags["alterat"] or rk == "gresos":
            c_c.append(Candidate(0.5, "0.50", "roca tova/alterada (signat Vilanova 2: sorrenques)", "eva"))
    elif klass in ("grava", "sorra"):
        c_c.append(Candidate(0.0, "0.00", "granular net (signat Bell-lloc, Anciles 2)", "cte"))
        if flags["carbonatat"]:
            c_c.append(Candidate(0.05, "0.05", "granular carbonatat (signat Rubí)", "eva"))
            c_c.append(Candidate(CRESPO_C_CEMENTED_GRAVEL_KGCM2, "0.25", "Crespo p.175: grava/sorra cimentada", "crespo"))
    elif klass == "rebliment":
        c_c.append(Candidate(0.0, "0.00", "rebliment (signat Alcoletge 1)", "eva"))
    elif klass == "argila":
        c_c.append(Candidate(0.10, "0.10", "argila (Hunt via Crespo; signat Vilanova 1, Anciles 1)", "crespo"))
        c_c.append(Candidate(round(hunt_cohesion_from_nspt(nb), 2), f"{hunt_cohesion_from_nspt(nb):.2f}",
                             f"Hunt c = qu/2 per N={nb:.0f}", "crespo"))
    else:
        c_c.append(Candidate(0.05, "0.05", "transicional (llims, sorres argiloses; signat Linyola 1)", "crespo"))
        c_c.append(Candidate(round(hunt_cohesion_from_nspt(nb), 2), f"{hunt_cohesion_from_nspt(nb):.2f}",
                             f"Hunt c = qu/2 per N={nb:.0f}", "crespo"))
    c_c = _dedupe(c_c)

    # --- γ ----------------------------------------------------------------
    g_c: list[Candidate] = []
    if klass == "roca":
        g_c.append(Candidate(2.20, "2.20", "roca (CTE D.27; signat Castellar, Linyola 2, Vilanova 2)", "cte"))
        if flags["alterat"]:
            g_c.append(Candidate(2.00, "2.00", "roca alterada (signat Alcoletge 2)", "eva"))
    elif klass == "rebliment":
        g_c.append(Candidate(1.80, "1.80", "rebliment (signat Alcoletge 1)", "eva"))
        g_c.append(Candidate(1.90, "1.90", "cohesiu fluix (CTE D.27)", "cte"))
    elif klass in ("grava", "sorra"):
        g_c.append(Candidate(2.00, "2.00", "granular (CTE D.27; signat Bell-lloc, Rubí, Anciles 2)", "cte"))
    else:
        g_c.append(Candidate(1.90, "1.90", "cohesiu/transicional (CTE D.27; signat Linyola 1, Vilanova 1, Anciles 1)", "cte"))
    g_c = _dedupe(g_c)

    # --- E ----------------------------------------------------------------
    e_c: list[Candidate] = []
    if klass == "roca":
        base = E_ROCK_BASE_KG_CM2
        e_c.append(Candidate(base, f">{base}", "CTE D.23 roques toves, límit inferior; l'Eva imprimeix «>» en roca (signat Castellar >500)", "cte"))
        if rk == "lutites" or flags["alterat"]:
            e_c.append(Candidate(400, ">400", "lutites alterades (signat Alcoletge 2: >400)", "eva"))
        if rk == "lutites":
            e_c.append(Candidate(800, ">800", "lutites (signat Linyola 2: >800, també «alterades»: judici per projecte)", "eva"))
        if rk == "gresos":
            e_c.append(Candidate(550, "550", "gresos/sorrenques (signat Vilanova 2: 550, sense «>»)", "eva"))
    else:
        e_cte_raw = nspt_to_E_kg_cm2(n20)
        e_cte = e_cte_raw
        why = f"CTE D.23 banda baixa (E_min + 10 %) amb N20={n20:.0f}"
        if klass in ("grava", "sorra") and refusal and n20 < E_MEDIOS_MIN_N:
            e_cte = nspt_to_E_kg_cm2(E_MEDIOS_MIN_N)
            why = f"rebuig ⇒ compacitat densa: banda «medios» de la D.23 com a mínim (N20 mitjà pre-rebuig {n20:.0f})"
            notes.append("E: rebuig granular ⇒ banda «medios» com a mínim")
        if e_cte < E_FLOOR_KG_CM2:
            why = f"mínim professional {E_FLOOR_KG_CM2} (la D.23 amb N20={n20:.0f} dona {e_cte_raw:.0f}: cap informe signa un mòdul d'un dígit)"
            e_cte = E_FLOOR_KG_CM2
            notes.append("E: sòl mínim 50")
        e_default = round_E(e_cte)
        if klass == "transicional" and nb >= 10 and e_default < 100:
            e_default = 100
            why += "; llims ≥ 100 (signat Linyola 1)"
        e_c.append(Candidate(e_default, str(e_default), why + " · arrodonit a 10/50", "cte"))
        if flags["carbonatat"] and klass in ("grava", "sorra"):
            n_band = max(n20, E_MEDIOS_MIN_N) if refusal else n20
            e_carb = round_E(d23_band_E(n_band, 0.4))
            e_c.append(Candidate(e_carb, str(e_carb),
                                 "ajust litològic ↑ per carbonatades/cimentades: E_min + 40 % del rang D.23 (signat Bell-lloc 650; "
                                 "Rubí, també carbonatat, signa 450: pregunta 6b a l'Eva)", "eva"))
        if flags["bolos"]:
            e_c.append(Candidate(350, ">350", "bolos i graves irregulars (signat Anciles 2: >350)", "eva"))
        if klass == "argila":
            e_c.append(Candidate(90, "90", "argila sorrenca fluixa (signat Anciles 1: 90)", "eva"))
            e_c.append(Candidate(50, "50", "argila llimosa fluixa (signat Vilanova 1: 50)", "eva"))
        if klass == "transicional":
            e_c.append(Candidate(100, "100", "llims argilosos (signat Linyola 1: 100)", "eva"))
        if klass in ("grava", "sorra"):
            e_c.append(Candidate(450, "450", "graves i sorres denses (signat Rubí 450)", "eva"))
        e_c.append(Candidate(round(e_cte_raw), f"{e_cte_raw:.0f}", f"CTE D.23 banda baixa sense arrodonir (fórmula anterior) N20={n20:.0f}", "cte"))
    e_c = _dedupe(e_c)

    seismic_type, seismic_C = seismic_type_for(regime, klass)
    return GeotechCriteria(
        gamma=g_c[0].value, cohesion=c_c[0].value, phi=phi_c[0].value, E=e_c[0].value, E_display=e_c[0].display,
        regime=regime, seismic_type=seismic_type, seismic_C=seismic_C, flags=flags,
        candidates={"gamma": g_c, "cohesion": c_c, "phi": phi_c, "E": e_c}, notes=notes,
    )


def alternatives_for_wizard(crit: GeotechCriteria) -> dict[str, list[dict]]:
    """Els candidats que NO són el defecte, en la forma que el wizard ja pinta com a «+N» (`_alternatives`)."""
    out: dict[str, list[dict]] = {}
    for param, key in (("gamma", "geomech_gamma"), ("cohesion", "geomech_cohesion"), ("phi", "geomech_phi"), ("E", "geomech_E")):
        alts = [{"value": c.value, "source": c.source, "confidence": 0.5} for c in crit.candidates.get(param, [])[1:]]
        if alts:
            out[key] = alts
    return out
