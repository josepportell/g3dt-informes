# Fase 8b — les taules llegides arriben al `.docx` (2026-08-26)

**Què tanca:** el forat 6 de `../fase8-e2e/_RESULTATS.md` — «seleccions de taula de la UI (`lecturaState.selections`)
encara no viatgen al backend/generador». Fins ara la via A llegia les taules de camp molt bé i l'informe sortia
igualment amb les taules de la via B (Excel + `sondeig_extracted.json`).

**Cadena nova, completa:**

```
_decisions.json (tables)  ──►  tables_report.build_report_tables()  ──►  user_data.json["lectura_tables"]  ──►  context del .docx
        ▲                                    ▲                                      ▲
   runner/consolidador          tries d'Eva (lectura_selections)         POST /api/wizard/{p}  (o, sense wizard,
                                    des de la UI del wizard              lectura directa de validation/lectura/)
```

## Mesura (informe generat vs informe signat de l'Eva, `scripts/compare_tables_vs_eva.py`)

Mateix `user_data` als dos costats; l'única diferència és el bloc `lectura_tables` (aquí, el de la **lectura d'or de
taules** — el sostre: què surt si la lectura és perfecta). 11 taules per informe, cel·la a cel·la.

| projecte | via B (avui) | + Fase 8b | delta |
|---|---|---|--:|
| CASTELLAR | 26 M · 9 C · 30 X → **54 %** | 39 M · 12 C · 14 X → **78 %** | **+24 pp** |
| RUBÍ | 31 M · 4 C · 20 X → **64 %** | 37 M · 8 C · 10 X → **82 %** | **+18 pp** |
| BELL-LLOC | 36 M · 6 C · 13 X → **76 %** | 35 M · 6 C · 14 X → **75 %** | −1 pp |

(M = idèntica, C = propera, X = diferent. Els 3 projectes són els que tenen `user_data` reutilitzable a
`reference-material/`; Linyola, Alcoletge, Vilanova i Anciles no en tenen i no s'han pogut generar.)

**Taula DPSH de Castellar: 12 M / 8 X → 20 M / 0 X.** És el canvi més visible i el més típic: la via B posava la
`cota_referencia` absoluta (`+570.90`) a les quatre files i la fondària de l'última fila de la graella (`-1.00`);
l'Eva escriu la cota **per punt** i **relativa al carrer** (`-4.0`, `-4.20`) i la fondària **exacta del peu
«Rebuig a»** (`-1.08`). La lectura ja ho tenia bé des del 24 d'agost; ara arriba al document.

**Taula SPT/MA:** era **buida sencera** a Castellar (5 cel·les) i ara surt amb les 5. La plantilla només tenia una
fila fixa d'escalars; ara és un bucle (`scripts/template_spt_ma_loop.py`, idempotent), perquè Anciles en necessita 3.

**Bell-lloc −1 pp:** una sola cel·la, i és de format, no de fons — `1/0` vs `1/--` a la columna SPT/MA de la taula
de sondeigs. Els 4 sondeigs dels informes signats la formaten de 4 maneres diferents (`1/--`, `1/0`, `1/0/0`,
`1/0/1`): no hi ha regla derivable → **pregunta 7 a l'Eva**. La resta de Bell-lloc queda igual perquè la via B ja hi
encertava (les seves cotes són absolutes i l'Excel hi coincideix).

## Què NO ha canviat (a propòsit)

- **Via B intacta.** Sense `_decisions.json` ni `lectura_tables`, l'informe generat és cel·la a cel·la el d'abans
  (verificat: Castellar via B abans i després = 26 M · 9 C · 30 X).
- **Cap càlcul.** Les fondàries `de`/`a` de `soil_levels` viatgen al bloc però **no** toquen `depth_from_m` /
  `thickness_m`: canviar-les mou gruixos i la taula sísmica, i això és una decisió de càlcul (tram 3), no de taula.
- **Cap regla semàntica nova al consolidador.** El que aquesta fase fa és format d'informe, no interpretació.

## Regles de format aplicades (deduïdes dels 6 informes signats, `../../golden-read-taules/_eva_truth/`)

| cel·la | forma | evidència |
|---|---|---|
| cota d'inici | signe explícit, 2 decimals (`+199.50`, `-4.00`) | 23/23 files dels 6 informes porten signe |
| profunditat assolida | sempre negativa, 2 decimals (`-1.08`) | idem |
| rebuig | `Si` / `No` (sense accent) | 23/23 |
| nivell freàtic | fondària negativa si és nombre; si no, el text llegit | `No detectat`/`No detectado`/`-1.00` |
| fondària SPT/MA | `-1.00 a -1.20` | 6/6 informes |
| N30 | xifra, `R` o `--`; s'escapça l'anotació del lector (`R (rebuig)` → `R`) | només si el davanter és un N30 vàlid |
| SPT/MA | triple `n/n/n` si hi ha TP o MA; parella `n/n` si només SPT | 2 de 4 exactes; vegeu pregunta 7 |
| superfície construïda | **xifra**, mai la prosa del lector | Castellar: el `total` de l'or porta 2 línies d'aclariment |
| litologia | **literal**, sense escurçar | és la redacció que Eva ha triat entre candidats |

## Troballes de camí (arreglades)

1. **Una llista de candidats crua podia acabar impresa al `.docx`** (`[{'value': …, 'font': …}, …]` dins de la
   cel·la de litologia de Bell-lloc): en aquell dialecte `litologia` és una llista sense embolcall. `resolve_cell`
   ara la resol i `fmt_text` mai imprimeix una estructura — cel·la buida abans que un bolcat.
2. **UI: la columna d'identificador de totes les taules es veia `—`.** `punt`, `sondeig` i `nom` són text pla per
   contracte i `_lecturaCellDisplayValue` només sabia llegir cel·les-dict.
3. **UI: la columna «Prof. Extracció» de la taula SPT/MA sempre buida** — llegia `row.fondaria`, que
   `canonicalize_row_keys` ja havia convertit en `row.profunditat`.
4. **`lab_sample_id` / `lab_location` / `lab_depth` no arribaven mai a l'informe**: són camps de lectura sense input
   al wizard, i `collectWizardFields()` només recull inputs. Ara viatgen dins del bloc (§8.3 del disseny: «si el
   wizard no té el camp, el valor viatja igualment a `user_data` per al generador»).
5. Doble punt a la taula de característiques geotècniques (`… vermells..`) quan la litologia ja acabava en punt.

## Pendent (no és d'aquesta fase)

- **Anotacions del lector dins de `litologia`** (`"… gresos vermells (NIVELL 1, 0.50-1.20)"`, `"Graves i sorres.
  Carbonatat. (Nivell 1)"`): el valor hauria de ser la litologia i el matís hauria d'anar a `note`. Es corregeix al
  skill/consolidador, no al generador — el generador no ha d'endevinar quin parèntesi és contingut.
- La resta de MISMATCH que queden són **càlculs** (E, Qa, φ, K30, sísmica) i **escalars** (superfície de parcel·la,
  plantes): tram 3 i lectura d'escalars, respectivament.

## Fitxers

`automation/lectura/tables_report.py` (nou, pur + CLI) · `automation/report_generator.py`
(`lectura_tables`, `_apply_lectura_tables`, `_apply_lectura_soil_levels`, `_level_material`) ·
`automation/report_data.py` (`SoilLevel.description_verbatim`) · `automation/wizard.py` (`save_wizard_data(extra=)`) ·
`web/api.py` + `web/wizard_service.py` (`lectura_selections` → `_build_lectura_block`) ·
`templates/validation/review.html` (3 correccions + enviament de les tries) ·
`templates/g3dt-jinja-template.docx` (taula SPT/MA → bucle) · `scripts/template_spt_ma_loop.py` ·
`tests/test_lectura_tables_report.py` (49 tests).
