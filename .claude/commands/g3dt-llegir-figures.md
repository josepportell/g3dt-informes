# /g3dt-llegir-figures

Tria les FIGURES que van a l'informe geotècnic d'un projecte tretes del projecte de l'arquitecte i dels fulls de l'Eva
(G3 Geotècnia), com ho faria ella, MIRANT-LES, i digues el retall.

<command-name>g3dt-llegir-figures</command-name>

## Rol

Ets l'ajudant de l'Eva. A cada informe signat, abans de la cullera SPT, hi ha entre 2 i 4 figures: la SITUACIÓ (sempre),
la dels ASSAIGS (el dibuix amb els punts, gairebé sempre) i, quan ajuden a entendre l'obra, 0-2 figures del PROJECTE
(«Font: Projecte»). La teva feina és dir, per a cada ranura, QUIN candidat hi va i QUIN RETALL (en fraccions de la
imatge amb quadrícula), i escriure el peu de les figures del projecte. Res més: ni text, ni valors. Si cap candidat
val, la ranura queda `null` i ho dius a `cap_font`. **Mai** una imatge que no sigui del projecte, **mai** una pàgina
sencera amb caixetí «per omplir», **mai** inventar. Aquest projecte no l'has vist mai: decideix només amb el que hi
ha a la carpeta i amb els criteris d'aquí sota.

## Les tres ranures i el criteri de l'Eva (7 informes signats, 2026-09-07)

- **`assaigs`** (capítol 2.2, «Situació de l'estructura projectada i els assaigs realitzats»): el dibuix on es veuen
  els PUNTS D'ASSAIG (etiquetes «P-1», «P-2», «S-1»; cercles o creus de color) sobre la planta o l'ortofoto. La font
  normal és el **retall del full «plànol de situació» de l'Eva** (candidat `annex_crop`): ella dibuixa els punts en
  aquest full abans d'obrir el wizard, i és el que hi ha a l'informe a 5 de 6 signats amb figura d'assaigs. Dona'l
  **sencer** (`crop: null`). Només si no hi ha `annex_crop`, o no porta cap punt, busca un altre candidat que porti
  els punts (una planta del projecte amb els punts marcats, un PNG amb punts sobre ortofoto): planta abans que
  ortofoto (4 de 6). **Si cap candidat porta punts, `null`**: no triïs mai un dibuix sense punts per a aquesta
  ranura. Retall dels candidats que no són `annex_crop`: el dibuix sencer amb els punts i les cotes, sense caixetí
  ni llegenda.
- **`projecte`** (capítol 1.1, 0-2 figures, «Font: Projecte»): dibuixos del projecte de l'arquitecte que aporten el que
  la figura d'assaigs no ensenya. Als signats hi ha: la SECCIÓ o perfil de l'habitatge respecte del terreny (el tall
  vertical amb el terreny ratllat, els forjats i les cotes de carener i de forjat; no l'alçat de façana), la planta
  d'EMPLAÇAMENT de l'edifici dins la parcel·la sense punts quan la figura d'assaigs no mostra la parcel·la sencera,
  el plànol TOPOGRÀFIC de la parcel·la si l'arquitecte l'ha facilitat i les PLANTES/TIPOLOGIES quan hi ha diversos
  habitatges. **Cap** quan el projecte de l'arquitecte no és a la carpeta (només hi ha l'ortofoto o els fulls de
  l'Eva) o quan l'únic plànol útil ja és la figura d'assaigs. **Regla de sobrietat**: als 7 signats, 3 no en tenen
  cap, 3 en tenen UNA i 1 en té dues (topogràfic + tipologies de diversos habitatges). Per defecte, com a màxim UNA;
  dues només amb topogràfic facilitat i diversos habitatges. No afegeixis l'emplaçament si la figura d'assaigs ja
  mostra l'edifici sencer dins la parcel·la. En cas de dubte, cap. Retall: només el dibuix (sense caixetí, sense
  llegendes ni quadres de text); una secció, sencera d'extrem a extrem, la meitat del full que toca. Peu curt, en
  l'idioma de l'informe, a l'estil dels exemplars («Detall de…» / «Detalle de…», «…projectat» / «…proyectada»),
  acabat amb «Font: Projecte.» (ca) / «Fuente: Proyecto.» (es).
- **`situacio`** (capítol 1.1, Figura 1): **sempre `null`**. La situació la fa el camí determinista (els dos mapes del
  full de l'Eva, de costat). Mesurat el 2026-09-09: «si el plànol de l'arquitecte porta els dos mapes com a insets,
  l'Eva els fa servir» encerta en un signat i falla en un altre: no és cap regla. Si l'Eva vol una altra situació,
  ho tria al wizard.

**Mai** van a l'informe: pressupostos, memòries de text, fulls de camp (PENETROS, sondeig), el tall de correlació,
l'annex de fotografies, portades, caixetins, taules de càlcul, pàgines amb només text o taules, ni una pàgina sencera
quan la figura és un dibuix d'aquella pàgina.

## Pistes que tens

1. **Full de contacte** amb tots els candidats numerats (índex, fitxer, pàgina, mides, tipus, rol). Tipus:
   `annex_crop` (el retall determinista del full de l'Eva, ja sense caixetí), `project_page` (pàgina d'un PDF del
   projecte de l'arquitecte), `project_image` (imatge de l'expedient), `eva_png` (PNG que l'Eva ha compost a ALTRES).
   **L'`annex_crop` i els `eva_png` van sempre SENCERS (`crop: null`)**: ja són el retall de l'Eva; un retall a sobre
   «per netejar» l'empitjora.
2. **Cada candidat amb la quadrícula**: línies cada 0,1 amb l'etiqueta, origen a dalt a l'esquerra, i una FRANJA a
   dalt que diu «CANDIDAT N · fitxer · pàgina». **L'índex que escrius és el de la franja de la imatge que has mirat**:
   a `raons`, cita sempre «candidat N (fitxer, pàgina)» tal com ho llegeixes a la franja. El retall és
   `[x0, y0, x1, y1]` en fraccions de la imatge sota la franja (p. ex. `[0.08, 0.12, 0.92, 0.80]`). Sigues generós
   d'un 2 %: Python treu el marge blanc sobrant, però no pot recuperar el que hagis tallat. Deixa fora el TÍTOL i
   l'escala de la figura («AEREA E. 1/500», «ESCALA GRÁFICA»): l'Eva retalla només el dibuix.
3. **Exemplars**: per a cada ranura, les figures que l'Eva va posar als informes signats d'ALTRES projectes, amb el
   peu. Serveixen per reconèixer el tipus de figura i l'estil del peu, no per copiar-les: aquest projecte és nou.
4. **Rols de SmartScan** (`architect_plan`, `architect_project`, `figure_test_points`…): orientatius, poden estar
   equivocats.

## Procediment

1. Read del full de contacte. Read dels exemplars (un per ranura). Read de cada candidat amb quadrícula que puguis
   necessitar (les pàgines amb dibuix del projecte; els PNG d'ALTRES només si dubtes). **Només Read i Write**: no
   facis servir Bash ni cap altra eina, no obris els PDF originals. Mira i decideix: són 1-3 tries.
2. Per a cada ranura, l'índex i el retall. Un mateix candidat pot servir per a dues ranures amb retalls diferents;
   el mateix retall dues vegades, no.
3. Escriu la sortida (Write tool) al camí que et diu el prompt i imprimeix el mateix JSON com a resposta final.

## Sortida (només JSON)

```json
{
  "assaigs": {"idx": 1, "crop": null},
  "projecte": [
    {"idx": 7, "crop": [0.06, 0.50, 0.94, 0.90], "caption": "Detall del perfil de l'habitatge projectat. Font: Projecte."}
  ],
  "situacio": null,
  "raons": {"assaigs": "candidat 1 (plan_crop…, annex_crop): el retall del full de l'Eva porta P-1, P-2 i S-1 sobre la planta", "projecte": "candidat 7 (…pdf, pàgina 4): la meitat inferior és la secció amb el terreny i les cotes de carener i forjat"},
  "confianca": {"assaigs": 0.95, "projecte": 0.7},
  "cap_font": [],
  "notes": "el plànol del projecte no porta cap punt; el topogràfic és dins el mateix full que la planta"
}
```

`assaigs` és un objecte o `null`; `situacio` sempre `null`; `projecte` és una llista de 0 a 2 objectes amb `caption`;
`crop` és `null` (tot el candidat) o `[x0, y0, x1, y1]`. `cap_font` llista les ranures que has deixat a `null` perquè
cap candidat val (no hi posis `projecte` si simplement no calen figures del projecte: digues-ho a `notes`).
