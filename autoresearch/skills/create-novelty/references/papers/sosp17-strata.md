# Strata: A Cross Media File System
SOSP'17 · Youngjin Kwon, Simon Peter, Emmett Witchel, Thomas Anderson et al. / UT Austin, University of Washington · Full text: https://www.cs.utexas.edu/~simon/sosp17-final207.pdf (final version from author homepage, ACM format, DOI is a placeholder) · Selected: Highly cited (245 citations)

**One sentence**: NVM makes synchronous persistence cheap enough to log operations first and let the kernel reorganize them in batches in the lower layers according to each device's traits, so one file system manages the three tiers NVM, SSD and HDD.

## Problem
Storage has split into tiers, and each tier differs by an order of magnitude in latency and price: NVM (300 ns, 4 $/GB), SSD (10 µs, 0.25 $/GB), HDD (10 ms, 0.02 $/GB).
Applications such as LevelDB, Redis, mail servers and persistent RPC need small random writes to be synchronously durable and crash consistent, while their data is also large. A file system designed for only one tier cannot meet all these needs.

## Strawman / Baseline
- **NVM file systems (PMFS, NOVA, EXT4-DAX)**: work only on NVM, whose capacity is expensive. Every operation needs a system call. Metadata is updated in place (PMFS), copy-on-write (NOVA) or copied through a kernel buffer (EXT4-DAX), so small writes under 1 KB are very inefficient.
- **SSD/HDD file systems (F2FS, EXT4)**: synchronous writes are slow. Device firmware does remapping, and random writes trigger write amplification: on the test SSD, once full, random writes of 8 MiB blocks drop throughput 12.2×.
- **Stack existing systems per tier**: user space migrates whole files between the file systems of each tier. Mechanisms such as block allocation are duplicated, and access information is not passed between tiers. An LVM block cache sees only the block interface, cannot use NVM's byte addressing, and adds cache-metadata IO.

## Novelty
1. **On NVM, synchronous persistence costs no more than a memory copy, so the write path only needs to append to a per-process operation log**
   Insight: One write to NVM costs about the same as a copy into a DRAM buffer. And most data, after it is written, belongs only to the writing process until another process sees it.
   So: A user-space library bypasses the kernel and appends each system call (including metadata) as one idempotent operation record, in order, to the process's own NVM log; when the call returns, it is durable. Creating a directory entry needs one record instead of writing three blocks. The shared area is read-only to processes, protected by the MMU/NVMe namespaces, and reading and writing the same file is coordinated by leases. This needs no system call per operation and no buffer copy.
2. **Deferring cleanup to digest time lets it see a whole batch of operations**
   Insight: Many operations in the log are cancelled by later ones (temporary files, overwrites), and the remaining writes can be gathered into large blocks.
   So: The kernel "digests" the log in the background into extent trees organized per file: first drop cancelled records and merge adjacent writes, then write to the lower tier. Writes to SSD/HDD are sequential and aligned to erase blocks (512 MiB) / shingled zones, and reclamation also happens in whole blocks. The firmware sees no small random writes, so write amplification comes back under software control.
3. **Only the file system knows both "which block belongs to whom" and "who used it recently"**
   Insight: Reads complete in user space, and the user-space library can report LRU; writes are seen by the kernel at digest time.
   So: The kernel migrates between tiers at block granularity: hot blocks stay in the upper tier, cold blocks sink down sequentially in large chunks, and metadata stays in the fast tier as much as possible. This is exactly the information that neither user-space migration nor a block-layer cache can see.

## Evidence
- End to end (NVM emulated with DRAM, plus an Intel 750 SSD and an HDD): Varmail is 26% higher than NOVA, Fileserver 7% higher. LevelDB random-write latency is 27% lower than PMFS. Redis SET is 22% higher than NOVA.
- Novelty 1 → microbenchmarks: 99th-percentile latency of small writes is up to 33% lower. A persistent 1 KB RPC is only 1 µs slower than a non-persistent one. 2-thread random writes are 3× NOVA, but sequential writes are up to 26% slower. "User-space log vs kernel log" has no direct ablation.
- Novelty 2 → digest optimizations on/off: digest latency drops up to 80%, throughput rises up to 15%. Varmail skips 86% of log records and copies 14 GB less. SSD write throughput is 7.8× F2FS mounted synchronously. The reduction of firmware write amplification is not measured directly.
- Novelty 3 → Fileserver working set spilling to SSD/HDD: at first 2.8× the LVM cache, 2.0× after spilling to SSD. Zipf reads/writes 4.4 GB/s vs 1.3 GB/s for F2FS.
- Gaps: NVM is emulated by DRAM with a latency model. KernelFS actually runs in a separate process. Leases are not fully implemented. There is no redundancy, so the mean time to data loss is set by the least reliable device. The worst-case sharing test (two processes alternate writes using a lock file) is 4.3× slower than EXT4-DAX and 1.7× slower than NOVA.

## When it applies
Needs an NVM tier to absorb the log, and data mostly not shared concurrently. When processes often share the same file, each handoff needs a digest, and the log's advantage becomes a burden.
