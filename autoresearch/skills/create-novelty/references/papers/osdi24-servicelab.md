# ServiceLab: Preventing Tiny Performance Regressions at Hyperscale through Pre-Production Testing
OSDI'24 · Mike Chow, Yang Wang et al. / Meta Platforms, The Ohio State University · Full text: https://www.usenix.org/system/files/osdi24-chow.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Once a few coarse factors match, heterogeneous cloud machines are as stable as one machine; only by picking the statistical model per service can a 0.01% regression be detected in parallel.

## Problem
FrontFaaS (Meta's serverless platform) runs on more than 500,000 machines and gets thousands of changes per day; a 0.01% CPU regression equals more than 50 machines, and regressions add up.
To detect regressions this small, each change needs many A/B trials, each averaging over 1 hour, so they must run in parallel.

## Strawman / Baseline
- **Run all trials in sequence on the same machine**: Lowest variance → 25 trials take more than a day.
- **Build a pool of identical test machines (the early approach)**: → Once the pool grows, upkeep is unaffordable, and test load is bursty.
- **Take any machines of the same model from the cloud**: → SSD wear, memory vendor, and uncore frequency differ, so performance differs even within one model, and noise hides small regressions; filtering by full hardware model (over 10,000 kinds) cannot gather enough machines.
- **A single statistical model (at first, t-test + outlier trimming)**: → Each service has a different outlier pattern. With many trials, outlier trials and requests cause false positives, and deleting outliers causes false negatives.
- **A fully isolated test environment with deterministic replay**: → FrontFaaS calls hundreds of downstream services, and copying a social graph of billions of users for each test is not feasible.

## Novelty
1. **Variance comes mainly from a few coarse factors that the cloud can expose**
   Insight: Use ANOVA (variance decomposition) to find factors that explain performance differences; R² is the fraction of variance explained. On 21.5 million benchmark records, the three factors ServerType, CPU architecture, and kernel version give R² of 0.87, close to the upper bound of 0.89 from the full hardware model; memory speed and vendor hardly matter. On 186,000 real application tests, adding datacenter region (applications read the regional production database) and turbo raises R² by at most another 0.23 (the paper does not give this group's baseline R²), versus only 0.01 on benchmarks.
   So: Request a batch of machines at once, keep only the "nearly identical" machines that match on these factors, are in the same region, and have turbo off, run them in parallel, and return the rest; also avoid high-variance CPUs and kernels (coefficient of variation CoV, i.e. standard deviation/mean, reaches 42% for one CPU and 52% for one kernel).
   This solves sequential runs being too slow, a dedicated pool being too costly, and exact filtering not gathering enough machines.
2. **The best statistical model differs by service and drifts, but ground truth can be made cheaply with A/A experiments**
   Insight: Any "significant" result in an A/A experiment (both sides run the same code) is a false positive; injecting a regression into one side of an A/A gives an A/B experiment with a known answer.
   So: For each ⟨service, metric⟩, use these two kinds of experiments to measure the false-positive rate, false-negative rate, and detectability of 7 "test method × preprocessing" combinations; pick the highest-scoring one whose false-positive rate is below a threshold, and re-pick regularly.
   This solves a single model that sometimes gives false positives and sometimes false negatives.
3. **No need to copy downstream services; share production directly**
   Insight: Most downstream calls of the service under test are read-only or idempotent, and test traffic is negligible next to production traffic.
   So: Replay recorded requests, without requiring behavior to match production, and call production downstream services directly; database writes are dropped by a client shim, and other RPCs are allowed only by allowlist.
   This avoids the cost of copying downstream services, at the price of some code paths not being exercised.

Other design: Production profiling gives each change an impact score, and only high-score changes are tested.

## Evidence
- End to end (FrontFaaS, over 5 years, threshold 0.01%, 25 trials each): over 100,000 changes per month, 23% tested, 0.3% of those (5,560) reported. By developer feedback, 57% true positives, 15% false positives, 28% unknown, giving an estimated false-positive rate of about 21%, so 0.014% of changes hit a false positive; compared with production monitoring, the false-negative rate is about 32%. Median true regression is 0.14%, and over 5 years regressions <1% added up to the equivalent of over 2 million machines. Across the whole platform it covers more than half of Meta's code changes.
- Novelty 1 → CoV P50/P99 across nearly identical machines is 5.7%/38%, versus 5.9%/28% on one machine; the effect of machine selection on detection accuracy is not measured.
- Novelty 2 → In periodic A/A experiments, the false-positive rate across 6,783 metrics has P50/P90/P99 of 0.6%/40%/64%; among services using adaptation, over half changed models within 90 days. Accuracy of adaptive versus fixed models: no direct ablation.
- Novelty 3 → No direct ablation. The top cause of false negatives is that requests for new features are not in the recorded traffic.
- Gaps: True/false positives rely on developer labels, and the false-negative rate relies on production monitoring; the other 483 use cases have no accuracy data.

## When it applies
The cloud must let you pick bare-metal machines by CPU architecture, kernel, and region (not validated on VMs). Downstream calls must be mostly side-effect free, and requests must be mostly independent.
