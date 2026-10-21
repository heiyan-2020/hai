# ZygOS: Achieving Low Tail Latency for Microsecond-scale Networked Tasks
SOSP'17 · George Prekas, Marios Kogias, Edouard Bugnion / EPFL · Full text: https://marioskogias.github.io/docs/zygos.pdf (camera-ready from author homepage, with ACM DOI) · Selected: Highly cited (295 citations)

**One sentence**: A dataplane's throughput comes from an independent network stack per core, not from pinning requests to cores. Make only the application layer stealable, and you get both the throughput and the tail latency of a single queue.

## Problem
In-memory data services (KV, in-memory transactional stores) need only a few to a few dozen µs per RPC, and the SLO is "99% of requests complete within 10× the mean service time".
Queueing theory shows a single FCFS queue is far better than one queue per core: with 16 cores and exponentially distributed service times, the former can carry 96.3% load under this SLO, the latter only 53.7%.

## Strawman / Baseline
- **Linux with connections partitioned per core (epoll + RSS, i.e., the NIC hashes flows to per-core queues)**: equivalent to one queue per core. Poisson bursts and service-time variation cause temporary imbalance: some cores idle while others back up. Kernel overhead is high; tasks must be ≥120 µs to reach 90% of the theoretical value.
- **Linux with floating connections (all threads share one connection pool)**: close to a single queue, best for large tasks. But two threads may read the same socket at once, garbling request parsing and making replies out of order or even interleaved, so the application must add its own synchronization.
- **Kernel-bypass dataplane (IX)**: polling, run-to-completion (a batch of packets is processed from the NIC all the way through the application without yielding), connections pinned to cores by flow, nothing shared between cores; memcached throughput reaches 6.4× Linux. → It is not work-conserving (some cores idle while requests are queued), and it has head-of-line blocking (a long request blocks the ones behind it). For tasks ≥14–50 µs, it is overtaken by Linux floating mode.
- **Add cooperative stealing directly on the dataplane**: → while the home core (the core responsible for the flow) runs user code, nobody processes the packets in the NIC queue, and other cores cannot steal them. Replies of stolen tasks also wait until the home core comes back.

## Novelty
1. **Schedule globally only at the application layer; keep the network stack independent per core**
   Insight: A dataplane's throughput comes from lock-free, cache-local per-core TCP/IP processing. Its poor tail latency comes from application tasks also being pinned to cores. The two can be separated.
   So: The driver and TCP/IP still run independently on the home core. On top, a per-core shuffle queue holds "connections with pending events". Idle cores steal connections from other cores' shuffle queues and run them. The whole approximates a single FCFS queue while keeping IX's throughput.
2. **The unit of stealing is a connection, not a packet**
   Insight: Requests on the same connection must stay in order; requests on different connections need not.
   So: A core that takes a connection owns it exclusively until the events are processed and the replies are sent. System calls produced by stolen execution are sent back to the home core to run, so TCP state still never crosses cores. The application gets per-connection ordering without locks, which fixes the reordering of floating mode; the cost is that global FCFS is only approximate.
3. **Break run-to-completion with inter-core interrupts**
   Insight: All remaining blocking comes from the home core running user code and not yielding. An interrupt is used only as a hint; losing one affects only latency, not correctness.
   So: Idle cores poll other cores' NIC queues and shuffle queues. When they find stuck work, they send an exit-less inter-processor interrupt (IPI, which causes no VM exit) that forces the home core to process received packets and pending replies. This targets the head-of-line blocking of cooperative stealing.

## Evidence
- End to end: Silo running TPC-C (service time mean 33 µs, p99 203 µs), SLO p99 ≤1000 µs: ZygOS 344 KTPS, IX 267, Linux 211, i.e., 1.63× Linux. At 90% load, p99 is 1.6× the service-time p99; IX is 3.8×.
- Novelty 1 → synthetic load (SLO 10× mean): exponentially distributed 10 µs/25 µs tasks reach 75%/88% of the theoretical single-queue load. For tasks ≥5 µs it beats IX and Linux across the board; for 10 µs tasks, throughput matches IX.
- Novelty 2 → ordering is a semantic guarantee with no direct experiment: no direct ablation.
- Novelty 3 → the version with interrupts off has clearly worse tail latency under medium and high variance distributions (figures only). Interrupts make the steal rate much higher than the ~33% peak without them.
- Gaps: In Table 1, 344/267 is about 1.29×, but the text says 1.26× faster than IX (1.26× is the table's figure for IX relative to Linux). On memcached (<2 µs) it loses to IX with batching on; when the SLO is relaxed to 100× the mean, IX's throughput is slightly higher. Silo ran with GC off.

## When it applies
Tasks of about 5 µs or more, service time with limited variance, and a tight SLO. For very small tasks or a loose SLO, batching pays off more; with extreme variance, time-sliced preemption (processor sharing) is needed and FCFS is not enough.
