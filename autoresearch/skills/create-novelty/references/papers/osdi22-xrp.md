# XRP: In-Kernel Storage Functions with eBPF
OSDI'22 · Yuhong Zhong, Asaf Cidon et al. / Columbia, Google, Utah · Full text: https://www.usenix.org/system/files/osdi22-zhong_1.pdf (USENIX camera-ready) · Selected: Best Paper

**One sentence**: The application does not need the intermediate I/Os of an index traversal at all, and the layout of an on-disk index rarely changes, so the next hop can be computed and resubmitted directly in the NVMe interrupt.

## Problem
On an Optane P5800X, one 512 B random read takes 6.27 µs in total, and the kernel software stack accounts for 48.6% (ext4 32%, block layer 6%, user/kernel switching only 5.6%).
B-tree and LSM lookups are pointer chasing: with 10 billion objects, DRAM holds only the top few index levels, so each lookup still needs 3–4 I/Os. Each level goes through the whole kernel stack, and the node read back is used only to find the next pointer, then thrown away.

## Strawman / Baseline
- **Kernel bypass (SPDK)**: The application drives the device directly → it must write its own file system and has no isolation; completions can only be polled, so cores cannot be shared. Once threads outnumber cores, throughput drops 3×, and at 24 threads 0.28% of requests exceed 1 ms.
- **io_uring**: Batches submissions, which saves only the switching cost; each I/O still goes through the whole file system and block layer.
- **Hook a BPF function at the syscall layer to resubmit**: Saves only the switching. The authors' earlier measurement (a B-tree of depth 10): throughput only 1.2×.
- **Put the hook in the NVMe driver**: The driver does not know about files. The BPF function computes an offset within a file, which the driver cannot translate to a physical block, nor can it stop the function from reading someone else's blocks. Concurrent writes land only in the page cache, which the driver cannot see. And taking locks in an interrupt is too expensive.
- **Near-storage computing**: Requires dedicated hardware.

## Novelty
1. **The cost is in the file system and block layer, so the "next hop" must be computed as close to the device as possible**
   Insight: Intermediate nodes are used only to compute the next address; what is expensive is that each I/O passes through the file system and block layer, while the switch itself is cheap.
   So: In the NVMe driver's completion interrupt, call a user-registered eBPF function (a small safe program in the Linux kernel, checked by the verifier). It parses the block just read, gives the next offset, and the driver reuses the original NVMe command to resubmit directly. Only the first I/O goes through the full kernel stack; the result returns through a 4 KB scratch buffer.
   It uses interrupts instead of polling, so cores can be shared and isolation remains; this answers SPDK's root cause. Hooking in the driver instead of the syscall layer answers why io_uring and syscall hooks cannot save the bulk of the cost.
2. **On-disk indexes are usually a few large files whose layout rarely changes, so the driver needs only a small cache of file mappings**
   Insight: An LSM SSTable is immutable once written. With TokuDB running YCSB for 24 hours, the index file's extents changed on average only once every 159 s, and there were only 5 block frees in 24 hours. Also, one index does not span files, and mainstream storage engines have their own user-space caches and do not depend on the page cache.
   So: A resubmission chain is limited to one file. The file system pushes a cache of that file's logical→physical mapping (the metadata digest) to the driver; the ext4 implementation uses RCU, with lock-free lookups averaging 96 ns. An out-of-range lookup is rejected, which is the access control. After a read, the extent version number is checked again; if it changed, the chain aborts and the application falls back to a normal read.
   The mapping changes very rarely, so the cache almost never goes stale; this gets around the obstacle of "the driver lacks context, and locks cannot be taken in an interrupt".

## Evidence
- End to end (BPF-KV: a B+-tree KV the authors wrote for XRP, no cache, uniform random lookups): with a 6-level index, average latency is XRP 29.3 µs, read() 48.8 µs, SPDK 20.2 µs. XRP is 45% slower than SPDK, and read() is 142% slower. With 3 levels and multiple threads, throughput is 47–94% higher than read() and p99 is 20–34% lower. WiredTiger (YCSB, 1 billion records, 46 GB): throughput up to 1.25× higher, p99 up to 40% lower.
- Novelty 1 → Comparison of hook locations (cited from the authors' earlier measurement, a B-tree of depth 10): syscall layer 1.2× throughput, NVMe driver 2.5×. Each extra resubmission adds only 3.5–3.9 µs of latency, close to the device itself. Once threads outnumber cores, SPDK throughput keeps falling while XRP stays stable; with two threads sharing one core, p99 is 56% better than SPDK.
- Novelty 2 → No direct ablation: no experiments under concurrent writes or extent changes, and fallback frequency is not measured; "use ext4's own locked lookup" is argued only qualitatively.
- Gaps: The hook-location numbers come from an earlier paper. BPF-KV is custom-built for XRP. WiredTiger spends only 63% of its time on I/O, YCSB D/E show almost no gain, and the more skewed the distribution, the smaller the gain. The prototype has no cap on the number of resubmissions, and aborts directly when fan-out is greater than 1.

## When it applies
Requires a µs-scale device (where software overhead is a large share), an index whose layout within a single file is stable, and an application with its own cache. The method does not apply if the data structure needs locks during traversal or often changes its layout in place.
