# Troballes — run Rubí 17-09-2026 (clon WSL, release/2026-09 @ 35d4fd3)

## T1 — «< 1 min restants» durant els primers minuts d'una lectura de 35 min

**Vist:** 14:29:01, 9 s després de prémer «Començar», la fila de l'Eva deia:
`Llegint documents · 0/12 · < 1 min restants`
amb `estimate_s = {"remaining": 0, "basis": ""}`.

**Mecanisme (llegit al codi, no deduït):**
- `Job.estimate_remaining_s` neix a `0` i `estimate_basis` a `""` (`jobs.py` L165, L204).
- `_recompute_estimate()` NOMÉS es crida a `lectura_doc` (document acabat) i als
  `lector_imatges_*` (`jobs.py` L296, L312, L315). **Mai a `lectura_inici`.**
- `job_text._round_estimate(0)` entra per `if s < 60` i retorna `«< 1 min»`
  (`job_text.py` L60-62). El zero de «encara no ho sé» és indistingible del zero
  de «ja quasi està».

**Conseqüència:** des del clic fins que acaba el PRIMER document (mediana ~224 s
a Alcoletge, o sigui ~4 min) l'Eva llegeix «< 1 min restants» en una feina de 35
min. És el primer que veu després de prémer el botó, i contradiu el mateix botó,
que acabava de dir «uns 35 min».

**No és cap dels 31 vermells esperats i no hi ha cap test que cobreixi el cas.**
`tests/test_lectura_job_text.py` prova l'arrodoniment amb valors reals (L54), mai
el zero sense base.

**Arreglable de dues maneres (no aplicades: decisió del Josep):**
1. Cridar `_recompute_estimate()` també a `lectura_inici`. A casa de l'Eva ja hi
   ha telemetria d'altres projectes, així que sortiria un número real de seguida.
2. Fer que `basis == ""` (cap mesura) doni `None` → la fila no diria res de temps
   en comptes de dir una mentida. Les dues alhora és el més honest.

**Risc de tocar-ho avui:** baix i localitzat (2 fitxers), però és codi de
`release/2026-09` amb la visita demà.

**CORREGIT el mateix dia** (loop implementer → reviewer ×2 → tester). Veure DECISION-LOG 2026-09-17 (2).
Mesura empírica del defecte abans de corregir-lo, en aquest mateix run: «< 1 min restants» des de
les 14:28:32 (clic) fins a les 14:32:15 (primer document acabat) = **3 min 43 s**, i llavors salt
correcte a «≈ 35 min restants».

---

## T2 — `3001631_DPSH.xls`: 0 de 6 dades llegides (observació, no defecte nou)

El banner de format nou ho diu obertament a l'Eva: «Del fitxer 3001631_DPSH.xls només n'he pogut
llegir 0 de 6 dades». **No ha costat res**: les 3 files de `dpsh_tests` surten de l'annex PDF i
s'alineen 3/3 amb l'or. Després de «Generar» el format learner ha desat l'schema
(«Format desat. Proper cop s'extrauran automaticament»).

Val la pena mirar si el `.xls` de Rubí té un format que val la pena ensenyar al sistema, o si amb
l'annex PDF ja n'hi ha prou per disseny. No bloqueja res.

## T3 — «Observacions de camp» a cada obertura (ja conegut)

Confirmat també a Rubí. Ja és a la llista de defectes menors del pla «després del 18-09».

---

## Verificació de la correcció T1 a l'aplicació real (17-09, 16:41)

Clon actualitzat a `37c8c93` (release/2026-09 amb la correcció), servidor rearrencat amb el HOME net,
credencial refrescada i verificada amb un `claude -p` real.

Projecte de prova **nou** creat per a això (`9999998 PROVA-RELLOTGE`, còpia d'1 document, mai llegit
→ sense cau). Botó: «1 document · uns 15 min».

**Amb 0 documents llegits, la fila diu ara:**
```
detall  = '≈ 20 min restants'
basis   = 'median_doc_s=221 from 44 telemetry rows'
remaining = 1061
```
Estable durant tota la finestra observada (16:41:51 → 16:42:20). **Abans deia «< 1 min restants»
durant 3 min 43 s.** El número surt de la telemetria real de la màquina (44 mostres), com estava
dissenyat: es calibra amb l'experiència de l'ordinador, no amb la d'aquest job.

Captura: `rellotge-corregit-2026-09-17.png`.
