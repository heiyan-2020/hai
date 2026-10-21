# Snap: a Microkernel Approach to Host Networking
SOSP'19 · Marty, de Kruijf et al. / Google · Full text: https://storage.googleapis.com/gweb-research2023-media/pubtools/5281.pdf (camera-ready hosted by Google Research) · Selected: Highly cited (263 citations)

**One sentence**: Multicore makes cross-core IPC cheap, so the network stack can be a separate user-space process: it can be upgraded every week and still keep OS-style central scheduling.

## Problem
Google's host networking functions (virtualization, rate limiting, transport) change fast, but a change to the kernel network stack takes 1–2 months to roll out: most changes need a reboot, and applications must be moved off first.
Applications also need low latency and low CPU overhead, and one machine runs dozens of applications.

## Strawman / Baseline
- **Kernel TCP/IP (Linux)**: releases are tied to the kernel cycle; softirq CPU is charged to whatever application happens to be running. One flow at 22 Gbps uses 1.17 cores; with 200 flows it drops to 12.4 Gbps.
- **Put the transport in the application process (IX, ZygOS, mTCP, Shenango)**: the transport code ships with the application binary, so upgrades depend on each service. Low latency needs one spin-poll core per application, which is not practical with dozens of applications. Waking on interrupts instead makes scheduling delay uncontrolled: packets arrive and nobody handles them, which causes timeouts and retransmits.
- **Classic microkernels**: user-space protocol stacks were rejected long ago because of IPC and address-space switch overhead.

## Novelty
1. **Multicore makes IPC no longer expensive, so the network stack can be a separate user-space service**
   Insight: servers have dozens of cores. The network service can run on its own cores and talk to applications through lock-free shared-memory queues. With zero-copy, little state crosses the IPC, and system calls are avoided too. For the transport, being on the NUMA node near the NIC and the transport's own locality matter more than being near the application thread.
   So: network functions go into an ordinary Linux process, organized as "engines" (single-threaded, stateful processing units that share no data). The transport, Pony Express, runs on separate cores and uses an asynchronous command/completion queue interface that is not socket-compatible.
   Releases are decoupled from the kernel and the application, and the system keeps the central management and accurate accounting that in-application designs lose.
2. **End-to-end transports already tolerate packet loss, so a short pause during an upgrade can be treated as congestion**
   Insight: loss from a pause of a few hundred milliseconds looks to the transport the same as congestion loss, so connections need not break.
   So: the old and new Snap processes run side by side and move engine by engine. In the background, control connections and shared-memory fds are transferred first; then the old engine stops and its state is serialized through tmpfs to the new engine. Only one engine stops at a time, so the pause is bounded and applications need no draining. This fixes the kernel stack's root cause: "a change requires draining the machine".
3. **Once centralized, polling cores can become a machine-wide shared resource that scales dynamically**
   Insight: with only one network service, spin-poll need not be one per application; it can scale with load. The remaining problem is how to compete for cores with ordinary tasks.
   So: engines are scheduled in groups, in three modes: dedicated cores; spreading (one thread per engine, woken by interrupts); compacting (squeezed onto a few cores that spin, scaled by queueing delay). A new kernel scheduling class, MicroQuanta, gives Snap a bounded run time in each period, with time slices at microsecond scale. This answers the two root causes of in-application transports: one spin core per application, and uncontrolled interrupt wake-up delay.

Other design: software one-sided operations (RDMA-like reads, indirect reads); I/OAT copy offload.

## Evidence
- End to end (vs. Linux TCP): with about 1 core, 38.5 Gbps for one flow and 39.1 Gbps for 200 flows; 82.2 Gbps with a 5 kB MTU plus I/OAT. Small-message RTT: TCP 23 µs, Snap 18 µs (<10 µs when the application spins). All-to-all RPC on 42 machines at 80 Gbps load: CPU efficiency over 3× that of TCP. In production, one core reaches 5M IOPS of one-sided operations; after replacing hardware RDMA, an analytics service doubled its performance (mainly because the rate limit that protected the NIC from overload was removed).
- Novelty 1 → no direct ablation: the same Pony Express is not compared inside the application process. The gap to TCP mixes in protocol, copy, MTU (5000 B vs. 4096 B) and other factors, and the paper attributes it that way too.
- Novelty 2 → upgrade data from one production cluster: median pause 250 ms (target 200 ms); the long tail correlates with state size. The release cycle shrank from 1–2 months to weekly. "Applications do not notice" is only an empirical statement.
- Novelty 3 → scheduling mode comparison (Fig. 6–7): compacting mode has the best CPU efficiency and the best latency at low load (it avoids C-state wake-ups) and under mmap interference; spreading mode has the best tail latency at high load. Under compute interference MicroQuanta beats CFS at nice -20; the main text gives no numbers.
- Gaps: no quantitative comparison with other user-space stacks (IX, Shenango); no flow rebalancing between engines.

## When it applies
Spare cores must be available for the network service, and the operator must be able to change the kernel (scheduling class, drivers) and the application interface across the whole fleet. Applications must accept a non-POSIX interface and tolerate a pause of a few hundred milliseconds once a week.
