# SplitFS: Reducing Software Overhead in File Systems for Persistent Memory
SOSP'19 · Rohan Kadekodi, Se Kwon Lee et al. / UT Austin, Georgia Tech, Penn State, VMware Research · Full text: https://www.cs.utexas.edu/~vijay/papers/sosp19-splitfs.pdf (author home page, camera-ready) · Selected: Highly cited (227 citations)

**One sentence**: On PM, data reads and writes are just load/store; only metadata operations need the kernel. And an append can become a pure metadata operation by using the file system's extent swap.

## Problem
Persistent memory (PM) sits on the memory bus and is accessed with load/store. Writing 4 KB takes only 671 ns, but appending 4 KB through a file system takes 9002 ns on ext4 DAX and 3021 ns on NOVA-strict. Software overhead is 3.5–12.4 times the device time.

## Strawman / Baseline
- **Kernel PM file systems (ext4 DAX, PMFS, NOVA)**: every call traps into the kernel, and the critical path does allocation, logging and updates to several structures.
- **Turn reads and overwrites into load/store on mmap (Quill, FLEX)**: no synchronous or atomic semantics; appends change the file size and still go into the kernel.
- **A fully user-space file system (Strata)**: data is first written to a per-process private log, then merged and copied into a shared area. Appends cannot be merged, so data is written twice; the VFS also has to be rewritten in user space.
- **Write appends to a staging area first and copy them into the file at fsync**: whether staging is on PM or DRAM, the copy at fsync becomes the bottleneck (PM and DRAM have similar speed, so a DRAM buffer saves little).
- **Atomic operations through a log (NOVA)**: each operation writes at least 2 cache lines and issues 2 fences; the log tail is on PM and must be flushed every time.

## Novelty
1. **Data operations are common and are just load/store; metadata operations are rare, so hand them to an existing kernel file system**
   Insight: under DAX a file can be mmapped straight into the process, so the data path needs no software. What needs correctness guarantees is metadata, and it is a small share of most workloads.
   So: a user-space library intercepts POSIX calls with LD_PRELOAD. Reads and overwrites run directly on the mmapped region; metadata operations such as open, close and fsync are passed unchanged to ext4 DAX. Metadata gets slower as a result, but the mature ext4 is reused and need not be rewritten as in Strata.
2. **ext4 extents can be "transferred" whole between files, so an append needs no copy**
   Insight: ext4 already has a journaled extent swap (the swap_extents ioctl). By changing only metadata, it can atomically move physical blocks from one file to another.
   So: appends are first written with non-temporal stores into a preallocated, premapped staging file. At fsync, a new relink call atomically transfers those blocks to the target file, with no data copy, and existing mmaps stay valid. In strict mode, overwrites are also staged and then relinked, so data is written only once and the write is atomic. This removes the copy of staging designs and the double write of Strata.
3. **Log entries carry their own checksum, so one cache line plus one fence is enough**
   Insight: the second fence only serves to tell a complete log entry from a half-written one. If the log is zeroed in advance and each entry contains a checksum, recovery can scan non-zero entries and check them, and the log tail need not be persisted.
   So: each operation writes one 64 B log entry that only records a logical pointer to the staged data, and issues one fence. The log tail lives only in DRAM, and multiple threads advance it with CAS. This is half the writes and fences of NOVA.

## Evidence
- End to end: Optane DC PMM. With the same guarantees, up to 2.70× faster than other PM file systems on LevelDB (YCSB), Redis and SQLite (TPC-C) (on Run A, POSIX mode is 2× faster than ext4 DAX and strict mode is 2× faster than NOVA-strict). On emulated PM, 1.72–2.25× faster than Strata. git/tar/rsync are up to 13% slower.
- Novelty 1 → split architecture alone: sequential overwrites are over 2× faster than ext4 DAX; appends do not change. System call latency (POSIX mode vs. ext4 DAX): append 2.84 vs. 11.05 µs; metadata gets slower, unlink 14.33 vs. 8.60 µs.
- Novelty 2 → added step by step: the staging file alone makes appends about 2× faster; adding relink to remove the fsync copy raises throughput another 5×.
- Novelty 3 → strict-mode random writes are 5.8× faster than NOVA, which the authors attribute to the cheaper log, but this is a whole-system comparison: no direct ablation.
- Gaps: the comparison with Strata uses only small workloads on PM emulated in DRAM. Correctness was only checked by matching the final state against ext4 DAX; there is no systematic crash-consistency testing.

## When it applies
The workload is mainly data reads and writes, and appends are block-aligned (otherwise relink must copy the unaligned part). Metadata-heavy workloads get slower; the application must use POSIX and be interceptable with LD_PRELOAD.
