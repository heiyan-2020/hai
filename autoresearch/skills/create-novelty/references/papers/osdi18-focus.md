# Focus: Querying Large Video Datasets with Low Latency and Low Cost
OSDI'18 · Kevin Hsieh, Ganesh Ananthanarayanan et al. / CMU, Microsoft, ETH Zurich · Full text: https://www.usenix.org/system/files/osdi18-hsieh.pdf (USENIX camera-ready) · Selected: Highly cited (310 citations)

**One sentence**: A cheap CNN's top-1 answer is often wrong, but the right answer is almost always in its top few. So at ingest time aim only for recall, and recover precision at query time.

## Problem
Traffic and surveillance cameras record all the time. Later, people want to find "which frames contain a certain class of object (such as an ambulance)", and fast.
Taking YOLOv2 as the accuracy standard (GT-CNN), running detection over one month of traffic video takes about 190 GPU hours and 380 dollars.
Which class will be queried is not known in advance, and most video will never be queried.

## Strawman / Baseline
- **Run GT-CNN over everything at ingest (Ingest-heavy)**: a query only needs an index lookup. → Ingest is very expensive, and most video is never queried, so all that work is wasted.
- **Process at query time (NoScope)**: train a small binary classifier for the queried class to filter frames, and pass only uncertain ones to GT-CNN. → Every query must scan all frames, while a class of object appears on average in only 0.16% of frames. One query over a month of video takes 5 hours.
- **Move NoScope to ingest time**: a binary classifier must run for every class, and GT-CNN must be called if any one is uncertain. Most frames still go through GT-CNN, so it saves almost nothing.
- **Label with a cheap CNN at ingest**: recording only the top-1 often disagrees with GT-CNN, so queries miss frames (recall drops). Recording the top-K leaves precision at 1/K, and queries must run GT-CNN on K times as many candidates.

## Novelty
1. **GT-CNN's answer almost always falls inside the cheap CNN's top-K**
   Insight: The cheap CNN's top-1 is unreliable. But on the lausanne video, with K≥4 (5% of 80 classes), GT-CNN's result falls in its top K 99% of the time. Also, each video stream shows only a few classes: 2–10% of classes cover ≥95% of objects.
   So: At ingest, use a compressed CNN trained specifically for this stream (up to 96× cheaper than GT-CNN) to record the top-K classes for each object, building in one pass an index that covers all classes. At query time, run GT-CNN only on candidates that hit the index, which pulls precision back up from 1/K.
   Ingest is responsible only for recall; precision is deferred to query time. This solves both Ingest-heavy's ingest cost and NoScope's full scan, and needs no classifier per class.
2. **The same object appears again and again across many frames, and the cheap CNN's features can recognize it**
   Insight: A pedestrian takes 15 seconds to cross the street, so the same object appears in many frames. Nearest neighbors found with the feature vectors from the cheap CNN's second-to-last layer are of the same class over 99% of the time.
   So: At ingest, a single-pass incremental clustering (linear in the number of objects) groups similar objects into clusters. At query time, GT-CNN looks only at cluster centers, and the result is applied to the whole cluster. This cancels the K-fold candidates that top-K brings.

Other design: label sampled frames with GT-CNN, search for parameters (CNN, K, clustering threshold) that meet the precision/recall targets, then pick a point on the Pareto frontier of ingest cost vs query latency.

## Evidence
- End to end: 14 streams of 12 hours each (traffic, surveillance, news), with a target of 99% precision and recall relative to GT-CNN. Ingest is 48× cheaper than Ingest-heavy (up to 92×), and queries are 125× faster than NoScope (up to 607×). A query over a month of video drops from 5 hours to 2.4 minutes, and ingest costs 8 dollars per stream per month. On moving cameras (news) it is only 5× cheaper.
- Novelty 1 → top-K index only (no clustering, but including "skip GT-CNN when confidence is high"): queries are 114× faster than NoScope. For the relation between K and recall, see above. "Training per video": no direct ablation.
- Novelty 2 → adding clustering gives 195×, with the clearest effect on surveillance video.
- Trade-off: when tilted toward ingest, it is 65× cheaper than Ingest-heavy and queries are still 100× faster; when tilted toward queries, queries are 202× faster and ingest is 53× cheaper.
- Gaps: the query side also uses NoScope's binary classifier as a filter, so not all gains come from Focus itself. Accuracy is relative only to YOLOv2, and the rarest 5% of classes are excluded. Switching to the 1000 ImageNet classes drops the query speedup to 15×.

## When it applies
Each stream has few classes and highly redundant frames (fixed cameras are best). When the fraction of video that is queried is below about 1%, ingest cost exceeds that of a pure query-time approach.
