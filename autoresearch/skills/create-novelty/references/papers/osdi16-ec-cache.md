# EC-Cache: Load-Balanced, Low-Latency Cluster Caching with Online Erasure Coding
OSDI'16 · K. V. Rashmi, Mosharaf Chowdhury et al. / UC Berkeley, University of Michigan · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-rashmi.pdf (camera-ready) · Selected: Community favorite (4 sources: Marc Brooker blog, Michigan EECS 582 2016, Michigan EECS 598/CSE 585 2019, Princeton COS 518 2017)

**One sentence**: Objects cached in analytics clusters are tens of MB. Split and encode them, and any k pieces restore the object. So load spreads at 1/k granularity, and reading one extra piece shakes off slow nodes.

## Problem
Data analytics clusters often put an in-memory cache layer (such as Alluxio) in front of object storage (S3 and others). In a trace of 3000 Facebook machines, object access is highly skewed: the hottest 5% are 7 times hotter than the coldest 3/4. For more than half the time, the busiest oversubscribed link has more than 4.5 times the average utilization. When a server fails, reads fall to disk.
As a result, a few cache servers are overloaded, and both median and tail latency get worse.

## Strawman / Baseline
- **Selective replication (Scarlett and others; more replicas for hot objects)**: → each extra replica costs 1× more memory. The granularity is too coarse: hotness can only be spread in whole copies. At the same 15% memory overhead, the busiest server's load is 43.45% above the ideal average. If a replica's machine is saturated by background traffic, reads still get stuck.
- **Replication + splitting (each piece replicated the same number of times)**: parallel reads and finer load. → One read must wait for all k pieces, so any slow piece holds up the whole read, and tail latency gets worse. To "send one extra and take the first to arrive" costs at least 2× memory plus 2× bandwidth.
- **Erasure codes in storage systems (encoding across objects)**: k objects produce r parity objects, used only to rebuild lost data. → Rebuilding reads other objects, with high bandwidth cost. It serves only fault tolerance and cannot share read load.

## Novelty
1. **Objects are large enough to erasure-code each object on its own, which spreads load at 1/k**
   Insight: Objects in analytics workloads are MB-scale (only 7% of reads in the trace are smaller than 1 MB). After splitting into k pieces, the costs of opening connections and decoding are amortized.
   So: Split each object into k pieces and compute r parity pieces with a Reed-Solomon code (any k pieces can decode). Put the k+r pieces on different servers. A read reads any k pieces and decodes. The load variance of one server drops to 1/k of selective replication. Redundancy is tuned as the fraction r/k: hot objects get a few more parity pieces instead of whole copies. This solves the coarse granularity of selective replication.
2. **"Any k pieces will do" means reading one extra piece costs only 1/k more bandwidth**
   Insight: When reading exactly k pieces, the chance of hitting a slow node rises from p to 1−(1−p)^k, so tail latency gets worse. But erasure-coded pieces can replace each other. Unlike replication, there is no need to read a particular replica of a particular piece.
   So: Read k+Δ pieces and decode with the first k to arrive (late binding). With k=10 and Δ=1, it costs only 10% more bandwidth, and it avoids slow nodes, background-traffic hot spots and failed nodes. For replication + splitting to get the same choice costs at least 2×.

Other design: a persistent layer sits under the cache, so codes optimized for repair are not needed; it picks MDS RS codes and uses Intel ISA-L to speed up encoding and decoding; objects smaller than 1 MB still use selective replication; built on Alluxio.

## Evidence
- End to end: on EC2 with 25 cache servers and 30 clients, Zipf 0.9, 40 MB objects, both at 15% memory overhead. Load imbalance 43.45% → 13.14% (3.3×). Median latency is 2.64× faster, P99.9 is 1.79× faster. With unbalanced background traffic added, P99.9 is 2.56× faster. With one server turned off, P99.9 is 2.8× faster. With object sizes from the Facebook trace, the median gain rises from 1.33× at 1 MB to 5.5× at 100 MB. P99 gains only above 10 MB (1.25×–3.85×).
- Novelty 1 → only k was varied: larger k gives better load balance, with shrinking median latency gains, but too large a k makes tail latency worse. As memory overhead grows, the load balance gap between the two narrows.
- Novelty 2 → Δ=0 vs Δ=1 (k=10): without the extra read, median latency is good but high percentiles are very bad. One extra piece holds down the tail. With k=12, sweeping Δ=0–4: the first one or two pieces give the largest gain. The replication + splitting baseline is shown only as a CDF plot, with no numbers.
- Gaps: decoding is single-threaded and takes about 30% of read time. For objects smaller than 40 MB, writes are slower than replication. Hotness uses a synthetic Zipf; the trace gives only object sizes. Background traffic is simulated. Hotness that changes over time is not implemented (Alluxio does not support append).

## When it applies
Objects must be large (MB-scale or more) and immutable. An in-place update must recompute all parity pieces. When connection setup cost dominates for small objects, the method does not pay off.
