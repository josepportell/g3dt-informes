# Pla d'Accions per al Delivery — G3DT
Data: 2026-03-30

## Objectiu

Lliurar un sistema funcional a l'ordinador de l'Eva que generi informes geotècnics per a **qualsevol projecte nou**, no només els 7 de test. Resoldre la preocupació de la Sílvia (23/3): "quan eren informes nous, no es generaven".

---

## 1. MERGE feat/smartscan → main

**Estat:** 40 commits pendents, branca estable
**Risc:** Baix — main no ha tingut commits paral·lels
**Acció:** Merge ara, abans de res

```bash
git checkout main
git merge feat/smartscan
git push
```

**Bloqueja:** Tot el que segueix. Sense merge, la instal·lació a Eva seria amb codi antic.

---

## 2. UX Expert Overrides — Redisseny

**Problema actual:**
- Amagats al final, col·lapsats per defecte ("opcional") → Eva no els veu
- Són els paràmetres MÉS importants: gamma, c, phi, E, Es — tot el càlcul de Qa, K30 i assentament en depèn
- Editar un camp (ex: phi) NO actualitza dinàmicament els resultats afectats (Qa, K30, settlement)
- Eva no veu l'efecte de les seves decisions fins que genera l'informe

**Solució proposada:**

### 2a. Pujar els overrides al cos principal del wizard
- Treure del grup col·lapsable → secció visible "Paràmetres Geomecànics"
- Posició: després de "Dades del Projecte" i "Adjacents", abans de "Coordenades"
- Títol: "Paràmetres Geomecànics" (no "overrides", no "opcional")

### 2b. Recàlcul dinàmic en viu
- Quan Eva canvia gamma, c, phi, E o Es → recalcular Qa, K30, assentament al moment
- Mostrar resultats calculats INLINE sota els camps, amb highlighting:
  - Fons groc momentani (flash) quan un valor canvia per indicar "això s'ha actualitzat"
  - Color diferent per valors que depenen del camp editat
- Terzaghi Qa, K30 i Schmertmann es poden calcular en JS al client (fórmules senzilles)

### 2c. Mostrar la cadena de dependències
```
phi → Nq, Nc, Ny → Qa(Terzaghi) → Qa_final(min(Terzaghi, cap))
E → K30 (= E/75 o E/60)
Es → assentament Schmertmann
c → Qa(Terzaghi) + determina cap (rock vs soil)
gamma → Qa(Terzaghi)
```
- Visual: petites fletxes o indicador de "→ afecta Qa, K30" al costat de cada camp

### 2d. Rang de referència d'Eva
- Ja tenim `calc-notes` (implementat 29/3) amb rangs típics
- Millorar: si el valor està FORA del rang d'Eva, borde taronja d'avís (no error, avís)

**Esforç:** ~4-6h

---

## 3. SmartScan — Projectes nous funcionals

**Problema:** El sistema falla amb noms de fitxer inesperats (el que va passar a la demo)
**Estat:** Tier 1 (filename) + Tier 2 (fingerprint) + Tier 3 (vision) implementats, però:

### 3a. Gaps pendents
- **Imatges .jpg/.png com a documents** (PENETROS.jpeg a Alcoletge) → SmartScan les classifica però el pipeline de vision no les processa encara
- **Emails .msg** → MsgMiner implementat, adjunts s'extreuen, però no re-entren al pipeline
- **DPSH Excel amb noms variant** → SmartScan Tier 1 ja cobreix la majoria, verificar amb nous projectes reals
- **Carpetes amb noms espanyols** (ANEXOS vs ANNEXES, ACEPTACION vs ACCEPTACIO) → SmartScan ho gestiona

### 3b. Test amb projecte real desconegut
- Demanar a l'Eva 1-2 carpetes de projectes que NO siguin els 7 de test
- Executar el pipeline complet → verificar que:
  1. FileScanner troba tots els fitxers rellevants
  2. SmartScan els classifica correctament
  3. El wizard es pobla amb dades raonables
  4. L'informe es genera sense errors

**Esforç:** ~3-4h (implementació) + 1h (test amb projecte nou)

---

## 4. Instal·lació a l'ordinador d'Eva

**Prerequisits:**
- [ ] Python 3.11+ instal·lat
- [ ] `uv` instal·lat (`pip install uv`)
- [ ] Git instal·lat
- [ ] Claude Code instal·lat (API key configurada)
- [ ] Accés a les carpetes de projectes d'Eva

**Procediment:**
```bash
git clone https://github.com/josepportell/g3dt-informes.git
cd g3dt-informes
uv sync
# Configurar path a les carpetes de projectes d'Eva
# Iniciar: .venv/bin/python -m web
# Obrir: http://localhost:8765/review.html
```

**Actualitzacions futures:** `git pull && uv sync` (30 segons)

**Esforç:** ~1-2h (amb possibles imprevistos de Windows/permisos)

---

## 5. Extracció d'imatges → Vision pipeline

**112 fitxers amb dades potencials no processats** (inventari complet a `docs/smartscan/01-INVENTARI-FITXERS.md`)

### 5a. Crítics (bloquegen completesa)
- PENETROS.jpeg (Alcoletge) → N20 de camp
- Plans d'arquitecte en carpetes numèriques (A01_TIPOL.pdf a Anciles, planol-*.pdf a Alcoletge)

### 5b. Report figures & photos
- 105 imatges entre fotos de camp i mapes geològics
- Photo picker ja implementat (11 slots) — cal que SmartScan classifiqui les imatges amb rols de report
- Patrons de nom ja definits al pla (`F1 SIT`, `M1-M12`, `P1.jpg`, `maquina_dpsh`)

### 5c. Emails .msg
- 20 fitxers amb adreces, contactes, plans adjunts
- MsgMiner bàsic ja implementat, cal integrar adjunts al pipeline

**Esforç:** ~6-8h (Phases 2-4 del pla "Read First, Decide After")

---

## 6. Preguntes pendents a Eva

Sense aquestes respostes, el benchmark no pot millorar més enllà del ~53% actual:

1. **N20:** Quin criteri exacte per fer la mitjana? (excloure refús, ponderar poc profunds?)
2. **Qa cap:** Per què Rubí té 3.50 si el cap és 3.0? Hi ha criteris per pujar el cap?
3. **E per carbonatades:** Bell-Lloc E=650 vs CTE que donaria ~450. Sempre es puja per carbonatades?

**Acció:** Preguntar directament quan es faci la instal·lació

---

## Ordre d'execució recomanat

| # | Acció | Prerequisit | Esforç | Impacte |
|---|-------|-------------|--------|---------|
| 1 | Merge feat/smartscan → main | — | 5 min | Desbloqueja tot |
| 2 | UX Expert Overrides | Merge | ~4-6h | Eva veu i controla els càlculs |
| 3 | Test amb projecte nou | Merge | ~4-5h | Valida que funciona per Sílvia |
| 4 | Instal·lació a Eva | Merge + test | ~1-2h | Sistema en producció |
| 5 | Extracció imatges/emails | Post-instal·lació | ~6-8h | +112 fitxers processats |
| 6 | Preguntes a Eva | Instal·lació (aprofitar visita) | 30 min | Desbloqueja benchmark >53% |

**Camí crític:** 1 → 3 → 4 (amb 2 en paral·lel si hi ha temps)

---

## Criteris d'acceptació per la Sílvia

La Sílvia considerarà el sistema "acabat" quan:
1. Eva selecciona un projecte NOU (no de test) → el wizard es pobla sense camps buits
2. Eva revisa/ajusta (~30s) → genera informe .docx descarregable
3. L'informe és prou complet per servir de base (Eva farà retocs finals a Word)
4. El procés és repetible amb qualsevol projecte, no només els 7 coneguts
