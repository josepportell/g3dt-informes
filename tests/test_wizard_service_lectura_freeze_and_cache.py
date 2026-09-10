"""Correccions del 2026-09-01 a `web/wizard_service.py`.

Dos defectes independents, tots dos silenciosos:

1. **La tria congelada de l'Eva es perdia** (`save_wizard`). Després d'una
   recàrrega de pàgina la UI enviava `lectura_selections={}`; les taules es
   reconstruïen sense cap tria i `resolve_cell` queia al candidat 1, de manera
   que la tria validada revertia al `.docx` sense cap avís. Ara, quan l'entrada
   ve buida, es recuperen les tries del desat anterior — i cal mirar TAMBÉ
   `_user_data_prev.json`, perquè cada arrencada del pipeline hi reanomena
   `user_data.json` (`_clear_stale_user_data`).

   1b. **...i ressuscitar-les a cegues era pitjor** que perdre-les. Les claus de
   tria són POSICIONALS (`{bloc}.{índex}.{cel·la}`) i `tables_report._selected`
   les retorna crues i manen. Quan arriba un document nou i la lectura reordena
   les files, la tria d'ahir aterra sobre una fila que no li correspon: un valor
   mort amb aparença de validat, justament quan la lectura acaba de millorar.
   Ara tota tria — vingui del desat anterior o de la UI — es valida contra el
   `_decisions.json` d'ARA i només sobreviu si casa amb un candidat de la seva
   cel·la. El text lliure de l'Eva no en casa cap per definició: només sobreviu
   si ve marcat (`_lliure`), i sense marca es descarta.

2. **Una caiguda transitòria d'ICGC/Cadastre/Groq es replicava 30 dies**
   (`_auto_extract_cached`). La cache de disc de la Fase 13(a) desava
   incondicionalment, i una execució degradada té el mateix aspecte que una de
   bona. Ara no es desa ni una execució amb fallades de serveis externs ni una
   on els fitxers del projecte han canviat a mig camí (l'empremta es calcula
   ABANS de l'extracció i es compara després; `auto_result_cache.save()` la
   calcula al final i signaria un resultat que no ha vist els fitxers nous).

Frontera deliberada: els passos que salten per una condició ESTRUCTURAL del
projecte ("fitxer no trobat", "sense municipi al nom de carpeta") no vetan la
cache — si ho fessin, gairebé cap projecte no la faria servir mai i tornaríem
als 43-141 s per obertura.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from automation import auto_result_cache as arc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Projecte mínim resoluble per nom (`wizard_service._REF_DIR`)."""
    from web import wizard_service

    ref_dir = tmp_path / "projectes"
    p = ref_dir / "3001621 CASTELLAR"
    (p / "validation" / "lectura").mkdir(parents=True)
    (p / "PENETROS.pdf").write_bytes(b"%PDF-1.4 penetros")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return p


def _decisions() -> dict:
    """Un nivell de sòl amb dues redaccions candidates (cas del popup/dropdown)."""
    return {
        "tables": {
            "soil_levels": {
                "rows": [{
                    "nom": "Nivell 1",
                    "litologia": {
                        "estat": "candidats",
                        "value": None,
                        "candidates": [
                            {"value": "Reblert antropic", "font": "sondeig.pdf"},
                            {"value": "Argiles llimoses marrons", "font": "tall.pdf"},
                        ],
                    },
                    "de": "0.00",
                    "a": "1.20",
                }],
            },
        },
    }


def _decisions_after_tall() -> dict:
    """Re-lectura amb un `tall.pdf` nou: la fila 0 ja no és el nivell 1 sinó la
    capa vegetal, i cap candidat no és el que l'Eva va triar ahir."""
    def _lit(value: str) -> dict:
        return {"estat": "candidats", "value": None, "candidates": [{"value": value, "font": "tall.pdf"}]}

    return {
        "tables": {
            "soil_levels": {
                "rows": [
                    {"nom": "Terreny vegetal", "litologia": _lit("Llims marrons")},
                    {"nom": "Nivell 1", "litologia": _lit("Graves")},
                ],
            },
        },
    }


def _write_decisions(project: Path, decisions: dict | None = None) -> None:
    (project / "validation" / "lectura" / "_decisions.json").write_text(
        json.dumps(decisions if decisions is not None else _decisions()), encoding="utf-8",
    )


CHOICE = {"soil_levels.0.litologia": "Argiles llimoses marrons"}
FREE_TEXT = "Graves amb matriu sorrenca (Eva)"


def _saved(project: Path) -> dict:
    return json.loads((project / "user_data.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. La tria congelada sobreviu a una entrada buida
# ---------------------------------------------------------------------------

def test_empty_selections_recover_the_frozen_choice_from_user_data(project: Path):
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {"client_name": "X"}, lectura_selections=dict(CHOICE))
    assert _saved(project)["lectura_tables"]["soil_levels"][0]["litologia"] == "Argiles llimoses marrons"

    # Recàrrega de pàgina: la UI encara no ha restaurat res i envia {}.
    save_wizard("3001621 CASTELLAR", {"client_name": "Y"}, lectura_selections={})

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Argiles llimoses marrons"
    # ...i `lectura_selections` segueix explicant d'on surt (no queda orfe).
    assert saved["lectura_selections"] == CHOICE
    assert saved["client_name"] == "Y"


def test_empty_selections_recover_the_frozen_choice_from_the_backup(project: Path):
    """Cas real: el pipeline ha reanomenat `user_data.json` -> `_user_data_prev.json`."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {"client_name": "X"}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")

    save_wizard("3001621 CASTELLAR", {"client_name": "Y"}, lectura_selections=None)

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Argiles llimoses marrons"
    assert saved["lectura_selections"] == CHOICE


def test_selections_sent_by_the_ui_win_over_the_frozen_ones(project: Path):
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))
    save_wizard(
        "3001621 CASTELLAR", {},
        lectura_selections={"soil_levels.0.litologia": "Reblert antropic"},
    )

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Reblert antropic"
    assert saved["lectura_selections"] == {"soil_levels.0.litologia": "Reblert antropic"}


def test_without_any_previous_choice_the_first_candidate_still_wins(project: Path):
    """Via A sense cap tria: comportament d'abans, intacte."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {"client_name": "X"}, lectura_selections={})

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Reblert antropic"
    assert saved["lectura_selections"] == {}


def test_previous_selections_are_ignored_when_illegible(project: Path):
    from web.wizard_service import _previous_lectura_selections

    (project / "user_data.json").write_text("{ no json", encoding="utf-8")
    assert _previous_lectura_selections(project) is None


# ---------------------------------------------------------------------------
# 1b. ...pero nomes si encara casa amb la lectura d'ARA
# ---------------------------------------------------------------------------

def test_a_new_reading_discards_the_frozen_choice_that_no_longer_fits(project: Path):
    """El cas real: arriba un `tall.pdf` i la fila 0 passa a ser la capa vegetal.

    La tria d'ahir (`soil_levels.0.litologia`) hi aterraria per posició i
    l'informe sortiria amb el valor d'una lectura morta a la capa vegetal.
    """
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")

    _write_decisions(project, _decisions_after_tall())
    save_wizard("3001621 CASTELLAR", {}, lectura_selections={})

    rows = _saved(project)["lectura_tables"]["soil_levels"]
    assert [r["litologia"] for r in rows] == ["Llims marrons", "Graves"]
    assert _saved(project)["lectura_selections"] == {}


def test_a_dead_choice_sent_by_the_ui_is_discarded_too(project: Path):
    """Mateixa regla per a l'entrada de la UI: cap tria s'estampa sense validar."""
    from web.wizard_service import save_wizard

    _write_decisions(project, _decisions_after_tall())
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Llims marrons"
    assert saved["lectura_selections"] == {}


def test_a_choice_that_still_matches_a_candidate_survives_a_re_reading(project: Path):
    """La re-lectura manté el candidat triat en una altra posició: es conserva."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")

    decisions = _decisions()
    decisions["tables"]["soil_levels"]["rows"][0]["candidates_extra"] = "soroll"
    _write_decisions(project, decisions)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections={})

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Argiles llimoses marrons"
    assert saved["lectura_selections"] == CHOICE


def test_marked_free_text_survives_the_validation(project: Path):
    """L'«altre…» del desplegable: no casa amb cap candidat, però és de l'Eva."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections={
        "soil_levels.0.litologia": FREE_TEXT,
        "_lliure": ["soil_levels.0.litologia"],
    })

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == FREE_TEXT
    assert saved["lectura_selections"]["_lliure"] == ["soil_levels.0.litologia"]


def test_unmarked_free_text_is_discarded(project: Path):
    """Sense marca no es distingeix d'una tria morta: val més el candidat 1."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections={"soil_levels.0.litologia": FREE_TEXT})

    saved = _saved(project)
    assert saved["lectura_tables"]["soil_levels"][0]["litologia"] == "Reblert antropic"
    assert saved["lectura_selections"] == {}


def test_marked_free_text_dies_with_its_cell(project: Path):
    """La marca protegeix el text, no una fila que ja no existeix."""
    from web.wizard_service import _validated_lectura_selections

    _write_decisions(project, _decisions_after_tall())
    kept = _validated_lectura_selections(project, {
        "soil_levels.7.litologia": FREE_TEXT,
        "_lliure": ["soil_levels.7.litologia"],
    })
    assert kept == {}


def test_scalar_choices_are_validated_against_fields(project: Path):
    """Les claus escalars (`lab_*`, `superficie_construida`) segueixen la regla."""
    from web.wizard_service import _validated_lectura_selections

    _write_decisions(project, {
        "fields": {"lab_sample_id": {"estat": "candidats", "candidates": [{"value": "M-1"}]}},
        "tables": {"superficie_construida": {"total": "280+86"}},
    })
    kept = _validated_lectura_selections(project, {
        "lab_sample_id": "M-1",
        "lab_location": "S-1",           # no és a `fields`: mor
        "superficie_construida": "280+86",
    })
    assert kept == {"lab_sample_id": "M-1", "superficie_construida": "280+86"}


def test_the_free_text_mark_alone_is_not_a_selection(project: Path):
    """`{"_lliure": []}` és una UI que no ha restaurat res, no una tria buida."""
    from web.wizard_service import save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")

    save_wizard("3001621 CASTELLAR", {}, lectura_selections={"_lliure": []})

    assert _saved(project)["lectura_selections"] == CHOICE


def test_selections_are_dropped_when_there_is_no_reading(project: Path):
    """Via B (sense `_decisions.json`): res a validar, res a congelar."""
    from web.wizard_service import _validated_lectura_selections

    assert _validated_lectura_selections(project, dict(CHOICE)) == {}


def test_the_ui_gets_the_same_choices_the_backend_would_freeze(project: Path):
    """`/api/user-data/{p}` després d'arrencar el pipeline.

    `user_data.json` ja és `_user_data_prev.json`: sense mirar el backup, la UI
    rebia `{}` i pintava el candidat 1 mentre `save_wizard` congelava la tria
    recuperada. L'Eva veia una cosa i l'informe en portava una altra.
    """
    from web.wizard_service import load_user_data, save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {"client_name": "X"}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")

    served = load_user_data("3001621 CASTELLAR")
    assert served["lectura_selections"] == CHOICE
    # Nomes les tries: la resta del desat anterior no es ressuscita.
    assert "client_name" not in served


def test_the_ui_is_not_offered_a_choice_from_a_dead_reading(project: Path):
    from web.wizard_service import load_user_data, save_wizard

    _write_decisions(project)
    save_wizard("3001621 CASTELLAR", {}, lectura_selections=dict(CHOICE))
    (project / "user_data.json").rename(project / "_user_data_prev.json")
    _write_decisions(project, _decisions_after_tall())

    assert load_user_data("3001621 CASTELLAR") == {}


def test_a_dead_choice_inside_user_data_is_not_served_either(project: Path):
    """Igual que l'anterior PERO sense reanomenar `user_data.json`.

    Es el cas que faltava: una re-lectura sense arrencada de pipeline (o un
    `_decisions.json` reescrit) deixa les tries mortes dins del fitxer viu.
    Validant nomes el cami del backup, `load_user_data` les servia tal qual:
    els desplegables s'auto-curaven (les taules ja venen validades) pero les
    cel·les de `_lecturaCellBadgeSpan` es quedaven amb el valor mort i el
    tornaven a enviar al desat seguent.
    """
    from web.wizard_service import load_user_data

    _write_decisions(project, _decisions_after_tall())
    (project / "user_data.json").write_text(
        json.dumps({"client_name": "X", "lectura_selections": dict(CHOICE)}),
        encoding="utf-8",
    )

    served = load_user_data("3001621 CASTELLAR")
    assert "lectura_selections" not in served
    assert served["client_name"] == "X"  # la resta del fitxer viu no es toca


def test_saving_clears_a_dead_choice_left_in_user_data(project: Path):
    """`save_wizard_data` fa `existing.update(extra)`: si el bloc de la Fase 8b
    ometia `lectura_selections`, la tria morta del fitxer sobrevivia al desat i
    `user_data.json` quedava dient dues coses contradictories."""
    from web.wizard_service import save_wizard

    _write_decisions(project, _decisions_after_tall())
    (project / "user_data.json").write_text(
        json.dumps({"lectura_selections": dict(CHOICE)}), encoding="utf-8",
    )

    save_wizard("3001621 CASTELLAR", {"client_name": "Y"}, lectura_selections={})

    saved = _saved(project)
    assert saved["lectura_selections"] == {}
    assert [r["litologia"] for r in saved["lectura_tables"]["soil_levels"]] == [
        "Llims marrons", "Graves",
    ]


def test_via_b_never_grows_a_lectura_key(project: Path):
    """Sense `_decisions.json` no hi ha bloc de Fase 8b: `user_data.json` queda
    exactament com abans (cap `lectura_tables`, cap `lectura_selections`)."""
    from web.wizard_service import save_wizard

    save_wizard("3001621 CASTELLAR", {"client_name": "X"}, lectura_selections=dict(CHOICE))

    saved = _saved(project)
    assert "lectura_tables" not in saved
    assert "lectura_selections" not in saved


# ---------------------------------------------------------------------------
# 2. Fallades de servei extern vs. condicions estructurals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skip", [
    ("ICGC geologia", "HTTPSConnectionPool(...): Read timed out"),
    ("ICGC elevació", "Connection error"),
    ("Cadastre adjacents", "503 Service Unavailable"),
    ("Groq Deep Mine", "groq.APIStatusError: 503"),
    # La sonda visual de ConceptScout crida Groq/OpenAI/Anthropic: un `concept_map`
    # coix per un 429 no pot quedar-se servit 30 dies.
    ("ConceptScout", "groq.RateLimitError: 429"),
    # Fase 0.46: classifica adjunts i subcarpetes amb visio d'OpenAI
    # (`auto_extractor.py:975`). Un 429 deixa fitxers reals sense rol assignat.
    ("Deep folder classify", "openai.RateLimitError: 429"),
    ("Ortho enrichment", "ICGC WMS error"),
    ("Ortho enrichment", "visió fallida"),
    ("Geocodificació", "name resolution failed"),
    # Nominatim que no troba res: sense UTM cau TOTA la Fase 3 (ICGC + Cadastre).
    # Revisat a consciencia el 2026-09-01 i MANTINGUT: un projecte rural que no
    # geocodifica mai pagara els 43-141 s a cada obertura (queixa real de l'Eva),
    # pero uns prefills sense territori tenen el mateix aspecte que uns de bons i
    # es servirien 30 dies sense que ella ho pugui veure. L'espera es visible; el
    # buit, no. Vegeu `_STRUCTURAL_SKIP_REASONS` a `web/wizard_service.py`.
    ("Geocodificació", "no s'han trobat coordenades"),
])
def test_external_failures_are_detected(skip):
    from automation.auto_extractor import AutoExtractionResult
    from web.wizard_service import _external_service_failures

    assert _external_service_failures(AutoExtractionResult(steps_skipped=[skip]))


@pytest.mark.parametrize("skip", [
    ("Pressupost PDF", "fitxer no trobat"),
    ("Historia geològica", "sense municipi al nom de carpeta"),
    ("DPSH Excel", "sense dades vàlides"),
    ("Lab PDF", "fitxer no trobat"),
    ("Fase 3: APIs HTTP", "sense coordenades UTM"),
    ("Deep folder classify", "no file_mapping"),
    ("Ortho enrichment", "sense ref. cadastral"),
    ("Ortho enrichment", "sense polígon"),
    ("Geocodificació", "sense adreça disponible"),
    ("Geocodificació", "sense municipi (nom carpeta)"),
    ("Geocodificació", "adreça interna G3: Ronda Sant Pere, 1"),
    ("Geocodificació", "mòdul no disponible: No module named 'pyproj'"),
    # Locals, encara que el motiu tingui forma d'excepció (2026-09-01): un PDF
    # corrupte o un permís tornaran a fallar igual en re-executar, i vetar la
    # cache per qualsevol `str(exc)` la deixaria inservible per a tot el projecte.
    ("FileMiner", "OSError: [Errno 5] Input/output error"),
    ("Contingut", "PDFSyntaxError: No /Root object"),
])
def test_structural_skips_are_not_failures(skip):
    """Tornarien a saltar igual en re-executar: han de poder anar a la cache."""
    from automation.auto_extractor import AutoExtractionResult
    from web.wizard_service import _external_service_failures

    assert _external_service_failures(AutoExtractionResult(steps_skipped=[skip])) == []


def test_malformed_skip_entries_do_not_crash():
    from web.wizard_service import _external_service_failures

    class _Fake:
        steps_skipped = [("ICGC geologia",), "ICGC geologia", None, ["ICGC pendent", "boom"]]

    assert _external_service_failures(_Fake()) == ["ICGC pendent: boom"]


# ---------------------------------------------------------------------------
# 3. Què es desa (i què no) a la cache de disc
# ---------------------------------------------------------------------------

def _install_fake_extract(monkeypatch: pytest.MonkeyPatch, result, side_effect=None):
    import automation.auto_extractor as ae

    def fake(path, on_progress=None, **kw):
        if side_effect:
            side_effect(Path(path))
        return result

    monkeypatch.setattr(ae, "auto_extract", fake)


def test_a_degraded_run_is_not_cached(project: Path, monkeypatch: pytest.MonkeyPatch):
    from automation.auto_extractor import AutoExtractionResult
    from web import wizard_service

    degraded = AutoExtractionResult(
        prefills={"client_name": "GRUP ALMA"},
        steps_skipped=[("ICGC elevació", "Read timed out")],
    )
    _install_fake_extract(monkeypatch, degraded)

    assert wizard_service._auto_extract_cached(project).prefills == {"client_name": "GRUP ALMA"}
    assert not arc.cache_path(project).exists()


def test_a_run_with_only_structural_skips_is_cached(project: Path, monkeypatch: pytest.MonkeyPatch):
    from automation.auto_extractor import AutoExtractionResult
    from web import wizard_service

    ok = AutoExtractionResult(
        prefills={"client_name": "GRUP ALMA"},
        steps_skipped=[("Pressupost PDF", "fitxer no trobat")],
    )
    _install_fake_extract(monkeypatch, ok)

    wizard_service._auto_extract_cached(project)
    assert arc.load(project).result.prefills == {"client_name": "GRUP ALMA"}


def test_a_file_arriving_mid_run_is_not_cached(project: Path, monkeypatch: pytest.MonkeyPatch):
    """`A.01.pdf` que arriba durant els 43-141 s de l'extracció: el resultat no
    l'ha vist mai, i l'empremta que calcularia `save()` diria que sí."""
    from automation.auto_extractor import AutoExtractionResult
    from web import wizard_service

    _install_fake_extract(
        monkeypatch,
        AutoExtractionResult(prefills={"client_name": "GRUP ALMA"}),
        side_effect=lambda path: (path / "A.01.pdf").write_bytes(b"%PDF-1.4 planol"),
    )

    wizard_service._auto_extract_cached(project)
    assert not arc.cache_path(project).exists()


def test_a_clean_run_is_still_cached(project: Path, monkeypatch: pytest.MonkeyPatch):
    """La xarxa de seguretat no pot trencar el cas normal (Fase 13(a))."""
    from automation.auto_extractor import AutoExtractionResult
    from web import wizard_service

    _install_fake_extract(monkeypatch, AutoExtractionResult(prefills={"client_name": "GRUP ALMA"}))

    wizard_service._auto_extract_cached(project, on_progress=lambda t, d: None)
    assert arc.load(project).result.prefills == {"client_name": "GRUP ALMA"}


def test_a_degraded_run_does_not_erase_a_healthy_entry(project: Path, monkeypatch: pytest.MonkeyPatch):
    from automation.auto_extractor import AutoExtractionResult
    from web import wizard_service

    arc.save(project, AutoExtractionResult(prefills={"client_name": "BO"}))
    _install_fake_extract(
        monkeypatch,
        AutoExtractionResult(prefills={"client_name": "COIX"},
                             steps_skipped=[("Cadastre adjacents", "503")]),
    )

    wizard_service._auto_extract_cached(project, force_refresh=True)
    assert arc.load(project).result.prefills == {"client_name": "BO"}


# ---------------------------------------------------------------------------
# 4. «Actualitzar prefills» ha de poder forçar el refresc
# ---------------------------------------------------------------------------

def test_streaming_forwards_force_refresh(project: Path, monkeypatch: pytest.MonkeyPatch):
    """La capa de servei propaga el `?refresh=true` que envia «Actualitzar
    prefills» (cablejat a `web/api.py`, cobert per `test_refresh_prefills_wiring`)."""
    from web import wizard_service

    seen: list[bool] = []

    def fake_cached(path, *, force_refresh=False, on_progress=None):
        seen.append(force_refresh)
        return object()

    monkeypatch.setattr(wizard_service, "_auto_extract_cached", fake_cached)
    monkeypatch.setattr(wizard_service, "_merge_prefills", lambda *a, **kw: {})
    import web.vision_groq as vg
    monkeypatch.setattr(vg, "groq_available", lambda: False)

    list(wizard_service.get_prefills_streaming("3001621 CASTELLAR"))
    list(wizard_service.get_prefills_streaming("3001621 CASTELLAR", force_refresh=True))

    assert seen == [False, True]
