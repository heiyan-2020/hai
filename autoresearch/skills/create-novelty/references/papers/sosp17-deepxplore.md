# DeepXplore: Automated Whitebox Testing of Deep Learning Systems
SOSP'17 · Kexin Pei, Yinzhi Cao, Junfeng Yang, Suman Jana / Columbia University, Lehigh University · Full text: https://www.cs.columbia.edu/~junfeng/papers/deepxplore-sosp17.pdf (camera-ready from author homepage, same as arXiv 1705.06640v4) · Selected: Best Paper

**One sentence**: Several independently trained models for the same task serve as each other's oracle, and the models are differentiable in their input, so "make them disagree" can be searched for directly with gradients.

## Problem
DNNs in self-driving and malware detection fail on rare inputs. For example, a Tesla did not recognize a white trailer against a bright sky.
Testing DNNs has two hard parts: how to generate inputs that trigger the model's different "rules", and how to tell that an output is wrong without manual labels.

## Strawman / Baseline
- **Manually labeled test sets (random split)**: → labeling is expensive (deciding whether an executable is malicious means running it in a sandbox), and random inputs almost never hit rare feature combinations.
- **Measure test adequacy with code coverage**: → a DNN's rules are learned and live in the weights, not in the code. 10 random inputs reach 100% code coverage, while neuron coverage stays below 34% (only 0.3–1.5% on ImageNet).
- **Adversarial examples**: add perturbations invisible to humans to an image so the model changes its decision → the perturbation must stay invisible for the label to stay the same; once visible, it needs manual checking. So they explore only a tiny region around the seed, and neuron coverage is about the same as random inputs.
- **Unguided simulation, formal verification**: simulation does not look inside the model; verification does not scale to real-sized DNNs.

## Novelty
1. **Several independently trained models for the same task rarely make the same mistake, so disagreement itself is the oracle**
   Insight: Developers often train several DNNs with the same function themselves, and their decision boundaries differ slightly. If on one input one model says turn left and another says turn right, at least one is wrong.
   So: Borrow differential testing from traditional software; no labels are needed. Perturbations then need not be invisible. They can be real, visible changes, as long as they meet domain constraints: brightening or darkening the whole image, pasting an occluding patch, simulating dirt on the lens; for Android apps, only adding manifest features.
   This solves two root causes at once: expensive labeling, and adversarial examples being limited to tiny perturbations.
2. **A DNN is differentiable in its input, so test generation can be written as gradient ascent**
   Insight: For traditional programs, finding an input that triggers a given branch needs symbolic execution, which is very costly. A DNN is a differentiable function. Treat the weights as constants and the input as the variable, and one backward pass gives the direction in which to change the input. This is orders of magnitude cheaper than training (training VGG-16 takes 7 days; one prediction plus gradient takes about 120 ms).
   So: Start from a seed and maximize a joint objective: make one model lower its confidence in the original class while the other models keep the original class, plus the output of a neuron not yet activated. At each step, first correct the gradient by the domain constraints, then update the input.
   This solves the problem that random testing and simulation are unguided and do not reach rare corners.
3. **A DNN's logic is in its neurons, so coverage should be counted per neuron**
   Insight: Different neurons tend to extract different features, and inputs of different classes activate quite different neurons.
   So: Define neuron coverage: the fraction of neurons whose output exceeds a threshold at least once over the tested input set. Put it into the joint objective above so the errors found are more diverse. This answers the failure of code coverage.

## Evidence
- End to end: 15 DNNs (132,057 neurons in total) on 5 datasets (MNIST, ImageNet, Udacity driving, PDF and Android malware). With 2,000 seeds per DNN, it found 789–2,000 inputs that cause disagreement; on a laptop it generates one error-inducing input per second on average. Retraining LeNet with majority-vote labels gave 1–3% higher accuracy than augmenting with random or adversarial examples.
- Novelty 1 → the more similar two models are, the harder it is to find disagreement: when the conv layers differ by only 1 filter, it takes 69.6 iterations; when the training sets differ by only 1 sample, none is found within 1000 iterations. Nobody manually checked how many disagreements are real errors.
- Novelty 2 → compared with the same number of random test inputs and adversarial examples, neuron coverage is 34.4% and 33.2% higher on average. Pushing each model's coverage (excluding some fully connected layers) to 100% takes only 6.6–196.4 seconds. But there is no comparison with "random perturbation under the same constraints and the same oracle": no direct ablation.
- Novelty 3 → removing the coverage term (λ2 from 1 to 0): on three MNIST experiments, input diversity (L1 distance from the seed) dropped from 283.3/253.2/182.7 to 237.9/194.6/170.8. Coverage differed by only 1–2 points, and more disagreements were found without it (871 vs 776). Inputs of the same class activate 74.2 overlapping neurons on average; different classes only 45.9.
- Gaps: Diversity is measured only by pixel distance; the number of distinct root causes is not counted.

## When it applies
You need at least two models with the same function, trained independently, whose gradients you can get. Errors that all models make are not detected. Domain constraints must be expressible as simple limits on the gradient.
