# Resposta Eva — Preguntes sobre Càlculs

Data: 2026-02-26
En resposta a: `CORREU-EVA-PREGUNTES-CALCULS.md`

---

## Pregunta 1. Qa — Topall o càlcul?

**Resposta Eva:** 3.0 quilos és un topall màxim que solem donar, en roca clara seria 4.0-4.50. Sinó en fonamentació superficial preval Terzaghi-Peck.

## Pregunta 2. E — Com hi arribes?

**Resposta Eva:** Hauria de consultar taules, però la veritat és que l'agafo com a criteri després de molts estudis. Pots agafar la taula, i com que després revisem el document, ja ho ajustarem (ull amb les unitats!).

## Pregunta 3. c i phi — Taula de Crespo Villalaz

**Resposta Eva:** Doncs és complicat tenir dades concretes, és la part potser més important de l'estudi. T'adjunto un document que tinc per a més correlacions.

**Fitxer adjunt:** `Spt-correlacions.doc` (6 pàgines, creat per Eva, 2014)

## Pregunta 4. Nb → N: factor 0.83

**Resposta Eva:** Això és imprescindible fer-ho, per temes de correlacions. Intento explicar: els càlculs de Terzaghi es basen amb el valor de N, i hi ha correlacions directes entre N i Nb (Borrows, que és un assaig com el DPSH, però amb menys energia) per tant el valor que obtenim a camp que és el DPSH, l'hem de transformar amb un valor de Nb que s'obté per les diferències energètiques (pes, alçada…) dividint els valors per 0.83. Per tant, el valor a utilitzar és el Nb.

---

## Implicacions per al codi

### Qa: TOPALL + Terzaghi-Peck
- Sòl granular: Qa ≤ 3.0 kg/cm² (topall)
- Roca clara: Qa ≤ 4.0-4.50 kg/cm²
- Terzaghi-Peck preval en fonamentació superficial

### E: Criteri professional
- Usar taules com a base, Eva ajustarà en revisió
- ATENCIÓ amb les unitats (MPa vs kg/cm²)

### c i phi: Document de correlacions
- Schmertmann (1970) per angle de fricció: factor n depèn del tamany de gra
  - n=2.5 sorres lleugerament llimoses
  - n=2.0 sorres llimoses
  - n=1.25 llims sorrencs
- Hunt per cohesió: C(Cu) = qu/2, taula qu vs NSPT

### Nb: IMPRESCINDIBLE
- **N20 / 0.83 = Nb** → Nb és el valor a usar per a TOTES les correlacions
- Raó: DPSH té més energia que Borrows, cal corregir
- Referència: Dapena, Lacasa & García (2000)
