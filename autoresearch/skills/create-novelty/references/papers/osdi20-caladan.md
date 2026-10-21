# Caladan: Mitigating Interference at Microsecond Timescales
OSDI'20 · Joshua Fried, Zhenyuan Ruan, Amy Ousterhout, Adam Belay / MIT CSAIL, UC Berkeley · Full text: https://www.usenix.org/system/files/osdi20-fried.pdf (USENIX camera-ready) · Selected: Highly cited (253 citations)

**One sentence**: Interference changes within microseconds, and only core reallocation is fast enough. Pair it with signals that can tell within microseconds "who is contending for what", and there is no need for hardware partitioning.

## Problem
Data centers co-locate latency-critical (LC) and best-effort (BE) tasks to raise CPU utilization. They contend for memory bandwidth, LLC, and hyperthreads.
Interference often appears suddenly: one GC in a BE task lasts 100–200 ms and saturates memory bandwidth. memcached's service rate halves, queueing delay grows 5 µs every 10 µs, and tail latency rises 1000×.
To keep the added latency within X, the system must react within 2X: 50 µs means 100 µs.

## Strawman / Baseline
- **Static core partitioning (LC pinned to dedicated cores)**: Memory bandwidth and LLC are still shared, so a GC still causes spikes.
- **Dynamic partitioning (Heracles, Parties)**: Uses application tail latency as the signal, which needs hundreds of milliseconds of measurement to stabilize. It also does not know the source of interference, so it can only adjust core counts and CAT partitions step by step by trial. Convergence takes 10–30 s, more than 50 times one GC. They also disable hyperthreading, losing up to 30% throughput.
- **Hardware partitioning and monitoring (CAT, MBA, CMT/MBM)**: CAT (splits the LLC by way) is slow to take effect after a change and lowers associativity. MBA throttling leaves cores idle-waiting a lot. CMT takes 112 ms to stabilize, and MBM also takes milliseconds.
- **Reallocate cores with Linux system calls (sched_setaffinity, etc.)**: Locks and blocks on the calling core, and does only one operation at a time. The heavier the interference and the more cores, the slower it is.

## Novelty
1. **Both effects of interference can be corrected by allocating cores, and cores can be changed within microseconds**
   Insight: Interference does two things: it slows the service time of individual requests, and it lowers total processing capacity, which causes queueing. Giving BE a few fewer cores lowers its memory bandwidth. Giving LC a few more cores makes up the lost capacity. LLC interference cannot be removed quickly, but this keeps queueing from running away.
   So: Use only one mechanism, core allocation, adjusted every 10 µs, with no CAT/MBA at all. This avoids the slowness of hardware partitioning.
2. **Choose signals that can be measured accurately within microseconds and point straight at the culprit**
   Insight: A global DRAM bandwidth counter shows whether bandwidth is saturated. Per-core LLC misses show who is using the bandwidth. How long a request has been running finds long requests slowed by a hyperthread sibling. The waiting time of the oldest element in a queue catches all remaining interference.
   So: When bandwidth is saturated, take back one core at a time from the BE task with the most misses. When a long request passes a threshold, put the sibling hyperthread to sleep until the request ends. When queueing exceeds 10 µs, add a core. The signals name the task and the resource directly, so one step is enough to act, with no Parties-style trial and error. This is also why hyperthreading can stay on.
3. **The bottleneck of core reallocation is the Linux interface, not the scheduling decision itself**
   So: The kernel module KSCHED lets the scheduler core write commands into per-core shared memory and wake several cores at once with a multicast IPI, all asynchronously. Heavy work such as sending signals and pinning is done on the target core. This targets the root cause that system calls are serial and blocking.

## Evidence
- End to end: memcached co-located with swaptions with GC (800,000 RPS), compared with Parties*, the authors' rewrite: 99.9% latency during GC drops from 580 ms to 52 µs (11,000×), and BE throughput is 5% higher too. Convergence takes about 20 µs, versus 10–20 s. In 15 LC/BE pairs, the tail latency of storage and memcached is close to running alone.
- Novelty 1 → Under constant bandwidth interference, Linux and Shenango, which ignore interference, see tail latency rise 235×/6×. Caladan and Parties* see no rise. "Cores only vs adding CAT" has no direct ablation. silo is sensitive to LLC, and its tail latency still rises slightly at low load.
- Novelty 2 → Turning off controllers one by one (storage + stream-DRAM): at high load both controllers are needed. Turning off the hyperthread controller raises tail latency by up to 117 µs. LC throughput is 37% higher than with Elfen's hyperthread policy.
- Novelty 3 → Migrating 22 tasks at once, the Linux interface costs 43× the scheduling work and 5× the latency. With 11 LC tasks, KSCHED peaks at 560,000 core reallocations per second, while the Linux version stalls at about 285,000.
- Gaps: Parties is not open source. Parties* is the authors' rewrite, and they also gave it the kernel-bypass networking and hyperthreading of the Caladan runtime. Applications must run on the Caladan runtime and expose concurrency (memcached changed to one thread per connection). NUMA is not supported.

## When it applies
LC tasks must benefit from extra cores (have enough concurrency), and the interference source must be a local task whose cores can be taken back. LLC capacity interference can only be compensated by giving more cores, so idle cores must be kept as headroom.
