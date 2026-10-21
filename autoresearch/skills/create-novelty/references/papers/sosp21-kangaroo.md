# Kangaroo: Caching Billions of Tiny Objects on Flash
SOSP'21 · Sara McAllister, Nathan Beckmann, Gregory R. Ganger et al. / CMU, Facebook, MSR · Full text: https://www.pdl.cmu.edu/PDL-FTP/NVM/McAllister-SOSP21.pdf (camera-ready hosted by CMU PDL, with ACM DOI) · Selected: Best Paper

**One sentence**: A small log that takes only 5% of capacity lets small objects that map to the same set be grouped into one write, so a flash cache can save both DRAM and writes.

## Problem
Social graphs, tweets and IoT metadata have billions of objects of about 100 B that must be cached on flash (about 2 TB of flash and 16 GB of DRAM per machine).
Flash lifetime limits the write volume (3 full-drive writes per day, i.e. 62.5 MB/s). Flash writes in 4 KB pages: writing one 100 B object writes a whole page, a 40× amplification. Small random writes also raise the SSD's internal write amplification from about 1× to about 10×, and the two multiply.

## Strawman / Baseline
- **Log-structured cache (LS, e.g. Flashield)**: sequential batched writes, write amplification about 1× → but every object needs a DRAM index entry. The leanest uses 30 bit/object, and 2 TB of 100 B objects still needs 75 GB of DRAM. In the experiments, a 16 GB index can manage only 61% of flash.
- **Set-associative cache (SA, e.g. CacheLib SOC)**: hashes the key to one 4 KB set and needs only a Bloom filter of about 3 bit per object → but each inserted object rewrites the whole set (40×). In production, over half of flash is left empty to keep SSD write amplification down, and some objects are rejected at random, which lowers the hit ratio.
- **Eviction policy under set associativity**: there is no DRAM index to store access information, and changing on-flash metadata on a hit costs more writes → only FIFO is possible, and hot objects keep getting pushed out.
- **Flash KV stores (SILT, RocksDB)**: assume deletes are rare, but a cache evicts all the time → holes or frequent compaction. Netflix needs 67% more capacity when using RocksDB as a cache.

## Novelty
1. **A small log already has enough hash collisions to amortize set writes**
   Insight: the number of log objects that map to a given set follows a binomial distribution. With 500 million objects in the log and 460 million sets in total, flushing one object can often carry other objects of the same set along.
   So: put a log layer with 5% of capacity in front (with a DRAM index) and a set-associative layer with 95% behind it. When the log flushes, it writes the log objects in the same set as the flushed object into that set at once. The index's hash buckets are partitioned by set, so finding objects of the same set only scans one bucket.
   The log holds only 5% of objects, so total DRAM is 7.0 bit/object, 1/4.3 of Flashield. This answers both root causes: log-structured caches lack DRAM, and set-associative caches write too much.
2. **A cache can drop objects, so write only when the write is worth it**
   Insight: a KV store must keep objects; a cache need not.
   So: if fewer than 2 objects of the same set are gathered, do not write them into the set-associative layer; drop them (objects that were hit in the log go back into the log). The writes saved outweigh the objects dropped: only 44.4% of 100 B objects are admitted, and write volume falls to 22.8%. The model gives write amplification of 5.8×, vs. 17.9× for a set-associative cache of the same size.
3. **RRIP only needs to change metadata at eviction, and at eviction the set is rewritten anyway**
   Insight: RRIP state (a multi-bit, clock-like eviction policy) changes in only two places: "promote on access" and "age on eviction". Promotion can be deferred to the next rewrite of the set, as long as "was it accessed" is remembered.
   So: the 3-bit prediction value is stored in the set on flash; DRAM keeps only a 1-bit access bit per object, applied when the set is rewritten, with no extra writes. This answers the "only FIFO is possible" root cause.

## Evidence
- End to end (Facebook trace, 16 GB DRAM, 1.9 TB, 62.5 MB/s): 29% fewer misses than SA (miss ratio 0.29→0.20) and 56% fewer than LS. Usable flash: Kangaroo 93%, SA 81%, LS 61%. Peak throughput is 94% of SA. Production trial deployment (vs. SA): 18% fewer flash misses at the same write volume; 38% fewer writes with full admission; 42.5% fewer writes with ML admission.
- Novelty 1 → step-by-step ablation: adding the log layer cuts writes by 42.6% with misses nearly unchanged (<0.05%).
- Novelty 2 → threshold 2: writes down 32.0%, misses up 6.9%; at the highest threshold, writes down 70.4%, misses up 72.9%.
- Novelty 3 → vs. FIFO: a 1-bit prediction value gives 3.4% fewer misses, 3 bits give 8.4% fewer.
- Gaps: LS is an optimistic version built by the authors (Flashield is not open source). Sensitivity experiments come from a simulator (error within 10%). With a very low write budget or small flash (<1.2 TB on the Facebook trace), LS is better. The theoretical model assumes independent object accesses and FIFO; the appendix was not peer-reviewed.

## When it applies
Objects must be much smaller than a 4 KB page, and DRAM must be scarce relative to flash. When objects approach 2 KB or DRAM is plentiful, a log-structured cache is enough.
