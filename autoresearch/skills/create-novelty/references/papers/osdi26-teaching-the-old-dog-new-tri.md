# Teaching The Old Dog New Tricks: Building Efficient Data Pipelines for Large-Scale LLM Pre-training
OSDI'26 · Luofan Chen, Chenhan Wang et al. / USTC, ByteDance Seed · Full text: https://www.usenix.org/system/files/osdi26-chen-luofan.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Pre-training I/O can be computed before it happens (evaluation schedule, hot files, sample order), so let storage prepare in advance instead of reacting afterwards.

## Problem
ByteDance runs pre-training on 4K–20K GPUs over HDFS. A 90-day trace of 30,000 jobs shows three places where GPUs sit idle:
companion evaluation across data centers (DCs) (periodically running benchmarks on the latest checkpoint), checkpoint loading at restart, and decoding of multimodal samples.

## Strawman / Baseline
- **The evaluation cluster reads checkpoints across DCs on demand**: training writes a checkpoint as many shards (including optimizer state). Before evaluation they must be "merged": read back the needed parameter shards, assemble full tensors, convert to the inference format. One MM-L evaluation takes over 4 hours; I/O is 56.6% of it, and 84.8% of that is reading about 2.6 TB over the WAN during merging. Over 60% of tensors are smaller than 16 KB, so reading them one by one is limited by the 100 ms RTT. On the WAN, an average of 208 tasks compete for bandwidth first-come-first-served. As a result, the discovery of 156 regressions was delayed, wasting about 2.6 million GPU hours.
- **Reactive hot-spot replication (Scarlett-style)**: at restart, the top 5% of files cause 38.8% of peak read pressure, and a few slow reads account for 67.97% of the waiting time. The window is only a few tens of seconds; by the time a hot spot is detected, loading is over. Temporary replication also competes with loading for bandwidth.
- **CPU decoding on training machines**: decoding is 94.4% of load time (5.05 s / 5.35 s). A host that gets a long video needs 42.72 s, the per-step gap across machines reaches 5 s, and over 10,000 GPU hours are wasted per day.
- **Offline pre-decoding**: video grows more than 40×, and any hyperparameter change means redoing it. **A separate decoding cluster (tf.data service, Ray Data)**: tensors that grew 50–100× take an extra network trip, and extra machines must be provisioned for the peak.

## Novelty
1. **Evaluation is slow because of RTT, not bandwidth, and the evaluation schedule is fixed**
   Insight: Evaluation runs about every 1000 steps, so as soon as a checkpoint starts being written, we know it will be evaluated.
   So: When writing the checkpoint, pack the needed shards into large blocks and pre-replicate them to the evaluation DC. The namespace proxy NNProxy steers reads to the local copy. Evaluations triggered by anomalies (such as loss spikes) can preempt background traffic.
2. **Hot files are determined by the parallel configuration and are known at job submission**
   Insight: With checkpoint deduplication, a tensor shared by many ranks (such as the embedding) is stored as one file, and the hundreds of ranks that need it all read that file. So which files are hot, and how many ranks read them, is determined by the world size and the tensor-to-rank mapping.
   So: The training framework passes a hint to storage. Storage divides the expected concurrency by the capacity of one replica, adds replicas before loading, and reclaims them with a TTL. This avoids the root causes of reactive replication: "too late" and "competes for bandwidth".
3. **Storage-node CPUs are idle and know the upcoming samples**
   Insight: Storage nodes are bound by disk and NIC, with CPU utilization of only 20–30%. A deterministic dataloader fixes the global sample order offline, so the storage side can compute the upcoming samples.
   So: While step N computes, storage nodes decode the samples for step N+1 and extract frames before sending them back. Above 80% CPU they fall back to raw bytes. Compared with a separate cluster: the "storage → training machine" transfer already exists, so decoded data takes no extra hop and no machines are added. But the paper gives no number for how much frame extraction cuts the size. Slow decoding of long videos is hidden by doing it one step ahead and spreading it over the CPUs of the whole storage cluster. The paper does not say whether one video on one node can still take over 2 minutes.

## Evidence
- End to end: merge latency dropped 76.1% on average (T-S 89.3%, MM-L 70.8%). GPU hours wasted per regression dropped from 16,800 to 4,000, saving about 2 million GPU hours over the observation period. In a 2048-GPU controlled experiment, checkpoint loading dropped from 38.48 s to 22.78 s (−40.8%). Multimodal loading P99 dropped 85.7%, stalls dropped 63.2%, MFU rose 10.8% relative, and loading CPU on training machines dropped 94%.
- Novelty 1 → pre-replication and priority were not measured separately: no direct ablation.
- Novelty 2 → 3 replicas vs 128 replicas, measured on only one 2048-GPU job; no measured comparison with reactive replication.
- Novelty 3 → no separate ablation of frame extraction or fallback; storage-node load and network traffic are not reported.
- Gaps: The evaluation and decoding numbers are before/after comparisons in production with few setup details. The alternatives are only argued, not tested.

## When it applies
I/O must be predictable: a fixed evaluation schedule, a parallel configuration known at submission, and a deterministic dataloader. Storage nodes must have spare CPU (cloud object storage does not).
