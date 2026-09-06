"""Assentament per CRITERI (bloc 2, 2026-09-06): la frase de l'informe i l'Es de Schmertmann amb candidats.

Regla d'or (`docs/CRITERIS-CALCUL-EVA.md`, 2026-09-02): modelar criteris, no fórmules. L'assentament és una
verificació de servei («està ben per sota de 2,54 cm?»), no una predicció (`ANALISI-SETTLEMENT-BACK-ENGINEERING.md`
§5). Els criteris que els 7 informes signats DESCRIUEN (`RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`):

1. **Frase per règim del nivell portant.** Granular (graves, sorres, bolos) → valor precís: «seran iguals o inferiors
   a 1.50 cm, immediats en el temps donat el comportament granular dels materials» (Bell-lloc 1,20; Rubí 1,50; Anciles
   1,5). Roca o cohesiu (lutites, bretxes, llims argilosos, argiles) → frase genèrica «seran menyspreables o bé
   inferiors a 1.0 cm» (Castellar, Linyola L2, Alcoletge L2, Vilanova). Schmertmann és un mètode per a granulars.
2. **Valor < 1,0 cm → frase genèrica** encara que el nivell sigui granular (`CRITERIS` §2, comportament de l'Eva).
3. **Arrodoniment a 0,1 cm**, imprès amb dos decimals («1.20», «1.50»).
4. **Topall de servei:** 2,54 cm (1 polzada) per a sabates, 5 cm per a llosa (boilerplate dels 7) → avís, no error.
5. **Es** («E = mòdul de deformació definit per Schmertmann, 2,5 (aïllades) / 3,5 (corregudes) × colpeig del
   penetròmetre estàtic, obtingut de l'Nspt amb factors per material», 7/7 informes): l'Eva diu que l'agafa «com a
   criteri després de molts estudis». Cap fórmula única reprodueix els tres valors signats (abril 2026: 12 hipòtesis).
   Es modela com a DEFECTE + CANDIDATS amb procedència (mateix patró que `geotech_criteria.py`):
     - `2,5 × N` amb l'N de l'SPT del nivell (la columna «N» de la taula geotècnica, P0): l'Nspt del text signat.
       Bell-lloc N=54 → Es 135 → 1,16 cm (signat 1,20).
     - `2,5 × Nb` (el back-engineering d'abril: Rubí Nb 47 → 1,52 cm, signat 1,50).
     - `E` del criteri (mòdul de la taula geotècnica, `geotech_criteria`): l'altra lectura possible del text.
   Defecte: l'SPT del nivell si n'hi ha, si no Nb. L'Eva tria al wizard («+N»). Pregunta 15 a l'Eva.

Cap crida externa; pur. Sortida: `SettlementCriteria` (frase, valor, Es, candidats, avisos).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SENTENCE_HEAD = "Els assentaments màxims previstos per la càrrega recomanada anteriorment seran "
SENTENCE_GENERIC = SENTENCE_HEAD + "menyspreables o bé inferiors a 1.0 cm."
SENTENCE_GRANULAR = SENTENCE_HEAD + "iguals o inferiors a {s} cm, immediats en el temps donat el comportament granular dels materials."
SERVICE_CAP_FOOTING_CM = 2.54   # 1 polzada (Terzaghi), sabates
SERVICE_CAP_SLAB_CM = 5.0       # 2 polzades, llosa
GENERIC_THRESHOLD_CM = 1.0

#: Classe de `geotech_criteria._classify` → règim d'assentament
_KLASS_TO_REGIME = {
    "roca": "roca", "argila": "cohesiu", "transicional": "cohesiu",
    "grava": "granular", "sorra": "granular", "rebliment": "granular",
}


@dataclass
class EsCandidate:
    value: float
    display: str
    source: str
    settlement_cm: float | None = None   # amb aquest Es (mateixa Qa, B, Df)


@dataclass
class SettlementCriteria:
    regime: str                      # granular | roca | cohesiu
    Es: float | None                 # Es del defecte (kg/cm²)
    Es_source: str
    settlement_cm: float | None      # arrodonit a 0,1 (defecte)
    generic: bool                    # frase genèrica «menyspreables o bé inferiors a 1.0 cm»
    sentence: str
    candidates: list[EsCandidate] = field(default_factory=list)   # [defecte, alternatives…]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def settlement_regime(klass: str | None, cohesion: float | None = None, regime: str | None = None) -> str:
    """Règim d'assentament del nivell portant: roca (c ≥ 0,5 o règim roca), cohesiu (argila/transicional), granular."""
    if regime == "roca" or (cohesion is not None and cohesion >= 0.5):
        return "roca"
    return _KLASS_TO_REGIME.get((klass or "").lower(), "granular")


def round_settlement(value: float) -> float:
    """A 0,1 cm, mig amunt (1,15 → 1,2; no el banker's de `round`)."""
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def parse_spt_n(value: Any) -> float | None:
    """N de la columna «N» (P0): «54» → 54; «R», «--», buit → None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return n if n > 0 else None


def settlement_by_criteria(
    *, q_net: float, B: float, Df: float, gamma: float,
    nb: float | None, n_spt: float | None = None, E: float | None = None,
    regime: str = "granular", Es_override: float | None = None, shape: str = "square",
) -> SettlementCriteria:
    """Frase i valor d'assentament pel criteri de l'Eva. `q_net` = Qa (kg/cm²), `B`/`Df` en m, `gamma` en g/cm³.
    `nb` = Nb del NIVELL de l'informe (la cel·la «Nb», no la mitjana global), `n_spt` = N de la columna «N» (SPT del
    nivell), `E` = mòdul del criteri. `Es_override` = «Es assentament» escrit al wizard (mana). `regime` de
    `settlement_regime`."""
    from .terzaghi_calculator import FootingShape, schmertmann_settlement

    fs = FootingShape.STRIP if str(shape).lower() in ("strip", "correguda", "corrida") else FootingShape.SQUARE
    k = 3.5 if fs == FootingShape.STRIP else 2.5
    notes: list[str] = []
    cands: list[EsCandidate] = []
    if Es_override is not None and Es_override > 0:
        cands.append(EsCandidate(float(Es_override), f"Es={Es_override:.0f} (escrit al wizard)", "wizard: Es assentament"))
    if n_spt:
        cands.append(EsCandidate(k * n_spt, f"Es={k * n_spt:.0f} ({k:g}×N SPT {n_spt:.0f})",
                                 "2,5 × colpeig (Nspt del nivell, columna «N»; text dels 7 informes)"))
    if nb:
        cands.append(EsCandidate(k * nb, f"Es={k * nb:.0f} ({k:g}×Nb {nb:.1f})",
                                 "2,5 × Nb (back-engineering abril 2026: Rubí 1,52 ≈ 1,50 signat)"))
    if E and E > 0:
        cands.append(EsCandidate(float(E), f"Es={E:.0f} (E del criteri)", "E de la taula geotècnica com a Es"))
    # sense duplicats de valor (2,5×N = 2,5×Nb quan coincideixen)
    seen: set[float] = set()
    cands = [c for c in cands if not (round(c.value) in seen or seen.add(round(c.value)))]  # type: ignore[func-returns-value]

    for c in cands:
        s = schmertmann_settlement(q_net=q_net, B=B, Df=Df, Es=c.value, gamma=gamma, shape=fs) if q_net > 0 else None
        c.settlement_cm = round_settlement(s) if s is not None else None

    regime = regime if regime in ("granular", "roca", "cohesiu") else "granular"
    default = cands[0] if cands else None
    s_cm = default.settlement_cm if default else None
    generic = regime != "granular" or s_cm is None or s_cm < GENERIC_THRESHOLD_CM
    if regime != "granular":
        notes.append(f"nivell portant {regime}: Schmertmann és per a granulars → frase genèrica (7/7 signats)")
    elif s_cm is not None and s_cm < GENERIC_THRESHOLD_CM:
        notes.append("assentament < 1,0 cm → frase genèrica")
    if s_cm is not None and s_cm > SERVICE_CAP_FOOTING_CM:
        notes.append(f"⚠ {s_cm:.2f} cm supera el topall de servei de {SERVICE_CAP_FOOTING_CM} cm (1 polzada) per a sabates")
    sentence = SENTENCE_GENERIC if generic else SENTENCE_GRANULAR.format(s=f"{s_cm:.2f}")
    return SettlementCriteria(regime=regime, Es=default.value if default else None,
                              Es_source=default.source if default else "", settlement_cm=s_cm, generic=generic,
                              sentence=sentence, candidates=cands, notes=notes)


def alternatives_for_wizard(sc: SettlementCriteria) -> list[dict[str, Any]]:
    """Candidats d'Es que no són el defecte, en el format del badge «+N» del wizard (camp `Es_settlement`)."""
    return [{"value": round(c.value), "source": f"{c.display} → {c.settlement_cm:.2f} cm" if c.settlement_cm is not None else c.display,
             "confidence": 0.5} for c in sc.candidates[1:]]


def calc_note(sc: SettlementCriteria, B: float) -> tuple[str, str]:
    """(`_calc_settlement`, `_calc_Es`) per al wizard i el generador: defecte + alternatives + avisos."""
    if not sc.candidates:
        return "", ""
    d = sc.candidates[0]
    alts = " | alt: " + ", ".join(f"{c.display} → {c.settlement_cm:.2f} cm" for c in sc.candidates[1:] if c.settlement_cm is not None) \
        if len(sc.candidates) > 1 else ""
    shown = "frase genèrica «menyspreables o bé inferiors a 1.0 cm»" if sc.generic else f"«iguals o inferiors a {sc.settlement_cm:.2f} cm»"
    s_txt = f"Schmertmann {d.display}, B={B:g} m → {d.settlement_cm:.2f} cm · règim {sc.regime} → {shown}{alts}" \
        if d.settlement_cm is not None else f"Schmertmann {d.display} · règim {sc.regime}"
    if sc.notes:
        s_txt += " · " + "; ".join(sc.notes)
    es_txt = f"{d.display} · {d.source}{alts}"
    return s_txt, es_txt
