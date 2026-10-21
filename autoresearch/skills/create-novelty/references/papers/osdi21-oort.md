# Oort: Efficient Federated Learning via Guided Participant Selection
OSDI'21 · Fan Lai, Xiangfeng Zhu, Harsha V. Madhyastha, Mosharaf Chowdhury / University of Michigan · Full text: https://www.usenix.org/system/files/osdi21-lai.pdf (camera-ready) · Selected: Highly cited (262 citations)

**One sentence**: The training loss is reported anyway, so it can stand in for data value for free; picking clients by "value per unit of time" cuts both the number of rounds and the length of each round.

## Problem
In each round of federated learning (FL), a few hundred participants are picked from thousands to millions of devices. Each trains on its local data, a coordinator aggregates the results, and this often takes hundreds of rounds.
Devices differ greatly in data distribution and volume, and also differ by an order of magnitude in compute and bandwidth. The goal is to cut the wall-clock time to reach a target accuracy (time-to-accuracy).
Federated testing also requires the participants' data to meet a distribution requirement given by the developer.

## Strawman / Baseline
- **Random participant selection (current deployments, with algorithms such as Prox/YoGi)**: On OpenImage with 100 per round, Prox needs 372 rounds to reach 74.9%, while the ideal case of uniformly distributed centralized data needs only 64 rounds. A round waits for the slowest participant, and slow devices make each round even longer.
- **Pick only fast devices**: Each round gets shorter, but the fast devices' data is reused again and again, so more rounds are needed than with random selection.
- **Pick by data value (importance sampling by per-sample gradient norm)**: Requires an extra pass over the data to compute each sample's gradient, and value changes as the model updates; slow devices with high value make each round longer.
- **Fixed cap on round length**: Always suppresses slow but valuable devices, and the model converges to lower accuracy.
- **Random selection of the test set**: For the same number of participants, the deviation from the target distribution cannot be quantified, so developers can only pick more; the MILP that picks participants exactly by a given distribution cannot finish on a million clients.

## Novelty
1. **Data value can be read for free from the existing training loss, then divided by time cost**
   Insight: Samples with large gradients also have large loss, and the loss of each sample is computed during training anyway. A client only needs to report a local aggregate, which does not expose its sample distribution. Time-to-accuracy equals the number of rounds times the length of each round, and round length is set by the slowest participant.
   So: Client utility equals "data value from aggregated loss", multiplied by a penalty in proportion when the client is slower than the expected round length T. This targets both root causes of random selection at once, and avoids the two strawmen that look at only one side.
2. **Utility is known only after a client has participated, and it goes stale, so select by bandit and widen the time limit step by step**
   Insight: The utility of a client that has never participated is unknown; for one that has, its loss falls as the model trains. This is a multi-armed bandit (each client is an "arm", and picking it yields its utility as the reward).
   So: Most slots are sampled from a high-utility pool with probability by utility, and a few slots explore new clients; clients not picked for a long time get a bonus that grows with time. When the accumulated data value of the last few rounds drops, a pacer widens T by one step so slow but valuable devices can be picked again. This solves the root cause of a fixed cap on round length.
3. **The number of test participants can be computed without knowing each device's data distribution**
   Insight: The sample counts of different clients are independent of each other and can be treated as independent random variables, so the Hoeffding bound (an upper bound on the probability that the mean of independent variables deviates from its expectation) applies.
   So: A developer only gives the range of global sample counts and the total number of clients, and gets the number of participants needed for "deviation less than ε". When the distribution is known, first greedily collect enough samples of each class, then solve a MILP on this small set to minimize test time.

## Evidence
- End to end (simulated on 68 P100s, 1300 per round taking the first 100 to finish, device speeds from real measurements): versus random selection, time-to-accuracy is 1.2–14.1× faster (OpenImage 3.3–14.1×, Reddit/StackOverflow 7.3–9.1×, Google Speech only 1.2–1.3×). Final accuracy on OpenImage is 6.6–9.8% higher.
- Novelty 1 → Table 2 splits the speedup: on OpenImage, 1.8–4.8× fewer rounds, plus another 1.5–3.5× from round length. Removing the speed penalty (α=0) gives the fewest rounds (MobileNet 113 rounds, Oort 122, random 248) but longer total time. No direct comparison of loss versus gradient norm.
- Novelty 2 → Removing the pacer: final accuracy 2.4–3.1% lower than Oort; Oort is 2.7–3.3% from the ideal upper bound. No direct ablation of exploration and the staleness bonus; only α was tuned, plus robustness under label corruption and noisy utility.
- Novelty 3 → Sampled 1000 times, picking the computed number of participants, the deviation never exceeded the target. With a given distribution, test time is 4.7× shorter than direct MILP (selection cost 15 s vs 274 s); on a million clients, MILP cannot solve even one query.
- Gaps: Everything is simulated, including the clock; the only baseline is random selection.

## When it applies
Clients must be able to report loss and time cost, and loss must reflect data value. When labels are heavily corrupted, high loss does not mean useful; this can only be eased by clipping and removal.
