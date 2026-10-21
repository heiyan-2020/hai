# Neural Adaptive Content-aware Internet Video Delivery
OSDI'18 · Hyunho Yeo, Youngmok Jung, Jaehong Kim, Jinwoo Shin, Dongsu Han / KAIST · Full text: https://www.usenix.org/system/files/osdi18-yeo.pdf (camera-ready) · Selected: Highly cited (247 citations)

**One sentence**: The content of on-demand video is known in advance. A super-resolution DNN trained specifically for each video, and deliberately overfit, has predictable quality. Shipped along with the video, it lets client GPUs stand in for bandwidth.

## Problem
Adaptive bitrate streaming such as DASH cuts video into segments of a few seconds, and an ABR algorithm (adaptive bitrate) picks a bitrate for each segment. Quality is limited entirely by bandwidth.
Yet GPUs on users' PCs are mostly idle. People and scenes that recur in the same video are also not exploited, because codecs remove redundancy only within one GOP (a group of frames a few seconds long).

## Strawman / Baseline
- **Better ABR (BOLA, RobustMPC, Pensieve)**: only picks bitrates within the bandwidth. Pensieve's gain over MPC comes mainly from fewer stalls at the cost of bitrate; it cannot break the bandwidth limit.
- **Generic super-resolution DNN (trained on standard image sets)**: quality on unseen videos is unpredictable. For some categories (such as Music), PSNR/SSIM is even lower than plain upscaling of the original 240p.
- **Client always runs one fixed DNN**: desktop GPUs differ 5.68× in compute, and the load on one GPU also changes. MDSR on a Titan Xp processes 720p input at only 3.23 fps. Either it cannot run in real time, or it wastes compute.
- **Simply download the DNN while playing**: the largest DNN (2,145 KB) is about the size of one 4-second 1080p segment, so downloading it competes with video for bandwidth. Downloading at a fixed fraction of the video bitrate causes stalls if too fast, and the DNN arrives too late to use if too slow.

## Novelty
1. **Treat overfitting as a feature: the test set is the training set**
   Insight: The content of on-demand video is fully known at upload time. A DNN's training error is near zero; it is only unreliable on new data. If it is used only for this one video, there is no "new data".
   So: The server trains a dedicated super-resolution DNN for each video, restoring low-resolution frames to 1080p, and ships it with the manifest. Quality is the same as what was seen in training, which targets exactly the root cause of generic DNNs being unreliable. What it learns is content that recurs across GOPs, which amounts to covering the long-range redundancy that codecs cannot see. Fine-tuning from a generic model cuts training cost by 5–6×.
2. **Make the DNN a stream too, with selectable levels and partial use**
   Insight: Inference time depends only on the network structure, not on the weights. If residual blocks are randomly skipped during training, they can also be skipped at inference.
   So: Each input resolution offers four DNN levels. Using the layer and channel counts in the manifest, the client builds a fake model with random weights and test-runs it for 1.64–3.40 seconds, then picks the largest level that runs in real time, without downloading anything. The DNN is made of skippable residual blocks: it can be used once the base layers (about 35% of the full model) are downloaded, and when the GPU slows down, fewer blocks are used. This solves heterogeneous compute and slow downloads.
3. **ABR must treat "download the DNN" as an action**
   Insight: After DNN enhancement, the effective quality of low-bitrate segments goes up. The value of downloading the DNN depends on future bandwidth, so rules cannot be written by hand.
   So: Use reinforcement learning (reusing the Pensieve framework) to decide at each step whether to download the next DNN chunk or a video segment at some bitrate. The reward uses "effective bitrate": the enhanced SSIM mapped back to the bitrate with the same quality.

## Evidence
- End to end: 27 YouTube videos, real 3G and broadband bandwidth traces (mean 1.31 Mbps). QoE is 43.08% (linear), 36.26% (log) and 42.57% (HD-preferring) higher than Pensieve, 21.89–76.04% by category, and 92.28% higher than BOLA. At equal QoE it saves 17.13% bandwidth (simulator). Training costs 0.23 dollars per minute of video, recovered after 30 hours of cumulative viewing.
- Novelty 1 → dedicated DNN vs generic DNN: the former improves steadily in every category (figures only).
- Novelty 2 → before the full DNN finishes downloading (47.82 s on average), using a partial DNN raises median QoE by 17.54% and mean by 3.35%. All 6 GPUs pick a level that runs in real time. Under downclocking, a version that uses only the full DNN cannot run in real time.
- Novelty 3 → compared with downloading the DNN at 10%/100% of the video bitrate: QoE is 16.36%/9.13% higher; aggressive downloading has a 2.5× stall penalty. After the download, "enhancement-aware" bitrate selection helps only HD-preferring QoE (+28.96%), and log QoE instead drops 3.14%.
- Gaps: large-scale results are assembled from network simulation plus measured DNN quality and latency, checked against real devices only on part of the data. Only desktop GPUs were tested; the default is a 1,200-dollar Titan Xp. A 1080 Ti takes 3.76 seconds to process 4 seconds of video, leaving little margin.

## When it applies
Only for on-demand video; live streams cannot be trained in advance. Clients need desktop-class GPUs, and a video must be watched enough to amortize the training cost.
