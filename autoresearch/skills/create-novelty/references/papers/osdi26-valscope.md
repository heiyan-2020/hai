# ValScope: Value-Semantics-Aware Metamorphic Testing for Detecting Logical Bugs in DBMSs
OSDI'26 · Li Lin, Liehang Chen, Rongxin Wu / Xiamen University · Full text: https://www.usenix.org/system/files/osdi26-lin-li.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Many logical bugs do not change the result rows; they only compute wrong values. A monotonic local change moves a value in a predictable direction, and this direction can be pushed level by level up the syntax tree to the whole query.

## Problem
Logical bugs make a DBMS silently return wrong results. The hard part is the test oracle: nobody knows the correct result of a complex SQL query.
Metamorphic testing (MT) sidesteps this: transform the query and check whether the results of the old and new queries satisfy an expected relation (metamorphic relation).
But existing relations cannot catch bugs where aggregation, ordering or arithmetic computes a wrong value while the row set stays the same. For example, on MySQL, SUM(DISTINCT c4*2) gives 72; after removing *2 it should give 36, but it returns NULL.

## Strawman / Baseline
- **PQS (generate queries around one pivot row and check that it is returned)**: reasons about one row at a time, so coverage is narrow.
- **Equivalence relations (NoREC, TLP)**: rewrite the query into an equivalent form and compare whether the results are the same → the rewrite keeps the original operators and functions, so both queries run the same buggy code and get the same wrong result.
- **Set approximation (Pinolo)**: loosen or tighten predicates and check containment between result row sets → it only looks at whether rows are in the result, not at how values are computed. When a value is wrong but the row set is unchanged, containment still holds. Aggregation collapses a group of rows into one value, which breaks set monotonicity, so Pinolo does not support GROUP BY, HAVING or aggregates.

## Novelty
1. **Values also change in a predictable direction**
   Insight: Many operators are monotonic in their input: replacing MAX with MIN can only make the value smaller, replacing COUNT(DISTINCT c) with COUNT(c) can only make it larger, and adding a positive number to expr can only make it larger.
   So: Design 9 value-semantics mutators (plus 17 set mutators). Align the results of the two queries by grouping key, and check per group whether the target column satisfies ≥ or ≤.
   A mutator replaces the operator itself (AVG→MAX), so the two queries run different code. This avoids exactly the root cause of equivalence relations, "the same bug computed twice". And it checks values, which covers what set approximation cannot see.
2. **The direction propagates up the syntax tree, and set relations and value relations convert into each other**
   Insight: Each SQL operator either preserves or reverses order. Aggregation turns "row set grows" into "value grows or shrinks"; a predicate turns "value grows" into "row set grows or shrinks".
   So: Walk from the mutation point up the ancestor chain to the root. At each level, look up a table to get the level conversion (set↔value) and a sign ±1. Multiply the signs to get the relation the whole query must satisfy. For example, with MAX→MIN in a subquery, after passing WHERE x>100 and an outer COUNT(*), we infer that the outer count should shrink.
   This lets mutations sit deep inside nested subqueries, GROUP BY and HAVING, breaking Pinolo's limit of not handling aggregation.

Other design: The query generator supports JOIN, CTE, GROUP BY/HAVING. Data includes boundary values, and the sign of some columns is fixed. Floats are compared with a tolerance; NULL is handled separately. Test cases are reduced with SQLess and deduplicated by the version that introduced the bug.

## Evidence
- End to end: about one month of testing MySQL, MariaDB, OceanBase, Percona, PolarDB and TiDB found 67 new logical bugs, 57 confirmed (23 in MySQL). 48 of them already existed before 2020; the oldest had been latent for 20 years. 61 of the 67 were found in the first 24 hours.
- Comparison: in the same 24 hours, ValScope found 61, which is 28, 10, 20, 36, 40 and 23 more than PQS, NoREC, TLP, DQP, Pinolo and EET respectively. When these 61 bugs were rewritten by hand into each baseline's test form, Pinolo could catch 12, DQP 6, TLP 4 and NoREC 2; 48 (78.9%) could be caught only by ValScope.
- Novelty 1 → of the 57 confirmed bugs, 43 violate a value-semantics relation. This is a classification count, not an ablation that turns off the value mutators: no direct ablation.
- Novelty 2 → 32 need propagation across both the set and value levels to be inferred. Also no direct ablation.
- Gaps: The baselines ran on the latest versions, and the paper itself says this made them less effective. ValScope's query generator is also richer, so it is impossible to separate how many extra bugs come from the oracle and how many from the generator. False-positive rate is not reported; results rely on manual checking.

## When it applies
It depends on monotonicity: non-monotonic functions such as ABS, ROUND and CASE can only be treated as one whole expression and tested by adding a monotonic transform outside them. Table 2 lists SUM as monotonically increasing, which holds only for non-negative values. Non-deterministic functions such as RAND() and NOW() are out of scope.
