| Case ID | Size | Scenario | Expected | Actual | Uniqueness | Steps | Vars (Pri/Aux) | Clauses | SAT Calls | Dec | Back | Runtime (s) | Notes |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `case_3x3_inconsistent_conflict` | 3x3 | contradictory_clues | INCONSISTENT | **INCONSISTENT** | NO_SOLUTION | 0 | 9/0 | 10 | 1 | 0 | 0 | 0.00010 | contradictory_clues; Direct contradiction: SAME(A1,B1) vs DIFFERENT(A1,B1) |
| `case_3x3_stuck_missing_clues` | 3x3 | missing_clues | STUCK | **STUCK** | MULTIPLE | 0 | 9/2 | 14 | 8 | 7 | 0 | 0.00038 | missing_clues; Insufficient clues (7 cells remain ambiguous) |
| `case_4x4_inconsistent_cardinality` | 4x4 | contradictory_clues | INCONSISTENT | **INCONSISTENT** | NO_SOLUTION | 0 | 16/3 | 24 | 1 | 0 | 0 | 0.00018 | contradictory_clues; EXACTLY 2 vs PARITY ODD on row 1 |
| `case_4x4_stuck_ambiguous` | 4x4 | missing_clues | STUCK | **STUCK** | MULTIPLE | 2 | 16/0 | 27 | 35 | 0 | 0 | 0.00250 | missing_clues; Partial clues solve initial wave then become ambiguous |
| `case_5x5_stress_extensions` | 5x5 | stress_normal_30s | SOLVED | **SOLVED** | UNIQUE | 23 | 25/212 | 8842 | 161 | 313 | 4 | 0.45994 | stress_normal_30s |
| `case_5x5_stress_extensions` | 5x5 | tight_time_limit_0s | TIMEOUT | **TIMEOUT** | UNIQUE | 0 | 25/212 | 8842 | 0 | 1 | 0 | 0.00028 | tight_time_limit_0s |
| `case_5x5_stress_extensions` | 5x5 | step_limit_5 | STEP_LIMIT | **STEP_LIMIT** | UNIQUE | 5 | 25/212 | 8842 | 49 | 52 | 0 | 0.00397 | step_limit_5 |
