# Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms
SOSP'17 · Eli Cortez, Anand Bonde et al. / Microsoft, Microsoft Research · Full text: https://www.microsoft.com/en-us/research/wp-content/uploads/2017/10/Resource-Central-SOSP17.pdf (camera-ready) · Selected: Highly cited (795 citations)

**One sentence**: VMs of the same subscription behave very consistently, so a VM can be predicted from history the moment it is created, without first observing it and then migrating it.

## Problem
VM scheduling, power capping and maintenance scheduling all need to know how a VM will use resources in the future, but the cloud provider cannot see what runs inside the VM.
Three months of complete Azure VM data show: 60% of VMs have average CPU utilization below 20%, and over 1/3 of VMs have a low P95 too; but many VMs also have a P95 above 80%.
Reserving by requested size is wasteful, and blind oversubscription can exhaust physical CPUs.

## Strawman / Baseline
- **No oversubscription (Azure's existing scheduler)**: pack by requested size → resources sit idle; in simulation the scheduling failure rate is 0.25%, 2.5× the acceptable 0.1%.
- **Oversubscribe without predictions (Naive)**: no scheduling failures, but readings with utilization over 100% are 6× those of RC, because high-P95 VMs end up on the same machine.
- **Profiling + online reallocation (existing predictive schedulers)**: offline profiling is impossible because there is no input for a VM before it goes live. Online profiling does not know when it has "seen enough". Live migration holds the contended memory until it finishes and also causes network bursts.
- **A separate prediction service (REST-style prediction serving)**: the network and service stack are on the critical path of every prediction, and if the service is down the scheduler has no predictions.

## Novelty
1. **Behavior is consistent within a subscription, not across the whole platform**
   Insight: A subscription is a billing and quota unit and usually represents one user running related workloads again and again. For 80% of subscriptions, the coefficient of variation (standard deviation / mean) of average CPU is below 1; 96% create only one VM type; lifetime and deployment size are similarly stable.
   So: The model is trained across all subscriptions, but its features are "the fraction of this subscription's VMs so far that fall in each bucket", so it gives a prediction at the moment a VM is created. The most important features are exactly these fractions.
   This sidesteps the root cause of profiling: no need to observe this VM first, and no migration afterwards.
2. **Predictions are used only to relax, and fall back to the conservative value when uncertain**
   Insight: A wrong prediction for one VM does not matter; CPU is exhausted only when several VMs on the same machine are underestimated at the same time.
   So: Turn numeric prediction into bucketed classification with a confidence (for example, one bucket per 25% of utilization). The scheduler counts usage as the upper bound of the predicted P95 bucket. When confidence is below 0.6, it counts the full requested size. Only non-production first-party VMs are oversubscribed. The oversubscription cap is 125%, and the sum of predicted P95s must not exceed 100%.
   This solves exactly the problem of high-utilization VMs clustering under Naive oversubscription.
3. **Models and features are small enough to fit in the client**
   Insight: Each model is about 300 KB; all features are about 370 MB, only 850 B per subscription.
   So: Predictions run in a DLL inside the scheduler process. Models and features are pushed in the background, and results are cached by input hash. When storage is unavailable, a local disk cache is used. Predictions are therefore not on the network critical path and do not depend on service availability.

Other design: Use FFT to find daily periodicity, and classify VMs as interactive or delay-insensitive.

## Evidence
- End to end (faithful simulator, 336k VMs, 880 16-core servers, 1 month of real trace): RC oversubscription has 0 scheduling failures, with only 77 readings over 100% in the whole month. The non-oversubscribing Baseline has a 0.25% failure rate; Naive has 6× as many readings over 100% as RC.
- Novelty 1 → trained on 2 months, tested on the 3rd: accuracy 79–90% across 6 metrics; after dropping low-confidence predictions, precision is 85–94%. For subscription features there is only a feature-importance ranking, no ablation that removes them.
- Novelty 2 → random wrong predictions (RC-soft-wrong) give 3× as many readings over 100% as RC. With the cap lowered to 115%, failures are still 65% fewer than Baseline. "Fall back to the conservative value" has no direct ablation.
- Novelty 3 → result cache hit p99 1.3 µs; on a miss the model runs locally, median 95–147 µs; remote storage median 2.9 ms. No comparison with a real prediction service.
- Gaps: All simulation, not deployed. The simulator sums the per-5-minute maxima (pessimistic). Only CPU oversubscription was evaluated; lifetime and deployment-size predictions have no downstream experiments.

## When it applies
A subscription needs enough history; a new subscription gets no prediction. History becomes invalid when user behavior changes suddenly.
