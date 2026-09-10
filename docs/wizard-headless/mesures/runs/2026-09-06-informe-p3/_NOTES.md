# Mesura d'informe DESPRÉS de P3 (paràmetres per criteri, candidats amb procedència) — 2026-09-06 (tarda, 3)

Codi: P0 + nivell portant (P2a+P2b, GO Josep) + `automation/geotech_criteria.py` (γ/c/φ/E i tipus sísmic per criteri; rebuig
mirat al nivell de l'informe). Referència anterior: `../2026-09-06-informe-p2`. **Referència viva per a la propera peça.**

## Qa i paràmetres (variant `calc`), p2 ⇒ p3 (signat)

| | Castellar | Rubí | Bell-lloc |
|---|---|---|---|
| φ | 35 = (35) | 37 ⇒ **39** (39) | 33 ⇒ **38** (38) |
| E cel·la | «500» ⇒ **«>500»** (>500) | 469 ⇒ **450** (450) | 114 ⇒ 450 (650: candidat «carbonatades») |
| Nb cel·la | 27-R (17-R) | 42-R (47-R) | 23 ⇒ 23-R (25-R) |
| sísmica | III / 1,6 ⇒ **II / 1,3** (II / 1,3) | II / 1,3 | III / 1,6 ⇒ **II / 1,3** (II / 1,3) |
| **Qa** | 3,0 ✅ | 3,5 ✅ | 1,5 ⇒ **3,0 ✅** |
| assentament (cm) | 2,80 (<1,0) | 1,70 (1,50) | 1,00 ⇒ 2,10 (<1,20) |

Titulars `calc`: Castellar 86 ⇒ 88 %, Rubí 84 ⇒ 87 %, Bell-lloc 75 ⇒ 78 %. `viab`: 60 ⇒ 62, 69 ⇒ 73, 76 ⇒ 80 %.
Només es mouen la taula geotècnica i la sísmica; cap altra cel·la.

## Lectura

- El que mou el Qa de Bell-lloc no és l'E (Qa no en depèn) sinó φ: 38 pel criteri «rebuig al nivell ⇒ granular dens ⇒
  banda densa de Crespo». El rebuig és a 1,0-1,6 m, sota la capa portant (0-1,0) però dins del mateix nivell geològic:
  la cel·la signada «25-R» ho diu.
- L'E de Bell-lloc (650) queda com a candidat perquè Rubí, també «carbonatades», signa 450: la regla no és
  derivable dels informes (pregunta 14). El defecte (450) és la banda «medios» de la D.23 pel rebuig.
- L'assentament de Bell-lloc puja (1,00 ⇒ 2,10) perquè Schmertmann segueix E: camí a part, no tocat.
- Sobre les 11 files signades (test unitari): 35/44 cel·les exactes (φ 11/11, γ 10/11, c 9/11, E 5/11); les 9 restants
  tenen el signat com a candidat amb la seva font; cap fora.

## Comparar amb el següent run

```bash
M=docs/wizard-headless/mesures/runs; for s in castellar rubi bell-lloc; do for v in 8b calc t2 viab; do diff <(grep -v '^\*\*' $M/2026-09-06-informe-p3/$s/$v/_compare_informe.txt) <(grep -v '^\*\*' $M/<nou-run>/$s/$v/_compare_informe.txt) | grep '^[<>]' | sed "s/^/$s $v: /"; done; done
```
