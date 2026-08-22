# Verificació end-to-end dels fixes F1-F4 (2026-08-22)

**Branca:** `review/prod-audit-2026-08` · commits `89f34b5` (F1) … `6a6f780` (F4e) · pla: `docs/PLA-FIXES-PROD-2026-08.md`
**Entorn:** WSL, servidor `python -m web` amb el flux de producció (mode xarxa: sync → workspace local → copy-back),
workspace i `G3DT_CACHE_DIR` **nous a cada execució** (primera obertura freda, com l'Eva amb un projecte nou).
Projectes: Tulipa (real, còpia a `/mnt/c/claude/g3dt/projectes-debug/`), Rubí i Bell-lloc (còpies a
`/mnt/c/claude/g3dt/projectes/`). `reference-material/` només s'ha llegit.

⚠ **Anthropic:** la clau `ANTHROPIC_API_KEY` del `.env` d'aquest worktree retorna HTTP 400 *"credit balance is too
low"* (no és un bug: és el meu compte). A partir de l'execució 2 la via "anthropic" s'ha exercit amb
`G3DT_LLM_PROVIDER=openrouter` → **mateix model `claude-sonnet-4-6` via OpenRouter** (SDK Anthropic amb `base_url`;
`stop_reason` i `usage` arriben igual). L'Eva usa la clau directa (els seus logs mostren 200 OK d'Anthropic).

## 1. Taula resum

| Projecte / execució | Codi | Abans (logs Eva) | Prefills | Visió DPSH (prov./OK) | Informe | Camps vs Eva |
|---|---|---|--:|---|---|---|
| Tulipa run 1 | F1-F4 | 7,7 / 8,7 min, 0/3 OK | **708 s** (11,8 min) | anthropic FAIL (crèdit) → openai OK 34 s | ✅ 2,5 s | — |
| Tulipa run 2 | F1-F4b | | **504 s** (8,4 min) | **anthropic OK 78 s** (6.651 tok out) | ✅ | — |
| Tulipa run 3 | F1-F4c | | **273 s** (4,6 min) | **anthropic OK 77 s** | ✅ 1,7 s | 10 MATCH / 13 DIFF / 19 sense clau (1) |
| Rubí | F1-F4c (2) | — | **266 s** (4,4 min) | **anthropic OK 50 s** (4.159 tok out) | ✅ 16,6 s | 13 / 25 / 17 (3) |
| Bell-lloc run 1 | F1-F4c | — | **322 s** (5,4 min) | **anthropic OK 24 s** | ✅ 17 s | 20 / 23 / 17 |
| Bell-lloc run 2 | F1-F4e, `.env` antic | | **282 s** (4,7 min) (4) | **anthropic OK 31 s** | ✅ 12 s | |

(1) Referència extreta del `3001706_TULIPA_INFORME_FIX.docx` real amb `reference_extractor` (42 variables). "Sense
clau" = la variable d'Eva no té prefill amb el mateix nom (p. ex. `client` vs `client_name`, `plantes` vs `num_floors`) —
no és una fallada del pipeline, és el mapatge de noms del comparador ad hoc.
(2) Amb `GROQ_MODEL=qwen/qwen3.6-27b` a l'entorn (abans de F4d) per exercir `groq_miner` amb un model viu.
(3) Rubí: `street_address` = *"Calle Juan Coloma Fajardo 41A"* (font `vision_probe` d'una foto WhatsApp d'ACCEPTACIO) i
`municipality` = *"Sant Quirze del Vallès"* (font `vision_probe` de `F1 UBI.png`) → la síntesi LLM escriu la narrativa
**en castellà**. És un problema de prioritat de fonts (vision_probe > plànol/pressupost), **preexistent i fora d'abast**.
(4) Executat alhora que la suite de tests (contenció de CPU: ConceptScout 23 → 64 s). Valor pessimista.

**Criteris del pla (§4):**
- **Prefills < 3 min en els tres: ❌ NO assolit** — 273 / 266 / 282 s. Vegeu §3: el que queda és latència seqüencial dels
  models, no reintents ni errors.
- **DPSH via Anthropic OK en ≥ 2/3: ✅** — 3/3 (Tulipa run 2-3, Rubí, Bell-lloc ×2), `stop_reason=end_turn`, JSON parsejat
  al primer intent. Tulipa i Rubí han necessitat **6.651 i 4.159 tokens de sortida** → amb el límit antic de 4.096 (F3)
  s'haurien truncat totes dues.
- **0 tracebacks: ✅** en les 6 execucions.

Comptadors (execucions finals): `rate limited` 0 · `truncated at max_tokens` 0 · `Too many images` 0 · `HTTP 404` 0 ·
Groq `HTTP 400` 0 (run 1: 31) · `VISION FAIL` 0.

## 2. Què ha aparegut durant V que el pla no preveia (i s'ha fixat: F4b-F4e)

L'execució 1 de Tulipa (708 s) ha destapat que **el canvi de model de Groq del 23 jul (`qwen/qwen3.6-27b`) — "no
verificat" a l'auditoria — empitjorava el temps**:

| Símptoma (run 1) | Causa | Fix |
|---|---|---|
| 31 × HTTP 400 `json_validate_failed`, cada un reintentat 3 × ~10 s (456 s a ConceptScout) | qwen3.6 és un model de **raonament**: gasta 1.600-4.000 tokens "pensant" dins del `max_tokens` i mai tanca el JSON | `reasoning_effort="none"` (experiment directe: 250 tok, 1,5 s, JSON OK) · 4xx sense reintent (F4b) |
| `Too many images… supports up to 3` | el 5 era de llama-4-scout | `GROQ_MAX_IMAGES=3` (F4b) |
| SmartScan Tier 3: 18 fotos × (Groq 400 + Claude 7 s) = 163 s | mateix raonament, `max_tokens=256`, camí de crida propi | helper als 9 camins (F4c/F4e) |
| `groq_miner` HTTP 404 × 3 per fitxer | `GROQ_TEXT_MODEL=qwen/qwen3-32b` **retirat** (al `.env`, gitignored — també al de l'Eva) | mapa `RETIRED_GROQ_MODELS` → successor viu (F4d) |
| `ortho_vision` 105 s de 400s a Bell-lloc | mateix raonament, 4t camí | F4e |

Inventari: **9 fitxers** copien la mateixa crida httpx a `api.groq.com`; un test estàtic ara exigeix
`config.groq_payload_extras()` a tots (`test_every_groq_call_site_uses_payload_extras`).

## 3. On van els 273 s de Tulipa (run 3) — tot seqüencial

| Fase | s | Crides | Nota |
|---|--:|--:|---|
| Sync xarxa → workspace (78 MB, 112 fitxers) | 4 | — | abans dels prefills |
| SmartScan + Tier 3 (18 fotos, Groq) | 27 | 18 | era 163 s |
| FileMiner + groq_miner | 5 | 11 | era 43 s (404s) |
| ConceptScout vision probes (23 fitxers, en sèrie) | 52 | 22 | ~2,2 s/fitxer; era 456 s |
| deep_folder_classifier (OpenAI) | 15 | 5 | |
| **Visió per tipus (5 tipus, en sèrie)** | **145** | 5 | DPSH 77 (Claude, 6,6k tok out) · sondeig 20 · annex 32 · plànol 6 · projecte 4 |
| Geocode / Cadastre / ICGC | ~5 | | |
| LLM synthesis | 20 | | |

El que queda no són reintents ni errors: és **latència de generació dels models, en sèrie**. Els 5 tipus de visió són
independents entre si (→ paral·lel: 145 → ~80 s) i les 23 probes també (→ ~10 s). Amb això Tulipa quedaria ≈ 2 min.
És el "reordenar fases / mostrar prefills bàsics abans de la visió" de l'AUDIT §3.2 — **fora d'abast, decisió del Josep**.

## 4. Evidència

Logs i perfils (scratchpad de sessió, no versionats): `tulipa-run{,2,3}.log`, `old-run.log` (Rubí + Bell-lloc),
`bell-run2.log`, perfils amb `scripts/profile_eva_logs.py`. Còpia de seguretat dels caches esborrats de la còpia de
Tulipa: `tulipa-backup/`. Informes generats: `3001706_generated.docx` (11,8 MB), `3001631_generated.docx`,
`4001612_generated.docx` a les carpetes de còpia (copy-back del flux de xarxa).
