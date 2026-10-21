# ghOSt: Fast & Flexible User-Space Delegation of Linux Scheduling
SOSP'21 · Jack Tigar Humphries et al. / Google, Stanford · Full text: https://storage.googleapis.com/gweb-research2023-media/pubtools/6413.pdf (ACM camera-ready hosted by Google Research) · Selected: Community favorite (6 sources: ACM Queue RfP, Cornell CS6410 2022, Micah Lerner blog, Stanford CS240 2023)

**One sentence**: Scheduling decisions can be made asynchronously, with a check at commit time on whether the state they used is stale; so the policy can live in an ordinary user process, and a change only needs a process restart.

## Problem
Datacenters need custom scheduling policies: μs-scale tail latency, placement by NUMA/CCX topology, core isolation against L1TF/MDS. But kernel schedulers are hard to write (C, RCU, no common libraries) and even harder to deploy: kernel releases take months, and workloads must be moved off and machines rebooted. During development, only about 5 versions can be tried per day.

## Strawman / Baseline
- **Modify a kernel scheduling class (CFS, MicroQuanta)**: → the development and rollout costs above; a scheduler bug can hit the whole machine (one once cost millions of dollars). The framework is designed for "each CPU decides for itself", which makes it hard to build a centralized policy where one scheduler directs all CPUs.
- **User-level threading libraries**: can decide which user thread runs on a kernel thread, but not when or on which CPU the kernel thread runs. Either they own CPUs exclusively, or they lose latency control.
- **Dedicated dataplane OSes (Shinjuku, Shenango)**: schedule requests with threads spinning on dedicated cores. → They serve one kind of workload and need specific NICs; batch tasks cannot use the cores Shinjuku holds at all.
- **Attach BPF programs to the scheduler**: → BPF runs synchronously when a scheduling event happens and must decide at once, so it cannot see global state gathered from several events. It also cannot have unbounded loops or floating point.

## Novelty
1. **Decisions can be made asynchronously, with a check at commit time on whether the state is stale**
   Insight: the kernel only needs to carry out decisions (context switches); it does not have to make them. As long as "a decision made on old state" can be detected, it does not matter who makes the decision or when.
   So: the kernel writes thread state changes (block, wake-up, etc.) into shared-memory message queues. A user-space agent (an ordinary process in any language) decides from them and commits "thread T runs on CPU c" as a transaction, attaching the sequence number it saw; if the sequence number is behind, the kernel rejects it.
   The policy is not in the kernel, so it avoids the cost of changing the kernel and is not bound by BPF's synchronous decisions.
2. **The remote overhead of centralized scheduling can be amortized by batching**
   Insight: the main cost of remote scheduling is sending IPIs (inter-processor interrupts), and the processor supports sending one interrupt to several CPUs.
   So: a global agent spin-polls the queues and commits transactions for several CPUs at once, delivered by one batched IPI. It cannot be preempted; when another thread needs its CPU, it first hands its role to an agent on an idle CPU.
   Threads are still ordinary kernel threads, and idle CPUs are left to other workloads, which fixes the dedicated-core flaw of dataplane OSes.
3. **The delegated scheduling class sits below CFS, so a fault only hurts itself**
   Insight: as long as ghOSt threads have lower priority than other threads and a fault can fall back to the default scheduler, a bug in a user-space policy cannot bring down the whole machine. So: ghOSt threads can be preempted by CFS threads. When an agent crashes or hangs (a runnable thread is not scheduled for more than a set number of milliseconds), the kernel destroys its enclave (a partition by CPU) and the threads fall back to CFS. Upgrading a policy means a new agent takes over after the old agent exits; neither the kernel nor the application needs a restart.

## Evidence
- Overhead: message delivery to the global agent 265 ns; local scheduling 888 ns (a CFS switch 599 ns).
- End to end: on a RocksDB mix of long and short requests, a 710-line policy reproduces Shinjuku within 5% of its saturation throughput; the non-preemptive CFS version saturates about 30% earlier. Snap vs. MicroQuanta: 5–30% lower at P99.9 and above for 64 kB messages, up to 1.7× worse at P99.99 and above for 64 B messages. Search on a 256-CPU AMD Rome: throughput on par with CFS, 40–45% lower tail latency for query types A and B. Side-channel-safe VM core scheduling: bwaves score 468, kernel implementation 464.
- Novelty 1 → one iteration shrinks from about 1 hour or more ("compile + deploy + test") to under 1 minute. No direct ablation of the sequence number check.
- Novelty 2 → committing 10 transactions at a time raises the theoretical limit from 1.5 million to 2.52 million per second; measured, one agent peaks at about 2.4 million per second and drops to about 1.5 million when managing 112 CPUs (read from the figure). Shenango-style reclaiming of idle CPUs takes only 17 more lines of code; batch tasks can use idle CPUs with no change in tail latency.
- Novelty 3 → no direct experiment (no injected agent crash).
- Gaps: Shinjuku runs on Linux 4.4, ghOSt on 4.15. Part of the Search gain comes from μs-scale rebalancing and topology optimization (NUMA and CCX bring 27% and 10% throughput), not all from "moving to user space". The global agent needs one spinning CPU.

## When it applies
Threads must run much longer than the scheduling overhead: with one agent managing 100 CPUs, threads must run at least about 40 μs. With small messages and bursty load, events are too dense and the far tail latency gets worse.
