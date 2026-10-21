# Byzantine Ordered Consensus without Byzantine Oligarchy
OSDI'20 · Yunhao Zhang et al. / Cornell, Microsoft Research · Full text: https://www.usenix.org/system/files/osdi20-zhang_yunhao_0.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Ordering by "real-time precedence" has no cycles, and the median of 2f+1 timestamps is bounded by correct nodes' values. So the order can be fixed before consensus.

## Problem
Permissioned blockchains keep their ledger with BFT SMR (state machine replication), and the order of transactions directly decides profit: front-running bots have already made more than $6 million on Ethereum.
But SMR's correctness definition only requires all replicas to have the same order, whatever that order is. So "manipulating the order" is not a violation and cannot even be expressed.

## Strawman / Baseline
- **Leader-based BFT (PBFT, HotStuff, Concord)**: The leader decides which command goes into each slot → A Byzantine leader can set the order alone. The larger the batch, the more commands it can order at will.
- **Rotating leaders / accountability**: Only shortens the dictatorship. While it is leader, a node still sets the order, and there is no clear statement of what property should be guaranteed.
- **Leaderless protocols (Lamport, DBFT, HoneyBadgerBFT)**: Need O(f) rounds or randomized consensus, which is expensive, and still do not guarantee order.
- **Require that "an order all correct nodes prefer must be respected"**: With f=1, 4 nodes can form a Condorcet cycle (every pair of commands has 3 votes, but together they form a cycle), so it cannot be satisfied. Concurrent work on order-fairness therefore has to weaken it, and needs 4f+1 nodes.

## Novelty
1. **First ask "what can be guaranteed": influence cannot be removed, but oligarchy can**
   Insight: As long as node preferences can affect the result (free will), it is impossible to tell which node is Byzantine. So there must be cases where Byzantine nodes can sway the order (a theorem the authors prove). The reachable goal is: Byzantine nodes cannot set the order of any two commands they choose (Byzantine oligarchy).
   When preferences are expressed as timestamps, "c1 ends before c2 starts" is real-time precedence, which is acyclic by nature and avoids the Condorcet trap: if every correct node gives c1 a smaller timestamp than c2, then c1 must come first (ordering linearizability).
2. **The median timestamp is bounded by correct nodes, so the order can be fixed before consensus**
   Insight: Take the median of 2f+1 signed timestamps, dropping the f smallest and f largest. The result must fall between values given by correct nodes.
   So: Nodes first collect timestamps to get a position, then have 2f+1 nodes accept it (two RTTs). After that the leader only confirms that "commands in a given time interval are all collected". It cannot pick commands or change their order. Finally, commands are sorted by timestamp. This directly takes the ordering power away from the leader in leader-based BFT, while keeping the leader's efficiency.
3. **Let the leader safely declare "the prefix is stable"**
   Obstacle: A command that arrives late may carry a smaller timestamp and slip into a prefix that has already executed.
   So: Each consensus slot corresponds to a fixed time window. After a node confirms its clock has passed the end of the window and then waits another Δ, it rejects commands with earlier timestamps.

Other design: send only the hash of localSequencedSet to compress CollectResponse; a node can batch its own organization's commands and take one timestamp for the batch.

## Evidence
- End to end (n=4, one data center): Pompē-HS does 361,687 cmd/s with 53.1 ms consensus latency; HotStuff does 253,360 cmd/s with 49.9 ms. That is 1.4× higher throughput and 6% higher latency. Ordering latency is only 5.7 ms. Across three data centers: HotStuff drops to 2.4% of its single-data-center throughput, while Pompē-HS keeps 87.3% (consensus latency 1518 ms, HotStuff 916 ms). Network bytes are about 18% higher.
- Novelty 1, 2 → Only proofs, no adversarial experiments (such as injecting a Byzantine leader to measure front-running): no direct ablation.
- Novelty 3 → No direct ablation. Δ and the time window are fixed parameters.
- Gaps: The throughput advantage comes mainly from the implicit batching the time window brings (the effective batch is 82 without batching), not from removing the leader's ordering. As n grows, throughput falls as the per-node batch shrinks, and the scale-up numbers for n≥31 are predictions. A single Byzantine node can still flip the order within a small time window through the median timestamp. Getting a timestamp and then not submitting (selective submission) can only be mitigated.

## When it applies
Correct nodes' clocks must be roughly synchronized and network latency must be small. An adversary who can manipulate the network between correct nodes can bias timestamps. The ordering semantics must be expressible as "real-time precedence".
