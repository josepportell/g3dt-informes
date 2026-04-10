# Anàlisi d'hipòtesis Qa — Bateria de tests

**Data:** 2026-04-10
**Script:** `scripts/qa_hypothesis_tester.py`

---

## Matriu de resultats

| Projecte | Eva Qa | H1 T-P Nb | H2 cap3 | H3 T-P N20 | H5 Full | H7 cap dir | Millor fit |
|---|---|---|---|---|---|---|---|
| **Castellar** (roca) | 3.0 | 3.56 | **3.0** | **2.96** | 5.0 | 3.0 | H2/H3/H7 |
| **Rubí** (graves) | **3.5** | 5.09 | 3.0 | 4.22 | 3.0 | 3.0 | Cap! (**3.5 > cap**) |
| **Linyola** (graves) | 3.0 | 2.54 | 2.54 | 2.11 | **3.0** | **3.0** | H5/H7 |
| **Bell-Lloc** (carb.) | 3.0 | 5.09 | **3.0** | 4.22 | **3.0** | **3.0** | H2/H5/H7 |
| **Alcoletge** (carb.) | **3.5** | 3.81 | 3.0 | 3.17 | 3.0 | 3.0 | H1 (CLOSE) |
| **Vilanova** (llims) | 2.5 | 1.91 | 1.91 | 1.58 | 1.96 | 3.0 | Cap! |
| **Anciles** (argila) | 2.0 | 1.53 | 1.53 | 1.27 | 1.43 | 3.0 | Cap! |

---

## Patrons observats

### Grup A: Projectes amb Qa = 3.0 (cap del sòl)
**Castellar, Linyola, Bell-Lloc** → Eva Qa = 3.0 en tots tres.

Cap hipòtesi sola funciona perfectament per tots tres:
- T-P Nb/12 sobreestima Castellar (3.56) i Bell-Lloc (5.09), subestima Linyola (2.54)
- Full Terzaghi dóna exactament 3.0 per Linyola i Bell-Lloc (perquè el cap els talla)
- El cap directe (3.0) coincideix trivalment

**Interpretació:** Eva probablement calcula Terzaghi-Peck, i si > 3.0 → aplica cap 3.0.
Per Linyola (T-P = 2.54 < 3.0), Eva posa 3.0 igualment → **Eva arrodoneix cap amunt al cap?**
O bé Eva usa el Full Terzaghi (que dóna 3.0 per Linyola).

### Grup B: Projectes amb Qa > 3.0 (per sobre del cap estàndard)
**Rubí (3.5), Alcoletge (3.5)** → Eva Qa > 3.0!

Això contradiu el cap de 3.0 per sòls. Cap hipòtesi amb cap=3.0 funciona.
- Rubí: graves molt denses (N20=40). Eva posa 3.5 → cap augmentat per densitat?
- Alcoletge: graves carbonatades (N20=30). Eva posa 3.5 → carbonatades = quasi-roca?

**Hipòtesi nova H12:** Eva usa un cap variable:
- Sòls normals: 3.0
- Graves molt denses o carbonatades: 3.5
- Roca: 4.0-4.5

Rubí amb N20=40 → Nb=48 → T-P=5.09 >> 3.0 → cap a 3.5 perquè és molt dens.
Alcoletge amb N20=30 → Nb=36 → T-P=3.81 → cap a 3.5 per carbonatades.

### Grup C: Projectes amb Qa < 3.0 (sòls febles)
**Vilanova (2.5), Anciles (2.0)** → Qa per sota de qualsevol hipòtesi.

Cap fórmula arriba a 2.5 o 2.0 amb els paràmetres que tenim:
- Vilanova: millor fit és 1.96 (Full Terzaghi) → Eva diu 2.5 (+27%)
- Anciles: millor fit és 1.53 (T-P Nb) → Eva diu 2.0 (+31%)

**Hipòtesi nova H13:** Eva arrodoneix cap amunt en sòls febles:
- Si Terzaghi dóna < 2.0 → Eva posa 2.0 (mínim per fonamentació superficial)
- Si dóna entre 2.0 i 3.0 → Eva arrodoneix al 0.5 superior

O bé els paràmetres d'entrada (phi, c, gamma) que hem assumit NO són els d'Eva.

---

## Conclusions de la primera bateria

### Confirmat
1. **Eva aplica un cap** — però NO és fix a 3.0. És variable per tipus de sòl.
2. **Terzaghi-Peck (Nb/12) és la base** — però el cap domina el resultat final.
3. **El cap és la decisió principal** — no la fórmula.

### Necessita verificació
4. **Grup C (Vilanova, Anciles):** Els paràmetres d'entrada poden ser incorrectes.
   Si phi fos 32° en comptes de 28° per Vilanova, el Full Terzaghi donaria ~2.5.
   Cal verificar quins phi/c/gamma usa Eva per cada projecte (estan als PDFs signats).
5. **Grup B (Rubí, Alcoletge):** El cap 3.5 és per densitat, per carbonatació, o per una altra raó?

### Pròxims passos
1. **Extreure phi/c/gamma dels PDFs signats** d'Eva per cada projecte
2. **Testejar H12 (cap variable)** amb els paràmetres reals
3. **Testejar H13 (arrodoniment)** amb els paràmetres reals
