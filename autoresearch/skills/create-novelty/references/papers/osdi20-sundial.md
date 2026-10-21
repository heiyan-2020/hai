# Sundial: Fault-tolerant Clock Synchronization for Datacenters
OSDI'20 · Yuliang Li, Gautam Kumar et al. / Google, Harvard · Full text: https://www.usenix.org/system/files/osdi20-li_yuliang.pdf (camera-ready) · Selected: Community favorite (3 sources: DSRG (charap.co), Micah Lerner blog, Murat blog)

**One sentence**: Only when a node "forwards a message only after it receives one from upstream" does receiving a message prove that the node is still connected to the root; then the time uncertainty does not need a margin for failures the node cannot see.

## Problem
Databases such as Spanner and FaRMv2 must wait out the time uncertainty ε (the upper bound on the error between the local clock and other clocks) before they commit. In FaRMv2, ε is about 20 µs, which is already 25% of the median transaction latency.
Datacenters want ε of about 100 ns. It must also hold when links, devices, or a whole failure domain (a group of devices and links that fail together) fail.
ε equals a fixed error plus "time since the last sync with the root × maximum drift rate". Cooling failures can make oscillator frequency jump around, so the drift rate must be set conservatively to 200 ppm. So 100 ns requires a sync interval below 500 µs.

## Strawman / Baseline
- **PTP (hop-by-hop sync along a spanning tree)**: Software sends sync messages every 15 ms–2 s; a shorter interval burns CPU. When a segment of the tree breaks, a grandchild node downstream still receives messages from its parent, so it cannot tell whether it is still connected to the root. To keep ε correct, every node not directly connected to the root must always assume "it may have been disconnected for the whole recovery time". The controller takes about 100 ms to recompute the spanning tree, so ε must exceed 20 µs, and nodes must report this even in normal operation.
- **Huygens**: Pure software. It filters noise with many messages, runs one round every 2 s, and has a median ε of 200 µs.
- **DTP**: Changes the physical layer and syncs every few microseconds, but has no master clock, so it does not reflect physical time.
- **Mesh sync (the Marzullo algorithm, used by NTP/TrueTime)**: Multiple paths give fault tolerance for free. But each node receives messages from several neighbors, so it cannot "forward only after receiving" (the message count multiplies at each hop). It can only be asynchronous, and ε accumulates hop by hop.

## Novelty
1. **"Forward only after receiving" makes the arrival of a message itself prove connection to the root**
   Insight: On a spanning tree, if every node sends downstream only after it receives a message from upstream, any upstream failure makes downstream nodes stop receiving messages.
   So: Message send/receive and timeout detection go into NIC/switch hardware. The root sends once about every 100 µs (100 bytes, under 0.01% of bandwidth). If messages are missing for several consecutive periods, an interrupt raises an alarm. On receiving a message, a node can record "last sync with the root" as the current time and no longer subtract the recovery time. This removes the root cause of PTP having to report a large ε even in normal operation. Doing it in hardware also removes the CPU cost of high-frequency sync.
2. **One precomputed backup plan can cover all failure types**
   Insight: Detection is already at the microsecond level, so the big remaining cost is the 100 ms controller recomputation. If the backup edges satisfy a few graph properties, a node does not need to know what failed; it just switches to its backup parent. The properties: the backup edges of any subtree form no cycle (handles any single link failure); a backup parent is not one of the node's own ancestors (handles non-root node failure); the backup root reaches all nodes through backup edges (handles root failure); no single failure domain can cut both the primary path and the backup parent (handles domain failure).
   So: The controller searches ahead of time for a primary tree plus a backup graph that satisfy these properties. On the 88K-node Jupiter topology this takes 148 ms on average. After a device detects a timeout, it switches locally, and the controller recomputes slowly afterward. Messages travel on the mesh graph, but sync follows only the current spanning tree, so the design gets both mesh fault tolerance and "forward only after receiving".

Other design: A timestamp outside the local ε is judged invalid, and two steps tell whether the node's own clock or the parent's clock is broken; the maximum tree depth after a switch is precomputed and used to set the fixed error; the host clock follows the NIC clock with a PI controller.

## Evidence
- End to end (552 servers, 276 switches, 90 µs sync interval): with no failures, ε ≤43 ns; PTP+ε up to 800 µs, PTP+DTP+ε about 20 µs, Huygens+ε median 200 µs. Across 50 injected failures: after a link failure, ε peaks at 84 ns and recovers in 270 µs; after a root failure, it peaks at 103 ns and recovers in 365 µs; total time all devices were affected is 131 ms. Spanner commit wait: median 211→49 µs, p99 784→238 µs.
- Novelty 1 → Step-by-step stacking (PTP+ε → add high-frequency messages → add "forward only after receiving" → Sundial): high-frequency messages cut ε by an order of magnitude; "forward only after receiving" further lowers ε in normal operation.
- Novelty 2 → With the backup plan, ε during failures drops by two more orders of magnitude. When the failure-domain condition is removed, devices whose primary and backup parents fail together fall back to the no-backup case. In an 88K-node simulation, the maximum ε is 178 ns (root failure).
- Gaps: The ε of the compared systems was filled in by the authors from formulas; DTP was emulated with PTP at a 5 µs interval, and Huygens was not implemented, only estimated under idealized assumptions. Concurrent failures across failure domains still wait for the controller, and ε rises to about 20 µs during that time. Hardware details are confidential.

## When it applies
All switches and NICs must support sending and receiving sync messages in hardware, and sync only with directly connected neighbors. The topology must have enough redundancy to find a backup graph that meets all conditions.
