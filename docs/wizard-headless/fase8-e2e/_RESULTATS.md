# Fase 8 — E2E real del wizard headless (2026-08-24, WSL, claude 2.1.241, skill v1.2→1.3)

**Què:** dos projectes reals (còpies locals a `~/g3dt-e2e/projectes/`, mai `/mnt/c`) llegits per `claude -p` de veritat.
Bell-lloc pel runner directe (driver); **Castellar pel wizard sencer** (Playwright: dropdown → `/api/lectura-stream` →
runner → consolidació → merge → badges de 3 estats a la UI, 0 errors de consola). Evidència: `*_decisions.json` +
`*_telemetry.jsonl` d'aquest directori; comparador `../fase0-acceptacio/compare_consolida.py`.

## Resultat de qualitat (contra l'or de la lectura d'or) — erroni-amb-confiança = 0 als dos projectes

| Projecte | Crides | Errors/timeouts (a 600 s) | Escalars vs or | Taules vs or | Validador |
|---|--:|--:|---|---|---|
| Bell-lloc | 17 only + 1 consolida (1 cache, 1 duplicat) | 0 / 0 | 18 OK · `num_floors` mateix valor reordenat · `utm_x/y` no_trobat (vegeu forat 1) · `architect_company` nou | 18 OK · `spt_ma` en comptes (regla v1) · nivell de cobertura de l'or absent (candidat, no error) | OK |
| Castellar | 13 only + 1 consolida | 0 / 0 | 15 OK · 4 més prudents que l'or (bo dins dels candidats) · `street_address`/`building_type` mateix valor, format/CLOSE | 17 OK · 3 format (`-4,0` vs `-4`) · claus de fila no canòniques (→ skill v1.3) | OK |

Detalls que confirmen les regles d'or en producció: Castellar `cota_referencia` = candidats amb "-4 m (respecte el carrer)"
primer (l'ERR històric no es repeteix); profunditats DPSH -1,08/-0,48/-0,76/-1,55 exactes; n30 = candidats ['R'] mai segur;
Bell-lloc SPT registre [24,34,28,30] amb candidats 62|58.

## Resultat de temps (la troballa dura)

| Mesura | Bell-lloc | Castellar |
|---|---|---|
| Per document (min / mediana / màx) | 108 / 279 / 501 s | 142 / 264 / 418 s |
| Suma de temps `claude` | 86 min | 64 min |
| Consolidació | 562 s | 585 s |
| Paret (concurrència 2, **els dos projectes solapats**) | 58 min | 37 min |

Cost fix per crida ≈ 100-120 s (un `.txt` de 3 línies triga 108-118 s): arrencada del CLI + CLAUDE.md + skill de 40 KB +
exploració Python en sessió. L'estimació del disseny (5-12 min el primer open) **no s'aguanta**: mesurat 35-60 min amb
concurrència 2 i dos projectes alhora. Segona obertura: cache per md5 → 0 crides (verificat: `DADES CLIENT.txt` cached).

## Forats trobats (i estat)

1. **Fonts Python no-g3_templates invisibles al consolidador** (`COORDENADES.txt`, Cadastre): el consolidador cec no les veu
   → `utm_x/y` i `referencia_catastral` surten `no_trobat` a la lectura encara que la via B els ompli. La UI mostra
   "no trobat" al costat d'un camp ple. → Següent: emetre els lectors Python (coordenades, cadastre) com un `_python_readers.json`
   més a `--out`, o enrutar-los a claude (barats). PENDENT.
2. **Timeouts**: 240 s per document matava els pesants; 360 s de consolidació hauria matat totes dues consolidacions.
   → defectes 600 / 900 s (`f91fa0d`, `30920d5`). FET.
3. **Autenticació**: el `.env` de la via B filtra `ANTHROPIC_API_KEY` sense crèdit al fill → `G3DT_LECTURA_AUTH=login` (`bb7b4f3`). FET.
4. **Claus de fila no canòniques** (`prof_extraccio`, `punt`/`cota_inici` al sondeig) → skill v1.3 + àlies + validador (`ce01aa6`). FET.
5. **Progrés invisible durant la lectura** (`#lectura-progress` dins del formulari ocult) → mirall a l'stepper (`f91fa0d`). FET.
6. Seleccions de taula de la UI (`lecturaState.selections`) encara no viatgen al backend/generador. PENDENT (Fase 8b).

## Palanques de temps a decidir (Josep)

- Concurrència 3-4 (les crides són latència d'API, no CPU): paret ÷ ~1,5-2.
- Reduir el cost fix: prompt headless prim (sense CLAUDE.md del repo: `cwd` neutre + skill instal·lat com a user-command),
  skill "mode --only" més curt que el de 40 KB.
- Enrutar menys documents: `*_fotografies.pdf`, `LAB-SIG.pdf`, còpies `Print To PDF` (`tall.pdf`, `pl. situaci.pdf`) quan
  ja hi ha el `PDF/ANNEXES/` equivalent → 4-5 crides menys per projecte.
- Consolidació Python-first (només conflictes a claude): -9 min.

## GO/NO-GO de la Fase 8

✅ Pipeline sencer funciona a WSL amb claude real (runner + servei + UI). ✅ Erroni-amb-confiança = 0 (2 projectes). ✅ Cache.
⏳ Temps del primer open inacceptable tal qual per a l'Eva (35-60 min) — palanques a sobre. ⏳ Windows sense provar.
⏳ Forat 1 i Fase 8b. Veredicte: **GO tècnic, NO-GO de latència** fins a aplicar palanques i remesurar.
