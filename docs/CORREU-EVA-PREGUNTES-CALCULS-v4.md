# Correu per Eva — Preguntes sobre càlculs (v4, 2026-04-17)

**Canvis respecte v3:** la pregunta 3 (c i phi cohesius) ja NO és oberta —
hem trobat la taula a Crespo Villalaz Ch.11 p.175 (Tabla 11.2), i el teu
informe de Bell-Lloc ja cita "Crespo Villalaz, a partir de la resistència
dels materials". Ara només demanem **confirmació** de la nostra hipòtesi
sobre el topall 28° per transicionals. Les tres preguntes obertes són:
(1) Nb factor 0.83, (2) E per carbonatades (re-llegint l'informe hem
vist que N=54 és SPT del sondeig, així que la pregunta real és el factor
n≈4.8 per cementades), (3) Qa topall vs càlcul.

---

**Text del correu:**

---

Hola Eva,

Hem avançat molt amb l'automatització i només ens queden tres dubtes concrets (el quart punt és una confirmació ràpida). Respostes curtes perfectes.

**1. Nb → N: factor 0.83**

Als Excel de DPSH veiem que Nb es converteix a N amb un factor 0.83. Quan busques paràmetres en taules (phi, E, gamma), entres amb l'**N corregit (×0.83)** o l'**N20 brut** del DPSH? És la pregunta que més afecta tots els càlculs.

**2. Bell-Lloc E=650 — factor n per graves carbonatades**

A la teva Base de Càlcul descrius el mètode Schmertmann literalment: E = 2.5 × qc (sabates aïllades), on qc = n × N amb "factors de conversió per cada tipus de material". Si fem els números al revés per Bell-Lloc (E=650, N=54), surt n≈4.8 — molt per sobre dels valors clàssics (2.5 / 2.0 / 1.25). Entenem que per materials **cementats** (graves carbonatades, lutites alterades com les d'Alcoletge on E>400) empres un factor n més alt, o directament puges E per criteri professional. Com ho decideixes? Si tens alguna regla pràctica del tipus "per carbonatades, n=4-5" o "per cementats, prenc el valor alt de D.23", ens ajudaria.

(Col·lateralment: al teu informe l'encapçalament de la taula ja ens confirma que N=54 és l'SPT del sondeig, no un N20 corregit. Això ja ho tenim clar.)

**3. Qa — Topall o càlcul?**

Quan Terzaghi clàssic i Terzaghi-Peck donen valors diferents, quin prevalia? I el 3.0 kg/cm² que surt en la majoria de projectes, és resultat del càlcul o un topall pràctic?

**4. Confirmació — c i phi cohesius (Crespo Villalaz Tabla 11.2)**

Ens hem mirat el "Mecánica de suelos y cimentaciones" de Crespo Villalaz (5a ed., p.175, Tabla 11.2 "En arenas"). La fila "muy floja" dóna φ=28° per Ncorr=0-4, i la nota inferior diu "el limo un φ=20°". La nostra hipòtesi és que, per materials transicionals (llim argilós, sorres argiloses com els de Linyola, Alcoletge, o el rebliment de molts projectes), tu apliques el topall de **φ=28°** (fila "muy floja") independentment de l'N real, com a valor conservador. Ho confirmes?

Moltes gràcies!

---

**Notes internes (no enviar):**

- Preguntes 1 i 2 (Nb + Bell-Lloc) són les que queden realment obertes
- Pregunta 3 (Qa topall) — menys urgent, però val la pena tancar-la
- Pregunta 4 (Tabla 11.2 confirmació) — si Eva confirma → podem afegir el flag `fine_fraction="transitional"` com a path automàtic per alguns conceptes (p.ex., `sondeig_layer_desc` que contingui "argiloses" o "llimoses"). Si no confirma → ens explica el veritable criteri i ajustem.

**Resoltes des de v3:**
- Crespo Tabla 11.2 localitzada (Ch.11 p.175, no Ch.22 com indicava un hint inicial)
- 28° anchor = "muy floja sand" + criteri conservador per transicionals
- Tota la metodologia d'Eva (Qa caps + Crespo/Hunt + Schmertmann qc + bicapa) codificada al pipeline (commit d70030c, 379 tests)
