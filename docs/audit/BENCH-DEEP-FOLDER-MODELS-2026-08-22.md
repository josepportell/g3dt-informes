# Benchmark `deep_folder_classify` — models (2026-08-22)

27 fitxers reals que el pipeline ha enviat a visió (Tulipa, Rubí, Bell-lloc). Prompt i imatges idèntics al codi de prod (`deep_folder_classifier._VISION_USER_PROMPT`, 1 imatge/fitxer). gpt-4.1-mini via el codi de prod (API OpenAI directa); la resta via OpenRouter. Cada model en sèrie en el seu propi fil (els 5 fils en paral·lel).

## Resum

| Model | OK | ERR | latència mediana | p90 | total | tokens in/out (mitjana) | cost/fitxer | acord amb gpt-4.1-mini |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| gpt-4.1-mini | 27/27 | 0 | 1.78 s | 2.69 s | 46 s | 0 / 0.0 | $0.0000 | 27/27 |
| sonnet-5 (no-think) | 25/27 | 0 | 3.49 s | 4.65 s | 96 s | 2296 / 7.2 | $0.0047 | 25/27 |
| sonnet-5 (adaptive,low) | 27/27 | 0 | 3.43 s | 4.89 s | 95 s | 2296 / 5.9 | $0.0047 | 25/27 |
| sonnet-4.6 (no-think) | 27/27 | 0 | 2.37 s | 3.50 s | 65 s | 1265 / 5.9 | $0.0039 | 25/27 |
| gpt-5.6-luna (minimal) | 27/27 | 0 | 2.22 s | 2.91 s | 59 s | 2055 / 6.1 | $0.0004 | 24/27 |

(tokens de gpt-4.1-mini no capturats pel camí de prod — cost estimat amb els d'entrada de Sonnet, que compten imatges semblant)

## Per fitxer

| Projecte | Fitxer | gpt-4.1-mini | sonnet-5 (no-think) | sonnet-5 (adaptive,low) | sonnet-4.6 (no-think) | gpt-5.6-luna (minimal) |
|---|---|---|---|---|---|---|
| Tulipa | `ULIPA/PDF/ANNEXES/3001706_fotografies_CASA 1.pdf` | field_photo (4.2s) | field_photo (6.6s) | field_photo (6.7s) | field_photo (4.8s) | field_photo (4.9s) |
| Tulipa | `ULIPA/PDF/ANNEXES/3001706_tall de correlació.pdf` | situation_plan (1.9s) | ?geotechnical_cross_sectio (4.7s) | other (5.0s) | other (2.8s) | other (2.0s) |
| Tulipa | ` CARRER TOSCA/PDF/3001706_fotografies_CASA 2.pdf` | field_photo (3.4s) | field_photo (5.5s) | field_photo (5.3s) | field_photo (3.6s) | field_photo (4.5s) |
| Tulipa | ` CARRER TOSCA/PDF/3001706_tall de correlació.pdf` | situation_plan (1.8s) | ?geological_cross_section
 (3.7s) | other (3.7s) | other (2.7s) | other (2.6s) |
| Tulipa | `PETICIÓ PRESSUPOST ESTUDI GEOTÈCNIC/image001.jpg` | signature_image (0.8s) | signature_image (2.5s) | signature_image (2.8s) | signature_image (1.4s) | signature_image (1.5s) |
| Rubí | ` WhatsApp 2025-11-14 a les 11.17.54_936f3908.jpg` | dpsh_sheet (2.6s) | dpsh_sheet (3.3s) | dpsh_sheet (4.0s) | dpsh_sheet (2.8s) | dpsh_sheet (2.3s) |
| Rubí | ` WhatsApp 2025-11-14 a les 11.49.21_a3e04224.jpg` | field_photo (1.6s) | field_photo (4.2s) | field_photo (3.4s) | field_photo (3.5s) | dpsh_sheet (2.9s) |
| Rubí | `FOTOGRAFIES/P2.jpg` | field_photo (2.0s) | field_photo (3.8s) | field_photo (3.7s) | field_photo (2.9s) | field_photo (2.9s) |
| Rubí | `FOTOGRAFIES/P3.jpg` | field_photo (2.7s) | field_photo (5.5s) | field_photo (4.9s) | field_photo (3.4s) | field_photo (3.0s) |
| Rubí | `validation/msg_attachments/PRESSU/image001.jpg` | signature_image (0.8s) | signature_image (2.5s) | signature_image (2.4s) | signature_image (1.3s) | signature_image (1.3s) |
| Rubí | `validation/msg_attachments/PRESSU/image005.png` | signature_image (0.8s) | signature_image (2.4s) | signature_image (2.7s) | signature_image (1.5s) | signature_image (1.0s) |
| Rubí | `lidation/msg_attachments/RE_ PRESSU/image005.jpg` | signature_image (0.7s) | signature_image (2.5s) | signature_image (2.6s) | signature_image (2.4s) | signature_image (1.0s) |
| Rubí | `lidation/msg_attachments/RE_ PRESSU/image006.jpg` | signature_image (0.7s) | signature_image (2.6s) | signature_image (2.7s) | signature_image (1.4s) | signature_image (1.5s) |
| Bell-lloc | `FOTOGRAFIES/DPSH/P2.jpg` | field_photo (2.5s) | field_photo (4.5s) | field_photo (3.6s) | field_photo (3.6s) | field_photo (2.2s) |
| Bell-lloc | ` WhatsApp 2025-10-01 a las 12.54.41_ccbf024a.jpg` | field_photo (1.9s) | field_photo (3.9s) | field_photo (3.8s) | field_photo (2.5s) | field_photo (2.5s) |
| Bell-lloc | ` WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` | field_photo (1.8s) | field_photo (4.2s) | field_photo (3.4s) | field_photo (3.4s) | field_photo (2.4s) |
| Bell-lloc | ` WhatsApp 2025-10-01 a las 12.55.21_2f75bf2a.jpg` | field_photo (1.8s) | field_photo (3.0s) | field_photo (3.5s) | field_photo (1.9s) | field_photo (1.8s) |
| Bell-lloc | ` WhatsApp 2025-10-01 a las 12.54.57_83d08c82.jpg` | field_photo (2.1s) | field_photo (3.5s) | field_photo (3.4s) | field_photo (2.7s) | field_photo (2.6s) |
| Bell-lloc | ` WhatsApp 2025-10-06 a las 12.03.25_47ce45a0.jpg` | field_photo (2.9s) | field_photo (3.4s) | field_photo (4.2s) | field_photo (2.5s) | field_photo (2.9s) |
| Bell-lloc | ` WhatsApp 2025-10-06 a las 12.03.36_f091c815.jpg` | field_photo (1.6s) | field_photo (3.5s) | field_photo (3.5s) | field_photo (2.2s) | field_photo (2.3s) |
| Bell-lloc | ` WhatsApp 2025-10-06 a las 12.53.10_6b9bc5f4.jpg` | field_photo (2.0s) | field_photo (3.7s) | field_photo (3.6s) | field_photo (2.3s) | field_photo (2.3s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image001.jpg` | signature_image (0.8s) | signature_image (2.5s) | signature_image (2.5s) | signature_image (1.4s) | signature_image (1.0s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image005.png` | signature_image (0.7s) | signature_image (2.7s) | signature_image (2.7s) | signature_image (1.6s) | signature_image (1.0s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image008.jpg` | field_photo (1.1s) | field_photo (2.6s) | field_photo (3.1s) | field_photo (1.8s) | field_photo (2.1s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image009.jpg` | field_photo (1.5s) | field_photo (3.7s) | field_photo (3.3s) | field_photo (2.0s) | field_photo (2.1s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image005.jpg` | signature_image (0.8s) | signature_image (2.6s) | signature_image (2.1s) | signature_image (1.4s) | signature_image (1.3s) |
| Bell-lloc | `_ Mestre Ramon Ortiz -  Jordi Bosch/image008.jpg` | signature_image (0.6s) | signature_image (2.5s) | signature_image (2.7s) | signature_image (1.4s) | signature_image (1.0s) |

## Conclusions (2026-08-22)

1. **Qualitat: empat pràctic en aquest conjunt.** 27 fitxers, 23 són fotos de camp / signatures de correu — trivials per a
   tots. Els 2 desacords reals són els `tall de correlació.pdf` (tall geològic): `gpt-4.1-mini` diu `situation_plan`
   (**error**, i `situation_plan` és un rol promovible al slot del plànol); Sonnet 5 sense thinking inventa una categoria
   millor (`geological_cross_section`) que el parser descarta → `failed` (innocu); Sonnet 5 adaptive-low, Sonnet 4.6 i
   GPT-5.6 diuen `other` (**correcte** segons el prompt). GPT-5.6 confon una foto WhatsApp de Rubí amb `dpsh_sheet`.
2. **Latència: Sonnet 5 és ~2× més lent que gpt-4.1-mini en aquesta crida** (3,4 s vs 1,8 s mediana; 4.6: 2,4 s; GPT-5.6:
   2,2 s). `deep_folder_classify` fa 5-14 crides **en sèrie** per obertura → +20-25 s amb Sonnet 5. Sonnet 5 consumeix
   ~1,8× més tokens d'entrada que 4.6 per la mateixa imatge (tokenitzador nou) — irrellevant en cost (0,5 ¢/fitxer) però
   pesa en latència.
3. **Recomanació per a `deep_folder_classify`: no canviar de model ara.** El guany de Sonnet 5 és en intel·ligència, i
   aquesta crida no en necessita. Si es vol treure l'error del `tall` amb gpt-4.1-mini, és més barat afegir la categoria
   `geological_section` al prompt que canviar de model.
4. **On sí que cal provar Sonnet 5: la visió difícil** — `dpsh` (manuscrit, 50-78 s i 4-7k tokens de sortida amb 4.6) i
   `sondeig`/`sondeig_annex`. Allà hi ha (a) marge de qualitat real, (b) ground truth (N20 de l'Excel DPSH), i (c) un
   throughput anunciat superior (56 vs 38 tok/s) que reduiria la fase més llarga dels prefills. Proposta: A/B `dpsh` +
   `sondeig` Sonnet 5 vs 4.6 sobre Tulipa, Rubí, Bell-lloc + 2 projectes de referència amb comparació N20 vs Excel i
   cotes de rebuig vs `eva_reference_values.json`. ~30 min, < 2 $ d'OpenRouter.
5. Sonnet 5 per l'SDK Anthropic via OpenRouter funciona tal qual (`thinking={"type":"disabled"}` i
   `output_config.effort` via `extra_body` acceptats); **cal** desactivar o acotar el thinking quan `max_tokens` és petit,
   si no el pressupost se'n va al raonament.
