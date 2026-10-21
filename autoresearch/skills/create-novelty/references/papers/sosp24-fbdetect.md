# FBDetect: Catching Tiny Performance Regressions at Hyperscale through In-Production Monitoring
SOSP'24 · Dong Young Yoon, Yang Wang, Chunqiang Tang et al. / Meta, Ohio State · Full text: https://dl.acm.org/doi/10.1145/3694715.3695977 (ACM camera-ready, PDF obtained from a Wayback Machine archive) · Selected: Best Paper

**One sentence**: A regression usually lands in one subroutine, where it is relatively large and the noise is small; and transient events recover on their own, while code regressions do not.

## Problem
Meta has millions of servers. Its serverless platform has about 800 performance regressions a year. One in ten raises CPU by only 0.005–0.01%, yet together they waste about 4000 servers; the median is only 0.048%.
Pre-release testing cannot reproduce production, so regressions must be found in production. But production data is very noisy: mixed server generations, many request types, plus failures, maintenance, load spikes, gradual rollouts and traffic shifts.

## Strawman / Baseline
- **Watch service-level metrics and rely on fleet size for samples**: the smallest detectable regression is proportional to the sample variance divided by the square root of the sample count. Service-level variance is so large that, even at Meta's scale, gathering enough samples takes weeks to years. In simulation, 50 million machines are needed to see 0.005%.
- **Instrument every subroutine**: hard to deploy, high overhead.
- **Standard change-point detection (CUSUM, etc.)**: transient events also create change points; in production 99.7% of change points are such false positives. A longer window makes detection slow; a higher threshold misses small regressions.
- **General anomaly detection (Yahoo EGADS)**: sensitivity can only trade false positives against false negatives.
- **Report regressions per subroutine directly**: a refactoring moves code from A to B, so B looks slower while the total is unchanged. 34% of subroutine-level regressions are such "cost shifts".

## Novelty
1. **Service-level variance is spread over tens of thousands of subroutines, but a regression is concentrated in one**
   Insight: when a process's CPU variance is spread over k subroutines, each subroutine's variance falls to about 1/k (the median gCPU of non-trivial subroutines is 0.0083%, k is about 12,000). A regression usually comes from one subroutine: a 0.005% service-level regression that lands in a subroutine using 0.1% of CPU is a 5% relative change.
   So: sample call stacks periodically across the whole fleet and use the share of samples in which a subroutine appears as its CPU share (gCPU), with no instrumentation. Variance drops 100–10000×, and a few hours to a few days give enough samples.
2. **Transient events recover on their own; code regressions persist**
   Insight: most change points come from events such as failures and maintenance, and return to the old level afterwards; a regression caused by code is a sustained level rise, or brings a shape never seen before.
   So: first run change-point detection and a chi-square test; then look at an extended window after the change point (the went-away detector). Discretize the series into a string of letters (SAX), and report only when "a new shape appears", or when "the magnitude is significant, the trend persists, and there is no drop at the end". Seasonality is removed afterwards. So neither a longer window nor a higher threshold is needed.
3. **A cost shift only moves cost within a "cost domain"; the domain's total is unchanged**
   Insight: code moved by a refactoring usually stays in the same caller, the same class or the same commit.
   So: for a subroutine-level regression, also look at the cost domain one level up. If the domain's total cost barely changed, judge it a cost shift and do not report it. This patches the new false positives created by Novelty 1.

Other design: for Python, the eBPF sampler PyPerf rebuilds end-to-end call stacks; two-level clustering for deduplication; ranking candidate changes to find the root cause.

## Evidence
- End to end: 7 years in production, monitoring about 800,000 time series. In one month on FrontFaaS, 3.96 million change points led to only 217 reports (1/18857). Of 70 confirmed by developers, 49 were real regressions, the smallest 0.005%. Of FrontFaaS's 4 performance incidents in 2023, none was one it should have caught but missed. Root cause analysis gave 75 suggestions, 71 correct (within the top three).
- Novelty 1 → simulation only: subroutine level sees 0.005% with 1000 times fewer servers. There is no "service level vs. subroutine level" control in production. A small service with 16 servers (Invoicer) can also detect 0.5%.
- Novelty 2 → the went-away detector filters 99.7% of change points. Comparison with EGADS (107 series with reported regressions, plus about 35,000 unreported): FBDetect false positive rate 0.00088; when EGADS pushes its false positive rate below 0.02, it misses 84% of real regressions.
- Novelty 3 → filters 34% of input regressions. But 15 of the 21 confirmed false positives are still cost shifts, and the only missed incident in three years was caused by its wrong filtering.
- Gaps: 123 of the 217 reports are only marked "resolved", so whether they are true is unknown. The comparison with EGADS simply assumes FBDetect's false negative rate is 0.

## When it applies
Needs a large enough fleet or a long enough window to gather samples (small services need a 14-day history window), and regressions must be concentrated in a few subroutines. Non-CPU metrics such as memory need manual instrumentation to get down to the subroutine level.
