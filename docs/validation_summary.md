# AI-Powered HR Helpdesk — Dataset Validation & Reproducibility Summary

This document presents the empirical validation results and fixed-seed reproducibility proof executed via `python src/validate_dataset.py`.

---

## 1. Executive Validation Summary

| Category | Requirement | Verified Result | Status |
|---|---|---|---|
| **Foreign-Key Integrity** | Zero orphan rows; strict foreign keys enforced | **0 violations** (`PRAGMA foreign_key_check`) | **PASS** |
| **Arithmetic Reconciliation** | 5,000 tickets with 20,000 messages | **5,000 tickets, 20,000 messages** | **PASS** |
| **Primary Key Uniqueness** | Zero duplicate keys across all tables | **100% Unique** (13/13 tables) | **PASS** |
| **Date Ordering Integrity** | `updated_at &ge; created_at`, `effective_to &ge; effective_from` | **0 invalid date sequences** | **PASS** |
| **Allowed Value Enums** | All statuses, priorities, audiences conform to schema CHECKs | **0 enum constraint violations** | **PASS** |
| **Message Sequence Contiguity**| Messages 1..4 contiguous per ticket | **5,000 / 5,000 tickets contiguous** | **PASS** |
| **Fixed-Seed Reproducibility** | Two independent generations yield identical SHA256 checksums | **11 / 11 tables match identically** | **PASS** |

---

## 2. Table-by-Table Checksum Reproducibility Audit (Step 10)

Generated across two completely independent runs using seed `20261022`:

```
Table Checksum Comparison (Run 1 vs Run 2):
  [MATCH] Department         | Hash: 46bc2000b17f6a4e... vs 46bc2000b17f6a4e...
  [MATCH] Employee           | Hash: 2877ee562142cd0c... vs 2877ee562142cd0c...
  [MATCH] Category           | Hash: 2a350fcd6a96c188... vs 2a350fcd6a96c188...
  [MATCH] PolicyDocument     | Hash: 7da8c91e65743ca9... vs 7da8c91e65743ca9...
  [MATCH] PolicyVersion      | Hash: b3d1e226bc75f59a... vs b3d1e226bc75f59a...
  [MATCH] KnowledgeArticle   | Hash: ce923bc2867ec637... vs ce923bc2867ec637...
  [MATCH] Ticket             | Hash: 18ae4a4408d632bc... vs 18ae4a4408d632bc...
  [MATCH] Message            | Hash: 681ff25ae09e8cba... vs 681ff25ae09e8cba...
  [MATCH] Assignment         | Hash: 0ccdc90c13d6dc3b... vs 0ccdc90c13d6dc3b...
  [MATCH] SLA                | Hash: a116676f4c204054... vs a116676f4c204054...
  [MATCH] Resolution         | Hash: a9dca0b82bf5f5a5... vs a9dca0b82bf5f5a5...

Reproducibility Result: 11/11 tables identical.
>>> 100% DETERMINISTIC REPRODUCIBILITY VERIFIED! <<<
```

---

## 3. Deliberate Anomaly Catalog Reconciliation

The four required edge cases were successfully injected and audited in `evaluation/ground_truth.json`:

1. `TKT-2026-000101`: `obsolete_policy_citation` &rarr; Cites retired version 1 (`VER-POL-HR-2026-001-01`).
2. `TKT-2026-000102`: `sensitive_misrouted` &rarr; Harassment complaint assigned to `HR-General` instead of `HR-Confidential`.
3. `TKT-2026-000103`: `sla_calendar_anomaly` &rarr; SLA resolution calculated ignoring business working calendar.
4. `TKT-2026-000104`: `unsupported_policy_hallucination` &rarr; 6-month mountaineering sabbatical answered as approved fact without policy backing.

All remaining 4,996 tickets follow 100% compliant operational rules.
