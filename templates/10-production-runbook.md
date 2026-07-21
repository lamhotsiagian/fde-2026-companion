# Runbook — [system]

**On-call:** · **Escalation:** · **Dashboards:** · **Traces:**

## Deploy
## Rollback
The command, tested. If it has not been tested this quarter, it does not work.

## Health checks
| Signal | Healthy | Alert at | Page at |
|---|---|---|---|
| p95 latency | | | |
| Error rate | | | |
| Eval score (daily) | | | |
| Token spend/hour | | | |
| Retrieval recall (sampled) | | | |

## Common incidents
| Symptom | Likely cause | First check | Fix |
|---|---|---|---|
| Answers suddenly vague | Retrieval returning nothing | Recall on the golden set | Check index freshness / ACL change |
| Cost spike | Loop, or a new heavy user | Top tenants by spend | Per-tenant cap |
| Latency spike | Provider degradation, or a stuck stream | TTFT vs total | Fail over, enable stuck detection |
| Wrong-tenant data | ACL regression | Permission-filter test | **Kill switch, then investigate** |

## Kill switches
How to pause tool access · how to disable the agent · how to revoke a credential.
Each with the exact command.

## Credentials
Where they live, who rotates them, how often.
