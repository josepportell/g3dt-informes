# FileMiner v1.0 — Insights i Limitacions

Data: 2026-03-21
Context: Primer desplegament de FileMiner (Phase 0.3), miners Python purs (regex + cel·les adjacents).

## Resultats reals (Anciles, 23 fitxers minats)

- 121 senyals totals, però **78 són imatges sense mapejar** (soroll)
- **43 senyals amb dades reals** → 11 variables resoltes de ~47 necessàries
- 0 errors, 3.6s

## Què funciona bé

### DADES PER ANAR A CAMP Excel (11 senyals, 9 mapejats)
- Format net: etiqueta a columna B, valor a columna C
- Consistent entre projectes (mateixa plantilla)
- Extreu: client_name, street_address, contact_name, access_url, client_phone
- El split de telèfon incrustat funciona ("MARIA ALBA BARRAU CASTÁN 616523792" → nom + telèfon)

### COORDENADES.txt (quan existeix)
- Regex UTM funciona perfectament (Bell-Lloc, Rubí)
- Format estable: punt ID + X ; Y ; Z

### Competició de senyals
- municipality="ANCILES" guanya correctament (filtre G3 office funciona)
- client_nif="18037382T" guanya (filtre G3 CIF funciona)
- Prioritat per font funciona: DADES Excel (35) > PDF genèric (45)

## Què NO funciona

### 1. PDFs amb text fluït (pressupost, informe)
**Problema**: El text del PDF no segueix patrons `ETIQUETA: VALOR` ni `ETIQUETA\tVALOR`. Les dades estan en paràgrafs, taules renderitzades, o layouts complexos.

**Exemple**: El pressupost PDF conté l'arquitecte, superfícies, nombre de plantes... però el text extret amb PyMuPDF és un flux continu sense separadors nets.

**Impacte**: architect_name, architect_company, superficie_*, num_floors queden buits.

**Per què regex no ho resol**: El text pot ser "Arquitecto: D. Juan Pérez\nEstudio: XYZ Arquitectos" però també "El presente estudio ha sido encargado por el arquitecto D. Juan Pérez del estudio XYZ". El LLM entén ambdós; el regex només el primer.

### 2. Coexistència de dades G3 i dades client al mateix fitxer
**Problema**: La comanda laboratori té les dades de G3 (sol·licitant) i les del projecte (obra) al mateix Excel, amb les mateixes etiquetes ("ADREÇA", "POBLACIÓ").

**Exemple real**:
```
Row 13: G="ADREÇA ", N="C/ Vallbona, 22"       ← G3 office
Row 20: G="ADREÇA "                              ← project (buit!)
Row 14: G="POBLACIÓ ", N="ELS OMELLS DE NA GAIA" ← G3 office
Row 21: G="POBLACIÓ ", N="ANCILES"               ← project
```

**Impacte**: street_address capta "C/ Vallbona, 22" (G3) en comptes de l'adreça del projecte. Hem afegit filtres per NIF i municipi G3, però l'adreça encara pot filtrar-se malament.

**Per què regex no ho resol**: Cal entendre el CONTEXT ("DADES DEL SOL·LICITANT" vs "DADES DE L'OBRA") per saber quina secció és G3 i quina és el projecte. El Python miner veu cel·les aïllades.

### 3. Etiquetes que no estan al diccionari
**Problema**: El diccionari LABEL_TO_VARIABLE té 67 entrades, però cada projecte pot tenir variants noves.

**Exemple**: "QUI HA QUEDAT?" → no mapejat. "PREVISIÓ DE TREBALL DE CAMP" → no mapejat (podria mapejar a building_type o field_work_type).

**Impacte**: Informació potencialment útil es descarta silenciosament.

**Per què afegir-ne més no escala**: Cada nou projecte pot tenir noves variants. El diccionari creixeria indefinidament sense garantia de cobertura.

### 4. Valors adjacents incorrectes
**Problema**: El miner agafa "el proper valor no buit a la dreta o a sota". Quan una etiqueta no té valor al costat, agafa l'etiqueta de la fila següent.

**Exemple real**: `street_address` = "POBLACIÓ" (va agafar l'etiqueta de la fila de sota com a valor).

**Impacte**: Falsos positius amb alta confiança (0.90) que contaminen la competició.

**Per què regex no ho resol**: Cal entendre l'estructura visual del formulari (cel·les buides = "no respost"), no només la adjacència mecànica.

### 5. Emails i telèfons de G3 guanyen com a "client"
**Problema**: g3@g3dt.com, eva@g3dt.com, 974551273 (G3 office) apareixen a pressupostos i informes. El miner els detecta com a "client_email" i "client_phone".

**Impacte**: El wizard mostra l'email de G3 com a email del client.

**Solució parcial aplicable**: Afegir g3@g3dt.com, eva@g3dt.com, 974551273 a una llista d'exclusió interna (com ja fem amb el NIF). Fàcil d'implementar.

### 6. Imatges extretes sense classificar (78 de 121 senyals)
**Problema**: S'extreuen imatges de PDFs i Excel però queden amb `maps_to=None`. Sense visió AI, no sabem si són plànols, fotos de camp, logos, o decoració.

**Impacte**: Infla el comptador de senyals sense aportar dades útils. El cap de 10 imatges/PDF ajuda però no resol el problema de fons.

**Quan es resoldrà**: Phase 1 (Claude vision) o Phase G (Groq vision) podrien classificar-les.

## On un LLM (Phase G) marcaria la diferència

| Limitació | Regex | LLM |
|-----------|-------|-----|
| PDF text fluït → label-value | No pot | Entén context i estructura |
| Distingir dades G3 vs client | No pot (mateixa etiqueta) | Entén seccions ("sol·licitant" vs "obra") |
| Etiquetes noves/variants | Cal afegir manualment | Infereix el significat |
| Cel·la buida vs valor | No pot | Entén que "buit" = "no respost" |
| Classificar imatges | No pot | Visió multimodal |

## Millores ràpides (sense LLM)

1. **Llista exclusió G3**: afegir emails (g3@g3dt.com, eva@g3dt.com) i telèfons (974551273) → elimina falsos positius immediats
2. **Validar valors adjacents**: si el valor candidat és una etiqueta coneguda del diccionari, descartar-lo (no és un valor real)
3. **Secció-aware per comanda lab**: detectar "DADES DEL SOL·LICITANT" i "DADES DE L'OBRA" per assignar prioritats diferents a cada secció
4. **Més entrades al diccionari**: afegir les variants trobades als 7 projectes reals

## Criteris per avaluar Phase G (Groq LLM)

Quan implementem Phase G, verificar que resol:
- [ ] Extreu architect_name del pressupost PDF (text fluït)
- [ ] Distingeix adreça G3 vs adreça projecte a la comanda lab
- [ ] Mapeja etiquetes noves sense diccionari previ
- [ ] No genera falsos positius amb valors adjacents incorrectes
- [ ] Temps acceptable (<3s per fitxer amb Groq)
- [ ] Cost acceptable (free tier Groq cobreix 10-20 projectes/mes)
