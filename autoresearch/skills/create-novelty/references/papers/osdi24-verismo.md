# VeriSMo: A Verified Security Module for Confidential VMs
OSDI'24 · Ziqiao Zhou et al. / Microsoft Research, UW-Madison, Purdue · Full text: https://www.usenix.org/system/files/osdi24-zhou.pdf (camera-ready) · Selected: Best Paper

**One sentence**: As long as the module keeps a few preconditions on hardware operations, hypervisor tampering can only make its memory accesses fail, never return wrong values, so hypervisor concurrency only needs to be proven once, in the hardware model.

## Problem
Confidential VMs such as AMD SEV-SNP no longer trust the hypervisor. Measurement, kernel code integrity, and key management, which the hypervisor used to provide, must now come from a security module at VMPL0, the highest privilege level inside the VM.
The hard part is that the hypervisor can interrupt it at any time and change the RMP (Reverse Map Table, a hardware table that records each physical page's owner, its GPA, and a "validated" bit) and the nested page tables; and the module itself runs concurrently on multiple cores.

## Strawman / Baseline
- **Write it in Rust and rely on the type system for memory safety (AMD SVSM, COCONUT SVSM)**: → Touching hardware requires unsafe; the two have 150 and 235 unsafe blocks. Rust also does not understand RMP semantics: this paper found a vulnerability in SVSM where VMPL3 (the guest OS) marks a page as shared, the hypervisor uses the chance to remap it to a physical page holding VMPL0 keys, and when the guest asks to turn it back to private, it reads the keys.
- **Floyd-Hoare verification directly on the implementation**: → Shared memory and hardware state can be changed by the hypervisor at any time, so specs that depend on these values cannot be proven; every step of every function must consider arbitrary hypervisor interleaving.
- **Verified OSes / security monitors (seL4, CertiKOS, Komodo)**: → Either trust the hypervisor or are themselves the highest privilege layer; none faced an untrusted, concurrent, and more privileged hypervisor.

## Novelty
1. **The hypervisor can only make an access fail, not return a wrong value, so external concurrency can be removed once at the model layer**
   Insight: The SEV-SNP RMP rule says that once a GPA has been validated by the VM, however the hypervisor changes things, that GPA either stays bound to the same physical page or becomes invalid. So as long as the module itself keeps a few preconditions on its operations, reading private memory has only two outcomes: the original value, or failure.
   So: The upper layer builds an abstract hardware machine (memory, page tables, RMP, TLB, etc.) on which the hypervisor and guest OS can do arbitrary operations, and proves confidentiality (the hypervisor reads only ciphertext) and integrity (VMPL0 reads the original value or fails) on it. The proof derives a precondition for each hardware instruction, such as not validating twice and not granting a VMPL0 private page to VMPL3. The lower-layer implementation only needs to prove that preconditions hold when it calls them, and can treat state recorded in software as hardware state.
   This gets around exactly the root cause of direct Hoare verification: hypervisor interleaving no longer appears in the implementation proof.
2. **Turn hardware resources into "permissions" whose ownership Rust can check, and leave internal concurrency to the borrow checker**
   Insight: Rust's ownership check already guarantees linear uniqueness, which is what separation logic must prove: "one resource has only one holder".
   So: Use tracked variables of Verus (a Rust verifier) to issue a non-copyable permission for each memory block, register, and lock. A memory permission carries the page's RMP and page-table attributes, and a lock permission checks an invariant on release. Unsafe is left only in primitives of one line of assembly. Permissions also bind a page's confidentiality attribute to the security level of the stored value: writing a secret into an externally visible page fails verification.
   This answers exactly the root cause of the Rust approach: unsafe shrinks to auditable primitives, and RMP semantics enter the types.

Other design: Information flow labels each variable with a "set of guessable values", and comparisons require both sides to be public; cryptography calls HACL*, which is trusted as a whole.

## Evidence
- End to end: AMD EPYC 7543P + Hyper-V. On UnixBench, Linux on top of VeriSMo has almost no overhead, while Hecate (an L1 hypervisor in VMPL0) is up to 40% slower. Performance is similar to the authors' own C and Linux versions of the module.
- Novelty 1 → Verification found the SVSM confidentiality vulnerability above; the fix only needs to zero the page after validation before handing it to VMPL3, and AMD has fixed it based on the report. The proof also shows that private pages need only the page-table encryption bit, not the RMP validated bit. How much effort the two-layer split saves: no direct ablation.
- Novelty 2 → Unsafe is only 31 lines of hardware primitives, 32 unsafe blocks in total (SVSM 150, COCONUT 235). Proof+spec at the implementation layer is about 2× the executable code, and full verification takes about 6 minutes on 32 cores. No effort comparison with other encodings, and no mutation testing.
- Gaps: The hardware model is a hand-written trusted spec and covers only key memory and cache operations (on #VC the VM is terminated directly). Verus, the Rust compiler, HACL*, and several axioms are trusted. No performance comparison with SVSM (different hypervisor).

## When it applies
Depends on hardware providing "tampering only causes failure" semantics (the SEV-SNP RMP validation binding), and on the hand-written hardware model being faithful to the manual. The module must be small enough to use only a few hardware instructions; otherwise the model and preconditions are hard to write in full.
