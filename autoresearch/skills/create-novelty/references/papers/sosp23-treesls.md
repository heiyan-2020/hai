# TreeSLS: A Whole-system Persistent Microkernel with Tree-structured State Checkpoint on NVM
SOSP'23 · Fangnuo Wu, Mingkai Dong, Gequan Mo, Haibo Chen / Shanghai Jiao Tong University IPADS · Full text: https://ipads.se.sjtu.edu.cn/_media/publications/wu-sosp23.pdf (lab home page, camera-ready) · Selected: Best Paper

**One sentence**: All of a microkernel's state is one capability tree, and an unmodified page on NVM is its own backup, so a whole-system checkpoint can be taken every millisecond.

## Problem
A single-level store (SLS) checkpoints the whole system periodically. Applications write no persistence code and recover from the checkpoint after a crash.
But updates between checkpoints are lost, so for any operation that has been answered to the outside (a KV store replied to a client), the application must still write its own log. To make this transparent, checkpoints must be very frequent and very cheap.

## Strawman / Baseline
- **Two-tier SLS (EROS, Aurora)**: stop the system, copy dirty data into a DRAM buffer, then flush it to disk asynchronously → byte-level changes are written in blocks, causing write amplification; the next checkpoint cannot start before the flush finishes. Aurora sets a 5 ms interval, but actual persistence takes 5–7 ms (on SSD the interval is about 100 ms), and external synchrony still relies on its logging API.
- **Whole-system checkpoints on a monolithic kernel**: the FD table, the dentry/inode cache and their cross references must be found, and each kind of kernel object needs special handling.
- **Run the system directly on NVM**: eADR (flushing CPU caches back to NVM on power loss) cannot save CPU and device registers, so a consistent checkpoint is still needed.
- **Applications write their own WAL**: with WAL on, Redis loses 64–78% of throughput on write-heavy workloads.
- **Naive copy-on-write checkpoints on NVM every millisecond**: after each round, the first write to each page faults and copies; this is the main source of run-time overhead.

## Novelty
1. **A microkernel gathers system state into one capability tree, so a whole-system checkpoint only needs to walk it**
   Insight: in a capability-based microkernel, all resources are a few kinds of objects reachable from the root cap group (threads, address spaces, physical memory objects (PMOs), IPC, etc.). Complex state such as file system caches is just ordinary memory of user-space service processes.
   So: after stopping the system, copy this tree into a backup tree. Small objects are copied directly; rebuildable state such as page tables and scheduling queues is not saved. Each object's ORoot records whether it has been backed up, so only increments are copied.
   This avoids the monolithic kernel's root cause of handling each kind of kernel object separately.
2. **Run-time pages on NVM are already persistent, so an unmodified page is its own backup**
   Insight: a two-tier SLS must wait for dirty data to flush. On NVM, once the PMO radix tree is copied and the pages are marked read-only, the checkpoint is persistent when the stop ends; only pages modified afterwards get a copy of the old version on a page fault.
   So: each page has at most one extra backup, and a global version number decides at recovery whether to use the backup page or the run-time page. This removes both write amplification and the frequency limit of "flush before the next one".
   To fix the page-fault cost of the last strawman, hot pages that are modified in almost every round are moved to DRAM and copied in parallel by cores that are idle during the stop; cold pages still use copy-on-write on NVM.
3. **With checkpoints frequent enough, external synchrony can be made transparent by delaying external output**
   Insight: only messages sent out are visible to the outside. As long as a message is sent only after the state it depends on is in a checkpoint, a crash rollback cannot break an external promise.
   So: the user-space network driver puts outgoing messages into a "permanent PMO" that is not rolled back, and releases them only in the checkpoint-complete callback. Applications need no code changes; the cost is a delay of about one checkpoint interval (1 ms).

## Evidence
- End to end (Optane PM, based on the ChCore microkernel, 1 ms interval): stop time about 25 µs when idle and about 100 µs for multithreaded applications. Redis on write-heavy workloads loses 18–21% throughput, and its absolute value is 1.9–2.2× Linux with WAL; on read-mostly workloads it loses 15–30% of its own throughput and is worse than WAL. RocksDB throughput is 2.4× Aurora's logging API and 2.5× RocksDB WAL; the 1 ms interval costs 10% throughput (Aurora's 5 ms interval costs 9%).
- Novelty 1 → incremental checkpoint of one object takes at most 3.28 µs, mostly nanoseconds. No direct comparison with checkpoints on a monolithic kernel: no direct ablation.
- Novelty 2 → checkpoints are much smaller than application memory (SQLite 1015 MiB vs. 161 MiB). Hot-page migration cuts run-time overhead by up to 49% and removes 11–95% of page faults.
- Novelty 3 → Redis latency grows by about one checkpoint interval, and client blocking lowers throughput (shown only as a figure). Only implemented for a local network service, not connected to a real NIC driver.
- Gaps: crash consistency is tested only by manual crash-and-reboot, with no systematic crash injection. The comparison with Aurora mixes in OS and libc differences; in absolute RocksDB performance, TreeSLS-1ms is lower than Aurora-5ms.

## When it applies
Needs a capability-based microkernel and byte-addressable NVM with eADR. Drivers must be rewritten, and device state must fit into a permanent PMO and be replayed after recovery. For read-mostly workloads, checkpoint overhead is higher than applications logging for themselves.
