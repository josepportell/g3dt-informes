# Fases 14a i 15 — tres botons, taula d'estat i avisos (2026-08-26, vespre)

**Què tanquen:** les files 14 i 15 del pla de l'annex
(`../../DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §10) — el que l'Eva veu del registre de jobs de la
Fase 10, i l'avís que li arriba quan un job acaba. Commits `ea82efe` (14a) i `da53e17` (15).
**14b** (*Actualitzar*) segueix pendent: depèn del delta-sync de la Fase 11.

---

## 14a — tres botons + taula d'estat

En comptes d'un sol botó «Començar amb aquesta carpeta»: **Preparar «per demà»** · **Enllestir** · **Des de zero**, i a
sota una fila per projecte amb `_job.json` dels últims 30 dies.

### La decisió que més pesa: el text el redacta el backend

Les regles de redacció de §3.3 són regles, no decoració — arrodonir, dir sempre «restants» i mai el total, i que
**«Interromput» no soni a error**. `templates/validation/review.html` fa 10.000 línies i no té cap test; el projecte en té
1.537 en pytest. Per això el text de cada fila el fa `automation/lectura/job_text.py` i `GET /api/jobs` l'adjunta com a
clau `eva` a cada job — **afegida**, no substituint el snapshot, de manera que res del que ja el consumia es mou.

| estat | el que veu l'Eva |
|---|---|
| `reading` | `2/4` · Llegint documents · **7/17** · ≈ 25 min restants |
| `ready` | `✓` · Preparat (ahir 18:32) · *2 documents nous o canviats des de llavors → Enllestir ≈ 8 min* |
| `interrupted` | `⚠` · Interromput a 2/4 (12/17 llegits) · *prem Preparar per continuar — els documents ja llegits no es tornen a llegir* |
| `error` | `✗` · No s'ha pogut preparar · *avisat Eficients* |

**Un matís sobre l'arrodoniment.** El disseny diu «a 5 min», però el seu propi exemple de delta de xarxa és
«Enllestir ≈ 8 min», i arrodonir 8 a 10 és un 25 % de més justament quan la xifra importa. Regla implementada: segons
mai, minut exacte fins a 10 min, múltiples de 5 a partir d'allà. Els dos exemples del disseny surten exactes.

### Comportament (§5.2)

- **Preparar** → `POST /api/jobs/{p}?button=preparar` i prou. **No obre cap SSE** — és l'única desviació del disseny, que
  deia obrir l'stream «només per pintar progrés». Ningú espera, el refresc de 5 s ja ensenya el progrés real i §6.1 ja
  diu que la taula és la veritat: així tancar la pestanya no costa literalment res.
- **Enllestir / Des de zero** → POST + el camí d'avui; el formulari s'obre al final.
- **Fila viva** → *Veure progrés* s'enganxa a l'stream que ja corre (`?attach=true`).
- Refresc cada 5 s **només** mentre hi ha una fila viva.

### Autocontenció

Bloc propi (CSS + `#jobsPanel` + JS al final), com el de la Fase 7. `nbSetState` s'**embolcalla** en lloc d'editar-la,
perquè treure el bloc no deixi rastre. L'únic canvi a codi existent és
`openLecturaStream(project, {attach})`, amb defecte idèntic a avui.

Sonda nova `GET /api/lectura/enabled` (200 sempre) en comptes de llegir un 404: `fetch()` d'un 404 deixa una línia
vermella a la consola encara que el codi el gestioni, i el criteri és **0 errors de consola** també amb el flag apagat,
on la UI d'avui no ha de canviar en res.

### Verificat al navegador (Playwright, servidor real amb jobs de prova)

| | flag ON | flag OFF |
|---|---|---|
| panell | visible, 3 botons, botó únic amagat | ocult, «Començar amb aquesta carpeta» intacte |
| files | reading / ready / error amb el text de §3.3 | 0 |
| comptador 7/17 | en negreta, fila ressaltada | — |
| refresc | el 9/17 arriba sol, sense recarregar | — |
| «Veure error» | desplega i replega el detall | — |
| **errors de consola** | **0** | **0** |

---

## 15 — avisos

Un senyal per projecte, en acabar o en fallar; mai per pas. Hook a `lectura_service._notify_finished`, només a
`ready`/`error` — mai a `cancelled` (l'Eva acaba de prémer «Aturar», ja ho sap). Destinatari buit = canal desactivat, no
error. `notify_job_finished()` no llança mai.

### El test ha obligat a canviar el disseny

§6.4 deia sanejar el log del CLI **substituint** els noms de fitxer per `doc_{i}`. Amb un projecte sintètic amb noms de
persona a tot arreu, el test va ensenyar que no n'hi ha prou: el log del CLI no només porta noms de fitxer, porta
**valors de camps** — `client detectat: Jordi Bosch Novell`. Cap substitució pot cobrir això, perquè el que hi pot
sortir és qualsevol cosa que el model hagi llegit del document, i la regla del mateix §6.4 és «mai valors de camps ni
cites».

**Criteri invertit:** en lloc d'esborrar el que sabem sensible, només es conserva el que sabem tècnic (codis de retorn,
timeouts, límits d'ús, errors de xarxa, traces) i de la resta només se'n diu quantes línies eren. Les que sobreviuen
encara passen per la substitució de fitxers, rutes i nom de carpeta.

Excepció documentada i provada: el missatge d'`error_event` l'escriu el nostre propi codi Python — se'n controla la
forma — i per això passa per la substitució però no per la llista blanca. La diferència està coberta amb un test que
passa el mateix text pels dos camins i comprova que donen resultats diferents.

### Què diu el correu de telemetria sense dir què hi havia

Àlies estable (`doc_1`), tipus de document (`annex_sondeig`), extensió, mida, mode, durada, `rc`, timeout, cache, `n`
documents per extensió, versió del CLI. Cap nom de fitxer, cap ruta, cap nom de carpeta, cap valor de camp.

---

## Pendent

- **14b** (*Actualitzar*) i el `network_delta` real de la fila `ready`: tots dos esperen la Fase 11 (delta-sync). El text
  ja el sap redactar; mentre `network_delta` sigui buit, la fila `ready` **no diu res sobre la xarxa** — millor que dir
  «res ha canviat» sense haver mirat.
- **Toast real a Windows** i tria del canal: Fase 17, presencial.
- **SMTP**: `.env.example` documenta les 9 variables; falta decidir Brevo vs bústia a `mail.eficients.cat` (§12.6) i
  l'encàrrec de tractament amb G3 (§12.4).

---
*Fi Fases 14a i 15. L'Eva ja té tres botons, una taula que parla el seu idioma i un avís per projecte.*
