# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols
OSDI'25 · Tony Nuda Zhang, Keshav Singh, Tej Chajed, Manos Kapritsos, Bryan Parno / U Michigan, UW–Madison, CMU · Full text: https://www.usenix.org/system/files/osdi25-zhang-tony.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Cross-host properties are all causal chains of "which step of whom wrote this value", and each link can be read statically from the steps of a single host.

## Problem
Proving a distributed protocol safe requires an inductive invariant: it holds initially, still holds after every step, and implies the safety property.
In a general-purpose (undecidable) logic such as Dafny, this can only be done by a person repeating "guess an invariant—proof fails—revise": IronFleet spent months on Multi-Paxos.

## Strawman / Baseline
- **Automatic inference (I4, DistAI, DuoAI, etc.)**: Requires the protocol to be written in EPR (a decidable fragment of first-order logic that forbids arithmetic and ∀∃ alternation). → It cannot even express i := i + 1; translation needs expertise and is sometimes impossible. All 16 protocols in this paper are outside EPR.
- **Kondo (OSDI'24)**: Automatically generates "local" invariants (monotonicity, resource ownership, message sending), but cross-host properties must be written by a person, such as "some participant decides Commit ⇒ the coordinator also decided Commit". → Paxos needs 20 hand-written ones, reportedly two person-weeks for an expert; each of its receive invariants needs a hint from a person.
- **Trace the source of each variable separately**: State separately that x came from some message and y came from some message. → This cannot prove that x and y came from the **same** message, so it is too weak.

## Novelty
1. **Cross-host properties can be split into a chain of "provenance" facts, and each provenance fact is naturally inductive**
   Insight: The receiver's current value must have been written by some step, usually one that received message M; and M must have been sent by some step of the sender, carrying the sender's state at that time. Joining these two links gives a relation "receiver state ↔ sender state".
   So: Add to the model an append-only, proof-only history (all past states of each host). Generate two kinds of Provenance Invariant: "every message of type M in the network was sent by some step T in the sender's history"; "if some non-initial local property of a host holds, some step T in the history made it true". The history is immutable, so each one is trivially inductive, with no search and no need for a decidable logic. Together with monotonicity invariants, they imply the cross-host properties that Kondo needs a person to write.
   This replaces the most creative part of IronFleet/Kondo, and also gets around EPR.
2. **"Which step wrote it" can be read statically from syntax: groups of variables that are always changed together**
   Insight: If a group of variables is always modified together by the same set of steps (an atomic shard: no step changes only part of it), then whenever they are not at their initial values, the latest modification must come from one of those steps, and all the variables were written by the same step.
   So: Use syntactic analysis to estimate which variables each step changes (its footprint), cut the largest atomic shards from intersections of footprints, and generate one provenance invariant per shard. The largest shards bind several fields to the same message, which solves the weakness of per-variable tracing; set-valued variables get their own shards and are traced to the source of each element. Overestimating a footprint only makes an invariant weaker, never wrong.
   So most provenance invariants need no hints, which removes Kondo's burden of a hint per invariant.

## Evidence
- End to end: 16 protocols (including Paxos variants, Raft leader election, and Multi-Paxos), all with 0 hand-written invariants; Kondo needs 20 on Paxos/Flexible Paxos and 4 on 2PC. Invariant generation <2 s, Multi-Paxos verification 61.5 s.
- Novelty 1 → 0 hand-written invariants shows directly that cross-host properties need no human writing. But the safety proof still has to be written by a person: Paxos 444 lines, Multi-Paxos 522 lines. On Flexible Paxos, the safety lemmas are 21% shorter than Kondo's (441 vs 559 lines), and over 200 lines of invariant definitions are also saved. On simple protocols it is actually longer (Ring leader election 80 vs 30 lines).
- Novelty 2 → Of 64 Host-Provenance invariants, only 6 need a hint from a person, all from implicit cross-step relations such as "clear a set when entering a new epoch". Largest shards vs per-variable shards: no direct ablation.
- Gaps: The first 6 protocols were used to develop the method itself, so only the last 10 count as a held-out set. Only final line counts are compared; human effort on trial and error is not recorded. Completeness is not guaranteed; only safety under crash fault tolerance is proven, not liveness.

## When it applies
State must be determined by "who wrote it". If a property is maintained by implicit constraints across several steps (such as clearing a set when changing epochs), a person must give hints. If footprints are overestimated too much, the invariants become too weak to use.
