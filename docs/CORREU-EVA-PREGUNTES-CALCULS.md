# Correu per Eva — Preguntes sobre càlculs (v3)

**Actualitzat amb troballes dels informes de referència + recerca de correlacions**

---

**Text del correu:**

---

Hola Eva,

Estem afinant l'automatització dels informes i ens queden uns dubtes concrets. Respostes curtes van perfecte.

**1. Qa — Topall o càlcul?**
A la Base de Càlcul tens el Terzaghi clàssic (F=3) i el Terzaghi-Peck (N/12). Quan donen valors diferents, quin prevalia? I el 3.0 kg/cm² que surt en la majoria de projectes, és resultat del càlcul o un topall pràctic per habitatges?

**2. E — Com hi arribes?**
Per un cas com Rubí (graves i sorres, N20≈40), com arribes a E=450? Mires la D.23 i agafes la banda baixa, fas servir alguna correlació concreta, o és criteri professional?

**3. c i phi — Taula de Crespo Villalaz**
Als informes diu que c i phi surten del Crespo Villalaz ("Mecánica de suelos y cimentaciones"). Per sòls granulars (graves, sorres) ens quadren els valors. Per cohesius (com els llims de Linyola, phi=28), quin criteri segueixes? Taula del llibre per tipus de sòl? Si ens pots dir quina taula o pàgina, ens ajudaria molt.

**4. Nb → N: factor 0.83**
Als Excel de DPSH veiem que Nb es converteix a N amb un factor 0.83. Després, per buscar paràmetres (phi, E, gamma), fas servir l'N corregit (×0.83) o l'N20 brut del DPSH?

Moltes gràcies!

---

**Nota interna:**

Ja NO preguntem (resoltes):
- ~~gamma~~ → D.27, peso específico, valor directe per litologia (confirmat)
- ~~Assentament quin mètode~~ → Schmertmann (confirmat pels informes)
- ~~cohesió mínima~~ → Pregunta baixa prioritat, afegim si queda espai

Preguntes descartades:
- ~~N20 vs N30~~ → Substituïda per pregunta 4 (Nb→N factor 0.83, més precisa)

**La pregunta clau és la 4** — si Eva usa N corregit (×0.83) per tot, els valors que li entren a les taules/correlacions són ~17% més baixos que N20 brut. Això afectaria phi, E i gamma.

**La pregunta 3** pot desbloquejar el problema dels cohesius (Linyola phi=28 vs nosaltres 35.8).
