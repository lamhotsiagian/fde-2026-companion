# Evaluation spec — [system]

## Golden set
- **Size:** ___ examples · **Built by:** ___ (a domain expert, not an engineer)
- **Slices:** by document type, line of business, user role, difficulty
- **Refresh:** ___ new examples/month drawn from production failures

## Scorers
| Scorer | Type | Threshold | Gate? |
|---|---|---|---|
| Retrieval recall@k | deterministic | ≥ 0.90 | yes |
| Citation present | deterministic | ≥ 0.98 | yes |
| Faithfulness | LLM judge | ≥ 0.92 | yes |
| Refusal when unsupported | deterministic | = 1.00 | yes |
| Answer helpfulness | human, sampled | ≥ 4.0/5 | no |

Deterministic scorers first, judges last. A judge is the most expensive and least stable
scorer you own — pin the judge model, randomise option order, never let one gate a release alone.

## Regression gate
Any gated metric dropping more than **2 percentage points** against baseline blocks the merge.
Overriding requires a named person and a written reason in the PR.

## Online
Sample ___% of production traffic daily. Alert on a 7-day slope, not a single bad day.

## Review
Weekly with the customer for the first 6 weeks. Bring the failures, not the averages.
