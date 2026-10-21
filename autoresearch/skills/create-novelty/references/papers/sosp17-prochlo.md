# Prochlo: Strong Privacy for Analytics in the Crowd
SOSP'17 · Andrea Bittau, Úlfar Erlingsson, Petros Maniatis, Ilya Mironov et al. / Google Brain, Google, U. Toronto · Full text: https://research.google.com/pubs/archive/46411.pdf (camera-ready hosted by Google Research) · Selected: Highly cited (302 citations)

**One sentence**: The noise of local DP grows with the total number of reports. Let an independent intermediary strip identity, shuffle, and release reports in crowds by a random threshold, and clients need not add more noise.

## Problem
Software telemetry (which apps use which APIs) must collect user data, and an app name or API combination can by itself be uniquely identifying.
The authors ran RAPPOR (local differential privacy: each client adds noise to its own data before reporting) on Chrome for 3 years, with billions of reports per day, yet developers often got no useful signal.

## Strawman / Baseline
- **Local DP (RAPPOR)**: each report must hide the individual with its own noise → the standard deviation of total noise grows with the square root of the number of reports, and in practice is an order of magnitude higher still. Among 1 billion reports, a signal shared by 1 million can be drowned out; 1000 apps × 100 APIs would need trillions of users.
- **Partition local-DP data by attribute before analysis**: cuts the data needed by two orders of magnitude → but "a partition exists" leaks "someone used this API", so DP breaks.
- **The intermediary enforces the threshold in plaintext**: crowd IDs in plaintext or only hashed → the intermediary can run a dictionary attack, and the threshold fails if it colludes with the analyst.
- **Let the analyst host the intermediary**: this can be guaranteed only by SGX, but private memory is only 92 MB, so data must be obliviously shuffled in external memory (watching the access sequence from outside reveals nothing about the permutation) → Batcher sort and cascade shuffles cost 49–114×; ColumnSort handles at most 118 million records; Melbourne Shuffle must keep the whole permutation in private memory and handles only tens of millions.

## Novelty
1. **Privacy can come from "hiding in a crowd" instead of "each person adds noise"**
   Insight: If the reports the analyst receives are anonymous and cannot be linked to each other, and every value is shared with at least T others, then the individual hides in the crowd and the reports need no noise. DP needs to be applied only to the single decision of "which values pass the threshold", and the noise size does not depend on the number of reports.
   So: Clients use nested encryption that only the designated shuffler and analyst can open, in order. The shuffler strips IP, time and order, shuffles in batches, and applies a threshold per crowd ID (partition key): a group is released only if its count exceeds "T plus Gaussian noise", and some records are dropped at random. Whether a partition exists therefore satisfies DP, which closes the hole in the partitioning scheme. The analyst gets a plaintext database that SQL can process.
2. **Random bucketing concentrates traffic near the mean, so a fixed quota plus a small stash suffices, with no need to remember the permutation**
   Insight: When each record picks its target bucket at random, the number sent from one input bucket to each output bucket follows a binomial distribution and rarely exceeds the mean plus a few standard deviations.
   So: Stash Shuffle processes one input bucket at a time. Each input/output bucket pair gets exactly C records written (slightly above the mean); shortfalls are filled with encrypted dummies, and overflow goes to the stash to be drained later. The read/write sequence seen from outside does not depend on the permutation. Private memory holds only the current bucket and the stash (170,000 records at 200 million). Finally each bucket is shuffled and dummies are removed. If the stash overflows, it changes keys and starts over.
3. **The threshold can also be enforced by cryptography, without trusting the shuffler**
   Insight: For unique data that is hard to guess, if it cannot be decrypted until t copies are collected, the threshold does not depend on any party's honesty.
   So: Encrypt data with a key derived from the message, and attach one Shamir share of that key to each report; only t users together can decrypt. Crowd IDs are El Gamal encrypted and then blinded by two shufflers. They still preserve equality and can be counted, but neither shuffler sees the plaintext.

## Evidence
- End to end (4 scenarios, non-SGX shuffler, crowd set (2.25, 10⁻⁶)-DP): on Vocab (a 3-billion-word corpus), RAPPOR's utility is less than 5% of Prochlo's. In web-permission analysis, RAPPOR recovers only a few dozen web pages, Prochlo thousands ((1.2, 10⁻⁷)-DP). Video recommendation uses only 3-tuple fragments, with accuracy about 90% of no privacy. Netflix-scale collaborative filtering RMSE 0.9242 (no privacy 0.9222).
- Novelty 1 → Vocab: a noisy threshold loses very little compared with no threshold; partitioning RAPPOR improves it only 1.13–3.45×.
- Novelty 2 → 10 million to 200 million 318-byte records, overhead 3.32–3.70×, security parameter log ε about −80 (−64.5 at 200 million); single-threaded 738 s to 4.1 h. Other algorithms are compared only by formula, not measured.
- Novelty 3 → encoding <50 µs per record; with 10 million clients, blinding increases shuffler 1 from 2.0 h to 4.1 h; utility is the same as without blinding.
- Gaps: None of the 4 applications used the SGX shuffler. No defense against Sybil attacks or data poisoning.

## When it applies
Needs a shuffler that does not collude with the analyst, or a trusted SGX. Analysis must need only common values or short fragments; analyses that depend on rare values or long sequences get no data.
