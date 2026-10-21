# Just Say NO to Paxos Overhead: Replacing Consensus with Network Ordering
OSDI'16 · Jialin Li, Ellis Michael et al. / University of Washington · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-li.pdf (USENIX camera-ready, system name NOPaxos) · Selected: Community favorite (5 sources: Cornell CS6410 2021, Morning Paper, Princeton COS 518 2018, The Paper Trail)

**One sentence**: Ordering and reliable delivery can be split. One counter in the network can guarantee order, and replicas only need to agree on which message to skip when a packet is lost.

## Problem
State machine replication requires all replicas to execute the same set of requests in the same order. Multi-Paxos needs the leader to order and a majority to confirm every request, so its performance is far below an unreplicated system.
Data center networks have controllable tree topologies, SDN and programmable switches, yet replication protocols still assume the network can reorder and drop packets arbitrarily.

## Strawman / Baseline
- **Multi-Paxos**: 4 message delays. The number of messages the leader sends and receives grows with the number of replicas, making it the throughput bottleneck. Batching raises throughput, but latency rises to 385–907 µs.
- **Let the network provide atomic broadcast (both ordered and reliable)**: this is equivalent to consensus. It only moves the same coordination cost to another layer.
- **Bet that the network is "usually ordered" (Fast Paxos, Speculative Paxos + Mostly-Ordered Multicast)**: order is not guaranteed, so the client must wait for a supermajority of 2/3 or 3/4. Speculative Paxos computes a log hash for every request, and on reordering or loss it must reconcile and roll back. At 1% packet loss, throughput falls back to the Paxos level.
- **Put all of Paxos into the switch (NetPaxos)**: the switch must store state for each consensus instance.

## Novelty
1. **Guaranteeing only order, not delivery, is almost free in the network**
   Insight: Reliable delivery is hard, and by the end-to-end principle it should be left to the application. Guaranteeing only order is simple: give each packet a consecutive sequence number. The receiver drops out-of-order packets and reports "one was lost" when it sees a gap. A data center is a multi-rooted tree. The lowest common ancestor switch of a replica group is already on most paths, so stamping sequence numbers there adds almost no path length.
   So: Define "ordered unreliable multicast" (OUM). SDN steers all packets for a replication group to a sequencer (a programmable switch, a network processor or a host) that writes the sequence number.
   The network keeps only one counter and stores no consensus state. So it is neither equivalent to consensus nor needs switches to store state.
2. **Once order is guaranteed, replicas only need to agree on "which message to skip"**
   Insight: Within a session, all replicas receive requests in the same order. The only possible disagreement is whether a given message was received. This is simpler than agreeing on order. It amounts to one binary consensus only when a packet is lost.
   So: In the normal case, a replica appends a request to its log on receipt and replies; only the leader executes. The client is done once it has f+1 matching replies including the leader's: one round trip, no coordination among replicas.
   On packet loss, a replica first asks other replicas for the message. If it cannot get it, the leader uses one round of messages to commit that slot as a NO-OP. Non-leaders do not execute, so no rollback is needed.
   This removes the supermajority, hashing and rollback of Speculative Paxos, and also the leader bottleneck of Paxos.

Other design: when the sequencer fails, the controller replaces it and increments the session number, and replicas run a view change to align logs. The controller takes part only in the switchover.

## Evidence
- End to end (3 switches emulate a fat-tree, a Cavium network processor acts as the sequencer, 5 replicas): throughput is 4.7× Paxos and 24% higher than Speculative Paxos. Latency is 111 µs (Paxos 240 µs, Fast Paxos 193 µs). Throughput is within 2% of an unreplicated system, and latency is at most 16 µs higher (about 8 µs is the Cavium hop). A transactional KV store (10 ms SLO) gets more than 4 times the throughput of Paxos, 45% higher than Speculative Paxos.
- Novelty 1 → packet-level simulation (2560 hosts): for 88% of requests, the time to reach a majority is unchanged; p99 rises by less than 5 µs. With a host as the sequencer, throughput stays high, and latency rises 36%.
- Novelty 2 → Fast/Speculative Paxos go through the same root switch and differ only in the ordering guarantee, so they can serve as a control. At 1% packet loss, NOPaxos throughput barely drops, while Speculative Paxos falls to the Paxos level. As the number of replicas grows, throughput stays the same, while Paxos drops.
- Gaps: there was no P4 switch hardware for the sequencer at the time, so it was not measured. During a sequencer switchover, throughput drops to zero; it recovers in about 110 ms and returns to peak in 270 ms.

## When it applies
Replicas and clients are in one data center, and the operator can control routing with SDN and place a sequencer on the common path. With frequent packet loss or frequent sequencer failures, it degrades into frequent gap agreement and view changes.
