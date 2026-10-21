# Pocket: Elastic Ephemeral Storage for Serverless Analytics
OSDI'18 · Ana Klimovic et al. / Stanford University, IBM Research · Full text: https://www.usenix.org/system/files/osdi18-klimovic.pdf (camera-ready) · Selected: Highly cited (385 citations)

**One sentence**: Intermediate data of serverless jobs lives only tens of seconds and can be recomputed, so scaling does not need to migrate data. Job size is also known at registration, so storage can be provisioned per job in seconds.

## Problem
Multi-stage analytics jobs (sort, video analytics, distributed compilation) run on AWS Lambda. Lambdas in different stages cannot talk directly, so intermediate data (ephemeral data) can only be exchanged through remote storage.
This data ranges from a few hundred B to a few hundred MB. A 100 GB sort with 500 lambdas needs 7.5 GB/s. Demand rises and falls with jobs, on the scale of seconds.

## Strawman / Baseline
- **Managed object stores like S3**: Scale automatically and bill by usage, but are designed for durability. → A 1 KB read takes about 12 ms. A 100 GB sort with ≥500 lambdas gets throttled and fails.
- **ElastiCache Redis**: DRAM key-value store with low latency. → Users must pick the instance type and node count themselves. Changing size often means rebuilding the cluster, nodes take minutes to start, and billing is per hour. Clients find nodes by hashing keys, so adding or removing nodes means moving data. All-DRAM is also expensive.
- **Flash/multi-tier storage (Aerospike, Crail)**: Cheaper, but still needs manual configuration. → Storage media, node count, CPU, and bandwidth combine into a large performance-cost space. Finding the Pareto-optimal point for one job is already hard, and harder when several jobs overlap.

## Novelty
1. **Intermediate data is short-lived and recomputable, so scaling only needs to steer new data**
   Insight: Intermediate data lives only 10–100 seconds. If lost, the framework can recompute it from lineage (the sequence of tasks that produced it). And it is often written once and read once.
   So: No replication. When scaling up, only direct the data of new jobs to new nodes. When scaling down, first stop placing new data on the node, wait for old data to disappear as its jobs end, then take the node offline. Data is never migrated. For this, key hashing is dropped. Instead, a metadata server routes requests by a weight table per job (the share of that job's data each storage node gets), and storage nodes do not know the metadata. This targets the root cause that Redis must move data and rebuild the cluster to scale. The cost is one extra metadata RPC of about 140 µs per access.
2. **A job's I/O needs can be estimated at registration**
   Insight: A serverless job knows its maximum number of concurrent lambdas N before it starts. And the network bandwidth of one lambda has a cap (about 600 Mb/s on AWS). So N times this cap is an upper bound on throughput.
   So: At registration a job can optionally give hints: N, whether it is latency-sensitive, capacity, and throughput. The controller uses them to allocate resources along three dimensions (throughput, capacity, media), then places them on nodes with online bin packing. If the job is not latency-sensitive, its data goes to NVMe Flash instead of DRAM. This solves the manual Pareto-point choice for the user.

Other design: the control, metadata, and data planes each scale to stay in a 60–80% utilization band; the NVMe tier is based on user-space ReFlex; a DELETE hint lets data that is deleted after reading be reclaimed at once.

## Evidence
- End to end: The three jobs perform the same as on ElastiCache Redis at 59% lower cost (for example, 100 GB sort costs $2.16 vs $5.32 per hour). For the two stages of video analytics, intermediate data I/O time is 3.2× and 4.1× lower than S3. Sort and video analytics are 40–65% slower on S3. A 1 KB access on Pocket-DRAM/NVMe takes <540 µs, more than 45× faster than S3.
- Novelty 1 → When three jobs register/deregister one after another, allocated bandwidth follows demand, and job time is within <5% of the default 50-node configuration. Starting containers takes only a few seconds. When a new VM is needed, registration can stall for up to 215 s. There is no comparison with "scaling that migrates data": no direct ablation.
- Novelty 2 → Adding hints one by one lowers cost step by step, and job time stays within <4% of the default configuration. NVMe throughput per GB per dollar is 19.7× that of HDD.
- Gaps: Redis is billed per whole VM, while Pocket is billed at an inferred fine-grained unit price, so part of the 59% comes from the billing method. S3 is still orders of magnitude cheaper. Fault tolerance is not evaluated. Hints come from the user, and a job that exceeds its hints is not throttled. λ-cc is CPU-bound, and the three show no difference.

## When it applies
The data must really be ephemeral and recomputable, and the job size must be known before it starts. The smallest cluster costs $1.632 per hour, so a cloud provider needs multi-tenancy to spread the cost.
