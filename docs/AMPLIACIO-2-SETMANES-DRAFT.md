# Ampliació de Contracte — G3DT

**Document:** Proposta d'Ampliació (2 setmanes)
**Data:** 23 de març de 2026
**Prestador:** Josep Portell Guarch (Eficients)
**Client:** G3 Desenvolupament Territorial S.L.

---

## 1. Situació actual

El sistema que estem construint va força més enllà del que vam acordar inicialment. A banda del prototip funcional, la interfície web i la integració amb les fórmules Excel — que ja funcionen — el sistema ha crescut per donar resposta als reptes reals que hem anat trobant:

- **Investiga cada projecte a fons.** Entra a la carpeta, obre cada fitxer — sigui Excel, PDF, Word, imatge o fins i tot correus d'Outlook amb adjunts, que també analitza — i n'entén el contingut per trobar les dades que necessita per l'informe.
- **Llegeix els PDFs de camp** (DPSH, sondeig, plànol) amb visió artificial, sense necessitat de transcriure res manualment.
- **Contrasta cada dada amb diverses fonts.** Per exemple, les coordenades UTM es validen creuant GPS de camp, Cadastre i ICGC, i el sistema decideix intel·ligentment quin valor és el més fiable. Ens hem trobat amb noms de carrer escrits de totes les maneres possibles, i el sistema ha après a buscar l'adreça correcta al Cadastre independentment de com estigui escrita a l'origen.
- **Prepara els càlculs.** A partir de les dades trobades, el sistema proposa valors de Terzaghi-Peck, assentaments, K30 i geologia regional, perquè l'Eva els pugui revisar i ajustar amb el seu criteri professional.
- **Quan el sistema troba totes les dades, l'informe surt complet.** El repte és precisament aquest: que les trobi totes, vinguin d'on vinguin i es diguin com es diguin. Les dades que no troba són camps buits que l'Eva ha d'omplir manualment — per això és tan important la millora de detecció que s'explica al punt següent.

Falta la instal·lació a l'ordinador de l'Eva (requereix sessió presencial) i la validació amb projectes nous — que és precisament el que va motivar l'ampliació.

## 2. Què va passar a la reunió del 16 de març

A la demostració amb un projecte nou proporcionat per l'Eva, el sistema no va trobar alguns fitxers perquè tenien noms i estructures de carpeta diferents dels projectes de prova.

Això és esperable: cada projecte ve amb noms de fitxers lleugerament diferents, dades repartides en llocs inesperats (dins correus electrònics, en subcarpetes amb noms canviats, en formats no estàndard), i fins i tot informació rellevant adjuntada dins missatges d'Outlook. El sistema ha de ser capaç de trobar i entendre tot això automàticament, sense que l'Eva hagi d'adaptar res ni seguir cap convenció específica de noms o carpetes. Que el sistema s'adapti al projecte, no al revés.

**Des de la reunió, ja s'ha desenvolupat la solució** — un sistema de detecció en tres nivells:

1. **Nom de fitxer** — Patrons coneguts (DPSH.xls, SONDEIG.pdf, A.01.pdf...)
2. **Empremta del contingut** — Analitza el fitxer per dins per saber què és, independentment del nom
3. **Visió artificial** — Per imatges i documents ambigus, un model de visió els classifica automàticament

Amb aquesta millora, el sistema ha inventariat 375 fitxers de 7 projectes diferents, amb 164 tests automàtics passant correctament. També s'ha afegit la capacitat de recuperar documents adjuntats dins correus electrònics d'Outlook (.msg).

## 3. Abast de l'ampliació (2 setmanes)

L'ampliació cobreix quatre àrees concretes:

### A. Validació amb projectes nous
- Provar el sistema amb els 2 projectes nous que l'Eva va facilitar
- Provar amb qualsevol projecte addicional que arribi durant les dues setmanes
- Objectiu: que funcioni amb el primer intent, sense preparació prèvia

### B. Suport castellà
- Generació d'informes en castellà (a més del català actual)
- L'Eva i la Sílvia van identificar aquesta necessitat a la reunió del 16 de març

### C. Instal·lació i formació
- Instal·lació a l'ordinador de l'Eva (sessió presencial, ~½ dia)
- Formació pràctica: generar un informe de zero amb un projecte real
- Documentació d'ús per l'Eva (ja redactada)

### D. Tancament
- Backup complet del sistema al núvol
- Documentació tècnica final
- Validació conjunta del lliurament

## 4. Condicions econòmiques

| Concepte | Import |
|----------|--------|
| Ampliació (2 setmanes) | 1.200 € |
| IVA (21%) | 252 € |
| **TOTAL** | **1.452 €** |

**Pagament de l'ampliació:** A l'acceptació d'aquesta proposta (abans d'iniciar les dues setmanes).

**Pagament final del contracte original** (1.200 € + IVA): Quan el sistema estigui instal·lat a l'ordinador de l'Eva i funcionant amb projectes reals, tal com es va acordar.

### Resum del projecte complet

| Fita | Import | Estat |
|------|--------|-------|
| 1. Signatura (gener 2026) | 1.200 € + IVA | ✅ Pagat |
| 2. Revisió Fase 1 (febrer 2026) | 1.200 € + IVA | ✅ Aprovat |
| 3. Ampliació (2 setmanes) | 1.200 € + IVA | 📋 **Pagament ara** |
| 4. Lliurament final — sistema instal·lat i operatiu | 1.200 € + IVA | ⏳ Al finalitzar |
| **Total projecte** | **4.800 € + IVA (5.808 €)** | |

## 5. Calendari

| Setmana | Activitat |
|---------|-----------|
| Setmana 1 (31 març – 4 abril) | Validació projectes nous + suport castellà |
| Setmana 2 (7 – 11 abril) | Instal·lació + formació + tancament |

## 6. Si no es fa l'ampliació

El sistema es lliura en l'estat actual:
- Funcional amb els 4 projectes de prova originals + millores de detecció ja implementades
- Es programa una sessió presencial d'instal·lació (½ dia)
- Tot el codi i documentació es lliuren a G3DT
- Opció de contractar manteniment bàsic (200 €/mes) com a xarxa de seguretat

---

**Per confirmar:** Resposta per email o WhatsApp és suficient.

**Josep Portell Guarch**
josep@eficients.cat | 687 838 596

---

*Proposta vàlida durant 15 dies des de la data d'enviament.*
