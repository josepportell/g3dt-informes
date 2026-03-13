# Guia d'Eva — Procés complet de generació d'informe

## 1. Arrencada del sistema

Eva fa doble clic a les icones de l'escriptori:

- **"G3DT Wizard"** — Arrenca el servidor web i obre el navegador automàticament

Només cal. El navegador s'obre sol a http://localhost:8765.

(Opcionalment: **"G3DT Claude"** — Terminal avançat per operacions manuals)

## 2. Flux complet (pas a pas)

### Pas A — Seleccionar projecte (navegador)

1. **Selecciona projecte** del dropdown
2. El sistema executa automàticament:
   - Escaneig de fitxers, DPSH Excel, Lab, ICGC, Cadastre, geocode (~5s)
   - Apareix un stepper amb el progrés en temps real
3. El wizard es pobla amb els prefills inicials
4. **Badges de color**: blau=auto, verd=guardat per Eva, gris=defecte

### Pas B — Llegir PDFs de camp (botó al wizard)

1. Eva veu el botó **"Llegir PDFs de camp"** amb badges planol/dpsh/sondeig
2. **Clica el botó** → el sistema llegeix els PDFs automàticament (~30 segons)
3. Apareix un indicador de progrés mentre treballa
4. Quan acaba, el wizard es refresca automàticament amb les dades extretes (~95% camps omplerts)

Si els PDFs ja s'han llegit anteriorment, apareix "Visió completada (3/3)" en mode col·lapsat amb opció de "Re-extreure" si cal.

### Pas C — Revisar i generar

1. Eva **revisa i ajusta** els camps que calgui (~30 segons)
2. Prem **"Guardar"** → desa user_data.json
3. Prem **"Generar Informe"** → descarrega el .docx complet

## 3. Resum visual del flux

```
Eva prepara carpeta del projecte (PDFs + Excel)
         ↓
Doble clic "G3DT Wizard" a l'escriptori
         ↓
NAVEGADOR: selecciona projecte → prefills automàtics (~5s)
         ↓
NAVEGADOR: clic "Llegir PDFs de camp" → visió IA (~30s)
         ↓
NAVEGADOR: wizard amb ~95% camps omplerts (automàtic)
         ↓
Eva revisa, ajusta (~30s) → Guardar → Generar → .docx complet
```

Tot es fa des del navegador. No cal canviar de finestra.

## 4. Altres operacions (terminal avançat)

Per operacions manuals, Eva pot obrir "G3DT Claude" des de l'escriptori:

| Comanda | Què fa |
|---------|--------|
| `/g3dt-geocodificar reference-material/XXXX` | Adreça → coordenades UTM |
| `/g3dt-adjacents-visor reference-material/XXXX` | Identifica parcel·les adjacents via Cadastre |
| `/g3dt-audit-informe reference-material/XXXX` | Compara generat vs referència |
| `/g3dt-editar-informe reference-material/XXXX` | Edita un informe ja generat |

## 5. Solució de problemes

| Problema | Solució |
|----------|---------|
| "claude CLI no trobat" | Verificar que Claude Code esta instal·lat. Contactar suport. |
| La visió tarda més de 2 minuts | Apareix avís. Verificar connexió i reintentar. |
| Botó "Llegir PDFs" no respon | Refrescar la pàgina (F5) i tornar a seleccionar el projecte. |
| El wizard no mostra projectes | Verificar que la carpeta de projectes existeix i té contingut. |
