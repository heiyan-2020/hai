# Coordinated and Efficient Huge Page Management with Ingens
OSDI'16 · Youngjin Kwon, Hangchen Yu, Simon Peter, Rossbach, Witchel / UT Austin, VMware Research · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-kwon.pdf (camera-ready) · Selected: Community favorite (4 sources: UIUC CS523 2019, UT Austin CS380L 2025, UW CSE 551 2024, Wisconsin CS736 2017)

**One sentence**: Physically contiguous memory is a scarce resource. Give it only to 2 MB regions that are fully used and often accessed. To do this, first measure utilization and access frequency.

## Problem
New CPUs have thousands of huge page (2 MB page) TLB entries. Under virtualization, huge pages can make applications up to 53% faster.
But Linux transparent huge pages (the kernel automatically merges 512 aligned 4 KB pages into a huge page) have too many problems. MongoDB, Redis and others recommend turning them off.

## Strawman / Baseline
- **Linux promotes to a huge page synchronously at page fault**: it must zero 2 MB, and under fragmentation it must also run compaction on the spot (move pages to make contiguous memory). Average page fault latency rises from 3.6 µs to 378 µs.
- **Linux does only background asynchronous promotion**: the default linear scan runs at 1.6 MB/s, and the SVM speedup drops from 30% to 2%. Scanning faster wastes CPU.
- **Linux greedily promotes sparse regions**: after Redis deletes 70% of its keys, it uses 69% more memory. It also uses up contiguous memory fast.
- **First come, first served**: after one VM exits, all 3 GB of freed huge pages go to the next VM that the scanner reaches. VM2 is 24% slower than the identical VM3.
- **KVM same-page merging (KSM)**: to share one 4 KB page it breaks up the whole huge page. It saves 9.2% memory but is 6.8–19% slower.
- **FreeBSD**: it promotes a region only when it is 100% full, and only read-only after promotion → Redis speedup is only 1.02× (Linux 1.15×).

## Novelty
1. **Give contiguous memory only to regions that are "already fully used", and move the decision off the page fault path**
   Insight: Bloat comes from allocating 2 MB to regions that are not fully used. Page fault latency comes from zeroing and compaction on the fault path. If you know how many 4 KB pages each 2 MB region uses, you can avoid both.
   So: A bitmap records the used pages of each 2 MB region. The page fault handler allocates only 4 KB pages. When usage exceeds 90%, the region goes into a high-priority queue, and a background thread moves pages and promotes it, without waiting for the slow linear scan. The threshold bounds bloat (at most about 10% extra memory). When some pages are freed, the region is demoted only if utilization falls below the threshold.
2. **Access frequency separates "huge pages worth keeping" from "huge pages that can be broken up"**
   Insight: The benefit of a huge page comes only from its often-accessed part. Breaking up cold huge pages for page sharing loses almost no performance.
   So: Periodically scan the hardware access bit and compute a moving average of each page's access frequency. KSM breaks up only cold huge pages. When a shared page is written, the region is promoted again at once if its utilization is high.
3. **Treat contiguous memory as a resource allocated by shares**
   Insight: Contiguous memory can be divided by shares, like memory capacity. Idle huge pages should not count as a benefit.
   So: Borrow ESX's shares plus idle penalty. The more huge pages a process/VM holds and the more of them are idle, the lower its promotion priority. The background thread first promotes for the process furthest from fairness.

## Evidence
- End to end (inside KVM virtual machines): under fragmentation (FMFI=0.9, 1 is most fragmented), Cloudstone throughput is 1.18×, average latency drops 29.2%, and p90 drops 41.4%. Without fragmentation, average overhead is 0.7%.
- Novelty 1 → Redis: Ingens uses 12.3 GB (Linux 20.7 GB, pure 4 KB pages 12.2 GB). Throughput is 20.9K/s (Linux 21.7K, pure 4 KB pages 19.0K). "Moving off the page fault path" has no separate ablation.
- Novelty 2 → mixed workload of three VMs: Ingens saves 6.8% memory and is at most 2.5% slower. KVM saves 9.6% but is 6.5–20.2% slower. Not breaking up pages saves only 2.1%.
- Novelty 3 → 3 canneal instances: Linux takes 181/192/195 s, Ingens 186/186/187 s.
- Gaps: without fragmentation, Cloudstone throughput instead drops 13.4%. The fix is to "fall back to the Linux greedy policy when fragmentation is low". Scanning the access bit takes 11.4% CPU. Only a single NUMA node and anonymous memory were tested. Cloudstone was modified so that some web pages use about 2 MB of memory.

## When it applies
The workload's memory behavior must be dynamic (sparse allocation, multi-tenant contention). When a single large program maps large blocks of memory at once, the Linux greedy policy is good enough.
