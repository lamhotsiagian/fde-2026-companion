# Capacity, cost and latency models

`fde_capacity_model.xlsx` — five worked models, all live formulas. Yellow cells are inputs;
change one and the sheet moves. `build_model.py` regenerates the workbook.

| Sheet | Answers | Default result |
|---|---|---|
| **GPU Sizing** | How many GPUs for N concurrent users? | 3 H100s (2 + HA), ~$9.9K/month |
| **RAG Cost per 1K** | What does a query cost? | $11.30 per 1,000 queries after caching |
| **Voice Latency** | Where does the 800ms go? | Exactly 800ms, zero headroom |
| **Self-host Breakeven** | Build or buy? | API wins below ~2,800M tokens/month |
| **Business Value** | What's the ROI? | ~3.0 month payback on a $400K build |

## Three things this model does that most don't

**GQA is in the KV math.** KV bytes per token is `2 × layers × (d × kv_heads/attn_heads) × bytes`.
Drop the head ratio and you overstate KV memory 8× on any modern 70B-class model — and then
buy 8× the GPUs. The sheet flags whether you are compute-bound or KV-bound.

**Reranking is priced per call, not per document.** Rerankers bill per search call covering
up to ~100 documents. Pricing it per document made reranking 78% of query cost in an early
draft of this model. It is closer to 12%.

**There is a realisation rate.** Saved minutes are not recovered dollars unless headcount or
contracted capacity actually changes. The sheet defaults to 30%. A model without this line
produces sub-one-month paybacks and no CFO believes it.

## Using it in a customer conversation

Fill the yellow cells live, on the call, with their numbers. The sheet is deliberately ugly
and legible rather than polished — a model the customer watched you build is worth more than
a deck they watched you present.
