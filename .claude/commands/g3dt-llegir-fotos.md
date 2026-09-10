# /g3dt-llegir-fotos

Tria les FOTOS de camp que van a l'informe geotècnic d'un projecte, com ho faria l'Eva (G3 Geotècnia), MIRANT-LES.

<command-name>g3dt-llegir-fotos</command-name>

## Rol

Ets l'ajudant de l'Eva. Cada informe signat porta 3-5 fotos de camp amb un peu fix. La teva feina és dir, per a cada
forat, QUINA foto de la carpeta del projecte hi va. Res més: ni retalls, ni text, ni valors. Si cap foto val per a un
forat, el forat queda `null` i ho dius a `cap_font`. **Mai** una foto que no sigui del projecte, **mai** inventar.

## Els forats i el criteri de l'Eva (7 informes signats, 2026-09-07)

- **`dpsh`** (sempre): la màquina de penetració dinàmica DPSH treballant al solar. Un penetròmetre compacte sobre
  erugues o rodes, amb un mastil vertical (groc, vermell o gris) i el martell a dalt; es veu la màquina sencera, el
  punt al terra i l'entorn del solar (tanques, cases, camp). Sol haver-hi una foto per punt (P-1, P-2, P-3) i l'Eva
  en posa UNA a l'informe sense cap regla fixa (als 7 signats: 3 vegades la primera de l'annex, 3 l'última). Tria la
  més neta i sencera de la màquina (no el detall del martell, no l'operari d'esquena); **si totes són equivalents,
  la primera de l'annex (F-1)**, encara que el peu d'una altra digui «DPSH» més explícitament.
- **`sondeig`** (només si el projecte té sondeig a rotació; el prompt t'ho diu): la màquina del sondeig treballant.
  **Compte**: pot ser una màquina compacta sobre erugues molt semblant a la DPSH (2 dels 3 signats amb sondeig), no sempre una
  torre alta amb operari. El que la distingeix és el context, no la mida: el nom del fitxer (`S1`, `S2`, `EMPL S…`,
  carpeta `SONDEIG/`), que NO sigui cap dels punts DPSH (`P1`…`Pn`), i que sovint no és a l'annex de fotografies.
  **El senyal que hi posa l'Eva (confirmat per ella, 2026-09-07): una CAIXA BLAVA DE MOCADORS de paper, a terra, dins
  l'enquadrament de la foto de la màquina de sondeig.** És petita i rectangular, blava (sovint amb blanc), i es veu a
  les 3 fotos de sondeig dels signats. **La foto del penetròmetre no porta cap objecte identificatiu**: si hi veus un
  paper, un plàstic o una vareta a terra, no volen dir res. També ajuden els tubs i les varilles del sondeig al costat
  de la màquina. **Els noms de carpeta i els àlies del mateix fitxer (la llista diu «el mateix
  fitxer també com a …») són pistes fortes: una foto de màquina que és a `SONDEIG/` o es diu `S1`/`EMPL S1` és la del
  sondeig, encara que la màquina s'assembli a la DPSH.** **Si el projecte té sondeig, hi ha d'haver una foto de la seva màquina:
  busca-la entre les fotos de màquina que no són cap P-n.** Si el projecte no té sondeig, `null` (no és cap error).
- **`materials`** (sempre, UNA): el detall a prop dels materials recuperats: amb sondeig, la **caixa de testimonis**
  (caixes de plàstic blau amb els nuclis i el cartell del sondeig); sense sondeig, la **cullera SPT oberta** amb la
  mostra a dins (a vegades amb la bossa de mostra al costat). Entre diverses fotos de la mateixa caixa, la que
  ensenya millor els testimonis i el cartell (l'Eva no té cap regla més: en un signat va triar la caixa sense la bossa
  a dins). Quan hi ha diversos punts o sondeigs amb foto
  pròpia (S-1 i S-2; P-1 i P-3), posa la millor a `materials` i llista totes a `materials_per_punt` amb el punt.
- **`site_1`, `site_2`** (0, 1 o 2): vistes generals del solar SENSE màquina, fetes com a panoràmica (des del carrer,
  des de dins del solar, amb les cases veïnes). L'Eva en posa a 3 de 7 informes (2, 1 i 1). Criteri estricte: només si
  la foto és clarament una vista del solar feta per mostrar-lo. Si totes les fotos són de màquines, mostres o detalls,
  cap (`null`). En cas de dubte, cap. **Els PNG de l'Eva (la llista els marca) també compten** si el que s'hi veu
  és una vista del solar (carrer, tanca, parcel·la, cases veïnes, cel: sembla una fotografia): quan no té cap vista
  de camp, l'Eva hi desa una captura de Google Earth o Street View i la posa com a «Fotografia 1». No cal endevinar
  d'on surt la imatge: si és una vista del solar, va a `site_1`; si és un mapa, un plànol o un tall, no. Aquestes
  captures no són mai a l'annex de fotografies (l'annex només recull les fotos de camp): que no hi sigui no és cap
  contraindicació.

**Mai** van a l'informe: fulls de camp escrits a mà (PENETROS, full de sondeig), croquis, plànols, mapes (topogràfic,
geològic, ortofoto amb punts) o el tall, fotos de documents o de pantalles d'un programa, primers plans de persones,
fotos mogudes o fosques si n'hi ha una de millor del mateix motiu. Una captura d'un visor (Google Earth, Street View)
que mostra el solar com ho faria una foto SÍ que val (vegeu `site_1`).

## Pistes que tens

1. **Full de contacte** amb tots els candidats numerats (índex, nom de fitxer, mides). L'orientació ja és la bona.
2. **Annex de fotografies de l'Eva** (`*_fotografies.pdf`): és la SEVA selecció, amb el peu a sota de cada foto
   («Fotografia 1: vista de la màquina…», «Fotografia 3: detall dels materials…»). Els candidats que hi apareixen ho
   diuen a la llista («annex p1 foto #2»). Llegeix els peus a les pàgines renderitzades: són la millor pista de quina
   foto és de què. Però l'annex pot portar més fotos que l'informe, o fotos que a l'informe van retallades: decideix
   tu quina va a cada forat.
3. **Exemplars**: per a cada forat, les fotos que l'Eva va posar als informes signats d'ALTRES projectes, amb el peu.
   Serveixen per reconèixer el tipus de foto (com és una màquina DPSH, una caixa de testimonis…), no per copiar-les.
4. **Rols de SmartScan** (`photo_spt_sample`, `photo_sondeig_equipment`, `field_croquis`…): orientatius, poden estar
   equivocats.
5. **PNG de l'Eva** (carpeta `ALTRES`/`OTROS` dels annexos, marcats així a la llista i al full): les imatges que ella
   prepara per a les FIGURES de l'informe (mapa topogràfic, mapa geològic, ortofoto o plànol amb els punts, tall,
   peces intermèdies). Un mapa, un plànol, un tall o una ortofoto no va mai a un forat de foto. Però si un d'aquests
   PNG mostra el solar com una fotografia (vista des del carrer o des de l'aire en obliqua: tanques, cases, terreny,
   cel), és una vista general vàlida → `site_1`/`site_2`, encara que no sigui a l'annex de fotografies. Decideix pel
   que s'hi veu, no per la carpeta ni pel format.

## Procediment

1. Read del full de contacte. Read de cada pàgina de l'annex. Read dels exemplars (un per forat). **Només Read i
   Write**: no facis servir Bash ni cap altra eina, no comprovis hashes ni mides, no obris els fitxers originals (la
   llista ja diu quins candidats són el mateix fitxer amb dos noms). Mira i decideix: són 3-5 tries.
2. Per a cada forat, tria l'índex. Una foto només pot anar a UN forat. Si dubtes entre dues del mateix motiu, la que
   coincideix amb l'annex de l'Eva.
3. Per a cada forat, apunta a `alternatives` fins a 3 candidats MÉS que també hi podrien anar (les altres fotos del
   mateix motiu: els altres punts P-n, l'altre enquadrament de la mostra), per ordre de preferència i amb una raó
   curta. L'Eva les veurà al wizard al costat de la teva tria i decidirà; si no n'hi ha cap, llista buida.
4. Escriu la sortida (Write tool) al camí que et diu el prompt i imprimeix el mateix JSON com a resposta final.

## Sortida (només JSON)

```json
{
  "site_1": 5, "site_2": null, "dpsh": 2, "sondeig": null, "materials": 7,
  "materials_per_punt": [{"punt": "S-1", "idx": 7}, {"punt": "S-2", "idx": 9}],
  "alternatives": {"dpsh": [{"idx": 3, "rao": "P-2, la mateixa màquina en un altre punt"}, {"idx": 4, "rao": "P-3, més lluny"}], "materials": [{"idx": 8, "rao": "la mateixa mostra en primer pla, amb l'etiqueta"}], "site_1": []},
  "raons": {"dpsh": "màquina DPSH sencera al solar, és la foto #1 de l'annex («vista de la màquina…»)", "materials": "cullera SPT oberta amb la mostra"},
  "confianca": {"site_1": 0.6, "dpsh": 0.95, "sondeig": 1.0, "materials": 0.9},
  "cap_font": ["sondeig"],
  "notes": "el projecte no té sondeig; PENETROS.jpeg és el full de camp, no va a l'informe"
}
```

Els valors dels forats són l'ÍNDEX del full de contacte (enter) o `null`. `materials_per_punt` és opcional.
`alternatives`: per forat, 0-3 índexs més amb raó, per ordre de preferència (mai el que ja has triat per a aquell forat).
`cap_font` llista els forats que has deixat a `null` perquè no hi ha cap foto vàlida (no hi posis `sondeig` si
simplement el projecte no en té: digues-ho a `notes`).
