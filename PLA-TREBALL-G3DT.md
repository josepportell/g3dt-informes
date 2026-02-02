# Pla de Treball G3DT
## Automatització d'Informes Geotècnics

**Data:** Gener 2026
**Durada:** 12 setmanes (6 pilot + 6 implementació)

---

## Àrees de Treball

### 1. UI Fàcil d'Usar
**Prioritat:** ALTA | **Risc:** ALT

**Objectiu:** Interfície que personal no-tècnic pugui utilitzar sense formació extensa.

**Tasques:**
- [ ] Avaluar opcions: wrapper visual vs. instruccions guiades vs. formulari web
- [ ] Dissenyar flux d'usuari mínim (input → processament → output)
- [ ] Crear guia visual pas a pas
- [ ] Testejar amb usuaris reals (observar reaccions a diàlegs de permisos)
- [ ] Iterar segons feedback

**Risc:** La UI de Claude Code (terminal, permisos, errors) pot ser intimidant.
**Mitigació:** Sessions inicials amb acompanyament intensiu. Documentació visual clara.

---

### 2. Motor d'Automatització (Python/DeepAgents)
**Prioritat:** ALTA | **Risc:** MITJÀ

**Objectiu:** Sistema robust que orquestri tot el procés de generació d'informes.

**Tasques:**
- [ ] Decidir arquitectura: scripts Python vs. DeepAgents vs. híbrid
- [ ] Desenvolupar flux principal: entrada dades → processament → sortida informe
- [ ] Implementar gestió d'errors i casos especials
- [ ] Crear logs per traçabilitat
- [ ] Documentar el sistema

**Consideracions:**
- DeepAgents: més flexible, però més complex
- Python pur: més previsible, però menys adaptable
- Recomanació: Python per càlculs/formatació + Claude per redacció/interpretació

---

### 3. Integració Fórmules Excel
**Prioritat:** CRÍTICA | **Risc:** CRÍTIC

**Objectiu:** Utilitzar exactament les mateixes fórmules que G3DT ja té validades.

**Tasques:**
- [ ] Inventariar tots els Excels amb fórmules (quants? quins càlculs?)
- [ ] Documentar cada fórmula: inputs, outputs, unitats
- [ ] Decidir estratègia: cridar Excel directament vs. replicar en Python
- [ ] Implementar amb verificació creuada
- [ ] Validar resultats amb casos reals (mínim 5 informes anteriors)

**REGLA D'OR:** Mai recalcular valors geotècnics. Usar Excel com a font de veritat.
**Risc:** Errors de càlcul = informes invàlids = responsabilitat professional.
**Mitigació:** Verificació humana obligatòria de tots els valors numèrics.

---

### 4. RAG + Corpus Tècnic (Terminologia Geotècnica)
**Prioritat:** ALTA | **Risc:** MITJÀ-ALT

**Objectiu:** Sistema que aprengui el vocabulari tècnic català específic de G3DT.

**Fase 1 - Setmanes 1-2:**
- [ ] Obtenir accés als ~2000 informes anteriors
- [ ] Extreure text de tots els informes (PDF → text)
- [ ] Construir glossari de termes tècnics (automàtic + revisió manual)
- [ ] Identificar patrons recurrents i estructures
- [ ] Crear base de dades vectorial (embeddings)

**Fase 2 - Setmanes 3+:**
- [ ] Implementar RAG per recuperar terminologia consistent
- [ ] Template matching amb informes similars anteriors
- [ ] Sistema de revisió humana per termes nous/desconeguts

**Avantatge competitiu:** Cap eina genèrica d'IA té aquest corpus especialitzat.

---

### 5. Sistema de Carpetes amb ID de Projecte
**Prioritat:** ALTA | **Risc:** MITJÀ

**Objectiu:** Integració perfecta amb l'estructura de carpetes existent de G3DT.

**Tasques:**
- [ ] Documentar estructura actual de carpetes (on guarden què?)
- [ ] Entendre sistema de codis de projecte (format, significat)
- [ ] Implementar detecció automàtica de carpeta de projecte
- [ ] Crear/respectar estructura de subcarpetes
- [ ] Gestionar arxius temporals vs. finals

**Preguntes a respondre:**
- Quin és el format dels IDs? (ex: 2024-001, G3DT-0123, etc.)
- On es guarden els inputs (dades de camp, Excel)?
- On s'han de guardar els outputs (esborranys, finals)?
- Hi ha servidor compartit o local?

---

### 6. Integració d'Imatges
**Prioritat:** MITJANA | **Risc:** MITJÀ

**Objectiu:** Incloure automàticament mapes, fotografies, gràfics als informes.

**Tasques:**
- [ ] Inventariar tipus d'imatges usades (mapes geològics, fotos camp, gràfics, plànols)
- [ ] Definir on es troben (carpeta? noms estàndard?)
- [ ] Implementar inserció automàtica amb llegendes
- [ ] Gestionar redimensionat i posicionament
- [ ] Verificar qualitat en PDF final

**Tipus d'imatges esperats:**
- Mapes de situació
- Mapes geològics/geotècnics
- Fotografies de camp (sondejos, cales)
- Gràfics de resultats (SPT, columnes litològiques)
- Plànols de planta

---

### 7. Integració de Taules
**Prioritat:** ALTA | **Risc:** MITJÀ

**Objectiu:** Generar taules de dades amb format professional i valors precisos.

**Tasques:**
- [ ] Inventariar tipus de taules (resultats assaigs, paràmetres, recomanacions)
- [ ] Definir fonts de dades per cada taula (Excel? entrada manual?)
- [ ] Implementar generació automàtica amb format consistent
- [ ] Assegurar precisió numèrica (decimals, unitats)
- [ ] Verificar renderització correcta en PDF

**Taules típiques:**
- Resum de sondejos/cales
- Resultats assaigs in situ (SPT, etc.)
- Resultats assaigs laboratori
- Paràmetres geotècnics recomanats
- Taula de normativa aplicable

---

### 8. Cerca de Fonts i Referències
**Prioritat:** MITJANA | **Risc:** MITJÀ

**Objectiu:** Replicar el procés actual de cerca d'informació normativa i geològica.

**Tasques:**
- [ ] Documentar fonts actuals (ICGC, normativa, bases de dades)
- [ ] Implementar accés automatitzat a fonts públiques
- [ ] Crear sistema de citació amb traçabilitat
- [ ] Gestionar fonts locals (PDFs, documents interns)
- [ ] Verificar actualització de normativa

**Fonts típiques:**
- ICGC (Institut Cartogràfic i Geològic de Catalunya)
- Mapes geològics 1:50.000
- CTE (Código Técnico de la Edificación)
- Eurocodi 7
- Normativa autonòmica

---

## Riscos Principals

| Risc | Severitat | Mitigació |
|------|-----------|-----------|
| **UI massa tècnica** | ALT | Wrapper visual, guia pas a pas, acompanyament inicial intensiu |
| **Errors de càlcul** | CRÍTIC | Excel com a font de veritat, mai recalcular, verificació humana obligatòria |
| **Català tècnic incorrecte** | MITJÀ-ALT | RAG amb corpus de 2000+ informes, glossari validat, revisió humana |
| **Expectatives desajustades** | ALT | Definir "automatització assistida" des del dia 1, no "màgia" |
| **Integració carpetes** | MITJÀ | 2 primeres setmanes = observació profunda del procés actual |
| **Dependència de fonts externes** | MITJÀ | Cache local de fonts estables, fallback manual |

**Risc més gran:** Esperen que el sistema funcioni sol; lliurem una eina que requereix supervisió.
**Mitigació:** Comunicació clara setmana 1. Demostració pràctica de limitacions.

---

## Àrees Addicionals a Considerar

### 9. Format de Sortida
- [ ] Definir format final: Word editable? PDF directe? Ambdós?
- [ ] Plantilla base amb estil G3DT (logo, capçalera, peu de pàgina)
- [ ] Numeració de pàgines, índex automàtic

### 10. Tipus d'Informes
- [ ] Inventariar tots els tipus d'informe que fan
- [ ] Prioritzar: quin tipus automatitzar primer?
- [ ] Documentar diferències entre tipus

**Tipus possibles:**
- Informe geotècnic complet
- Informe preliminar
- Estudi geològic
- Informe de reconeixement
- Annex de càlculs

### 11. Normativa i Compliance
- [ ] Assegurar referències normatives correctes i actualitzades
- [ ] Format de citació professional
- [ ] Disclaimers legals estàndard

### 12. Formació i Documentació
- [ ] Manual d'usuari (visual, pas a pas)
- [ ] Vídeos tutorials curts (2-3 min cadascun)
- [ ] FAQ de problemes comuns
- [ ] Procediment de resolució d'errors

### 13. Testing i Validació
- [ ] Definir criteris d'acceptació
- [ ] Seleccionar 3-5 informes de referència per validar
- [ ] Protocol de comparació: automàtic vs. manual
- [ ] Sign-off formal abans de producció

### 14. Backup i Seguretat
- [ ] On es guarden els prompts/configuració?
- [ ] Backup del sistema configurat
- [ ] Política de dades sensibles (informes confidencials)

---

### 15. Instal·lació i Configuració Claude Code
**Prioritat:** CRÍTICA | **Risc:** BAIX (però laboriós)

**Objectiu:** Sistema completament configurat als equips de G3DT.

**Tasques:**
- [ ] Instal·lar Claude Code (CLI)
- [ ] Configurar llicència (pagament mensual)
- [ ] Crear CLAUDE.md específic per G3DT
- [ ] Configurar subagents per a cada tipus de tasca
- [ ] Definir slash-commands personalitzats (/informe, /taula, etc.)
- [ ] Instal·lar i configurar MCPs necessaris
- [ ] Configurar permisos (carpetes, xarxa, execució)
- [ ] Registre a serveis tercers (APIs) i pagament de fees si cal
- [ ] Documentar tota la configuració per replicar/mantenir

**Serveis tercers potencials:**
- APIs de mapes/cartografia
- Serveis OCR (si s'usa)
- Bases de dades geotècniques

---

### 16. Protecció de Documents Word
**Prioritat:** MITJANA | **Risc:** MITJÀ

**Objectiu:** Respectar i/o replicar les proteccions de confidencialitat dels seus documents.

**Tasques:**
- [ ] Analitzar proteccions actuals dels Word d'exemple
- [ ] Entendre què s'amaga/protegeix i per què
- [ ] Decidir si els informes generats necessiten la mateixa protecció
- [ ] Implementar protecció equivalent si cal
- [ ] Documentar com gestionar documents protegits com a input

**Nota:** MS Word indica "protecció de confidencialitat" en obrir els seus documents.

---

### 17. Accés a Xarxa Privada G3DT
**Prioritat:** ALTA | **Risc:** MITJÀ

**Objectiu:** El sistema ha de poder accedir a carpetes compartides i recursos de xarxa.

**Tasques:**
- [ ] Documentar estructura de xarxa (servidor, unitats compartides)
- [ ] Obtenir permisos d'accés per a l'usuari/sistema
- [ ] Testejar accés des de Claude Code
- [ ] Gestionar credencials de forma segura
- [ ] Fallback si xarxa no disponible

**Preguntes:**
- Servidor local o cloud?
- VPN necessària?
- Permisos per usuari o per equip?

---

### 18. Infraestructura Windows
**Prioritat:** ALTA | **Risc:** BAIX

**Confirmació:** Els equips de G3DT són Windows.

**Tasques:**
- [ ] Verificar versió Windows (10/11)
- [ ] Verificar permisos d'administrador per instal·lació
- [ ] Compatibilitat amb WSL si cal
- [ ] Testejar rendiment amb documents grans
- [ ] Documentar requisits mínims

---

### 19. OCR per a Informes de Camp Manuscrits
**Prioritat:** BAIXA | **Risc:** ALT | **Experimental**

**Objectiu:** Intentar llegir automàticament els informes de camp escrits a mà.

**⚠️ IMPORTANT:** No s'ha garantit que això funcioni. És un experiment.

**Tasques:**
- [ ] Obtenir mostres d'informes de camp manuscrits
- [ ] Avaluar llegibilitat (qualitat lletra, format consistent?)
- [ ] Testejar OCR amb diferents eines (Tesseract, Claude Vision, etc.)
- [ ] Avaluar precisió acceptable (% encerts necessari?)
- [ ] Decidir si és viable o millor entrada manual

**Expectatives realistes:**
- Lletra clara i consistent: potser viable
- Lletra irregular o amb abreviatures: probablement no viable
- Recomanació: tenir sempre fallback d'entrada manual

---

### 20. Fonts de Dades Externes (Govern/Geotècniques)
**Prioritat:** MITJANA | **Risc:** MITJÀ

**Objectiu:** Accedir a les mateixes fonts de dades que G3DT usa manualment.

**Tasques:**
- [ ] Inventariar totes les fonts externes que utilitzen
- [ ] Classificar: públiques vs. amb autenticació
- [ ] Obtenir credencials/accés per fonts autenticades
- [ ] Implementar accés automatitzat (scraping, API, descàrrega)
- [ ] Gestionar cache local per fonts estables
- [ ] Documentar com actualitzar dades

**Fonts potencials:**
- ICGC (Institut Cartogràfic i Geològic de Catalunya)
- Cadastre
- Registres de sondejos existents
- Bases de dades de normativa
- Serveis meteorològics/hidrològics

**Diferència amb MCPs:** Aquestes són fonts específiques del sector, no APIs genèriques.

---

### 21. Plantilla Word amb Estil Corporatiu G3DT
**Prioritat:** ALTA | **Risc:** BAIX

**Objectiu:** Els informes generats han de semblar 100% G3DT.

**Tasques:**
- [ ] Obtenir plantilla Word oficial de G3DT
- [ ] Documentar estils: fonts, colors, capçalera, peu, logo
- [ ] Implementar generació amb estils correctes
- [ ] Verificar coherència visual amb informes existents
- [ ] Gestionar actualitzacions de plantilla

**Elements d'estil:**
- Logo G3DT
- Capçalera/peu de pàgina
- Fonts tipogràfiques
- Colors corporatius
- Format de títols/subtítols
- Numeració de pàgines

---

### 22. Confidencialitat de Dades
**Prioritat:** ALTA | **Risc:** MITJÀ

**Objectiu:** Assegurar que les dades sensibles es tracten correctament.

**Tasques:**
- [ ] Identificar dades sensibles (clients, ubicacions, resultats)
- [ ] Definir política: què pot sortir del sistema? què no?
- [ ] Configurar Claude Code per no enviar dades sensibles a cloud si cal
- [ ] Implementar anonimització si s'usa per training/exemples
- [ ] Documentar política de confidencialitat

**Relació amb punt 16:** La protecció Word és un mecanisme; la confidencialitat és la política.

---

### 23. Versionat del Sistema
**Prioritat:** MITJANA | **Risc:** BAIX

**Objectiu:** Gestionar canvis en plantilles, prompts, configuració.

**Tasques:**
- [ ] Definir què es versiona (CLAUDE.md, prompts, plantilles, scripts)
- [ ] Decidir eina (Git? Carpetes amb dates?)
- [ ] Implementar procediment d'actualització
- [ ] Documentar com fer rollback si alguna cosa falla
- [ ] Històric de canvis per auditoria

---

### 24. Multi-usuari
**Prioritat:** MITJANA | **Risc:** MITJÀ

**Objectiu:** Permetre que diversos usuaris utilitzin el sistema simultàniament.

**Tasques:**
- [ ] Definir quants usuaris (2? 3? més?)
- [ ] Avaluar si necessiten llicències separades de Claude
- [ ] Gestionar accés concurrent a fitxers
- [ ] Evitar conflictes (dos usuaris mateix projecte)
- [ ] Logs per saber qui ha generat què

**Preguntes:**
- Cada usuari té el seu ordinador?
- Comparteixen projectes o cadascú els seus?

---

### 25. Sistema d'Aprenentatge (Feedback Loop)
**Prioritat:** ALTA | **Risc:** MITJÀ | **Implementació:** Per definir

**Objectiu:** Aprendre de les correccions que G3DT fa als informes generats per millorar contínuament.

**Per què és important:**
- Mesurar precisió real del sistema (no assumir que funciona bé)
- Identificar patrons d'error recurrents
- Millorar el RAG amb correccions reals
- Demostrar ROI amb dades objectives

**Tasques:**
- [ ] Dissenyar mecanisme de captura d'edicions (diff automàtic?)
- [ ] Definir mètriques de precisió (% text sense canvis, tipus d'errors)
- [ ] Implementar comparació: generat vs. final revisat
- [ ] Categoritzar errors: terminologia, càlculs, format, estil, contingut
- [ ] Alimentar correccions al RAG/glossari
- [ ] Dashboard de qualitat (evolució setmanal/mensual)
- [ ] Reportar mètriques a G3DT periòdicament

**Possibles implementacions:**
1. **Manual:** G3DT guarda versió original i final, comparació periòdica
2. **Semi-automàtic:** Script que compara Word original vs. final
3. **Automàtic:** Hooks que detecten edicions i les registren

**Mètriques potencials:**
- % de paràgrafs sense canvis
- Temps d'edició per informe (decreixent = millora)
- Tipus d'error més freqüent
- Seccions més problemàtiques

**Valor afegit:** Amb dades reals podem demostrar:
- "El sistema ha passat del 70% al 92% de precisió en 2 mesos"
- "Estalvi mitjà: 3.5h per informe"

---

## Calendari Orientatiu

### Fase Pilot (Setmanes 1-6)

| Setmana | Focus Principal | Lliurables |
|---------|-----------------|------------|
| 1 | Observació + RAG corpus | Documentació procés actual, extracció textos |
| 2 | RAG + estructura carpetes | Glossari inicial, mapa de carpetes |
| 3 | Prototip bàsic | Primera versió funcional (1 tipus informe) |
| 4 | Excel + taules | Integració fórmules, generació taules |
| 5 | Imatges + refinament | Integració imatges, millores UI |
| 6 | Testing + demo | 2 informes de prova, presentació resultats |

### Fase Implementació (Setmanes 7-12)

| Setmana | Focus Principal | Lliurables |
|---------|-----------------|------------|
| 7-8 | Refinament segons feedback | Ajustos basats en avaluació pilot |
| 9-10 | Tipus addicionals + UI final | Més tipus d'informe, interfície polida |
| 11 | Formació + documentació | Manual, sessions amb usuaris |
| 12 | Posada en producció | Sistema final, sign-off |

---

## Preguntes Pendents per G3DT

### Accés i Infraestructura
1. **Accés als informes:** Com accedim als ~2000 informes anteriors per construir el RAG?
2. **Infraestructura:** Versió Windows (10/11)? Permisos d'administrador?
3. **Xarxa privada:** Servidor local o cloud? VPN? Unitats compartides?
4. **Multi-usuari:** Quants usuaris? Cada un amb el seu ordinador?

### Contingut i Formats
5. **Tipus d'informe prioritari:** Quin tipus d'informe fem primer? (probablement només un tipus)
6. **Excels:** Quants fitxers Excel diferents tenen amb fórmules?
7. **Plantilla Word:** Tenen plantilla corporativa amb estils definits?
8. **Protecció Word:** Per què els documents tenen protecció de confidencialitat?

### Fonts i Dades
9. **Fonts externes:** Quines fonts consulten? (ICGC, Cadastre, altres?)
10. **Autenticació:** Alguna font requereix login/subscripció?
11. **Informes de camp:** Són manuscrits? Volen intentar OCR?

### Seguretat i Confidencialitat
12. **Dades sensibles:** Quines dades no poden sortir del sistema?
13. **Usuaris:** Qui utilitzarà el sistema? (noms, rols, nivell tècnic)
14. **Llicències:** Qui paga la llicència Claude Code? (G3DT o inclòs en servei?)

---

*Document de planificació - Actualitzar setmanalment durant el projecte*
