# Llibre de mesures — wizard headless (Castellar, 13 documents a `claude`)

Generat per `ledger.py` a partir de `runs/*/`. **No editar a mà.** Una fila per run; els artefactes crus són a la carpeta del run.
Criteri de qualitat que mana: **erroni-amb-confiança de fons = 0** (valor `segur` diferent de l'or); ERR/ALERTA de format es llegeixen un per un (`meta.json` → `quality_judgement.notes`).

## Temps

| run | model | conc. | canvi respecte l'anterior | docs OK | suma claude | mediana/doc (nets) | turns/doc | tokens sortida docs | consolidació | paret real | paret reconstruïda | cost equiv. |
|---|---|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `2026-08-24-e2e-tarda-c2-solapat` | sonnet (defecte dels settings del Josep, no fixat pel runner) | 2 | linia base: primer E2E real | 13/13 (0 timeouts) | 64 min | 264 s (142-418) | — | — | 585 s / — turns | 37 min | 43 min | — |
| `2026-08-24-sonnet-c2` | sonnet (claude-sonnet-5) | 2 | primera remesura amb 1 projecte sol; runner instrumentat (turns/api_ms/cost) | 13/13 (0 timeouts) | 70 min | 290 s (210-591) | 20.7 | 341653 | 474 s / 26 turns | — | 43 min | 17.73 $ |
| `2026-08-24-sonnet-c3` | sonnet (claude-sonnet-5) | 3 | concurrencia 2 -> 3 (unic canvi) | 13/13 (0 timeouts) | 61 min | 292 s (148-424) | 20.6 | 305792 | 677 s / 24 turns | 32 min | 33 min | 15.39 $ |

*paret reconstruïda* = planificació de llista dels `elapsed_s` per document amb `conc.` slots + consolidació (model, no mesura). *cost equiv.* = `total_cost_usd` del CLI (amb subscripció no es factura; és el pes de la feina).

## Qualitat (comparador d'or `compare_consolida.py`)

| run | erroni-amb-confiança (fons) | escalars OK / CAUTELA / ALERTA / ERR / NOU | taules OK / CAUTELA / ALERTA / ERR / ABSENT | lectura dels no-OK |
|---|--:|---|---|---|
| `2026-08-24-e2e-tarda-c2-solapat` | **0** | 15 / 4 / 1 / 1 / 1 | 16 / 1 / 1 / 3 / 6 | street_address ERR = format (majuscules)<br>dpsh_tests cota_inici ERR x3 = format (-4,0 vs -4)<br>6 ABSENT de taules = claus de fila no canoniques (abans del skill v1.3)<br>building_type ALERTA = CLOSE |
| `2026-08-24-sonnet-c2` | **0** | 14 / 4 / 2 / 1 / 1 | 20 / 1 / 2 / 1 / 3 | street_address ERR = format (mateix valor)<br>spt_ma_tests[0].profunditat ERR = format signe/decimals (mateix valor)<br>cota_referencia ALERTA = puja a segur '570.90 msnm' amb 1 font; valor = preferit de l'or (+570,90); exces de confianca, NO valor erroni; guard determinista pendent (Fase 12)<br>sondeig_tests[0].spt_ma ALERTA = representacio en comptes (regla v1) + exces de confianca<br>building_type ALERTA = CLOSE (article/adjectiu) |
| `2026-08-24-sonnet-c3` | **0** | 17 / 1 / 3 / 0 / 1 | 17 / 1 / 2 / 3 / 4 | cota_referencia ALERTA = puja a segur '570.90 msnm' amb 1 font (2/2 runs de la Fase 9; l'E2E de la tarda era candidats) — valor = preferit de l'or; exces de confianca reproduible -> guard determinista Fase 12<br>street_address ALERTA = candidats amb 3 formats del mateix carrer/numeros, cap identic a l'or (format; no es segur)<br>building_type ALERTA = CLOSE<br>dpsh_tests cota_inici ERR x3 = format (-4,0 vs -4)<br>spt_ma_tests: 2 files (SPT-1 + MA1, mateix punt S-1 i mateixa fondaria 1,0-1,2) = mateixa mostra duplicada amb dos ids; bloc candidats (no segur) -> regla de fusio determinista (punt+fondaria) Fase 12<br>sondeig_tests[0].cota candidats nomes relatiu '-4 m'; or segur '570,90 msnm' -> conflicte SKILL (Pas 3b: cel·la relativa) vs OR (absoluta): decisio Josep/Eva, no error del model |

## Condicions i contaminacions

- `2026-08-24-e2e-tarda-c2-solapat` — pel wizard sencer (Playwright), SOLAPAT amb la lectura de Bell-lloc; sense turns/cost (runner no instrumentat)
- `2026-08-24-sonnet-c2` — Castellar SOL (cap altre projecte), WSL, login (subscripcio), MCPs del Josep carregats (cwd repo) · **contaminats:** 4687-GTL-25 Castellar del Vallés.pdf, PDF/ANNEXES/3001621_fotografies.pdf (tall de connexio/suspensio 20:43-22:01 (rellotge de paret); elapsed_s es monotonic (no compta suspensio); paret real del run INVALIDA)
- `2026-08-24-sonnet-c3` — Castellar SOL, WSL, login (subscripcio), MCPs del Josep carregats (cwd repo); run NET (sense talls), 22:26:14 -> 23:02:04

## Per a la taula «abans/després» de l'Eva

L'*abans* de l'Eva és la via B a producció (`docs/audit/DIAGNOSTIC-PROD-2026-08-23.md`: prefills Castellar 275 s, 59 % de camps iguals als de l'Eva sobre els 8 projectes; `docs/audit/VERIFICACIO-FIXES-2026-08-22.md`). Les mètriques que li importen són *camps correctes sense tocar-los*, *camps que ha hagut de corregir*, *temps fins al formulari* i *temps fins a l'informe*; aquest llibre guarda els artefactes crus perquè es puguin recomputar amb `scripts/compare_tables_vs_eva.py` i `docs/golden-read-taules/_eva_truth/` quan la Fase 8b (taules → generador) estigui feta.

