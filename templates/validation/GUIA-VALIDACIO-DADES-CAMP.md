# Guia de Validació de Dades de Camp

## Què és?

Un sistema per verificar que les dades dels fulls de camp (escrits a mà) són correctes abans de generar l'informe final.

**Avantatge principal:** Només cal revisar els valors que tenen problemes, no tots.

---

## Pas 1: Executar l'extracció

Obre Claude Code a la carpeta del projecte i executa el skill corresponent:

### Per DPSH (PENETROS.pdf)
```
/g3dt-validar-penetros PENETROS.pdf
```
Compara automàticament amb l'Excel i marca les diferències.

### Per Sondeig (SONDEIG.pdf)
```
/g3dt-validar-sondeig SONDEIG.pdf
```
Extreu capes de sòl i resultats SPT.

### Per Plànol (A.01.pdf)
```
/g3dt-extreure-planol A.01.pdf
```
Extreu dimensions i dades del projecte.

**Resultat:** Es crea un fitxer JSON a la carpeta `validation/` del projecte.

---

## Pas 2: Obrir el formulari de revisió

1. Obre un terminal a la carpeta `templates/validation/`

2. Executa:
   ```
   python3 -m http.server 8765
   ```

3. Obre el navegador: **http://localhost:8765/review.html**

---

## Pas 3: Carregar i revisar

1. Clica **"Carregar fitxer JSON"**

2. Selecciona el fitxer `*_extracted.json` del projecte

3. Es mostrarà la pestanya corresponent (DPSH, Sondeig o Plànol)

### Què cal revisar?

| Indicador | Significat | Què fer |
|-----------|------------|---------|
| 🟢 Verd / ✓ | Correcte | Res |
| 🟡 Groc / ⚠️ | Discrepància o baixa confiança | Verificar i corregir si cal |
| 🔴 Vermell / ?? | Il·legible | Entrar el valor correcte |

---

## Pas 4: Guardar

- **"Guardar com a Aprovat"** → Fitxer llest per usar a l'informe
- **"Guardar Progrés"** → Guarda sense aprovar (per continuar després)

---

## Resum ràpid

```
1. /g3dt-validar-penetros PENETROS.pdf    → validation/dpsh_extracted.json
2. /g3dt-validar-sondeig SONDEIG.pdf      → validation/sondeig_extracted.json
3. /g3dt-extreure-planol A.01.pdf         → validation/planol_extracted.json
4. Obre review.html al navegador
5. Carrega el JSON, revisa només els marcats, guarda com a aprovat
```

---

## Exemple Bell-Lloc

| Document | Resultat | Revisió necessària |
|----------|----------|-------------------|
| PENETROS.pdf | 18/18 valors coincidents | ❌ Cap |
| SONDEIG.pdf | SPT amb possible anomalia | ⚠️ Verificar SPT |
| A.01.pdf | Dades correctes, avisos urbanístics | ⚠️ Revisar avisos |

---

*Eficients.cat - Automatització amb Claude Code*
