# Taules-llista: informes generats (pipeline determinista) vs informes signats d'Eva

**Data:** 2026-08-23 nit · **Eina:** `scripts/compare_tables_vs_eva.py` · **Cobertura:** 5/7 projectes amb informe d'Eva
(Bell-lloc, Castellar, Rubí, Linyola, Alcoletge via conversió `.doc`→`.docx`). Pendents: Vilanova i Anciles (informe només
en PDF amb capa de text; transcripció manual de la veritat pendent). Tulipa exclosa (no hi ha informe d'Eva — n/a conegut).

## Propòsit (reenquadrat pel Josep a mitja sessió)

L'objectiu NO és puntuar el pipeline vell: és (1) **extreure la veritat de les taules de l'Eva** per derivar regles d'or de
lectura per al skill `g3dt-llegir-projecte` (v0.7, Pas 3b), i (2) servir d'**arnès de validació** quan l'agent generi taules.

## Resultats (5 projectes, cel·les de dades)

| projecte | MATCH | CLOSE | MISMATCH | files ±/− | (M+C)/comparables |
|---|--:|--:|--:|---|--:|
| BELL-LLOC | 38 | 6 | 11 | 0 | 80 % |
| CASTELLAR | 29 | 10 | 26 | 0 | 60 % |
| RUBI | 34 | 6 | 15 | +4 extra | 73 % |
| LINYOLA | 22 | 6 | 23 | +1/−5 | 55 % |
| ALCOLETGE | 17 | 9 | 25 | +1/−5 | 51 % |

**Caveat Q9:** els `_generated.docx` són de les obertures fredes del diagnòstic (generats SENSE desar el wizard →
`user_data.json` absent): les cel·les de plantes/superfícies surten buides per aquest artefacte de flux, no per extracció.

## Troballes que han esdevingut regles d'or (skill v0.7 Pas 3b)

1. **Cota d'inici per punt, pot ser relativa**: annex DPSH, capçalera de cada pàgina ("P-2 cota inici: -4,2 m (respecte el
   carrer)") — verificat Castellar = informe exacte. El pipeline vell posava +570,90 (absoluta del sondeig) a tots els punts.
2. **Profunditat assolida = Excel B80 "Rebuig a -X,XX m"** (exacta), no l'última fila de 20 cm — verificat Castellar
   (-1,08/-0,48/-0,76/-1,55 = informe; el vell: -1,20/-0,60/-0,80/-1,60).
3. **Nivell freàtic: columna `N.F.` de l'Excel DPSH** — Alcoletge informe -1,00; el vell deia "No detectat".
4. **Litologia: l'Eva re-redacta** (tall "Graves amb sorres" → informe "Graves en matriu sorrenca carbonatades") → sempre
   candidats, mai segur per a la cadena literal.
5. **El 2n nivell geològic** absent al generat (Linyola, Alcoletge −5 files; Rubí +4 extra) — el TALL mana (regla existent);
   les fondàries de transició alimenten sísmica (gruix) i geotècnica (rang Nb).
6. **La fila de sulfats porta el nivell d'on surt la mostra** (Linyola: 2on nivell), no sempre el 1r.
7. **Etiqueta de la fila de parcel·la segueix la font** ("segons plànols cadastrals"/"segons cadastre"/"segons informació
   aportada") + `superficie_construida` és un camp de lectura ("280+86", "120 m2").
8. Tier B (no lectura): K, Tipus terreny + Coef. C, γ/c/φ/E — criteri Eva/Python amb override; el skill en llegeix els inputs.

## Rerun

```bash
.venv/bin/python scripts/compare_tables_vs_eva.py GENERATED.docx EVA.docx|EVA.json --tag NOM --json OUT.json
# Alcoletge: convertir primer amb: soffice --headless --convert-to docx --outdir DEST "…/4001670_informe.doc"
```
