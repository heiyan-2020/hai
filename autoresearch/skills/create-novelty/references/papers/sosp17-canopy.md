# Canopy: An End-to-End Performance Tracing And Analysis System
SOSP'17 · Jonathan Kaldor, Jonathan Mace et al. / Facebook, Brown University · Full text: https://cs.brown.edu/~jcmace/papers/kaldor2017canopy.pdf (camera-ready from author homepage, with ACM DOI) · Selected: Community favorite (3 sources: Harvard CS260r 2019, Morning Paper, UIUC CS598 2018)

**One sentence**: Instrumentation is the hardest part to change, but the model must change often, so instrumentation records only generic events and the backend builds the model. Analysis needs only a few features computed per trace, so they are precomputed into tables as a stream.

## Problem
One Facebook page load spans the browser, mobile clients and many backend services. The symptom and the root cause of a performance regression are often in different layers. Engineers work from hypotheses and need to slice, group and compare interactively.
There are 1.3 billion traces per day. A browser trace has over 4500 events, a mobile one over 7500. Before, each domain had its own tracing, nobody could see across systems, the analysis pipelines were fixed, and one change took days.

## Strawman / Baseline
- **Build the high-level model directly into the instrumentation (Dapper's span tree, Zipkin, HTrace)**: instrumentation is easy to write and results are easy to read. → Queues, asynchrony and multi-parent dependencies cannot be expressed. Changing the model means redoing all instrumentation. A trace crosses many services with different instrumentation versions; Accumulo and Hadoop were hurt by an incompatible HTrace upgrade.
- **Give engineers the low-level event graph directly**: → nobody understands the event semantics of all components, and clients often drop events.
- **Ad hoc queries over raw traces, or black-box causal inference**: → too much computation at this data volume; Mystery Machine takes 2 hours to build a model from 1.3 million traces.

## Novelty
1. **Instrumentation is the hardest to change, so build the model in the backend**
   Insight: Instrumentation is compiled into each service and ships with each release, so it is the slowest and most expensive part to change. The high-level models people need keep changing with new uses.
   So: Each execution model (threads, continuations, RPC) has its own narrow API, but all of them emit the same generic events (22 types in total), with a TraceID and causal references, forming a DAG. The backend then interprets the events into one unified model (execution units, blocks, points, edges). Along the way it fills in missing end events, corrects errors, and aligns clocks across machines using causal edges. Changing the model needs no change to instrumentation, which targets the root cause of "model built into instrumentation".
2. **Analysis needs a few per-trace features, not the traces themselves**
   Insight: Most questions are answered by slicing on combinations of a few features (latency, critical-path breakdown, country, etc.). Each feature depends only on one trace, and causality within one trace is already computed.
   So: Shard by TraceID, with no communication between shards. Stateless user-written extraction functions run on each trace once it is complete and produce some rows, which are written into Scuba (an in-memory column store) for slicing in seconds. Raw events stay in HBase for drill-down and for computing new features on old traces. This gets around the compute wall of "ad hoc queries over all traces".

Other design: User-defined sampling policies sit on top of a global token bucket (default 5 traces/s per tenant). Events are not guaranteed to arrive, so processing starts on a trigger timeout. Per-tenant isolated queues use deficit round-robin; overflow goes to delayed extractors.

## Evidence
- End to end: 2 years in production, 1.3 billion traces per day, event traffic 1.16 GB/s, datasets grew from 35 to 129, backend uses <0.1% of data-center resources. Overhead: median web request time +2.14%, median Android cold start +10.78% (finest granularity), backend ServiceA +8.15%, ServiceB <1%. Cases: a 300 ms (13%) page regression traced to 10 kB of extra CSS from the UserInput component; a query missing an index was found, making the query 99% faster and the page 50% faster.
- Novelty 1 → the RPC model went through 4 versions, and old instrumentation mapped to each new model; HTrace was also connected. These are cases with no measure of instrumentation effort: no direct ablation.
- Novelty 2 → over 6 months, of 2,852 columns in 45 datasets, the median column was used by only 70 queries; the most used, page latency, was used 23,224 times. Interactive query latency was not measured: no direct ablation.
- Other: 99.5% of traces were processed directly from cache; <0.03% were processed twice. A Mobile load spike was injected by mirroring production traffic, and other tenants' output was not affected.
- Gaps: No comparison with other tracing systems, and no measure of faster diagnosis; the evidence is experience reports and cases. The DSL was not expressive enough, and exploratory analysis moved to iPython.

## When it applies
The traced actions must have a clear start and end, and the organization must be able to pass TraceIDs uniformly in core frameworks. A single request that was not sampled cannot be looked up. Long-running dataflows and multi-origin scenarios do not fit.
