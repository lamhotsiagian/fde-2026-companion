# FDE résumé bullets — the X-Y-Z pattern

> Accomplished **[X]**, measured by **[Y]**, by doing **[Z]**.

Reviewers spend under a minute. They are looking for: production ownership, a number,
and evidence you talked to a customer.

**Weak → strong**

| Weak | Strong |
|---|---|
| "Worked on a RAG chatbot" | "Cut analyst lookup time 38% (9→5.6 min, 200-case audit) by shipping permission-aware hybrid retrieval over 8M documents into the underwriting tool" |
| "Improved model accuracy" | "Raised faithfulness 0.71→0.94 on a 300-example golden set by adding a cross-encoder reranker and a citation gate, then held it with a CI regression gate" |
| "Deployed to production" | "Took a stalled 6-month pilot to production in 11 weeks for 400 users, clearing SOC 2 and a customer security review" |
| "Reduced costs" | "Cut inference spend 61% ($34K→$13K/month) via model routing and prompt caching, with no measured quality regression" |

**Checklist.** Every bullet has a number · at least three name a customer outcome, not a
technical artifact · at least one names a failure you recovered · no bullet needs the reader
to know your company's internal tooling.
