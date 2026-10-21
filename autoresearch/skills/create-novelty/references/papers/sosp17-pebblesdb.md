# PebblesDB: Building Key-Value Stores using Fragmented Log-Structured Merge Trees
SOSP'17 · Pandian Raju, Rohan Kadekodi, Vijay Chidambaram, Ittai Abraham / UT Austin, VMware Research · Full text: https://www.cs.utexas.edu/~vijay/papers/sosp17-pebblesdb.pdf (camera-ready from author homepage) · Selected: Highly cited (377 citations)

**One sentence**: LSM write amplification comes from "keys within each level never overlap", but reads need only coarse non-overlap, so partition only by ranges and allow overlap within a range.

## Problem
LSM (log-structured merge tree) stores such as LevelDB/RocksDB have high write amplification (total bytes written to disk / user data).
This wears out SSDs, and compaction also eats write bandwidth: RocksDB's write throughput is only 10% of its read throughput.

## Strawman / Baseline
- **Classic LSM (LevelDB, RocksDB, HyperLevelDB)**: the key ranges of the sstables (sorted files on disk) in each level do not overlap, so a lookup in one level reads only one file. → When an upper-level file is merged down, every file in this level whose range intersects it must be rewritten whole, so the same data is rewritten again and again within the same level.
- **B+ tree (KyotoCabinet)**: random in-place writes. → Inserting 100 million pairs wrote 829 GB, a write amplification of 61×.
- **Do not merge at compaction; just append files to the next level (FIFO/universal compaction)**: → the number of files explodes, file ranges in the same level overlap, binary search cannot locate a file, and one read must check many files. LSM-trie simply does not support range queries.

## Novelty
1. **Reads only need "which range a key is in"; overlap within a range is fine**
   Insight: LSM requires a whole level to be non-overlapping so that each level needs only one file lookup. But locating needs only coarse non-overlap. If overlap is allowed within a range, lower-level files need not be rewritten.
   So: Each level is cut into non-overlapping ranges by a set of guards (boundary keys). sstables within the same guard may overlap. At compaction, merge-sort a guard's files, cut them by the next level's guards, and append them to the matching guards without touching the files already there. Data is written only once per level; only the last level needs rewriting.
   Like a skip list, guards are chosen at random by key hash, and an upper level's guards are also guards of the lower level, getting finer with depth. Partitioning is even without knowing the key distribution in advance, and a compaction affects only the sub-ranges of one guard.
   This removes the root cause of classic LSM: rewriting within a level. With a limit of 1 file per guard, it degenerates into an LSM.
2. **Most of the read cost of overlap can be paid in memory**
   Insight: Many files in a guard means only that several files "may" need reading. Guard metadata and each sstable's bloom filter fit in memory, so a point lookup mostly reads only one file.
   So: A point lookup first binary-searches for the guard, then uses sstable-level bloom filters to rule out files; in theory each get needs only O(1) disk reads. Range queries cannot use bloom filters, so: only at the last level (the largest, likely not cached) are the files in a guard read in parallel; 10 consecutive seeks trigger a compaction of that guard.
   This answers "without merging, reads become too slow".

## Evidence
- End to end: db_bench random writes of 500 million keys; write amplification is 2.5× lower than RocksDB and HyperLevelDB, and 1.6× lower than LevelDB. Random-write throughput is 2.7× HyperLevelDB (abstract: 6.7× RocksDB). On YCSB, Load A/E is 1.5–2× faster, with half of RocksDB's write IO. HyperDex throughput improves by up to 59% (geometric mean 105% with 16 KB values). MongoDB throughput matches RocksDB with 40% less IO.
- Novelty 1 → HyperLevelDB was also given sstable bloom filters before comparing, to remove the bloom filters' contribution: compaction is 2.5× faster and update throughput 2.15×. No comparison of guard-selection methods.
- Novelty 2 → sstable bloom filters make reads 63% faster (the read lead also comes partly from larger sstables, whose index blocks hit the cache more easily). Removing all range-query optimizations cuts range throughput by 66%.
- Gaps: Range queries are 11–30% slower than HyperLevelDB (worst for seek only after full compaction). Sequential-insert throughput is only 1/3 of it. Seeks are 47% slower when all data is in memory. CPU 171%, other systems 98–110%.

## When it applies
Keys inserted randomly, data much larger than memory. With sequential inserts (LSM can move files down with zero IO), or many small range queries after a period of writes, LSM is better.
