# Ryoan: A Distributed Sandbox for Untrusted Computation on Secret Data
OSDI'16 · Tyler Hunt et al. / UT Austin · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-hunt.pdf (camera-ready) · Selected: Best Paper

**One sentence**: In request-based services, code computes on each input only once and keeps no state. So after the input arrives, all of the code's behavior visible to the OS can be cut off, and it cannot leak the input.

## Problem
Users hand tax forms and genetic data to online services. A service provider (such as 23andMe) then outsources part of the computation to another company (such as Amazon ML), and also wants to protect its own private feature mapping.
Users control neither the service code nor the platform (OS, hypervisor, administrators). The two may collude and send secrets out through covert channels (encoding secrets in visible behavior) such as syscall sequences, arguments and I/O sizes.

## Strawman / Baseline
- **Put the application in an SGX enclave (Haven, SCONE)**: an enclave is a memory region isolated by hardware encryption, and the OS cannot read it. → It only stops the platform from peeking at a **trusted** application. When the application itself is untrusted, it can vary the number and size of read calls based on the secret, and the OS can still read it out.
- **DIFC (HiStar, Flume, DStar)**: label data and let a reference monitor (a trusted kernel that enforces flow rules) block leaks. → You must trust the OS and root of the machine that processes the data, which is impossible on a third-party cloud.
- **Destroy and rebuild the sandbox for each request**, so secrets do not build up across requests: ClamAV takes 24 s to initialize (DSPAM 11 s), while processing one email takes only about 0.124 s. Even creating a small enclave takes 30 ms.

## Novelty
1. **A "one-shot" request model lets visible behavior be independent of secrets**
   Insight: Common data processing services work per request. A module reads its input and produces output. After seeing a secret, it does not need persistent storage or the OS.
   So: Run NaCl (a software fault isolation sandbox; code cannot leave its own address space, and syscalls must go through the runtime) inside an enclave. As soon as a module receives someone else's secret, it loses all syscalls and uses an in-enclave memory file system and preallocated memory instead. Computation starts only after the whole input is read. Output is padded or truncated to a "polynomial of the input size" fixed in the DAG. After processing, the module rolls back and cannot see the same input again.
   This cuts the syscall/traffic channels left by the enclave baseline. The execution time channel is not closed, but each request can use it only once: if time is quantized into 8 levels, at most 3 bits leak.
2. **The trusted reference monitor travels with the enclave onto untrusted machines**
   Insight: SGX attestation (remotely proving the hash of an enclave's initial code) can prove to users that every machine runs the same sandbox. Service providers trust only their own code, so modules that have seen only their own secrets need no constraints.
   So: A label is a set of tags, each tag a public key; reading data merges labels. While it has only its own tag, a module can use the network freely and read files to initialize. Once it has another party's tag, it enters the restricted environment of item 1 and may not persist anything. The rules are simpler than DIFC, and there is no need to trust each machine's OS.
3. **Initialization state contains no secrets and can be snapshotted and reused**
   Insight: Every request must start from the same state, "initialized and has not seen secrets". SGX reliably reports page faults inside the enclave, so it can know which pages were written without trusting the OS.
   So: Take a checkpoint at the first wait_for_work. During processing, write-protect pages and record dirty pages. Before the next request, restore only the dirty pages. This replaces the rebuild in the last strawman.

Other design: Ryoan-libc validates syscall return values to prevent Iago attacks (the OS returns malicious values to trick the enclave).

## Evidence
- End to end: four DAGs, email filtering (DSPAM+ClamAV), health prediction (SVM), image recognition (OpenCV) and translation (Moses), are 48%, 419%, 27% and 91% slower than native Linux.
- Novelty 1 → only the cost of the constraints is given: sandbox + encryption overhead is 100% on Health (computation is very light, so padding and buffering dominate) and 18% on Images. There is no leakage experiment; security rests only on argument.
- Novelty 2 → no direct ablation, only use-case demonstrations such as 23andMe→Amazon.
- Novelty 3 → creating an enclave and loading modules takes <0.5 s, but application initialization takes >20 s. Checkpoint restore takes <10 ms per request. Restore itself is 55% of the cost on Health and 3% on Images.
- Gaps: the available CPUs had only SGX v1; v2 instructions were emulated in QEMU and their latency estimated. If v2 instructions cost as much as EENTER, the four workloads get 25%, 14%, 7% and 4% slower. Hardware side channels such as page faults and caches are outside the threat model. Fixed execution time is not implemented.

## When it applies
The service must be request-based: each request is fully processed in the module's memory, and no state derived from secrets needs to be kept across requests. The service must be able to write an upper bound on output size in advance. Modules that depend on databases larger than memory or need cumulative learning do not fit.
