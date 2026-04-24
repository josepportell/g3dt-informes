# Cheap Vision LLMs — Pricing Reference

**Last updated:** 2026-04-24
**Purpose:** Reference pricing for vision-capable LLMs that could replace/augment Anthropic Sonnet for specific tasks in the AI pipeline (especially image-classification pre-filters like the D1 logo filter).

> ⚠️ Pricing changes frequently. Confirm current rates at the provider before committing to a choice.

## Top 10 cheapest paid vision LLMs (Apr 2026)

| Rank | Model                          | Input $/1M | Output $/1M | Provider notes                                      |
|------|--------------------------------|------------|-------------|-----------------------------------------------------|
| 1    | Gemma 3 12B                    | $0.04      | $0.13       | OSS, strong vision                                  |
| 2    | Gemma 3 4B                     | $0.04      | $0.08       | OSS, lightweight vision                             |
| 3    | GPT-5 Nano                     | $0.05      | $0.40       | Closed, efficient multimodal                        |
| 4    | Nova Lite 1.0                  | $0.06      | $0.24       | Closed, good for images                             |
| 5    | Qwen3.5-Flash                  | $0.07      | $0.26       | OSS, video/image support                            |
| 6    | Gemma 4 26B A4B                | $0.07      | $0.35       | OSS MoE, advanced vision                            |
| 7    | Gemini 2.0 Flash Lite          | $0.07      | $0.30       | Google's fast lite vision                           |
| 8    | Mistral Small 3.2 24B          | $0.07      | $0.20       | OSS, reliable multimodal                            |
| 9    | Llama 4 Scout (Groq)           | $0.08/$0.11| $0.30/$0.34 | Meta's MoE vision model, ultra-fast on Groq        |
| 10   | Qwen3 VL 8B Instruct           | $0.08      | $0.50       | OSS VL specialist (SiliconFlow ~$0.05 equiv.)       |

## Comparison anchors

For reference against what we currently use in the AI pipeline:

| Model                    | Input $/1M  | Output $/1M | Ratio vs Gemma 3 4B (input) |
|--------------------------|-------------|-------------|-----------------------------|
| **Gemma 3 4B**           | $0.04       | $0.08       | 1×                          |
| **Llama 4 Scout (Groq)** | $0.08       | $0.30       | 2×                          |
| **gpt-4.1-mini**         | $0.40       | $1.60       | 10×                         |
| **Claude Sonnet 4.6**    | $3.00       | $15.00      | 75×                         |
| **Claude Opus 4.7**      | $15.00      | $75.00      | 375×                        |

## Relevance to the AI pipeline

### D1 — Logo filter pre-Stage 4 (per-image logo/not-logo classification)

**Task shape:** one vision call per extracted image, comparing against a reference G3DT logo → `yes/no + confidence`. Very small prompt, very small output.

**Estimated cost per image** (~1500 input tokens for 256×256 image + ~10 output tokens):
- Gemma 3 4B (if available cheaply): ~$0.00006
- Llama 4 Scout (Groq): ~$0.00015
- gpt-4.1-mini: ~$0.0006
- Sonnet 4.6: ~$0.0045 (75× Gemma)

For the 54 extracted images in Alcoletge:
- Gemma 3 4B: ~$0.003
- Llama 4 Scout: ~$0.008
- gpt-4.1-mini: ~$0.032
- Sonnet 4.6: ~$0.25 (what we paid today for logo analysis)

**Savings vs doing this in Stage 4:** current Stage 4 cost per logo source was ~$0.01-0.05 (full concept-YAML context + vision call). Logo-filtering pre-Stage 4 with a cheap provider saves $0.20-0.40 per project.

### D16 — prompt caching on concept YAML + glossary

Anthropic's prompt caching makes the static-context overhead cheap on repeat calls:
- Normal input: $3.00/1M
- Cached input read: $0.30/1M (10% of normal, 5-min TTL)
- Cache write premium: $3.75/1M (25% markup on first write)

For 72 sources × 3.5k static tokens = 252k tokens of static context:
- Without cache: 252k × $3.00/1M = $0.76 (we paid this)
- With cache (1 write + 71 reads): 3.5k × $3.75/1M + 248.5k × $0.30/1M = $0.013 + $0.075 = $0.088
- **Savings: ~$0.67 per full run** (≈ 16% of Alcoletge's $4.06)

## Providers we already have wired

Per `.env` on this dev system:
- **OpenAI** (`OPENAI_API_KEY`) → gpt-4.1-mini already used for vision
- **Anthropic** (`ANTHROPIC_API_KEY`) → Sonnet/Opus for Stage 4
- **Groq** (`GROQ_API_KEY`) → Llama 4 Scout for some text mining

Provider we'd need to add for absolute-cheapest (Gemma):
- **OpenRouter** — aggregator that hosts Gemma variants; single API key, pay-as-you-go
- **HuggingFace Inference** — hosts Gemma directly
- **Fireworks / Together** — also host Gemma

Recommended default for D1 logo-filter implementation: **gpt-4.1-mini** (zero new integration cost). Add provider abstraction so we can swap to Gemma later with a config flag.

## Historical context

The price of the cheapest vision-capable LLM has dropped from ~$1.00/1M in 2023 to ~$0.04/1M in 2026 (~25× cheaper in 3 years). Expect further drops — revisit this table every 6 months.
