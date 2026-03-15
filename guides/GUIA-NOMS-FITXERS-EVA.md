# Guia de Noms de Fitxers per al Wizard

El wizard detecta i classifica fitxers automaticament. Si els noms son consistents, el sistema extreu mes dades sol = menys feina manual.

## Fitxers que el sistema reconeix

| Fitxer | On va | Que fa el sistema |
|--------|-------|-------------------|
| `A.01.pdf` | Arrel del projecte | Llegeix caixeti, dimensions, plantes, arquitecte |
| `A.01 amb punts.pdf` | Arrel del projecte | Igual que A.01 pero amb punts d'assaig marcats |
| `PROJECTE_BASIC_*.pdf` | Arrel del projecte | **NOU!** Extreu superficie parcella de la taula NORMATIVA URBANISTICA |
| `PENETROS.pdf` | Arrel del projecte | Llegeix valors N20 del full de camp |
| `SONDEIG.pdf` | Arrel del projecte | Llegeix capes de sol del full de camp |
| `*DPSH*.xls` | `ANNEXES/` | Dades DPSH transcrites (Excel) |
| `DADES CLIENT.txt` | `ACCEPTACIO/` | Dades del client (nom, adreca, NIF) |
| `PRESSUPOST*.pdf` | `ACCEPTACIO/` | Pressupost del projecte |
| `COORDENADES.txt` | `ANNEXES/ALTRES/` | Coordenades UTM del GPS de camp |
| `LAB-SIG.pdf` | `PDF/ANNEXES/` | Resultats de laboratori |
| `{expedient}_sondeig.pdf` | `PDF/ANNEXES/` | Annex formatat del sondeig (prioritat sobre fitxa de camp) |

## Estructura de carpetes esperada

```
{projecte}/
  A.01.pdf
  PROJECTE_BASIC_*.pdf           <-- NOU
  PENETROS.pdf
  SONDEIG.pdf
  ACCEPTACIO/
    DADES CLIENT.txt
    PRESSUPOST*.pdf
  ANNEXES/
    {expedient}_DPSH.xls
    ALTRES/
      COORDENADES.txt
  PDF/ANNEXES/
    LAB-SIG.pdf
    {expedient}_sondeig.pdf
```

## El mes important: PROJECTE_BASIC

Quan l'arquitecte t'envia el PDF del projecte basic, renombra'l a:

    PROJECTE_BASIC_NomArquitecte.pdf

o qualsevol nom que comenci per `PROJECTE_BASIC`. Exemples valids:

- `PROJECTE_BASIC_GARCIA.pdf`
- `PROJECTE BASIC BELL-LLOC.pdf`
- `PROJECTE_BASIC.pdf`

Amb aquest fitxer, el wizard extreu automaticament la superficie de la parcella que ara escrius a ma. Renombrar triga 2 segons, estalvia minuts.

## Notes

- Els noms no distingeixen majuscules/minuscules (excepte A.01.pdf).
- Si no hi ha COORDENADES.txt, el sistema calcula coordenades aproximades a partir de l'adreca.
- El fitxer `PENETROS+SONDEIG.pdf` tambe funciona si penetros i sondeig estan en un sol PDF.
