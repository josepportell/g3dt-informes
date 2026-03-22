# Guia d'Instal·lació — G3DT a l'ordinador d'Eva

Guia pas a pas per instal·lar el sistema G3DT en un ordinador Windows amb WSL.

**Temps estimat:** ~45 minuts (amb connexió a internet)
**Requisits:** Windows 10/11, accés a internet, permisos d'administrador

---

## Índex

1. [Preparació Windows](#1-preparació-windows)
2. [Instal·lar WSL i Ubuntu](#2-installar-wsl-i-ubuntu)
3. [Configurar l'entorn Linux](#3-configurar-lentorn-linux)
4. [Instal·lar el projecte G3DT](#4-installar-el-projecte-g3dt)
5. [Configurar Claude Code](#5-configurar-claude-code)
6. [Configurar variables d'entorn](#6-configurar-variables-dentorn)
7. [Crear dreceres d'escriptori](#7-crear-dreceres-descriptori)
8. [Verificar la instal·lació](#8-verificar-la-installació)
9. [Estructura de carpetes de projectes](#9-estructura-de-carpetes-de-projectes)
10. [Projectes en unitat de xarxa](#10-projectes-en-unitat-de-xarxa)
11. [Solució de problemes](#11-solució-de-problemes)

---

## 1. Preparació Windows

### 1.1 Crear la carpeta de projectes

Crear la carpeta on Eva deixarà els projectes. Dues opcions:

**Opció A — Carpeta local (més senzill):**
```
C:\claude\g3dt\projectes\
```
Accessible des de WSL com `/mnt/c/claude/g3dt/projectes/`.

**Opció B — Unitat de xarxa:**
Si els projectes estan en un servidor de xarxa (ex: `\\servidor\compartit\projectes`), cal mapejar la unitat. Veure [secció 10](#10-projectes-en-unitat-de-xarxa).

### 1.2 Verificar versió de Windows

Obrir PowerShell com a administrador i comprovar:

```powershell
winver
```

Es necessita Windows 10 versió 2004+ o Windows 11.

---

## 2. Instal·lar WSL i Ubuntu

### 2.1 Instal·lar WSL

Obrir **PowerShell com a administrador** i executar:

```powershell
wsl --install
```

Això instal·la WSL 2 amb Ubuntu per defecte. **Cal reiniciar l'ordinador.**

### 2.2 Configurar l'usuari Ubuntu

Després del reinici, s'obre automàticament una terminal Ubuntu que demana:
- **Nom d'usuari:** `eva` (o el que es prefereixi)
- **Contrasenya:** escollir una contrasenya i recordar-la

### 2.3 Verificar

```bash
wsl --status
```

Ha de mostrar WSL 2 amb Ubuntu.

---

## 3. Configurar l'entorn Linux

Obrir la terminal Ubuntu (o des de PowerShell: `wsl`).

### 3.1 Actualitzar el sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2 Instal·lar Python 3.12

Ubuntu 24.04 ja porta Python 3.12. Si no:

```bash
sudo apt install -y python3 python3-pip python3-venv
python3 --version
# Ha de mostrar Python 3.11 o superior
```

### 3.3 Instal·lar uv (gestor de paquets Python)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

### 3.4 Instal·lar Node.js (necessari per Claude Code)

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
```

### 3.5 Instal·lar git

```bash
sudo apt install -y git
git --version
```

---

## 4. Instal·lar el projecte G3DT

### 4.1 Clonar el repositori

```bash
mkdir -p ~/projects
cd ~/projects
git clone <URL_REPOSITORI> g3dt
cd g3dt
```

> **Alternativa sense git:** Josep copiarà la carpeta del projecte directament.

### 4.2 Crear l'entorn virtual i instal·lar dependències

```bash
cd ~/projects/g3dt
uv sync
```

Això crea `.venv/` i instal·la totes les dependències:
- `docxtpl` (generació Word)
- `xlrd` (lectura Excel .xls)
- `pydantic` (validació de dades)
- `fastapi` + `uvicorn` (servidor web)
- `pymupdf` (lectura PDFs)
- `anthropic` (API Claude per visió)
- `shapely` (geometria parcel·les)

### 4.3 Verificar

```bash
.venv/bin/python -c "import docxtpl, xlrd, pydantic, fastapi, fitz, anthropic, shapely; print('OK')"
```

Ha de mostrar `OK`.

---

## 5. Configurar Claude Code

### 5.1 Instal·lar Claude Code

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### 5.2 Autenticar Claude Code

```bash
claude
```

La primera vegada demana autenticació. Seguir les instruccions a pantalla per vincular el compte d'Anthropic.

> **Compte Anthropic:** G3DT necessita un compte amb subscripció Claude Code Pro (~20€/mes).
> El compte ha de ser de titularitat de G3DT (segons contracte, clàusula 5.6).

### 5.3 Verificar

```bash
claude --version
# Ha de mostrar la versió (ex: 2.1.76)
```

---

## 6. Configurar variables d'entorn

### 6.1 Crear fitxer .env

```bash
cd ~/projects/g3dt
nano .env
```

Contingut del fitxer `.env`:

```bash
# Carpeta on Eva deixa els projectes (accessible des de Windows)
G3DT_PROJECTS_DIR=/mnt/c/claude/g3dt/projectes

# Ruta al binari de Claude Code (normalment ja al PATH)
G3DT_CLAUDE_PATH=claude

# Timeout de la visió en segons (5 minuts per 3 PDFs)
G3DT_VISION_TIMEOUT=600
```

Guardar: `Ctrl+O`, `Enter`, `Ctrl+X`.

### 6.2 Configurar clau API Anthropic

La visió (lectura de PDFs de camp) utilitza l'API d'Anthropic directament. Afegir al `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXX
```

> **On trobar la clau:** console.anthropic.com → API Keys → Create Key
> Aquesta clau és diferent de l'autenticació de Claude Code.

### 6.3 Ajustar la ruta de projectes (si cal)

Si Eva vol que els projectes estiguin en una altra ubicació de Windows (ex: `D:\G3DT\projectes\`), canviar `G3DT_PROJECTS_DIR`:

```bash
G3DT_PROJECTS_DIR=/mnt/d/G3DT/projectes
```

La convenció: unitat Windows `C:\` = `/mnt/c/`, `D:\` = `/mnt/d/`, etc.

---

## 7. Crear dreceres d'escriptori

### 7.1 Copiar els scripts .bat

Des de PowerShell o l'explorador de Windows, copiar els 3 fitxers de `scripts/` a una carpeta accessible (ex: `C:\claude\g3dt\`):

- `scripts/G3DT-config.bat` — Configuració compartida (ruta del projecte)
- `scripts/G3DT-Wizard.bat` — Arrenca el wizard i obre el navegador
- `scripts/G3DT-Claude.bat` — Obre terminal Claude Code

> **Important:** Els 3 fitxers han d'estar a la mateixa carpeta.

### 7.2 Ajustar la ruta del projecte

Obrir `G3DT-config.bat` amb un editor de text. Només cal editar **aquest fitxer**:

```batch
set G3DT_PATH=/home/eva/projects/g3dt
```

Canviar `/home/eva/` pel nom d'usuari Ubuntu creat al pas 2.2. Els altres dos `.bat` llegeixen aquesta configuració automàticament.

### 7.3 Crear dreceres a l'escriptori

1. Clic dret a cada `.bat` → "Enviar a" → "Escriptori (crear drecera)"
2. Opcionalment, canviar la icona de la drecera per fer-la més reconeixible

---

## 8. Verificar la instal·lació

### 8.1 Test ràpid del servidor web

```bash
cd ~/projects/g3dt
.venv/bin/python -m web
```

Ha de mostrar:
```
G3DT Web Wizard: http://localhost:8765
```

Obrir al navegador: http://localhost:8765/review.html

El wizard ha de carregar i mostrar el dropdown de projectes.

### 8.2 Test amb un projecte

1. Copiar un projecte de prova a la carpeta de projectes (`C:\claude\g3dt\projectes\`)
2. Refrescar el wizard al navegador
3. Seleccionar el projecte del dropdown
4. Verificar que els prefills es carreguen (~5 segons)
5. Clicar "Llegir PDFs de camp" → verificar que la visió funciona (~30 segons)
6. Generar un informe de prova

### 8.3 Checklist de verificació

| Component | Com verificar | Resultat esperat |
|-----------|---------------|------------------|
| WSL | `wsl --status` (PowerShell) | WSL 2 amb Ubuntu |
| Python | `python3 --version` (Ubuntu) | 3.11 o superior |
| uv | `uv --version` (Ubuntu) | Instal·lat |
| Dependències | `.venv/bin/python -c "import fastapi"` | Sense errors |
| Claude Code | `claude --version` (Ubuntu) | Versió mostrada |
| API Anthropic | Botó "Llegir PDFs" al wizard | PDFs es llegeixen |
| Servidor web | Obrir localhost:8765 | Wizard es carrega |
| Projectes | Dropdown al wizard | Mostra projectes |
| Generació | Botó "Generar Informe" | .docx descarregable |

### 8.4 Test des de Windows (.bat)

1. Doble clic a **G3DT-Wizard.bat** des de l'escriptori
2. Ha d'obrir el navegador amb el wizard automàticament
3. Verificar que tot funciona igual que al test manual

---

## 9. Estructura de carpetes de projectes

Eva ha de crear cada projecte seguint aquesta estructura:

```
C:\claude\g3dt\projectes\
└── {expedient} {MUNICIPI}\
    ├── A.01.pdf                    ← Plànol arquitecte (obligatori)
    ├── PENETROS.pdf                ← Full de camp DPSH (obligatori)
    ├── SONDEIG.pdf                 ← Full de camp sondeig (obligatori)
    ├── tall.pdf                    ← Tall de correlació (obligatori)
    ├── ANNEXES\
    │   ├── {expedient}_DPSH.xls   ← Excel DPSH (obligatori)
    │   └── ALTRES\
    │       └── COORDENADES.txt    ← UTM (opcional, sinó geocodifica)
    ├── FOTOGRAFIES\               ← Fotos de camp (opcional)
    │   ├── DPSH\
    │   └── SONDEIG\
    └── PDF\
        └── ANNEXES\
            └── LAB-SIG.pdf        ← Resultats lab (opcional)
```

Nom de la carpeta: `{expedient} {MUNICIPI}` (ex: `4001612 BELL-LLOC`)

Document complet: `CONDICIONS-CARPETA-PROJECTE.md`

---

## 10. Projectes en unitat de xarxa

Si Eva té els projectes en una unitat de xarxa (`\\servidor\compartit\...`), WSL no pot accedir-hi directament. Cal mapejar la ruta de xarxa a una lletra d'unitat de Windows.

### 10.1 Mapejar la unitat de xarxa

1. Obrir **Explorador de Windows** (Win+E)
2. Clic dret a **"Aquest equip"** → **"Connecta a una unitat de xarxa..."**
3. Escollir una lletra d'unitat (ex: `Z:`)
4. Escriure la ruta de xarxa (ex: `\\servidor\compartit\projectes`)
5. Marcar **"Torna a connectar en iniciar sessió"**
6. Clic a **"Finalitza"**

### 10.2 Configurar G3DT per la unitat mapejada

Editar el fitxer `.env` del projecte:

```bash
G3DT_PROJECTS_DIR=/mnt/z/
```

La convenció de WSL: lletra d'unitat Windows → `/mnt/{lletra minúscula}/`

| Windows | WSL |
|---------|-----|
| `Z:\` | `/mnt/z/` |
| `Z:\projectes\` | `/mnt/z/projectes/` |
| `S:\G3DT\projectes\` | `/mnt/s/G3DT/projectes/` |

### 10.3 Verificar accés des de WSL

Obrir terminal Ubuntu i comprovar:

```bash
ls /mnt/z/
```

Ha de mostrar el contingut de la unitat de xarxa.

### 10.4 Problemes habituals amb unitats de xarxa

| Problema | Causa | Solució |
|----------|-------|---------|
| `ls /mnt/z/` no mostra res | Unitat desconnectada | Obrir `Z:\` a l'Explorador de Windows per reconnectar |
| Wizard no mostra projectes després de reiniciar | Windows no ha reconnectat la unitat automàticament | Obrir `Z:\` a l'Explorador. Si passa sovint, crear un script d'inici (veure 10.5) |
| Error d'accés/permisos | Credencials de xarxa caducades | Desconnectar i tornar a mapejar la unitat amb credencials actualitzades |
| Lectura de PDFs lenta | Latència de xarxa normal | Esperar — la diferència és de segons, no minuts |
| Excel DPSH bloquejat | Fitxer obert amb Excel | Tancar l'Excel abans de generar l'informe |

### 10.5 Reconnexió automàtica (opcional)

Si la unitat es desconnecta sovint després de suspendre/hibernar l'ordinador, crear un fitxer `reconnectar-xarxa.bat` a l'escriptori:

```batch
@echo off
net use Z: \\servidor\compartit\projectes /persistent:yes
echo Unitat Z: reconnectada.
pause
```

Eva pot fer doble clic en aquest fitxer si el wizard no mostra projectes.

---

## 11. Solució de problemes

| Problema | Causa probable | Solució |
|----------|----------------|---------|
| `wsl` no es reconeix | WSL no instal·lat | Executar `wsl --install` com a admin |
| "Python not found" | Python no instal·lat a Ubuntu | `sudo apt install python3` |
| `uv: command not found` | uv no al PATH | `source ~/.bashrc` o reinstal·lar |
| `claude: command not found` | Claude Code no instal·lat | `npm install -g @anthropic-ai/claude-code` |
| Error `ANTHROPIC_API_KEY` | Clau no configurada | Afegir al `.env` (pas 6.2) |
| Wizard no mostra projectes | Ruta incorrecta | Verificar `G3DT_PROJECTS_DIR` al `.env` |
| "Llegir PDFs" falla | Clau API invàlida o expirada | Verificar clau a console.anthropic.com |
| El .bat no funciona | Ruta WSL incorrecta | Ajustar `G3DT_PATH` a `G3DT-config.bat` (pas 7.2) |
| "G3DT-config.bat no trobat" | Scripts en carpetes separades | Posar els 3 `.bat` a la mateixa carpeta |
| Port 8765 ocupat | Servidor anterior encara actiu | Tancar la finestra del wizard anterior |
| Visió tarda >2 min | Latència API normal | Esperar, la primera vegada pot ser més lent |

### Contacte de suport

Josep Portell — Eficients.cat
- Email: josep@eficients.cat
- WhatsApp: 687 838 596
