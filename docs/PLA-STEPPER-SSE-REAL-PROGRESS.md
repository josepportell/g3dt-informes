# Pla: Stepper amb progrés real via SSE

## Situació actual

El stepper actual (Fitxers → Extracció → Visió IA → Wizard) és **cosmètic**: avança amb `setTimeout` cada ~600ms independentment del que fa el backend. El backend retorna tot (`/api/prefills/{project}`) en una sola resposta quan acaba (~3-8s).

A més, "Visió IA" no s'executa automàticament (Claude SDK no aprovat). Actualment Eva la fa manualment (`/g3dt-visio-projecte` al terminal).

## Objectius

1. **Stepper real**: cada pas avança quan el backend confirma que ha acabat aquella fase
2. **Eliminar "Visió IA"** del stepper automatitzat (no és automàtic)
3. **Fitxers sota cada icona** del stepper: mostrar quins fitxers/fonts s'han processat
4. **Eliminar l'acordió de fitxers** de la secció instruccions (la info migra al stepper)

## Arquitectura: dos steppers

El wizard mostra **dos steppers** amb propòsits diferents:

```
┌─────────────────────────────────────────────────────────────────┐
│  STEPPER 1: Automàtic (SSE)                                     │
│  Fitxers ──▶ Dades ──▶ Llest                                    │
│  S'executa sol quan selecciones projecte. ~3-8s.                │
├─────────────────────────────────────────────────────────────────┤
│  STEPPER 2: Visió manual                                        │
│  Copiar comanda ──▶ Executar al terminal ──▶ Actualitzar        │
│  Eva fa cada pas. El sistema detecta progrés automàticament.    │
└─────────────────────────────────────────────────────────────────┘
```

**Per què dos?** El stepper automàtic cobreix el que el sistema fa sol. El stepper de visió guia Eva pel pas que més la pot intimidar (el terminal) i li dóna confiança visual de que ho està fent bé.

**Quan es mostra cada un?**
- Stepper 1: sempre, al seleccionar projecte (reemplaça l'actual)
- Stepper 2: apareix dins la secció instruccions NOMÉS si falten visions (planol/dpsh/sondeig). Si totes les visions ja existeixen (JSONs presents), el stepper 2 no es mostra — només un missatge "Visió completada ✓".

---

## Stepper 1: Automàtic (SSE)

### Nous passos del stepper

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Fitxers  │────▶│  Dades       │────▶│    Llest      │
│ (scan)   │     │  (extract)   │     │   (ready)     │
└──────────┘     └──────────────┘     └──────────────┘
   ~0.5s             ~3-7s                instant
```

- **Fitxers**: FileScanner (Phase 0.1) → classifica els fitxers del projecte
- **Dades**: DPSH Excel + Lab PDF + Geocode + ICGC + Cadastre (Phases 1-3)
- **Llest**: Wizard prefills merged, formulari visible

Tres passos en lloc de quatre. Més honest, menys soroll.

## Fitxers sota les icones del stepper

A mesura que SSE envia events, es mostren els fitxers/fonts processats sota cada icona:

```
   ┌───┐           ┌───┐           ┌───┐
   │ ✓ │───────────│ ● │───────────│   │
   └───┘           └───┘           └───┘
  Fitxers          Dades           Llest

  DPSH.xls        ICGC geologia
  SONDEIG.pdf     ICGC elevació
  A.01.pdf        Cadastre adj.
  LAB.pdf         Geocode UTM
```

Cada sub-item apareix individualment quan l'event SSE corresponent arriba.

### Disseny visual dels sub-items

```css
.step-files {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    margin-top: 4px;
    font-size: 10px;
    color: #888;
    max-width: 80px;
    overflow: hidden;
}
.step-file-item {
    animation: fadeIn 0.3s ease;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    max-width: 100%;
}
.step-file-item.ok { color: #4a90d9; }
.step-file-item.skip { color: #ccc; text-decoration: line-through; }
```

## Implementació

### 1. Backend: SSE endpoint (`web/api.py`)

Nou endpoint que fa streaming dels events de progrés:

```python
@router.get("/prefills-stream/{project_name:path}")
async def prefills_stream(project_name: str):
    """SSE endpoint: streams progress events, then the final prefills JSON."""

    async def event_generator():
        # Phase 0.1: File scan
        yield sse_event("step", {"step": "scan", "status": "active"})
        file_mapping = _phase_scan(project_path)
        yield sse_event("step", {"step": "scan", "status": "done", "files": file_list})

        # Phase 1-3: Extraction
        yield sse_event("step", {"step": "extract", "status": "active"})
        # Sub-events per font de dades:
        yield sse_event("source", {"name": "DPSH Excel", "status": "done"})
        yield sse_event("source", {"name": "Lab PDF", "status": "done"})
        yield sse_event("source", {"name": "Geocode", "status": "done"})
        yield sse_event("source", {"name": "ICGC geologia", "status": "done"})
        # ...
        yield sse_event("step", {"step": "extract", "status": "done"})

        # Final: all prefills
        yield sse_event("step", {"step": "ready", "status": "done"})
        yield sse_event("prefills", merged_prefills)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Requisit**: `auto_extract()` s'ha de refactoritzar perquè accepti un callback `on_progress(phase, detail)` que el SSE endpoint pot cridar. Alternativa: executar cada `_phaseX()` individualment des de l'endpoint.

### 2. Backend: refactor `auto_extract()` amb callback

```python
def auto_extract(
    project_path: str | Path,
    *,
    skip_phase3: bool = False,
    on_progress: Callable[[str, dict], None] | None = None,
) -> AutoExtractionResult:

    def emit(event_type: str, detail: dict):
        if on_progress:
            on_progress(event_type, detail)

    # Phase 0.1
    emit("step", {"step": "scan", "status": "active"})
    _phase1_file_scanner(project_path, result)
    emit("file", {"name": "FileScanner", "roles": list(result.file_mapping.roles.keys())})
    _phase01_content_discovery(project_path, result)
    emit("step", {"step": "scan", "status": "done"})

    # Phase 1
    emit("step", {"step": "extract", "status": "active"})
    _phase1_dpsh(project_path, result)
    emit("source", {"name": "DPSH Excel", "ok": bool(result.dpsh_data)})
    # ... etc per cada fase
```

### 3. Frontend: EventSource reemplaça fetch

```javascript
const PIPELINE_STEPS = ['scan', 'extract', 'ready'];

async function loadProjectData() {
    const es = new EventSource(`/api/prefills-stream/${encodeURIComponent(selectedProject)}`);

    es.addEventListener('step', (e) => {
        const data = JSON.parse(e.data);
        if (data.status === 'active') setStepState(data.step, 'active');
        if (data.status === 'done') setStepState(data.step, 'done');
    });

    es.addEventListener('file', (e) => {
        // Afegir fitxer sota la icona "Fitxers"
        const data = JSON.parse(e.data);
        appendStepFile('scan', data.name, 'ok');
    });

    es.addEventListener('source', (e) => {
        // Afegir font de dades sota la icona "Dades"
        const data = JSON.parse(e.data);
        appendStepFile('extract', data.name, data.ok ? 'ok' : 'skip');
    });

    es.addEventListener('prefills', (e) => {
        wizardPrefills = JSON.parse(e.data);
        es.close();
        showWizardContent();
    });

    es.onerror = () => {
        es.close();
        showMessage('Error carregant dades', 'error');
    };
}

function appendStepFile(stepId, fileName, status) {
    const container = document.getElementById(`step-files-${stepId}`);
    const item = document.createElement('span');
    item.className = `step-file-item ${status}`;
    item.textContent = fileName;
    container.appendChild(item);
}
```

### 4. HTML: nou stepper amb contenidors de fitxers

```html
<div id="pipelineStepper" class="pipeline-stepper">
    <div class="pipeline-steps">
        <div class="pipeline-step" id="step-scan">
            <div class="step-circle">
                <div class="step-spinner"></div>
                <span class="step-icon"><!-- folder SVG --></span>
            </div>
            <span class="step-label">Fitxers</span>
            <div class="step-files" id="step-files-scan"></div>
        </div>
        <div class="step-connector" id="conn-1"></div>
        <div class="pipeline-step" id="step-extract">
            <div class="step-circle">
                <div class="step-spinner"></div>
                <span class="step-icon"><!-- clipboard SVG --></span>
            </div>
            <span class="step-label">Dades</span>
            <div class="step-files" id="step-files-extract"></div>
        </div>
        <div class="step-connector" id="conn-2"></div>
        <div class="pipeline-step" id="step-ready">
            <div class="step-circle">
                <div class="step-spinner"></div>
                <span class="step-icon"><!-- check SVG --></span>
            </div>
            <span class="step-label">Llest</span>
        </div>
    </div>
</div>
```

### 5. Eliminar l'acordió de fitxers de instruccions

La secció `renderInstructions()` ja no necessita el bloc `fileListHtml` amb l'acordió "N fitxers detectats". Aquesta informació ara viu al stepper sota la icona "Fitxers".

La secció instruccions queda centrada en el flux manual de visió:
- Badges planol/dpsh/sondeig (estat actual)
- Comanda `/g3dt-visio-projecte ...` per copiar
- Passos: executar → actualitzar prefills → revisar → generar

### 6. Endpoint original `/api/prefills/{project}` es manté

Per compatibilitat (botó "Actualitzar prefills" i qualsevol crida directa). El SSE endpoint és una alternativa, no un reemplaçament.

## Fitxers a modificar (tots dos steppers)

| Fitxer | Canvi |
|--------|-------|
| `web/api.py` | Nous endpoints: SSE `/api/prefills-stream/{project}` + `GET /api/vision-status/{project}` |
| `automation/auto_extractor.py` | Paràmetre `on_progress` callback |
| `templates/validation/review.html` | Stepper 1 (3 passos SSE) + Stepper 2 (visió manual) + step-files + polling + eliminar acordió fitxers |
| `web/wizard_service.py` | Funció `get_prefills_streaming()` que crida auto_extract amb callback |

## Events SSE (protocol)

```
event: step
data: {"step": "scan", "status": "active"}

event: file
data: {"name": "DPSH.xls", "role": "dpsh_excel"}

event: file
data: {"name": "SONDEIG.pdf", "role": "sondeig_pdf"}

event: step
data: {"step": "scan", "status": "done", "count": 7}

event: step
data: {"step": "extract", "status": "active"}

event: source
data: {"name": "DPSH Excel", "status": "done", "fields": 4}

event: source
data: {"name": "ICGC geologia", "status": "done"}

event: source
data: {"name": "ICGC elevació", "status": "done"}

event: source
data: {"name": "Cadastre adj.", "status": "skipped", "reason": "sense UTM"}

event: step
data: {"step": "extract", "status": "done"}

event: step
data: {"step": "ready", "status": "done"}

event: prefills
data: { ...merged prefills JSON... }
```

---

## Stepper 2: Visió manual

### Passos

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  1. Copiar   │────▶│  2. Executar     │────▶│  3. Actualitzar   │
│   comanda    │     │   al terminal    │     │    prefills        │
└──────────────┘     └──────────────────┘     └───────────────────┘
   clic botó          file watcher              clic botó + fetch
```

- **Pas 1 — Copiar comanda**: Eva clica "Copiar". El frontend detecta el clic i marca el pas com a `done`. Trivial.
- **Pas 2 — Executar al terminal**: Eva enganxa la comanda al terminal de Claude Code. El sistema fa **polling** dels fitxers que la comanda crea (`validation/planol_extracted.json`, `dpsh_extracted.json`, `sondeig_extracted.json`). Quan detecta canvis, marca el pas com a `done`.
- **Pas 3 — Actualitzar prefills**: Eva clica "Actualitzar prefills". El frontend marca el pas com a `active`, fa el fetch, i quan acaba el marca com a `done`.

### Detecció de progrés al pas 2: polling de fitxers

Endpoint lleuger per consultar l'estat dels JSONs de visió:

```python
@router.get("/vision-status/{project_name:path}")
def vision_status(project_name: str):
    """Check which vision JSONs exist and their mtime."""
    project_path = _resolve_project(project_name)
    vision_files = {
        'planol': 'planol_extracted.json',
        'dpsh': 'dpsh_extracted.json',
        'sondeig': 'sondeig_extracted.json',
    }
    status = {}
    for key, filename in vision_files.items():
        path = project_path / 'validation' / filename
        if path.exists():
            status[key] = {"exists": True, "mtime": path.stat().st_mtime}
        else:
            status[key] = {"exists": False}
    return status
```

El frontend fa polling cada ~3s mentre el pas 2 està actiu:

```javascript
let visionPollTimer = null;
let visionBaseline = {};  // mtime snapshot quan es va copiar la comanda

function startVisionPolling() {
    // Capturar baseline: quins JSONs ja existien ABANS de copiar
    fetch(`/api/vision-status/${encodeURIComponent(selectedProject)}`)
        .then(r => r.json())
        .then(status => {
            visionBaseline = status;
            visionPollTimer = setInterval(checkVisionFiles, 3000);
        });
}

function checkVisionFiles() {
    fetch(`/api/vision-status/${encodeURIComponent(selectedProject)}`)
        .then(r => r.json())
        .then(status => {
            // Comparar amb baseline: nous fitxers o mtime canviat?
            let newFiles = 0;
            for (const key of ['planol', 'dpsh', 'sondeig']) {
                const base = visionBaseline[key];
                const curr = status[key];
                if (curr.exists && (!base.exists || curr.mtime > base.mtime)) {
                    newFiles++;
                    // Actualitzar badge individual del stepper
                    markVisionBadge(key, 'done');
                }
            }
            if (newFiles > 0) {
                // Al menys un fitxer nou → pas 2 completat
                clearInterval(visionPollTimer);
                setVisionStepState(2, 'done');
                // Pas 3 queda "ready" (no actiu fins que Eva cliqui)
                setVisionStepState(3, 'ready');
            }
        });
}
```

**Per què polling i no WebSocket/SSE?** Perquè:
1. El procés que crea els fitxers és Claude Code al terminal, no el nostre backend
2. L'endpoint és molt lleuger (3 `stat()` calls)
3. Cada 3s és suficient — Eva triga ~30s+ al terminal
4. No cal infraestructura addicional

### Disseny visual del stepper de visió

Més petit que l'automàtic. Va dins la secció instruccions (reemplaça la llista `<ol>` actual).

```
┌─ Visió IA (1/3 completat) ──────────────────────────────────┐
│                                                              │
│  ┌───┐         ┌───┐         ┌───┐                          │
│  │ ✓ │─────────│ ● │─────────│   │                          │
│  └───┘         └───┘         └───┘                          │
│  Copiar       Terminal      Actualitzar                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ /g3dt-visio-projecte reference-material/4001612...  │    │
│  │                                        [Copiar]     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ● planol  ● dpsh  ○ sondeig                                │
└──────────────────────────────────────────────────────────────┘
```

- Els badges (planol/dpsh/sondeig) es mantenen sota el stepper
- Quan tots són `done`, el stepper sencer es col·lapsa amb "Visió completada ✓"
- El bloc de comanda només es mostra si pas 1 no és `done`

### Interacció pas a pas

| Moment | Pas 1 | Pas 2 | Pas 3 | Acció del frontend |
|--------|-------|-------|-------|-------------------|
| Projecte seleccionat, falten visions | `ready` | — | — | Mostra comanda + botó Copiar |
| Eva clica "Copiar" | `done` | `active` | — | `startVisionPolling()`, spinner al pas 2 |
| Polling detecta nous JSONs | `done` | `done` | `ready` | Para polling, destaca botó "Actualitzar prefills" |
| Eva clica "Actualitzar prefills" | `done` | `done` | `active` | Fetch prefills, spinner al pas 3 |
| Fetch completa | `done` | `done` | `done` | Wizard actualitzat, stepper col·lapsa |

### Cas especial: Eva ja coneix el procés

Si Eva no clica "Copiar" però directament va al terminal (coneix la comanda de memòria), el polling NO s'inicia. Però quan Eva clica "Actualitzar prefills", el sistema pot detectar que hi ha nous JSONs i marcar passos 1+2 com a `done` retroactivament.

### Fitxers addicionals a modificar

| Fitxer | Canvi |
|--------|-------|
| `web/api.py` | Nou endpoint `GET /api/vision-status/{project}` |
| `templates/validation/review.html` | Stepper de visió dins instruccions, polling JS, badges |

---

## Riscos i decisions

1. **SSE i FastAPI sync**: `auto_extract()` és síncron. L'endpoint SSE haurà de fer `run_in_executor` o refactoritzar a async. Opció pràctica: SSE endpoint crida cada fase individualment dins d'un `async def` amb `yield` entre fases.

2. **Granularitat dels sub-items**: Massa items sota una icona pot fer soroll visual. Limitar a ~5-6 items per pas, agrupar si cal (ex: "ICGC (3 fonts)" en lloc de tres línies separades).

3. **Amplada del stepper**: Amb sub-items, el stepper ocupa més espai vertical. Limitar `max-height` dels sub-items amb scroll si passa de 5 línies.

4. **Connexió SSE tallada**: Si el navegador perd la connexió SSE a mig pipeline, el frontend hauria de fer fallback al fetch normal (`/api/prefills/{project}`).

## Ordre d'implementació

### Fase A: Stepper 1 — Automàtic (SSE)
1. Refactoritzar `auto_extract()` amb callback (zero risc — callback és opcional)
2. Crear endpoint SSE a `api.py` + funció streaming a `wizard_service.py`
3. Actualitzar HTML: stepper 3 passos + step-files + EventSource
4. Migrar fitxers de l'acordió instruccions al stepper
5. Test manual amb projecte real

### Fase B: Stepper 2 — Visió manual
6. Crear endpoint `GET /api/vision-status/{project}` a `api.py`
7. Reescriure `renderInstructions()`: stepper de visió amb 3 passos
8. Implementar polling JS (`checkVisionFiles()`)
9. Connectar "Copiar" → pas 1 done + inicia polling
10. Connectar "Actualitzar prefills" → pas 3 done (retroactiu si Eva no va copiar)
11. Test manual: simular el flux complet (copiar → terminal → actualitzar)

### Fase C: Polish
12. Animacions de transició entre passos
13. Mida i espaiat dels sub-items sota icones
14. Responsive / mòbil (si Eva usa tablet al camp)
