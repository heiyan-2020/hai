# Komodo: Using verification to disentangle secure-enclave hardware from software
SOSP'17 · Andrew Ferraiuolo, Andrew Baumann, Chris Hawblitzel, Bryan Parno / Cornell, MSR, CMU · Full text: https://www.andrew.cmu.edu/user/bparno/papers/komodo.pdf (author version on Parno's homepage) · Selected: Highly cited (221 citations)

**One sentence**: Enclave security rests on isolation primitives, not on putting the management logic into the CPU, so the management logic can be a software monitor small enough to verify completely.

## Problem
Intel SGX protects user-mode enclaves from a malicious OS, but it puts isolation management of near-microkernel complexity (creating enclaves, adding pages, attestation) into the x86 instruction set.
This part is opaque and cannot be changed. SGXv2 (dynamic memory) was specified in 2014, and three years later no CPU supported it. The OS can force enclave page faults and observe addresses to infer secrets (controlled-channel attacks); a fix must wait for new hardware.

## Strawman / Baseline
- **SGX: enclave management as CPU instructions**: security rests on the belief that "hardware is more reliable than software" → Intel's formal model has no formal link to the implementation. Adding features and fixing bugs both wait for new CPUs. Enclave pages are still mapped by the OS page tables, so the OS can remove mappings and cause page faults.
- **Sanctum (modified RISC-V hardware + software monitor)**: needs significant hardware changes (one page table per enclave); the monitor is 5k lines of unverified C++.
- **Write a very small unverified monitor**: the authors' first version, 650 lines of C plus 300 lines of assembly, still had critical security bugs. For example, InitAddrspace did not consider that its two arguments could be the same page.
- **Fully verified kernels (seL4, CertiKOS)**: must handle scheduling, IPC and drivers; the proof effort is large and hard to evolve quickly.

## Novelty
1. **Separate mechanism from management: hardware needs only four primitives, and management logic is a software reference monitor**
   Insight: Inside SGX there are already two layers: core hardware such as memory encryption, and instructions that maintain the table of "which page belongs to which enclave". The latter is not on the performance-critical path and is in fact already implemented in microcode.
   So: Hardware provides only isolated memory, a protected privileged execution environment, a root of trust and a random number source. A software monitor runs in ARM TrustZone's monitor mode and maintains the type and owner of every secure page (PageDB).
   Management logic can therefore be upgraded like software (for example, adding dynamic memory). Enclave page tables are also built by the monitor from PageDB. Once an enclave is finalized, the OS cannot change its mappings, and pages can be reclaimed only after the enclave stops, so the OS cannot cause page faults (the paper admits this is also because demand paging is not yet supported).
2. **The monitor's duties are tiny, so noninterference can be proven at the assembly level**
   Insight: The monitor does no allocation (the OS picks pages and the monitor only checks), no scheduling, IPC or drivers. It runs on one core only, with interrupts off during a call. So an attacker can observe state only at call boundaries.
   So: Verify the assembly implementation directly with Dafny/Vale. Prove noninterference against an attacker where "the OS colludes with malicious enclaves" (secrets do not affect what the attacker sees, and outside input does not affect the enclave). A bisimulation per call is enough. Information leaked by exception types, return values and dynamic allocation is explicitly allowed by declassification axioms.
   Enclave user-mode code is not modeled instruction by instruction; the spec only says it changes registers and writable pages to arbitrary values. So the trusted spec is small, and the proof effort of a full kernel is avoided.

Other design: Only local attestation inside the monitor (an HMAC over the enclave measurement). The ARM model covers only 25 instructions.

## Evidence
- End to end: on a Raspberry Pi 2 (900MHz Cortex-A7), one full enclave entry and exit is 738 cycles, versus about 7,100 cycles reported for SGX. A ported notary application runs at the same speed as a Linux process.
- Novelty 1 → evolvability: adding dynamic memory to the verified system took 6 person-months, of which the noninterference proof needed only 3 person-weeks of changes. No control group.
- Novelty 2 → proof size: spec 4,446 lines, implementation 2,710 lines, proof 18,655 lines, generating 26,800 lines of assembly. Full verification takes 4 core-hours; total effort about 2 person-years. Writing the spec exposed bugs in the unverified prototype. No mutation testing, and no comparison with other proof structures: no direct ablation.
- Gaps: The board has no secure memory isolation and no hardware attestation, so the prototype does not actually provide security. The comparison with SGX crosses platforms and clock speeds, and SGX also does memory encryption. All bugs found after running on the board were in the trusted parts (assembly printer, barrier instructions, cache configuration). Single core only; side channels not addressed; bootloader not verified; remote attestation not implemented.

## When it applies
The hardware must have a privileged mode and isolated memory that keep the OS out (TrustZone, RISC-V machine mode, etc.). The proof depends on a single core and interrupts off. Extending to multiple cores or adding demand paging would both break the premise of "visible only at call boundaries".
