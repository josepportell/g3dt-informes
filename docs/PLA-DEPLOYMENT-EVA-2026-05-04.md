# Pla de Deployment — Instal·lació G3DT a Eva (2026-05-04)

**Data sessió de planificació:** 2026-05-03
**Data prevista d'instal·lació:** 2026-05-04 (dilluns)
**Versió producció objectiu:** `production/g3dt-eva-v1`

---

## 1. Context

Després del demo a la seu de G3DT (2026-04-30), Silvia i Eva han confirmat:
- Volen instal·lar el sistema a l'ordinador d'Eva el **dilluns 2026-05-04**.
- Pagaran l'última factura del contracte signat un cop instal·lat.
- A continuació signaran o bé extensió (afegir suport castellà) o bé pack mensual de manteniment ("bossa d'hores", no il·limitat) per cobrir millores i el que descobreixin amb ús real.

El que vam demo-ar va ser el **pipeline determinista** (Fase 0/0.3/0.4/0.45/0.5 + Fase 1 visió per API). El **AI pipeline experimental** (Stages 2-5, Pass A/B/C) NO formava part del demo i NO ha d'arribar a producció en aquesta v1.

---

## 2. Decisions preses (alineades amb Josep, 2026-05-03)

| # | Decisió |
|---|---|
| 1 | **Windows natiu primer.** Si funciona al Windows del Josep, hauria de funcionar al d'Eva. Pla B: instal·lar WSL si falla. |
| 2 | **Còpia local + copy-back** per al workflow de carpeta de projectes. Eva té els projectes a una unitat de xarxa (F:/G:/...). El pipeline corre sobre còpia local; només l'informe `.docx` torna a la xarxa. Així s'evita latència de xarxa, conflictes amb altres usuaris, i carpetes de rastre (`validation/`, JSONs) als servidors compartits. |
| 3 | **API keys generades demà** amb Eva, vinculades a tarjeta de crèdit de G3DT. Per a l'instal·lació al matí podem usar les del Josep temporalment. |
| 4 | **Branca de producció:** `production/g3dt-eva-v1`. |
| 5 | **Codi: amagar, NO eliminar.** Tot el que no ha de veure Eva s'amaga (UI, endpoints), però el codi queda. Si "Vision Claude" deixa de funcionar, recurs ràpid: instal·lar Claude Code i tornar a habilitar. |

---

## 3. Arquitectura objectiu (Eva, producció)

```
┌─────────────────────────────────────────────────────────────┐
│  ORDINADOR EVA — Windows natiu                              │
│                                                             │
│  C:\g3dt-ia\                       ← carpeta instal·lació      │
│  ├── app\                       ← codi Python (production)  │
│  │   ├── .venv\                 ← virtualenv Windows        │
│  │   ├── automation\            ← pipeline modules          │
│  │   ├── web\                   ← FastAPI wizard            │
│  │   ├── schemas\, templates\   ← config + plantilles       │
│  │   └── .env                   ← API keys + paths          │
│  ├── workspace\                 ← còpia local de projectes  │
│  │   └── {projecte}\            ← copiat des de xarxa       │
│  ├── reports\                   ← informes generats         │
│  ├── cache\                     ← caches geocode/cadastre   │
│  └── G3DT-Wizard.bat            ← launcher escriptori       │
│                                                             │
│  F:\projectes\ (xarxa)          ← origen + destí del .docx  │
│      └── {projecte}\                                        │
│          └── 4001712_informe.docx ← copy-back final         │
└─────────────────────────────────────────────────────────────┘

FLUX:
1. Eva obre G3DT-Wizard.bat → arrenca FastAPI a localhost:8765
2. Wizard llista projectes a F:\projectes\ (rsync llista, no contingut)
3. Eva selecciona projecte
4. Sistema: copy F:\projectes\{p}\* → C:\g3dt-ia\workspace\{p}\
5. Pipeline corre sobre workspace local
6. Eva revisa wizard, prem "Generar Informe"
7. .docx es genera a C:\g3dt-ia\reports\{p}\
8. .docx es copia a F:\projectes\{p}\
9. workspace local es manté com a cache (re-runs sense recopiar)
```

---

## 4. FASE A — Preparació branca i neteja codi (avui, ~3-4h)

### A.1 — Crear branca de producció

```bash
git checkout experiment/ai-pipeline   # ja som aquí
git status                            # confirmar fitxers .png borrats no afecten
git stash                             # opcional: parkar canvis pendents
git checkout -b production/g3dt-eva-v1
```

**Verificació:** `git branch --show-current` ha de retornar `production/g3dt-eva-v1`.

### A.2 — Amagar AI pipeline endpoints (no eliminar)

Tots els endpoints `/api/ai-pipeline/*` (8 endpoints a `web/api.py`) s'han d'amagar darrere d'un feature flag `G3DT_ENABLE_AI_PIPELINE` (default: `false`).

- [ ] Afegir `G3DT_ENABLE_AI_PIPELINE` a `automation/config.py`
- [ ] Embolicar registre dels endpoints `/api/ai-pipeline/*` a `web/api.py` amb el flag
- [ ] Verificar que el wizard d'Eva NO té cap UI que els crida

**Test:** amb el flag a `false`, fer `curl http://localhost:8765/api/ai-pipeline/inventory/test` ha de tornar 404.

### A.3 — Amagar botó "Vision Claude" del wizard + fixar Llama 4 com a default Groq

A `templates/validation/review.html`, l'UI té (segons commit `d359e1c`) botons "Vision Groq" i "Vision Claude" fora del DEV_MODE guard.

**Decisió de disseny (2026-05-03):** introduïm un flag específic per al pas vision via Claude Code, **independent del DEV_MODE**. Així podem activar-lo en producció sense haver de "passar a dev":

- `G3DT_DEV_MODE=false` — controla UI/herramientes de desenvolupament en general
- `G3DT_PROD_USE_CLAUDECODE_VISION=false` — controla específicament el botó "Vision Claude" i la invocació del subprocess `claude`. Si demà o més endavant volem activar-lo a producció (perquè Eva té Claude Code instal·lat), només cal canviar aquest flag a `true` sense tocar res més.

- [ ] Afegir `G3DT_PROD_USE_CLAUDECODE_VISION` a `automation/config.py` (default `false`)
- [ ] Mostrar botó "Vision Claude" només si `G3DT_DEV_MODE=true` OR `G3DT_PROD_USE_CLAUDECODE_VISION=true`
- [ ] Bloquejar `start_vision_cli()` (subprocess `claude`) quan ambdós flags són `false`
- [ ] Confirmar que el comportament default és Groq (que NO requereix Claude Code)
- [ ] Verificar que `start_vision_cli()` (subprocess `claude`) NO és invocat per cap path automàtic — només manual via botó dev

**Sobre el model Groq per defecte:** durant el demo (2026-04-30), Josep va seleccionar manualment **Llama 4 Scout** al dropdown del wizard (en lloc del default xinès — DeepSeek/Qwen) i els resultats van ser millors. Això és el que Eva ha vist i el que esperarà. Per producció:

- Model confirmat (.env actual): `GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct`
- [ ] Fixar Llama 4 Scout com a default a `automation/config.py` i al dropdown del wizard
- [ ] Documentar l'elecció a `.env.example` amb comentari
- **Millora futura (v2+):** avaluar Llama 4 Maverick (model superior dins la mateixa família) en una sessió de benchmark dedicada.

**Test:** carregar wizard amb `G3DT_DEV_MODE=false` i `G3DT_PROD_USE_CLAUDECODE_VISION=false` → botó "Vision Claude" no visible. Dropdown Groq pre-seleccionat amb Llama 4.

### A.4 — Workflow còpia local + copy-back

**Variables d'entorn noves:**

| Variable | Exemple Eva | Significat |
|---|---|---|
| `G3DT_NETWORK_PROJECTS` | `F:\projectes` | Carpeta projectes a la xarxa (read + write final) |
| `G3DT_LOCAL_WORKSPACE` | `C:\g3dt-ia\workspace` | Còpia local de treball |
| `G3DT_REPORTS_DIR` | `C:\g3dt-ia\reports` | Informes generats (abans del copy-back) |

**Implementació mínima:**

- [ ] Mantenir `G3DT_PROJECTS_DIR` com a alias temporal apuntant al workspace local (compatibilitat retro)
- [ ] Nou mòdul `automation/sync_workspace.py`:
  - `list_network_projects()` — llista carpetes a `G3DT_NETWORK_PROJECTS` (no copia res)
  - `sync_to_workspace(project_name)` — robocopy/shutil de xarxa → local; només fitxers nous o modificats
  - `copyback_report(project_name, docx_path)` — copia `.docx` final a la carpeta original a la xarxa
- [ ] Modificar `web/api.py` `/api/projects` perquè llisteixi des de la xarxa
- [ ] Modificar `/api/prefills/{p}` perquè faci sync_to_workspace primer si encara no s'ha fet
- [ ] Modificar `/api/generate/{p}` perquè faci copyback_report després de generar

**Test:** crear estructura de prova:
```
C:\g3dt-test\network\projecte-test\PENETROS.pdf, A.01.pdf, ...
C:\g3dt-test\workspace\
```
Apuntar `G3DT_NETWORK_PROJECTS=C:\g3dt-test\network` i comprovar que el workspace queda omplert només quan se selecciona el projecte.

### A.5 — Configuració .env

Cal crear DUES coses:
1. **`.env.example`** (committat a git) — plantilla per a l'instal·lació a Eva, sense secrets, paths Windows.
2. **`.env`** (NO committat — al `.gitignore`) — còpia funcional del `.env` actual del Josep, perquè avui i demà al matí puguem fer els tests al WSL del Josep sense haver-lo de configurar des de zero.

Crear `.env.example` net (sense secrets):

```env
# === API Keys (REQUIRED) ===
ANTHROPIC_API_KEY=
GROQ_API_KEY=

# === Paths ===
G3DT_NETWORK_PROJECTS=F:\projectes
G3DT_LOCAL_WORKSPACE=C:\g3dt-ia\workspace
G3DT_REPORTS_DIR=C:\g3dt-ia\reports

# === LLM provider ===
G3DT_LLM_PROVIDER=anthropic
G3DT_CC_MODEL=claude-sonnet-4-6

# === Feature flags ===
# AI pipeline experimental (Stages 2-5, Pass A/B/C) — NO activar a producció
G3DT_ENABLE_AI_PIPELINE=false
# DEV mode — eines de desenvolupament/diagnòstic al wizard
G3DT_DEV_MODE=false
# Vision via Claude Code subprocess (alternativa a Groq) — activar només si Claude Code està instal·lat
G3DT_PROD_USE_CLAUDECODE_VISION=false

# === Vision backend ===
G3DT_USE_GROQ=true
G3DT_USE_SMARTSCAN=true
# Model Groq per defecte: Llama 4 Scout (validat al demo del 2026-04-30, millors resultats que DeepSeek/Qwen)
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
```

- [ ] Crear `.env.example`
- [ ] Verificar `automation/config.py` carrega totes les variables noves
- [ ] Commentar/Resoldre (no Esborrar) referències hardcoded a `/home/josep/...` o `/mnt/c/claude/...` si n'hi ha. Pot ser que sigui 'brut', però primer ha de funcionar, després ja netejarem el codi.

**Búsqueda crítica:** `grep -rn "/home/josep\|/mnt/c\|josep" automation/ web/ schemas/`

### A.6 — Smoke test al Windows natiu del Josep

**Pre-requisits al Windows del Josep:**
- Python 3.11 o superior instal·lat (verificar amb `python --version` a CMD)
- pip funcional
- (opcional) PowerShell o CMD com a terminal

**Procediment de prova:**

```cmd
:: 1. Clonar la branca production a una carpeta nova (NO la del workspace habitual)
cd C:\
git clone -b production/g3dt-eva-v1 file:///mnt/c/users/josep/path/to/clients/g3dt g3dt-prod-test (Fora de 'c/users' perquè Windows aplica permisos sobre aquesta carpeta i afectarà el rendiment/funcionament, i no cal)
cd g3dt-prod-test

:: 2. Crear venv natiu Windows
python -m venv .venv
.venv\Scripts\activate

:: 3. Instal·lar deps
pip install -e .

:: 4. Configurar .env
copy .env.example .env
:: editar .env amb API keys reals i paths Windows

:: 5. Crear estructura de prova
mkdir C:\g3dt-test\network
mkdir C:\g3dt-test\workspace
mkdir C:\g3dt-test\reports
:: copiar 1 projecte conegut (BELL-LLOC) a C:\g3dt-test\network\

:: 6. Llançar wizard
python -m web

:: 7. Obrir http://localhost:8765/review.html
:: Verificar:
::   - Dropdown llista BELL-LLOC
::   - Seleccionar BELL-LLOC fa sync a workspace
::   - Prefills es carreguen (~5s)
::   - Visió funciona (Groq) → omple plànol/sondeig/penetros
::   - Generar informe → .docx descarregat + copiat a network
```

**Si tot funciona:** ✅ FASE A tancada. Següent: FASE B.
**Si falla qualsevol pas:** documentar error → decidir entre fix o passar a Pla B (WSL).

---

## 5. FASE B — Documentació i dry-run (avui vespre, ~1-2h)

### B.1 — Guia d'instal·lació (per al Josep, no per a Eva)

Crear `docs/INSTALL-EVA-v1.md` amb:

- [ ] Pre-requisits ordinador Eva (Windows version, espai disc, permisos admin)
- [ ] Pas-a-pas: Python install → clonar branca → venv → deps → .env → estructura carpetes
- [ ] Configuració API keys (procés amb Eva: targeta crèdit G3DT → console.anthropic.com → console.groq.com)
- [ ] Configuració path xarxa: editar `.env` amb el path real (F:\... que digui Eva)
- [ ] Crear icona escriptori que llanci `G3DT-Wizard.bat`
- [ ] Test end-to-end amb 1 projecte conegut

### B.2 — Procediment de validació in-situ

10 checkpoints, cadascun amb criteri "passa / no passa":

1. [ ] Python instal·lat correctament: `python --version` retorna 3.11+
2. [ ] venv creat i activable: `.venv\Scripts\activate` no dóna error
3. [ ] Deps instal·lades: `pip list` mostra fastapi, anthropic, pymupdf, docxtpl
4. [ ] `.env` amb API keys reals i paths correctes
5. [ ] Wizard arrenca sense errors: `python -m web` no llança traceback
6. [ ] Browser obre `http://localhost:8765/review.html`
7. [ ] Dropdown llista projectes de la xarxa (almenys 1)
8. [ ] Seleccionar projecte fa sync workspace (verificar `C:\g3dt-ia\workspace\{p}\` té fitxers)
9. [ ] Pipeline omple prefills correctament (visió funciona)
10. [ ] Generar informe → .docx descarregable + copiat a `F:\...\{p}\`

### B.3 — Pla de rollback

**Si Fase A.6 (smoke test al Windows del Josep) falla:**
- Opció 1: fix puntual i tornar a provar
- Opció 2: passar a Pla B (instal·lació WSL a Eva)

**Si la instal·lació in-situ a Eva falla:**
- Punt de no-retorn: després de pas 5 (wizard arrenca). Si aquí falla, parar instal·lació.
- Si falla abans del pas 5: fix in-situ amb terminal Windows
- Si falla després del pas 5 (wizard arrenca però hi ha errors funcionals): debug amb logs (`logger` ja escriu a stdout)
- Última opció: WSL-based deployment (els .bat existents serveixen)

---

## 6. FASE C — Dry-run final (demà matí, abans d'anar a G3DT)

- [ ] Repetir checklist FASE B.2 al Windows natiu del Josep
- [ ] Confirmar que la branca `production/g3dt-eva-v1` és pushable (git push origin production/g3dt-eva-v1)
- [ ] Preparar pendrive amb còpia del repositori (backup si la xarxa de G3DT no permet git clone)
- [ ] Preparar API keys del Josep (temporals, per si Eva no pot crear-ne avui)

---

## 7. FASE D — Instal·lació in-situ a Eva (demà tarda)

### D.1 — Pre-instal·lació (preguntes a Eva en arribar)

> Context: G3DT no té departament d'IT propi. Les decisions tècniques les prenen Eva i Silvia directament (potser amb suport extern puntual).

- Path real de la carpeta de projectes a la xarxa (F:\... ?)
- Qui crea els API accounts (preferent: Silvia amb tarjeta G3DT)
- Té Eva permisos admin al seu ordinador? Si no, alternatives: Python Embeddable / WinPython sense privilegis
- Si hi ha polítiques d'empresa que restringeixin instal·lar Python (preguntar a Silvia, no IT)

### D.2 — Instal·lació (seguir `docs/INSTALL-EVA-v1.md`)

### D.3 — Configuració in-situ

- [ ] Editar `.env` amb path xarxa real
- [ ] (Si Eva crea API keys avui) configurar amb les seves; altrament temporals del Josep
- [ ] Crear icona escriptori → `G3DT-Wizard.bat`

### D.4 — Test end-to-end amb projecte real d'Eva

- Triar 1 projecte que Eva conegui bé (preferent: un dels 7 de referència, ex BELL-LLOC)
- Executar pipeline complet
- Eva valida visualment l'output

### D.5 — Tancament

- [ ] Eva signa acta d'instal·lació
- [ ] G3DT emet última factura del contracte
- [ ] Conversa sobre extensió (suport castellà) o pack manteniment (bossa d'hores)

---

## 8. Decisions pendents per demà

| Decisió | Quan | Qui |
|---|---|---|
| Path concret carpeta xarxa | En arribar a G3DT | Eva confirma |
| API keys: noves (G3DT) o temporals (Josep) | Inici instal·lació | Silvia (té tarjeta G3DT) |
| Permisos admin a l'ordinador d'Eva | Pre-instal·lació | Eva confirma |
| Pack manteniment vs extensió suport ES | Post-instal·lació | Silvia |

---

## 9. Riscos identificats i mitigacions

| Risc | Probabilitat | Impacte | Mitigació |
|---|---|---|---|
| Dep Python no compila a Windows (pymupdf, shapely) | Baixa | Alt | Usar wheels precompilats (pip ho fa per defecte). Pla B: WSL. |
| Path xarxa no accessible des del CMD | Mitjà | Alt | Mapejar unitat (net use) abans d'instal·lar. Si no és possible: UNC path al .env. |
| Latència xarxa en sync workspace | Mitjà | Mitjà | Workflow ja minimitza copies. Sync incremental amb robocopy. |
| API keys G3DT no es poden crear avui | Mitjà | Baix | Usar les del Josep temporalment. Configurar les definitives en una segona visita o remot. |
| Eva no té permisos admin per instal·lar Python | Alt | Alt | G3DT no té IT — coordinar amb Silvia. Alternatives sense admin: Python Embeddable (zip portable, sense instal·lador), WinPython, o instal·lació local user-level. |
| Botó "Vision Claude" premut per error → falla | Baix | Baix | Ja amagat per FASE A.3. Si reapareix per bug: missatge d'error clar. |
| Conflicte amb antivirus G3DT (FastAPI binding port 8765) | Baix | Mitjà | Documentar excepció. Plan B: port alternatiu. |

---

## 10. Pla B: si Windows natiu falla → WSL

Si A.6 o D.X demostren incompatibilitat insalvable:

1. Instal·lar WSL2 a Eva (`wsl --install` requereix admin + reboot)
2. Instal·lar Ubuntu des del Microsoft Store
3. Dins WSL: clonar `production/g3dt-eva-v1`, crear venv Linux, instal·lar deps
4. Usar els 3 batch files existents a `scripts/` (ja assumeixen WSL)
5. Modificar `G3DT-config.bat` perquè apunti al path WSL correcte
6. Mapejar carpeta xarxa a WSL (`/mnt/f/...`)

Aquest és el camí més provat (és com el Josep desenvolupa). Però afegeix complexitat per a Eva.

---

## 10.1. Pla C: si Windows natiu I WSL fallen → deploy al VPS d'Eficients

**Idea**: el wizard corre a un VPS, Eva només obre el navegador apuntant a `https://g3dt.eficients.cat:8765` (o subdomini equivalent).

**Pros:**
- Independent de l'ordinador d'Eva (sense Python, deps, antivirus, permisos admin)
- Eva només necessita navegador
- Updates centralitzats: deploy una vegada, totes les actualitzacions arriben sense tocar-li res
- Si li canvia l'ordinador, no pateix

**Contres importants — per què no és l'opció default:**
1. **Carpeta de projectes a la xarxa local de G3DT NO és accessible des d'un VPS extern.** Les unitats `F:\projectes` viuen dins de la LAN de G3DT. Caldria una de les solucions següents, totes amb fricció:
   - Eva penja manualment cada projecte (ZIP) abans de generar i baixa el `.docx` després — trenca el workflow del demo
   - VPN site-to-site G3DT ↔ VPS — IT-heavy, poc realista
   - Túnel SSH/Tailscale des d'un agent a la LAN de G3DT — necessita un servei corrent al seu ordinador igualment
2. **Dades de clients de G3DT al núvol.** Cal verificar implicacions LOPD/contractuals abans de pujar PDFs amb dades de promotors, arquitectes, ubicacions de parcel·les, etc.
3. **Latència Internet** per pujar PDFs grans i baixar `.docx` — més lent que LAN, encara que el pipeline corri al VPS.
4. **Cost recurrent**: VPS + ample de banda + manteniment.

**Quan considerar-lo:**
- A v1 (demà): NO. Massa canvis arquitectònics, no provat, i el problema de la xarxa de G3DT és insalvable sense feina prèvia.
- A v2+: viable si Eva ha de generar des de fora de l'oficina (mòbil, casa) i podem resoldre la qüestió de la xarxa via Tailscale/VPN.

**Acció avui:** documentar com a opció disponible, **no executar.**

---

## 11. Comunicació amb Eva pre-instal·lació

> Eva no treballa avui (diumenge). El missatge s'envia demà al matí, abans de sortir cap a G3DT.

A enviar dilluns 2026-05-04, primera hora del matí:

> *"Bon dia Eva, ens veiem aquesta tarda per la instal·lació. Per anar de pressa, ¿em pots confirmar dues coses quan arribi?*
> *1. La ruta exacta de la carpeta de projectes a la xarxa (F:\, G:\, o el que sigui).*
> *2. Si tens permisos administratius al teu ordinador per instal·lar Python. Si no, no passa res — tinc alternatives sense permisos admin.*
> *Una abraçada, Josep"*

**Path xarxa**: el sabrem demà al matí o en arribar; el `.env` s'edita in-situ. No bloqueja la preparació d'avui (la branca `production/g3dt-eva-v1` queda parametritzada).

---

## 12. Pendents al final de la sessió 2026-05-03

A l'inici de FASE A demà cal verificar:

- [ ] Branca `production/g3dt-eva-v1` creada i amb tots els canvis necessaris
- [ ] Smoke test al Windows del Josep: ✅ passa o ⚠️ documenta errors
- [ ] `docs/INSTALL-EVA-v1.md` redactat
- [ ] Backup pendrive preparat
- [ ] Missatge a Eva enviat amb les 2 preguntes

---

*Document mantingut per Josep + Claude Code. Actualitzar in-situ a mesura que es completen fases.*
