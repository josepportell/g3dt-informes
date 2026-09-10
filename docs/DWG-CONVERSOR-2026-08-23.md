# Conversor DWG — viabilitat provada i misteri del 564 resolt

**Data:** 2026-08-23 (nit) · **Veredicte: VIABLE.** LibreDWG (`dwg2dxf`) + `ezdxf` llegeixen els 4 DWG de Tulipa
(AC1032/AutoCAD 2018 i AC1027/2013). Eina reutilitzable: `scripts/dwg_text_dump.py`.

## 1. Instal·lació (WSL Ubuntu 24.04 — cap paquet apt disponible)

```bash
# LibreDWG 0.13.3 compilat des del font (~5 min), instal·lat a ~/.local/bin
curl -sO https://ftp.gnu.org/gnu/libredwg/libredwg-0.13.3.tar.xz && tar xf libredwg-0.13.3.tar.xz
cd libredwg-0.13.3 && ./configure --prefix="$HOME/.local" --disable-bindings --disable-shared
make -j"$(nproc)" && make install       # → dwg2dxf, dwgread, dwggrep, dwg2SVG…
# ezdxf al venv del repo (el venv és uv, NO té pip):
uv pip install -p .venv/bin/python ezdxf   # → 1.4.4
```

## 2. Viabilitat sobre els 4 DWG de Tulipa

| Fitxer | Versió | Conversió | Collita de text |
|---|---|---|---|
| `PARAMETRES URBANISTICS.dwg` (VUA, zip) | AC1032 | ✅ 473 KB DXF | **PARCEL·LA 1 = 358,75 / PARCEL·LA 2 = 491,24** (planejament), "sup. ocup. max. 144 m²", amplades/fondàries |
| `…Tulipan 1 TOP.dwg` (topogràfic, zip) | AC1032 | ✅ 1,9 MB | **Caixetí complet**: RC `3445101DF2934E0001WG` + `3445105DF2934E0001GG`, promotor ALEIX SUBIRÀ FELIP, "CARRER TULIPA núm. 1-3", T.M. Cerdanyola, topògraf honorato scp, juliol 2024 |
| `PLANTA PROPOSTA.dwg` (VUA, zip, 23 MB) | AC1032 | ✅ 134 MB DXF (streaming) | "Aleix Subirà i Felip", "PL. SOTERRANI"/"Planta 01/02" (corrobora PSOT+PB+P1), "SUP. CONSTRUÏDA I D'OCUPACIÓ < 353,23 m²" |
| `PLANTA I SECCIO.dwg` (Factoria, casa 2) | AC1027 | ✅ 2,4 MB | Poc text: "Carrer Tosca" + "Camí Antic de Sant Cugat" (corrobora adreça), "SECCIÓ B"; plantes = geometria, no text |

Warnings de dwg2dxf sobre classes "unstable" (blocs dinàmics) = benignes, no afecten el text.

## 3. El misteri del 564 m², resolt

**La hipòtesi del handoff ("PARAMETRES URBANISTICS.dwg hauria de portar els 564 m²") era falsa.**
Cap DWG conté "564". El valor que l'Eva va posar al wizard és la **superfície gràfica del Cadastre**:

```
WFS INSPIRE GetParcel refcat=3445105DF2934E0001GG (C/ Tulipa 3, "suelo sin edificar")
  → <cp:areaValue uom="m2">564</cp:areaValue>          ← el valor de l'Eva
WFS INSPIRE GetParcel refcat=3445101DF2934E0001WG (C/ Tulipa 1, edificada 1958)
  → <cp:areaValue uom="m2">506</cp:areaValue>
```

La cadena completa ara és automatitzable: **TOP.dwg (caixetí, via dwg2dxf) → 2 RC → WFS INSPIRE → 564 m²**.
Les superfícies del planejament del DWG (358,75/491,24, suma ≈ 850 ≠ 506+564 = 1.070) són una divisió proposada
(reparcel·lació), NO la parcel·la cadastral: candidats diferents, no competeixen amb el Cadastre.

Conseqüència per a la lectura d'or: el `no_trobat` de `superficie_parcela` de Tulipa era correcte — el valor NO és
a cap fitxer de la carpeta (el NT* "ERR condicional" es pot rebaixar a NT genuí); la via de recuperació és
derivació Python (Cadastre), com ja fa `auto_extractor`, ara amb la RC llegida del DWG en lloc de geocodificar.

## 4. Repartiment lectura vs derivació (coherent amb el skill)

- **Lectura (skill/`dwg_text_dump.py`)**: RC del caixetí del topogràfic → `referencia_catastral` (candidats,
  2 parcel·les); promotor/arquitecte/adreça del caixetí; superfícies del planejament (etiquetades com a tals).
- **Derivació (Python, fora del skill)**: RC → WFS INSPIRE `areaValue` → `superficie_parcela` estil Eva.

## 5. Limitacions conegudes

- Camps AutoCAD (`FIELD`) surten com a `######`/`%<\_FldIdx…>%` — el valor cachejat no es recupera (afecta
  "SUPERFICIES CONSTRUÏDES" del PLANTA PROPOSTA).
- **Restes de plantilla**: el TOP porta un bloc `full` amb el caixetí d'UN ALTRE projecte (Òrrius 2023, un
  altre promotor) — exactament el cas que el Pas 0 del skill neutralitza (context abans de valor).
- Binaris a `~/.local/bin` (aquest WSL): a l'ordinador de l'Eva caldria el build Windows de LibreDWG o fer
  la conversió al servidor — decisió de desplegament pendent.
- DXF de 23 MB → 134 MB: llegir amb streaming (el script usa fitxer temporal i el neteja).
