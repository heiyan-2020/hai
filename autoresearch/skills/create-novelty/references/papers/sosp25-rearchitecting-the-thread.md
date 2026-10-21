# Rearchitecting the Thread Model of In-Memory Key-Value Stores with μTPS
SOSP'25 · Youmin Chen, Jiwu Shu et al. / Shanghai Jiao Tong University, Tsinghua University · Full text: https://cgi.di.uoa.gr/~mema/courses/m131/papers/tps.pdf (ACM camera-ready reposted on a course page) · Selected: Best Paper

**One sentence**: Within one KV request, receiving packets almost always hits in cache, while index lookups miss everywhere; split the two across different threads by cache residency, and the former no longer gets flushed out.

## Problem
RDMA in-memory KV stores must handle tens of millions of operations per second. Each request has only a few hundred ns, while one cache miss costs 50–150 ns.
The mainstream approach is run-to-completion (RTC): each thread is pinned to a core and does everything from receiving the packet to sending the reply in one go (MICA, FaRM).

## Strawman / Baseline
- **RTC (BaseKV, which differs from μTPS only in the thread model)**: the NIC uses DDIO (writing directly into the LLC) to put requests in cache, but the same thread then looks up the index and copies data, sweeping large areas of memory and pushing the network buffers out: LLC miss rate 33%. Under skewed writes, threads spin on the lock of a hot item and meanwhile neither receive nor reply; more threads mean more spinning, and throughput falls as the thread count grows (the paper only has a figure).
- **Add CAT (a per-core mask of which LLC ways a core may fill) to isolate DDIO's ways**: when DDIO hits, it writes in place, so lines stay scattered across other ways; and receiving and index lookup run on the same core, so they can only use the same mask. With small items it is on par with RTC.
- **Share-nothing (keys partitioned across threads, eRPC-KV) / share-everything (any thread handles any key)**: the former has load imbalance under skew; in the latter, synchronization overhead crushes throughput as threads increase.
- **Classic thread-per-stage (SEDA, HBase with about 1000 threads)**: splits into many stages by function and relies on OS scheduling; at µs scale, communication between stages is too expensive. In kernel-bypass RPC the client picks the server thread, so changing the thread count means notifying all clients.

## Novelty
1. **Split stages by cache residency, not by function**
   Insight: receiving/parsing/replying and the working set of the hottest ~10,000 keys are small and can stay resident in cache; the index and cold data are bound to miss.
   So: split into only two stages, on different cores. The cache-resident layer handles network buffers and hot keys; the memory-resident layer holds the full index and processes in batches, hiding misses with coroutines plus prefetching. Network buffers are touched only by the former's cores, so the same thread's index scans no longer flush them out. Only after the two kinds of access are on different cores can CAT give them different masks, so the memory-resident layer's cores can fill only their own share of ways. However, under skewed load the auto-tuner opens almost all ways to it, and the paper does not measure CAT's contribution separately.
2. **Only writes to the same item conflict, and they can be throttled on their own**
   Insight: when receiving, the i-th thread takes only slot m of the receive buffer (m mod n = i); replies use separate buffers; reading an item uses version numbers with no locks; only writes to the same item need a CAS lock.
   So: limit the number of threads that perform writes. Fewer threads spin, and the rest keep receiving and replying, so the whole request path does not stall as in RTC. The paper only says the auto-tuner adjusts thread counts per layer to reduce contention; it does not say which layer hot-key writes land in.
3. **Split into only two stages, and keep reconfiguration on the server side**
   Obstacle: in thread-per-stage, both inter-stage communication and thread count changes are too expensive.
   So: there is only one cross-stage handoff, with one lock-free ring per thread pair; requests are 16 B and pushed in batches. All clients share one receive queue (RDMA SRQ), so changing the thread count only changes the server's n. One auto-tuner adjustment takes about 0.9 s.

## Evidence
- End to end (28 cores, 200 Gbps RDMA): 1.03–5.46× faster than RTC; tree index YCSB-B/C 1.30×/1.29× on average; hash with 8B only 3.0–8.6% faster; Twitter traces 44.5%/39.8%/0.1% faster (the third is uniform writes). Latency is similar.
- Novelty 1 → motivation experiment (no CAT; deterministic replay removes inter-stage communication): 1.22–1.54×, LLC miss 2% vs. 33%; splitting off just the 0.1‰ hot keys gives 1.08×.
- Novelty 2 → under skewed writes, BaseKV falls as threads increase and μTPS does not (figure only). No direct ablation.
- Novelty 3 → batching +51.6% (tree)/+93.7% (hash); after a load change, tuning finishes within 0.9 s, throughput +20%. Under some write-heavy or uniform loads, eRPC-KV is faster (by up to 12% with write skew).
- Gaps: gains are small for hash or uniform loads; with uniform writes, coherence traffic cancels the gain; slightly worse with few threads.

## When it applies
The load must be skewed or use a tree index, and there must be enough cores to split in proportion; it depends on Intel LLC features such as DDIO and CAT.
