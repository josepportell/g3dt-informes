# L'informe de Rubí diu «solar pla» i alhora porta una secció d'estabilitat de vessant

**Trobat:** 2026-09-17, investigant quants camps arriben amb valor generat i font «automàtica»
sense que l'Eva els hagi confirmat mai.
**Gravetat:** contradicció interna en un informe que l'Eva signa. Visible per a qualsevol
enginyer que el llegeixi.

## El que hi ha al `.docx` generat avui

- **3.3.1 Hidrogeologia superficial:** «Com que es tracta d'**un solar pla**, no s'han detectat
  marques i/o indicis de processos d'erosió relacionats amb l'escolament hídric superficial…»
- **Índex, 4.5:** «**ESTABILITAT DE VESSANT**» (i 4.4 «EMPENTES DE TERRES»)

Les dues coses, al mateix document.

## Per què passa (cadena verificada)

1. Rubí no té `COORDENADES.txt` i la lectura no dona UTM. Al moment de calcular els prefills
   **no hi ha coordenades**.
2. `automation/auto_extractor.py:311` (`_phase3_slope(utm_x, utm_y, …)`) necessita les UTM per
   consultar el pendent a l'ICGC. Sense UTM, **no s'omple mai `slope_percent`**.
3. `web/wizard_service.py:558`: `slope_pct = _get_val('slope_percent')` → `None` →
   ```python
   slope_val = float(slope_pct) if slope_pct else 0.0   # ← el «no ho sé» es torna 0,0
   ```
   i `site_condition_sentence(0.0, …)` escriu la frase del **solar pla**, amb font
   `'computed (slope 0%)'`.
4. Més tard, `web/wizard_service.py:333` obté les UTM per la via de reserva dels adjacents
   (`geocode:adjacents_fallback`) — **després** que la Fase 3 hagi passat de llarg.
5. En generar, `automation/report_generator.py:1195-1205` ja té UTM, crida `get_slope()` i obté
   **21,6 %**:
   ```
   14:57:30 icgc_geology:754  Slope at (418109.66, 4595666.83): 21.6% toward W
   14:57:30 report_generator:1203  Auto-set is_sloped=True (slope=21.6% W)
   14:57:30 report_generator:1271  Auto-activated slope stability
   14:57:30 report_generator:1274  Auto-activated earth pressure
   ```
6. **Ningú recalcula `site_condition`.** La frase del «solar pla», congelada d'un 0 % que mai va
   ser cert (només era desconegut), viatja a l'informe al costat de les seccions de vessant.

## És el mateix error que hem corregit aquest matí

És exactament la forma del defecte T1 del rellotge: **un zero que vol dir «encara no ho sé»
tractat com un zero de debò.** Allà eren minuts a la pantalla; aquí és una frase dins d'un
informe signat.

## Per què no s'havia vist a Alcoletge

A Alcoletge les UTM es perdien per la coma decimal
(`TROBALLA-UTM-COMA-DECIMAL-2026-09-17.md`), o sigui que `get_slope()` no s'arribava a cridar
mai en generar. **Un defecte n'amagava l'altre:** l'informe sortia «pla» i sense seccions de
vessant, coherent però igualment basat en un pendent desconegut.

## Camins possibles (a decidir amb el Josep)

- **Que el pendent es consulti quan ja hi ha UTM**, encara que arribin per la via de reserva
  dels adjacents: avui la Fase 3 passa abans i no s'hi torna.
- **Que `site_condition` no es decideixi amb un pendent desconegut**: si no hi ha `slope_percent`,
  el camp hauria de quedar per revisar (i comptar a «Queden N camps a revisar»), no resoldre's
  com a «pla» per defecte.
- **Que el generador recalculi la frase** si acaba sabent un pendent que contradiu el que es va
  suposar, o com a mínim que avisi.
- Convé repassar si hi ha **altres frases narratives** decidides amb un valor per defecte que
  després es contradiu amb dades obtingudes més tard.

## Context de la mesura

A Rubí, dels **64 camps de cara a l'Eva**, **18 arriben amb valor generat/plantilla/per defecte**
presentat com a automàtic. Alguns són derivacions legítimes de dades reals (`num_dpsh_tests`,
`table_dpsh_range`, `num_site_photos`). Els que mereixen mirada són els que **escriuen prosa a
l'informe** (`site_condition`, `site_description`, `access_description`, `settlement_sentence`,
`access_street`, `lab_tests_text`) i els **defectes estàndard** sobre l'edifici
(`foundation_depth_m=0,3`, `has_basement=False`, `has_retaining_walls=False`,
`num_soil_levels=1`, `sulfate_level_name='1er nivell'`).

---

# ADDENDA 2026-09-17 (nit) — el que hem verificat després: la meitat greu era l'altra

Tot el que hi ha a dalt es manté. El que canvia és **quina de les dues meitats de la
contradicció és l'errònia.** El document original dona per bo que les seccions de vessant
són correctes i que la frase és la que ha quedat obsoleta. **És al revés.**

## 1. Les dues seccions auto-activades són capçaleres BUIDES

Al `.docx` generat de Rubí, el cos de l'informe diu literalment:

```
4.4. EMPENTES DE TERRES
4.5. ESTABILITAT DE VESSANT
G3 D T S.L. sol·licita que si es detectessin anomalies…     ← el tancament, directament
Els Omells de Na Gaia, 17 de setembre de 2026
Eva Vázquez Marcet — Geòloga col 4302
```

Cap de les dues té una sola línia de contingut. Són **dos títols nus damunt la signatura de
l'Eva**, afirmant que s'ha avaluat l'estabilitat del vessant i no mostrant res.
`docs/QA-STATUS.md:134` ja ho advertia: els àbacs de Hoek & Bray **no estan implementats**.

Això és més greu que la frase: una frase dolenta es corregeix llegint-la; una secció buida
dins un informe signat és una afirmació de feina feta que no existeix.

## 2. L'Eva, al Rubí signat, no escriu cap de les tres coses

| | §3.3.1 | 4.4 | 4.5 |
|---|---|---|---|
| **Rubí signat** (Eva) | «**Al solar**, no s'han detectat marques…» — cap afirmació topogràfica | no | no |
| **Rubí generat** (avui) | «Com que es tracta d'**un solar pla**…» | SÍ, buida | SÍ, buida |
| **Castellar signat** (33 %) | «**Tot i no ser un solar pla**…» | SÍ | SÍ, amb Hoek & Bray, F = 1,8, 20-25° |

I al §2.1.2 del Rubí signat l'Eva explica per què: *«fa una lleugera baixada, de sudoest a
nord-est… diferència de cota d'uns 13.20 metres… **tot i que la zona de treball es mostra
totalment plana. La pendent comença la zona posterior**»*.

**El pendent mitjà ICGC de la parcel·la no sap on es fonamenta l'edifici.** És exactament la
forma de la regla d'or dels càlculs (`docs/CRITERIS-CALCUL-EVA.md`): mana l'estrat **on
recolza la fonamentació**, no la mitjana del solar. Castellar 33 % → l'Eva escriu les
seccions; Rubí 21,6 % → no. **Cap llindar sobre la mitjana separa els dos casos.**

## 3. «Al solar,» — la capçalera neutra existeix i és de l'Eva

Repassades les capçaleres davant la cua fixa «no s'han detectat marques…» als signats
llegibles:

| projecte | §3.3.1 | §4.2 |
|---|---|---|
| Rubí | «Al solar,» | «Es tracta d'un solar no antropitzat,» |
| Bell-lloc | «Degut a que es tracta d'un solar antropitzat,» | igual |
| Castellar | «Tot i no ser un solar pla,» | igual |

**Rubí és l'únic cas on les dues seccions difereixen**, i ho fan precisament cap a una
capçalera que **no afirma res** — ni topografia ni antropització. `ANALISI-NARRATIVA-2026-09-06.md`
§4 no la va registrar (atribuïa a Rubí la capçalera del 4.2). És la forma que l'Eva té per a
«no em comprometo», i per això és el defecte honest quan el sistema no sap el pendent.
Confirmació demanada a l'Eva (pregunta 17 ampliada).

## 4. La causa arrel de les seccions buides: DUES auto-activacions mal ordenades

No és que ningú recalculi. És que **la informació arriba a mitja plantilla**:

1. `report_generator.py:1992` (pas 2b de `generate()`) activa
   `report_data.include_slope_stability` / `include_earth_pressure` a partir de
   `report_data.is_sloped` — que ve del prefill, on la Fase 3 no va córrer mai (sense UTM).
   Queda **False**.
2. `generate_sections()` construeix la secció 4. `Section4Generator.generate_empentes` i
   `generate_estabilitat` (`automation/sections/section4_conclusions.py:406` i `:437`)
   retornen `None` a la primera línia perquè els flags són False → els dos paràgrafs queden
   buits (`setdefault('', '')` a `report_generator.py:1890`).
3. `_build_template_context()` (`:1195`) fa una crida ICGC **nova**, obté 21,6 %, i a `:1269`
   activa els flags **de la plantilla**. La plantilla renderitza les capçaleres.
   **Els paràgrafs ja eren buits.**

La lectura tardana arriba a les capçaleres i no al contingut.

## 5. I la frase: la provinença hi és, i no es mira

`report_generator.py:1218-1226` decideix si mana el text del wizard **pel recompte de
paraules** (`len(_sc_user.split()) >= 4`), que no distingeix un text escrit per l'Eva d'una
conjectura del propi sistema. La provinença existeix: al `user_data.json` de Rubí,
`_sources['site_condition'] == 'computed (slope 0%)'` — no `'user'`. El mateix fitxer ja
consulta `_sources` a la línia 422 per a `cota_referencia`.

El generador, doncs, **ja calcula la frase bona** (amb 21,6 % diria «Tot i no ser un solar
pla») i la llença a favor de la conjectura congelada.

## 6. I el pendent es podia saber

`_fill_missing_adjacents()` (`web/wizard_service.py:333`) obté les UTM per geocodificació i les
desa a `merged`; el bloc narratiu que les necessita és **més avall** (`:2410`). Entremig ningú
consulta l'ICGC. **Cap dels 7 projectes de referència té `COORDENADES.txt`**: aquest camí no és
l'excepció, és la norma.

## 7. Conseqüència per al disseny

Les quatre coses són **la mateixa avaria**, i cap es resol triant un valor millor:

| on | el «no ho sé» | l'afirmació que en surt |
|---|---|---|
| `site_condition_sentence` | pendent desconeguda | `0.0` → «solar pla» |
| `wizard_service:561` | pendent desconeguda | `0.0` un segon cop |
| `report_generator:1224` | qui va escriure la frase | recompte de paraules → «l'Eva» |
| `report_generator:1269` | si toca la secció | capçalera sense contingut |

La pregunta bona no és quin valor hi posem, sinó **com distingim «no ho sé» de «ho sé i és
això»** — i, quan no ho sabem, com ho hi porta davant de l'Eva en comptes de decidir-ho sols.

*Fi addenda. La frase era el símptoma; les dues seccions buides damunt una signatura eren el problema.*

## 8. Dos defectes veïns trobats pel camí, NO tocats

Tots dos són la mateixa família («un fet conegut es perd i es torna desconegut, o a l'inrevés»),
però queden fora d'aquesta tanda. Anotats perquè no es perdin.

**(a) Vilanova es genera en català un informe que l'Eva signa en castellà.**
El `.docx` signat de Vilanova és sencer en castellà: §3.3.1 hi diu «En la zona de estudio no se
han detectado marcas de inicios de procesos de erosión relacionados con la escorrentía hídrica
superficial» — que és literalment `SITE_CONDITION_ES`, la branca de sortida ràpida de
`site_condition_sentence`. Però la mesura M341 del 2026-09-10
(`runs/2026-09-10-m341-pujada/vilanova/viaA/_context_usat.json`) mostra `report_language: 'ca'`
i un `site_condition` en català. La detecció d'idioma falla per a aquest projecte, i per tant
**tot l'informe surt en la llengua equivocada** — un defecte molt més gros que la frase que
investigàvem. Anciles (l'altre projecte ES) sí que es detecta bé.

**(b) `wizard_service.py:369` converteix un «no antropitzat» conegut en «no ho sé».**

```python
is_anthro = None if 'default' in anthro_source else (_get_val('is_anthropized') or None)
```

`_get_val` retorna `entry.get('value','') or ''`. Si `is_anthropized` val `False` **de debò**
(llegit, no per defecte), `_get_val` dona `''`, i `'' or None` → `None`. Un fet conegut es
presenta com a desconegut, i `site_condition_sentence` tria una altra branca.

És exactament la imatge especular del defecte principal: allà un desconegut es tornava una
afirmació; aquí una afirmació es torna un desconegut. Detectat per la revisió del 2026-09-17,
no verificat amb dades reals, no arreglat.
