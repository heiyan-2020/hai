# A large scale analysis of hundreds of in-memory cache clusters at Twitter
OSDI'20 · Juncheng Yang, Yao Yue, K. V. Rashmi / CMU, Twitter · Full text: https://www.usenix.org/system/files/osdi20-yang.pdf (USENIX camera-ready) · Selected: Highly cited (271 citations)

**One sentence**: 153 cache clusters show that short TTLs bound the effective working set, write-heavy caches are common, and FIFO≈LRU when capacity is enough. The focus should shift from eviction to expiration.

## Problem
Research on in-memory caches (Memcached/Redis) relies on assumptions about workloads. The only public basis is Facebook's 2012 analysis of 5 pools and YCSB-style synthetic workloads. TTL (object expiration time) is always set in practice, but almost no research looks at it. The authors collected and released one week of unsampled traces from 153 Twemcache clusters at Twitter.

## Strawman / Baseline
- **"Caches are read-heavy"**: Past systems (such as optimistic cuckoo hashing) optimize the read path specifically. → The write path is heavier and more likely to trigger eviction, and write-heavy workloads have higher tail latency. Optimizing only the read path does not help.
- **"Lower the miss ratio with better eviction algorithms"**: Recent work adds more metadata per object to improve eviction. → It ignores expired objects. Reading an expired object also counts as a miss, yet it still takes memory until it is evicted.
- **Existing proactive expiration**: Facebook's transient pool stores objects with second-level TTLs separately → It only works when second-level and long TTLs are mixed. Memcached's background crawler scans all objects periodically → A short period wastes CPU and bandwidth; a long period leaves expired objects around for one more period. The wider the TTL range, the harder the trade-off.
- **"LRU is better than FIFO"**: Extra metadata and locks are paid for this.

## Novelty
1. **TTL caps the effective working set, so expiration matters more than eviction**
   Finding: 66% of clusters have an average TTL ≤12 hours, and more than 25% have one shorter than 20 minutes. The total number of active objects keeps growing, but the total number of unexpired objects plateaus after one TTL. As long as expired objects are removed in time, many caches can bring misses down to only first accesses with bounded capacity.
   And existing proactive expiration cannot cover these workloads: only 20% of clusters use a single TTL (so the transient pool does not apply). Fewer than 35% have a minimum TTL shorter than 300 seconds, and more than 25% of clusters have a minimum TTL longer than 6 hours. 25% of clusters have a max/min TTL ratio ≥100: if the crawler must clear the shortest objects within 2×TTL, the longest objects get scanned 100 times.
2. **Write-heavy is a distinct class of workload, coming from "caching for computation"**
   Finding: More than 35% of clusters have a write ratio >30%, and more than 20% of clusters >50%. They mostly cache computation results and transient data with no backend (rate-limit counters); these two uses together make up 70% of clusters. Write-heavy comes together with short TTL, low access frequency, and low skew: the median TTL of write-heavy workloads is about 10 minutes, versus about 15 hours for read-heavy. The median Zipf α is 0.9 and 1.4 respectively. The Pearson correlation between write ratio and these items is between -0.63 and -0.77. Optimizing and evaluating only read-heavy workloads misses this whole class.
3. **When capacity nears production scale, differences between eviction algorithms disappear**
   Finding: Near production capacity, FIFO and LRU have about the same miss ratio. LRU is clearly better only at very small capacity (the authors guess that some workloads have reuse intervals in several bands, and LRU demotes objects that are accessed again only after a long time). Within 2× of production capacity, the differences between all algorithms disappear.
   Corollary: Instead of adding metadata to improve eviction, raise effective capacity: shrink metadata (38 B per object at Twitter, 56 B in Memcached), and compress keys (in 60% of workloads, keys and values are the same order of magnitude).

Other findings: Read-heavy workloads are highly skewed (α mostly in 1–2.5). Object size distributions change over time and cause slab calcification (memory stuck in old size classes); on these workloads, slab-level LRU is best.

## Evidence
- Data: 306 instances, about 700 billion requests, 80 TB. Analysis focuses on the 54 largest clusters, which carry 90% of QPS. Eviction algorithms are simulated with the authors' own libCacheSim (5 days of warm-up, 1 day of evaluation).
- Novelty 1 → Working set curves of two representative workloads, plus TTL distribution statistics. "How much memory and how many misses timely expiration saves" is not simulated: no direct validation.
- Novelty 2 → Write ratio CDF and correlation table. "Write-heavy has higher tail latency" is only a qualitative observation, with no numbers.
- Novelty 3 → Statistics of the best algorithm at 4 capacity levels: at the "large" level (76% of production clusters are larger than this level), slab-level LRU is best on only about 10% of workloads. Except at the smallest level, the distribution of the relative difference between FIFO and LRU is centered on 0 and symmetric.
- Gaps: Only one company. The shares of the three uses are the authors' estimates. LRU/FIFO are simulated as systems without slabs and fragmentation is not counted, so results favor them.

## When it applies
The conclusions depend on how Twitter uses caches: single tier, single tenant, TTL is mandatory (GDPR). Multi-tier caches flatten hotspots, so the conclusions about skew and FIFO≈LRU may differ.
