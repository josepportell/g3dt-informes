# Instal·lació G3DT v1 a l'Ordinador d'Eva

**Data prevista:** 2026-05-04
**Branca de producció:** `production/g3dt-eva-v1`
**Repo remote:** `https://github.com/josepportell/g3dt-informes.git`
**Audiència d'aquest document:** Josep (no és material per a Eva).

---

## 0. Resum executiu

Eva té els projectes a una unitat de xarxa de G3DT (`F:\` o `G:\` — confirmar). El sistema corre a Windows natiu, copia el projecte a una carpeta local (`C:\g3dt-ia\workspace\`), executa el pipeline determinista + visió Groq, genera el `.docx`, i el copia de tornada a la xarxa. Cap rastre (validation/, JSONs, caches) queda a la xarxa de G3DT.

Temps estimat d'instal·lació: **~45-90 min** (depenent de la velocitat d'internet, política d'antivirus, i si Eva té permisos admin).

---

## 1. Pre-requisits ordinador Eva (verificar en arribar)

### 1.1 Sistema operatiu
- Windows 10 64-bit o superior
- Mínim 8 GB RAM (recomanat 16 GB)
- Mínim 5 GB lliures a `C:\`

### 1.2 Permisos
- **Admin** o, si no, capacitat per instal·lar software user-level:
  - Si admin disponible: instal·lador oficial Python 3.11+ des de python.org
  - Si NO admin: alternatives sense privilegis a §2.1 (Python Embeddable / WinPython)

### 1.3 Connexió de xarxa
- Accés a `python.org`, `github.com`, `console.anthropic.com`, `console.groq.com`
- Verificar que l'antivirus no bloqueja descàrregues de `.exe` ni binding al port 8765

### 1.4 Carpeta de projectes
- Verificar amb Eva la **lletra de la unitat** (`F:`, `G:`, ...) i **ruta completa** (per exemple `F:\projectes`)
- Verificar **escriptura** a la carpeta (necessari per al copy-back del `.docx`)

### 1.5 API keys
- Decidir abans de començar:
  - **Opció A**: Eva/Silvia crea comptes nous a Anthropic + Groq amb tarjeta G3DT (recomanat — aïllament de cost)
  - **Opció B**: Usar les del Josep temporalment, migrar després (ràpid però barreja costos)

---

## 2. Procediment d'instal·lació pas-a-pas

### 2.1 Instal·lar Python 3.11+

**Cas A — Eva té permisos admin:**

1. Anar a [python.org/downloads](https://www.python.org/downloads/)
2. Descarregar Python 3.11 o superior (Windows installer 64-bit)
3. Executar instal·lador. **CRÍTIC: marcar "Add Python to PATH"**
4. Triar "Install Now" (default location)
5. Verificar a CMD nou: `python --version` → ha de mostrar `Python 3.11.x` o superior

**Cas B — Eva NO té permisos admin:**

1. Descarregar [Python Embeddable](https://www.python.org/downloads/windows/) (versió "embeddable package zip")
2. Descomprimir a `C:\g3dt-ia\python\`
3. Editar `python311._pth` per descomentar `import site`
4. Descarregar `get-pip.py` de [pip.pypa.io](https://bootstrap.pypa.io/get-pip.py)
5. Executar: `C:\g3dt-ia\python\python.exe get-pip.py`
6. Afegir `C:\g3dt-ia\python\` i `C:\g3dt-ia\python\Scripts\` al PATH user (no system)

### 2.2 Crear estructura de carpetes

A CMD:

```cmd
mkdir C:\g3dt-ia
mkdir C:\g3dt-ia\workspace
mkdir C:\g3dt-ia\reports
mkdir C:\g3dt-ia\logs
mkdir C:\g3dt-ia\cache
```

### 2.3 Clonar branca production

```cmd
cd C:\g3dt-ia
git clone --branch production/g3dt-eva-v1 --single-branch https://github.com/josepportell/g3dt-informes.git app
```

**Si Eva no té git instal·lat:**
- Opció A: instal·lar git for Windows ([git-scm.com](https://git-scm.com/download/win))
- Opció B: descarregar el ZIP de la branca des de GitHub i descomprimir a `C:\g3dt-ia\app\`
- Opció C (backup): `.bundle` al pendrive (vegeu §2.3.alt)

**§2.3.alt — Si la xarxa de G3DT bloqueja github.com:**
1. Al PC del Josep abans d'anar: `cd clients/g3dt-prod && git bundle create /mnt/c/users/josep/g3dt.bundle production/g3dt-eva-v1`
2. Pendrive amb el `.bundle`
3. A G3DT: `git clone --branch production/g3dt-eva-v1 --single-branch G:\path\to\g3dt.bundle C:\g3dt-ia\app`

### 2.4 Crear venv + instal·lar deps

```cmd
cd C:\g3dt-ia\app
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

**Observacions:**
- `pip install -e .` llegeix `pyproject.toml` i instal·la totes les deps (fastapi, anthropic, pymupdf, docxtpl, etc.)
- `pymupdf` i `shapely` tenen wheels precompilats per a Windows — no haurien de compilar
- Si alguna dep falla amb error de compilació: 99% és falta del Visual C++ Build Tools. Solució: instal·lar [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) o usar wheels prebuild

### 2.5 Configurar `.env`

```cmd
copy .env.example .env
notepad .env
```

A editar al `.env`:

| Variable | Valor a posar |
|---|---|
| `ANTHROPIC_API_KEY` | API key real (Eva o Josep) |
| `GROQ_API_KEY` | API key real |
| `OPENAI_API_KEY` | (opcional, recomanat per a fallback) |
| `G3DT_NETWORK_PROJECTS` | Path real de la carpeta xarxa (ex: `F:\projectes`) |
| `G3DT_LOCAL_WORKSPACE` | `C:\g3dt-ia\workspace` |
| `G3DT_REPORTS_DIR` | `C:\g3dt-ia\reports` |
| `G3DT_LOG_PATH` | `C:\g3dt-ia\logs\g3dt.log` |

Tots els flags de feature (`G3DT_ENABLE_AI_PIPELINE`, `G3DT_DEV_MODE`, `G3DT_PROD_USE_CLAUDECODE_VISION`) **deixar a `false`** com al `.env.example`.

**Avís sobre paths Windows al `.env`:** posar barres simples `\` o doblades `\\`. El loader de `.env` del projecte és tolerant a ambdós formats.

### 2.6 Crear icona escriptori (G3DT-Wizard.bat)

Crear nou fitxer `G3DT-Wizard.bat` a `C:\g3dt-ia\` amb el contingut següent (versió Windows natiu, no WSL):

```batch
@echo off
title G3DT - Wizard d'Informes
echo ============================================
echo   G3DT - Generador d'Informes Geotecnics
echo ============================================
echo.
echo Iniciant servidor... (no tanquis aquesta finestra)
echo.

cd /d C:\g3dt-ia\app
call .venv\Scripts\activate.bat

start "" http://localhost:8765/review.html

python -m web

echo.
echo Servidor aturat.
pause
```

**Crear drecera a l'escriptori d'Eva:**
1. Click dret → New → Shortcut
2. Target: `C:\g3dt-ia\G3DT-Wizard.bat`
3. Name: "G3DT — Wizard d'Informes"
4. Optional: canviar icona (right-click → Properties → Change Icon)

### 2.7 Test inicial (abans del checklist de validació)

```cmd
cd C:\g3dt-ia\app
.venv\Scripts\activate
python -c "from automation import config; print('Network:', config.G3DT_NETWORK_PROJECTS); print('Workspace:', config.G3DT_LOCAL_WORKSPACE); print('AI pipeline disabled:', not config.G3DT_ENABLE_AI_PIPELINE)"
```

Si retorna 3 línies coherents, configuració carregada bé. Si dóna error d'import, repassar §2.4 (venv + deps).

---

## 3. Validació in-situ — checklist 10 punts

Cada punt: **passa / no passa**. Si un falla, parar i arreglar abans de continuar al següent.

| # | Punt | Comprovació | Criteri d'èxit |
|---|---|---|---|
| 1 | Python instal·lat | `python --version` | `Python 3.11.x` o superior |
| 2 | venv activat | `where python` (a CMD amb venv actiu) | Path comença per `C:\g3dt-ia\app\.venv\Scripts\` |
| 3 | Deps instal·lades | `pip list \| findstr /i "fastapi anthropic pymupdf docxtpl"` | 4 línies retornades |
| 4 | `.env` carrega bé | `python -c "from automation import config; print(config.G3DT_NETWORK_PROJECTS)"` | Imprimeix path real (no buit) |
| 5 | Wizard arrenca | `python -m web` (deixar obert) | Veus `Application startup complete.` i `Uvicorn running on http://0.0.0.0:8765` |
| 6 | Browser obre review.html | Browser a `http://localhost:8765/review.html` | UI carrega, no error 404/500 |
| 7 | Llista projectes xarxa | Dropdown de projectes al wizard | Mostra els projectes de `F:\projectes` (o el que sigui) |
| 8 | Sync workspace | Seleccionar 1 projecte → esperar | Carpeta `C:\g3dt-ia\workspace\{nom}\` apareix amb fitxers copiats |
| 9 | Pipeline visió | Esperar al primer prefill (~30-60s) | Camps "Plànol", "Sondeig", "Penetros" omplerts (badges blaus = auto-extrets) |
| 10 | Generar + copy-back | Botó "Generar Informe" | `.docx` baixat al navegador + còpia a `F:\projectes\{nom}\*_generated.docx` |

**Si tot passa: ✅ instal·lació tècnica completa. Procedir al test funcional (§4).**

---

## 4. Test end-to-end amb projecte real

Triar **1 projecte que Eva conegui bé**. Recomanat: un dels 7 de referència que ja funcionen (BELL-LLOC, RUBÍ, LINYOLA, CASTELLAR, ALCOLETGE, VILANOVA, ANCILES). Bell-Lloc és el més "rodat" — bona primera demo.

### Procediment del test

1. Eva selecciona el projecte al wizard
2. **Cronomenta** quants segons triga el pipeline (objectiu: <90s)
3. Eva revisa els camps pre-omplerts. Per a un projecte de referència, ha de coincidir amb el seu informe original ~95%.
4. Eva fa els ajustos que cregui necessaris
5. Genera l'informe
6. **Eva obre el .docx generat i el compara amb el seu informe signat**
7. Anotar diferències (si n'hi ha) — material per a la conversa de manteniment futur

### Criteris d'acceptació

- [ ] Pipeline completa sense errors
- [ ] Camps pre-omplerts són raonables (no buits, no cridanters)
- [ ] El `.docx` generat s'obre a Word sense problemes
- [ ] El contingut és coherent amb el projecte (no barreja dades d'altres)
- [ ] Eva confirma "amb 30s d'ajustos puc lliurar això"

---

## 5. Pla de rollback (si la instal·lació falla)

### 5.1 Punts de no-retorn

- **Pas 2.4 falla** (deps no instal·len) → arreglar amb VC++ Build Tools o passar a Pla B (WSL)
- **Pas 5 del checklist falla** (wizard no arrenca) → cap més pas; debug intensiu
- **Pas 8 falla** (sync workspace error) → revisar permisos de lectura xarxa

### 5.2 Pla B: WSL (si Windows natiu falla)

Documentat al pla principal `docs/PLA-DEPLOYMENT-EVA-2026-05-04.md` §10. Resum:

1. `wsl --install` (requereix admin + reboot)
2. Ubuntu des de Microsoft Store
3. Dins WSL: clonar branca, venv Linux, deps via pip
4. Adaptar `G3DT-Wizard.bat` perquè invoqui WSL en lloc de Python natiu

### 5.3 Pla C: VPS (deferit a v2)

NO implementar avui. La carpeta de projectes a la xarxa de G3DT no és accessible des d'un VPS extern. Deferit fins a tenir VPN/Tailscale o canvi de workflow.

### 5.4 Pla d'emergència: tornar a casa

Si cap pla funciona, **tancar la sessió amb una promesa concreta** ("torno demà amb una solució") i **NO deixar el sistema en estat brut** (esborrar `C:\g3dt-ia\` si està a mig instal·lar). Eva no ha de quedar pitjor que abans.

---

## 6. Després de la instal·lació — handoff a Eva

### 6.1 Demostració d'ús

Mostrar a Eva (o Silvia, si està):
1. Com obrir el wizard amb la drecera de l'escriptori
2. Com seleccionar un projecte
3. Com revisar els camps i ajustar-los
4. Com generar i descarregar el `.docx`
5. **Com tancar el wizard** (tancar la finestra de CMD que diu "G3DT - Wizard d'Informes")

### 6.2 Documentació mínima per Eva

Deixar al desktop/escriptori:
- Drecera "G3DT — Wizard d'Informes" (la del .bat)
- Drecera al teu telèfon/email per a incidències

(NO deixar documentació tècnica detallada — Eva no la llegirà. Si volem documentació, fer-la curta, visual, basada en captures de pantalla. Pot ser feina d'una segona visita.)

### 6.3 Confirmació final

Abans de marxar:
- [ ] Eva genera 1 informe sense ajuda (assistència només verbal si cal)
- [ ] Acta de servei signada (tu portar-la)
- [ ] Conversa amb Silvia: factura final + extensió suport castellà o pack manteniment

---

## 7. Coses per **no** fer durant la instal·lació

- ❌ Tocar el codi a `C:\g3dt-ia\app\` directament. Si trobes un bug, anota'l, fes hotfix al PC d'Eva només si és bloquejant, i fes la solució neta al teu repo en tornar.
- ❌ Esborrar carpetes a `F:\projectes\` (la xarxa) ni renombrar res.
- ❌ Configurar `G3DT_ENABLE_AI_PIPELINE=true` ni `G3DT_DEV_MODE=true` "per provar". Avui no.
- ❌ Pujar al PC d'Eva les API keys del Josep si la sessió queda gravada en pantalla compartida o similar (ull amb reflexes a vidres, etc).
- ❌ Promès millores que no estiguin a la "bossa d'hores" de manteniment. Cada "ho arreglo demà" sense mecanisme s'acumula.

---

## 8. Material que el Josep ha de portar

| Item | Per a què |
|---|---|
| Portàtil personal del Josep | Backup si cal debug ràpid + tu mateix sentirses a casa |
| Pendrive amb `g3dt.bundle` | Si la xarxa G3DT bloqueja github.com |
| Portàtil amb internet (4G/5G) | Si la xarxa G3DT cau enmig |
| API keys del Josep (en paper o gestor) | Plan B si Silvia no pot crear comptes avui |
| Acta d'instal·lació en blanc | Per signar al final |
| Targeta amb el teu telèfon/email | Per deixar a Eva |

---

## 9. Comunicació pre-visita

A enviar dilluns matí (avui), abans de sortir cap a G3DT:

> *"Bon dia Eva, ens veiem aquesta tarda per la instal·lació. Per anar de pressa, ¿em pots confirmar dues coses quan arribi?*
> *1. La ruta exacta de la carpeta de projectes a la xarxa (F:\, G:\, o el que sigui).*
> *2. Si tens permisos administratius al teu ordinador per instal·lar Python. Si no, no passa res — tinc alternatives sense permisos admin.*
> *Una abraçada, Josep"*

---

*Document mantingut per Josep + Claude Code. Actualitzar al final de la instal·lació amb troballes reals i incidències, com a base per al manual de manteniment.*
