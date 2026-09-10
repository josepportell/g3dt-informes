# Perfil logs Eva — 2026-05-04 → 2026-07-23 (14 dies, 8953 línies)

## 1. Quadre per projecte

| Projecte | Dies | Obertures | Informes OK | Crash generació | Crash prefills | Dates |
|---|--:|--:|--:|--:|--:|---|
| IA | 2 | 3 | 0 | 0 | 0 | 05-04, 05-06 |
| 4001712 AINET DE CARDOS | 1 | 1 | 0 | 0 | 0 | 05-06 |
| 3001710 PSG.VOLTOR ST.CUGAT | 1 | 1 | 1 | 0 | 0 | 05-28 |
| 3001697 ESPARRAGUERA | 1 | 2 | 2 | 0 | 0 | 06-01 |
| 4001723 BORGES BLANQUES | 1 | 1 | 2 | 0 | 0 | 06-03 |
| 4001731 PUIGVERD DE LLEIDA | 1 | 1 | 1 | 0 | 0 | 06-03 |
| 3001706 C.TULIPA CERDANYOLA | 1 | 3 | 0 | 0 | 0 | 06-04 |
| 4001715 BORDA BOSSOST | 1 | 1 | 1 | 0 | 0 | 06-04 |
| 3001727 CASTELLOLI | 1 | 1 | 1 | 0 | 0 | 06-10 |
| 3001708 MONTCADA I REIXAC | 1 | 1 | 1 | 0 | 0 | 06-10 |
| 3001705 C.SENTMENAT CERDANYOLA | 1 | 1 | 1 | 0 | 0 | 06-10 |
| 3001722 VACARISSES | 1 | 1 | 1 | 0 | 0 | 06-12 |
| 4001713 C.MAJOR BELLPUIG | 2 | 2 | 0 | 3 | 0 | 06-12, 06-18 |
| 4001739 BENAVENT DE SEGRIA | 1 | 1 | 1 | 0 | 0 | 06-17 |
| 4001735 SEROS | 1 | 1 | 1 | 0 | 0 | 06-23 |
| 3001725 AVD.CAN MIR RUBI | 2 | 4 | 0 | 0 | 4 | 06-23, 06-25 |
| 4001740 MONTARDIT DE BAIX | 1 | 1 | 0 | 0 | 0 | 07-08 |
| 3001741 CAMP FUTBOL BADALONA | 1 | 4 | 1 | 0 | 0 | 07-23 |
| 4001769 IVARS DE NOGUERA | 1 | 1 | 0 | 1 | 0 | 07-23 |

**Total:** 19 projectes · 31 obertures · 14 informes OK · 4 crashes de generació · 4 crashes de prefills

## 2. Tipus de crash (línia culpable → excepció)

- **4×** `cp1252.py", line 23, in decode` → `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d in position 97: character maps to <undefined>`
- **3×** `report_generator.py", line 1259, in _build_template_context` → `TypeError: '<=' not supported between instances of 'float' and 'NoneType'`
- **1×** `report_generator.py", line 1259, in _build_template_context` → `TypeError: '<=' not supported between instances of 'NoneType' and 'float'`

## 3. Temps d'espera dels prefills (obertura → prefills llestos)

| Data | Projecte | Minuts | Resultat |
|---|---|--:|---|
| 05-04 18:58 | IA | 11.7 | ok |
| 05-04 19:13 | IA | 1.9 | ok |
| 05-28 17:44 | 3001710 PSG.VOLTOR ST.CUGAT | 6.1 | ok |
| 06-01 07:44 | 3001697 ESPARRAGUERA | 9.8 | ok |
| 06-01 08:10 | 3001697 ESPARRAGUERA | 1.9 | ok |
| 06-03 12:36 | 4001723 BORGES BLANQUES | 6.9 | ok |
| 06-03 17:30 | 4001731 PUIGVERD DE LLEIDA | 7.7 | ok |
| 06-04 16:05 | 3001706 C.TULIPA CERDANYOLA | 7.7 | ok |
| 06-04 17:55 | 3001706 C.TULIPA CERDANYOLA | 8.7 | ok |
| 06-04 18:20 | 3001706 C.TULIPA CERDANYOLA | 2.2 | ok |
| 06-04 19:05 | 4001715 BORDA BOSSOST | 8.2 | ok |
| 06-10 12:03 | 3001727 CASTELLOLI | 7.0 | ok |
| 06-10 13:35 | 3001708 MONTCADA I REIXAC | 7.1 | ok |
| 06-10 18:23 | 3001705 C.SENTMENAT CERDANYOLA | 9.2 | ok |
| 06-12 07:46 | 3001722 VACARISSES | 5.9 | ok |
| 06-12 13:11 | 4001713 C.MAJOR BELLPUIG | 7.0 | ok |
| 06-17 15:51 | 4001739 BENAVENT DE SEGRIA | 6.0 | ok |
| 06-18 16:18 | 4001713 C.MAJOR BELLPUIG | 1.7 | ok |
| 06-23 11:02 | 4001735 SEROS | 8.9 | ok |
| 06-23 18:30 | 3001725 AVD.CAN MIR RUBI | 5.7 | ok |
| 06-23 18:36 | 3001725 AVD.CAN MIR RUBI | 0.9 | ok |
| 06-25 07:06 | 3001725 AVD.CAN MIR RUBI | 1.2 | ok |
| 06-25 07:28 | 3001725 AVD.CAN MIR RUBI | 0.8 | ok |
| 07-08 16:33 | 4001740 MONTARDIT DE BAIX | 10.2 | ok |
| 07-23 16:34 | 3001741 CAMP FUTBOL BADALONA | 8.5 | ok |
| 07-23 16:44 | 3001741 CAMP FUTBOL BADALONA | 7.4 | ok |
| 07-23 17:08 | 3001741 CAMP FUTBOL BADALONA | 15.9 | ok |
| 07-23 17:36 | 4001769 IVARS DE NOGUERA | 13.8 | ok |

**28 obertures** · mediana 7.1 min · màxim 15.9 min · ≥5 min en 21 casos

## 4. On van els minuts: espera HTTP per proveïdor i context

(temps entre la línia anterior i la resposta HTTP, atribuït a la línia de log que la consumeix)

### OpenAI — 59 min d'espera, 438 crides

| Minuts | Crides | Context |
|--:|--:|---|
| 24.5 | 129 | `vision_groq: OpenAI Vision: ok in Nms (N in + N out tokens, m` |
| 9.7 | 8 | `vision_groq: OpenAI Vision: Unterminated string starting at: ` |
| 9.1 | 265 | `g3dt.vision: VISION OK provider=openai model=gpt-N-mini file=` |
| 7.1 | 6 | `vision_groq: OpenAI Vision: Expecting property name enclosed ` |
| 4.7 | 4 | `vision_groq: OpenAI Vision: Expecting ',' delimiter: line N c` |
| 1.1 | 1 | `vision_groq: OpenAI Vision: Expecting value: line N column N ` |
| 1.0 | 9 | `schemas.format_writer: Saved learned format: learned_dpsh_excel_eNecdNe` |
| 0.6 | 2 | `smartscan.classifier: SmartScan: N entries found in IA` |

### Groq — 72 min d'espera, 1472 crides

| Minuts | Crides | Context |
|--:|--:|---|
| 24.5 | 301 | `vision_groq: Groq Vision: ok in Nms (N in + N out tokens)` |
| 13.6 | 320 | `vision_groq: Groq Vision: rate limited (attempt N/N)` |
| 5.2 | 162 | `vision_groq: Groq Vision: HTTP N {"error":{"message":"The mod` |
| 2.1 | 39 | `fileminer.miners.groq_miner: Groq: rate limited on validation\msg_attachments` |
| 1.0 | 27 | `vision_groq: Groq Vision: HTTP N {"error":{"message":"Too man` |
| 0.9 | 16 | `fileminer.miners.groq_miner: Groq: rate limited on ANNEXES\N_DPSHNxls, waitin` |
| 0.9 | 29 | `fileminer.miners.groq_miner: Groq API error for validation\msg_attachments\RE` |
| 0.8 | 15 | `smartscan.tier3_vision: Groq Tier N: ANNEXES/ALTRS/MNpng → figure_situat` |

### Anthropic — 49 min d'espera, 132 crides

| Minuts | Crides | Context |
|--:|--:|---|
| 27.7 | 29 | `vision_groq: Anthropic Vision: Expecting value: line N column` |
| 12.6 | 20 | `vision_groq: Anthropic Vision: ok in Nms (N in + N out tokens` |
| 2.4 | 28 | `wizard_service: LLM synthesis: N identity + N narrative + N adja` |
| 1.4 | 12 | `smartscan.tier3_vision: Claude Tier N: FOTOGRAFIES/SN/N A Njpg → photo_s` |
| 0.6 | 6 | `smartscan.tier3_vision: Claude Tier N: FOTOGRAFIA/WhatsApp Image N-N-N a` |
| 0.5 | 4 | `smartscan.tier3_vision: Claude Tier N: FOTOGRAFIES/PARTE DPH'SNjpeg → dp` |
| 0.5 | 4 | `smartscan.tier3_vision: Claude Tier N: FOTOGRAFIA/PNjpeg → photo_sondeig` |
| 0.4 | 4 | `smartscan.tier3_vision: Claude Tier N error for Annexes/ALT/MNpng: Error` |

## 5. Visió: resultat per proveïdor i tipus

| Proveïdor | Tipus | OK | FAIL | % FAIL |
|---|---|--:|--:|--:|
| anthropic | dpsh | 2 | 23 | 92% |
| anthropic | sondeig | 6 | 0 | 0% |
| anthropic | sondeig_annex | 12 | 6 | 33% |
| groq | dpsh | 2 | 8 | 80% |
| openai | deep_folder_classify | 265 | 0 | 0% |
| openai | dpsh | 13 | 10 | 43% |
| openai | planol | 19 | 0 | 0% |
| openai | projecte_arquitecte | 23 | 0 | 0% |
| openai | sondeig_annex | 6 | 0 | 0% |

**Motius de FAIL (últim WARNING previ):**

- 29× anthropic: `Anthropic Vision: Expecting value: line N column N (char N) (Nms)`
- 8× groq: `Groq Vision: HTTP N {"error":{"message":"The model `meta-llama/llama-N`
- 4× openai: `OpenAI Vision: Expecting property name enclosed in double quotes: line`
- 2× openai: `OpenAI Vision: Unterminated string starting at: line N column N (char `
- 2× openai: `OpenAI Vision: Expecting ',' delimiter: line N column N (char N) (atte`
- 1× openai: `OpenAI Vision: Expecting value: line N column N (char N) (attempt N/N)`
- 1× openai: `OpenAI Vision: The read operation timed out (attempt N/N)`

