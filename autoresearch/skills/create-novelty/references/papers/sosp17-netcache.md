# NetCache: Balancing Key-Value Stores with Fast In-Network Caching
SOSP'17 · Xin Jin et al. / JHU, Barefoot Networks, Princeton, Cornell, UC Berkeley · Full text: https://xinjin.github.io/files/SOSP17_NetCache.pdf (author homepage, camera-ready) · Selected: Highly cited (727 citations)

**One sentence**: Balancing N servers needs a cache of only O(N log N) hot keys, but the cache must be orders of magnitude faster than the servers, and a ToR switch fits exactly.

## Problem
In-memory KV stores partition by hash. Hot keys overload a few servers, the whole rack is held back by the slowest one, and tail latency rises.
Without a cache, under Zipf 0.95/0.99 the total throughput of 128 servers falls to only 22.5%/15.6% of the uniform-load throughput.

## Strawman / Baseline
- **A server cache layer (SwitchKV)**: an in-memory cache in front of flash storage. → When storage is already in memory, cache nodes are as fast as storage nodes (about 10 MQPS). To carry the whole rack's load, you need as many cache nodes as the storage layer has. SwitchKV also needs a separate access-statistics component on the servers.
- **Selective replication / data migration**: copy hot keys to more nodes. → Uses more hardware, and must handle data movement, consistency and query routing.
- **NPU in-network cache (IncBricks)**: aims for a high hit rate, so it needs a large capacity; NPU throughput is not enough.
- **Naive implementation on the switch**: the control plane can update fewer than 10,000 table entries per second, so LRU/LFU, which change the cache on every access, cannot work. The register array of each pipeline stage can read or write only a small fixed number of bytes per packet, which cannot hold a 128B value.

## Novelty
1. **A load-balancing cache needs to be "fast", not "large"**
   Insight: Existing theory proves that absorbing the hottest O(N log N) keys keeps N partitions from overloading, regardless of the total number of keys; a hit rate under 50% is enough. But the cache's throughput must far exceed a single server's; otherwise the cache layer itself must be as large as the storage layer.
   So: Put the cache in the data plane of the ToR switch, with the values of hot keys in on-chip SRAM. A switch processes billions of packets per second, so one switch carries the whole rack, and it is already on the path. A few thousand small values (76% of Facebook's reads are for values <100B) fit in tens of MB of on-chip memory. This removes exactly the root cause of server caches, "as many as the storage".
2. **The switch is on the path of every query, so consistency and hot-key statistics can be done along the way**
   Insight: Every write must pass through the ToR switch, and so does every read miss.
   So: When a write passes, the data plane invalidates the cache entry and tells the server "this key is cached". The server finishes the write, replies to the client first, then sends a packet to write the new value back into the switch; until then it blocks later writes to that key. Hot-key statistics are also done in the data plane: counters for cached keys, and for uncached keys a Count-Min sketch (approximate counting) plus a Bloom filter (dedup) to report them. The controller replaces an entry only when a key is hot enough. This avoids the obstacle of slow control-plane updates, and needs no separate statistics component on the servers as SwitchKV does.
3. **Split variable-length values across register arrays in several stages, addressed by one index**
   Insight: Each register array can read only a small slice per packet, but several stages can read at the same index in parallel.
   So: One table lookup gives both a bitmap (which arrays hold the value) and a shared index. Each stage adds its slice to the packet according to the bitmap. The controller assigns slots with First Fit bin packing. Lookup entries need not be copied per array, so resource cost is minimal.

Other design: The lookup table is replicated in every ingress pipe; values are stored only in the egress pipe where the corresponding server is attached.

## Evidence
- End to end: 2 servers in rotation emulate 128 (each a 10 MQPS TommyDS store), with a 10,000-entry cache, read only. Compared with no cache, throughput rises 3.6×/6.5×/10× under Zipf 0.9/0.95/0.99. Without a cache, latency is 15 µs and saturates at 0.2 BQPS; NetCache averages 11–12 µs and stays flat up to 2 BQPS. One Tofino reached 2.24 BQPS (limited by the packet senders) using less than 50% of on-chip memory.
- Novelty 1 → cache-size experiment: caching only 1000 entries balances 128 nodes to uniform-load throughput.
- Novelty 2 → write-ratio experiment: with uniformly distributed writes, throughput drops linearly with the write ratio; with equally skewed writes, above a write ratio of 0.2 it matches or is slightly worse than no cache. Dynamic load: 200 cold keys turn hot every 10 s, and throughput recovers quickly. No comparison with other consistency schemes or server-side statistics: no direct ablation.
- Novelty 3 → throughput does not change with value size (≤128B) or cache size. No direct ablation.
- Gaps: Compared only with no cache, not with SwitchKV or replication. The 128 servers are pieced together by rotation; the dynamic experiment emulates 64 servers with 64 queues, with throughput scaled down 64×. Keys are fixed at 16B, values ≤128B, single rack only.

## When it applies
Read-heavy, write-light, with skewed reads. When writes are also concentrated on hot keys (write ratio >0.2), the benefit disappears. Values must be small enough to fit in the switch pipeline.
