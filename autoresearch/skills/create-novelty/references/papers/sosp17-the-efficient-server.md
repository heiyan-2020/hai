# The Efficient Server Audit Problem, Deduplicated Re-execution, and the Web
SOSP'17 · Cheng Tan, Lingfan Yu, Joshua B. Leners, Michael Walfish / NYU, Two Sigma · Full text: http://www.cs.nyu.edu/~mwalfish/papers/ssco-sosp17.pdf (camera-ready from author homepage; proofs in the extended version arXiv:1709.08501) · Selected: Best Paper

**One sentence**: Most web requests take the same code paths and compute on the same data, so they can be merged and replayed for auditing. The log the server provides is untrusted and is treated only as assertions checked one by one afterwards.

## Problem
A company puts PHP+SQL web applications (wikis, forums, review systems) in the cloud, but trusts no layer of the cloud: hardware, hypervisor, OS and the PHP runtime may all be faulty or compromised.
The company can capture the real request/response trace at the boundary, and the server can also hand over a log (untrusted). The auditor must decide whether each response was really computed by the program. The cost must be far less than re-running every request, and the server must be allowed to process requests concurrently.

## Strawman / Baseline
- **Re-run every request one by one**: the auditor must be as powerful as the server. Concurrent requests read and write a shared database, and re-running out of order cannot reproduce the values that were read at the time.
- **Record-replay, using the read values recorded in the log during replay (Poirot, LEAP)**: → the server can forge a log that is consistent with a false response, and replay then "reproduces" the false response and judges it correct. Making the server hand over the thread schedule can be forged just as well. Letting the auditor search for a schedule itself lets the adversary make the search fail, so a correct execution is wrongly rejected.
- **Verifiable computation / probabilistic proofs**: no concurrency support, and server overhead of at least 6 orders of magnitude.
- **SGX, TPM remote attestation**: proves only that a certain software stack is running, not that the program ran correctly on this possibly buggy stack. **AVM untrusted VM replay**: single core only, and no speedup.
- **Check only by log ordering**: requiring a total order wrongly rejects legal concurrency; using only a partial order lets through responses for which no schedule exists; only checking the log for cycles lets through responses that violate real-time order.

## Novelty
1. **Much computation is identical across requests, so replay can be "vectorized on demand"**
   Insight: Requests to the same web application take only a few control-flow paths, and pages seen by different users are very similar. So within a group of requests, most instructions have exactly the same operands.
   So: The server records a control-flow digest for each request. The auditor groups requests by digest and runs one "superposed" execution per group: each variable holds a multi-value vector. Where all requests have the same value, it collapses to a single value computed once; only differing values are computed one by one. The grouping itself is untrusted, but a wrong grouping makes the execution diverge, and a missing grouping makes the outputs mismatch; both are rejected.
   This removes exactly the cost of "re-run one by one", without trusting the log.
2. **Read values in the log need not be trusted on the spot, as long as the writes they depend on are all verified in the end**
   Insight: Whether a read is correct depends only on whether the write before it in the log is real. And every write is produced by some replayed request, so it can be checked when replay reaches it.
   So: During replay, a read is fed the value of the previous write in the log; a write is checked by comparing the operands computed by replay with those in the log. If all writes check out, all reads are proven retroactively. To block false responses that are consistent with a false log, a graph is built before replay: nodes are request arrivals, response departures and each log operation; edges are real-time order in the trace, program order and log order. If the graph is acyclic, there exists a schedule consistent with external observation. Real-time edges are generated in one pass over the trace, in time linear in the number of requests plus the number of needed edges, one log factor less than existing algorithms.
   This answers exactly the root cause of record-replay: the log is used, but never trusted. The extended version proves two properties: a misbehaving server is always rejected (soundness), and a correct execution is always accepted (completeness).

Other design: Database reads are answered by a versioned DB using log sequence numbers, and identical SELECTs on the same version are deduplicated. Non-deterministic return values such as time and pid get plausibility checks.

## Evidence
- End to end (system name Orochi): MediaWiki (2007 Wikipedia trace, 20,000 requests), phpBB (30,000), HotCRP (52,000). Audit CPU is 10.9×, 5.6× and 6.2× less than "re-run once" (measured as the original server's CPU, pessimistic for Orochi). Server CPU overhead 4.7%–8.6%, throughput down 11.1%–17.8%, including the cost of forcing the database to use strict serializability (transactions appear to run one by one in real-time order).
- Novelty 1 → instruction-level microbenchmarks show multi-value execution is slower than running n times separately; all the speedup comes from collapsing. MediaWiki has 527 groups, 237 of which have more than 1 request; in all groups, single-value instructions are >95%. No end-to-end comparison with collapsing turned off.
- Novelty 2 → proofs only; no experiment injecting a misbehaving server. Ordering checks take a small share in the CPU breakdown.
- Gaps: The baseline is a hypothetical re-run lower bound, with no real competitor. Non-determinism of PHP built-in functions is outside the proof, and the server can still choose its schedule, so the real system does not reach theoretical soundness. Applications need small changes (MediaWiki 346 lines, phpBB 270 lines, HotCRP 67 lines). The auditor must keep a copy of the database.

## When it applies
Needs a trusted point for collecting the trace, and requests must have high repetition in control flow and data. The application hardly interacts with external services, and database transactions do not nest operations on other shared objects.
