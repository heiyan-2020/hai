# Building Bridges: Safe Interactions with Foreign Languages through Omniglot
OSDI'25 · Leon Schuermann, Amit Levy et al. / Princeton, UCSD · Full text: https://www.usenix.org/system/files/osdi25-schuermann.pdf (USENIX camera-ready) · Selected: Best Paper

**One sentence**: Rust's invariants hang on "the type a value is given", so there is no need to reason about foreign code; just isolate it and check values that cross the boundary when needed.

## Problem
Systems written in Rust still need to call C libraries; for example, the Tock kernel needs a certified crypto library and LwIP.
Functions called through the FFI (foreign function interface) are always `unsafe`. A foreign bug can corrupt Rust memory directly, for example by overwriting a `Vec`'s length with a one-byte overflow.
Even when the foreign code itself is correct, it can break Rust's language rules and cause undefined behavior.

## Strawman / Baseline
- **Generate bindings with rust-bindgen and write safe wrappers by hand**: Correctness depends entirely on the developer. In in-place encryption, the C function returns dst and src pointing to the same memory, which breaks Rust's rule that "a mutable reference cannot have aliases". A C bool may be 2, while Rust encodes bool into enum discriminants (niche filling), so the value 2 is read as another variant, leading to out-of-bounds access or use-after-free.
- **Memory isolation only (MPK/PMP sandbox)**: Foreign code cannot touch Rust memory, but the values it returns and shared buffers can still hold illegal values or aliases, which isolation does not cover.
- **Isolation + copy/serialization (Sandcrust, passing data over IPC)**: Safe, but every boundary crossing copies, and the cost grows with data size.
- **Prove that the combination of host and foreign code is sound (linking types, etc.)**: Requires modeling the whole program, and also assumes the foreign code is correct.
- **Validate once and then trust it**: After validation, if foreign code runs again, the host writes again, or the allocation is freed, the validated value becomes invalid (TOCTOU). Preventing this with dynamic read-write locks costs runtime overhead, and errors show up only at runtime, as deadlocks.

## Novelty
1. **Check only values that cross the boundary; do not reason about foreign code**
   Insight: Each Rust invariant is attached to a value's type (a bool can only be 0/1, a str must be UTF-8). If values returned from foreign code are marked with an unconstrained type, they break nothing; when they really must be used as some type, most types only need a check of size, alignment, and bit pattern.
   So: The foreign library goes into a sandbox (RISC-V PMP or x86 MPK, two kinds of hardware memory protection). A pointer to foreign memory starts as a raw pointer; upgrade checks that it lies within a valid allocation of the foreign library and yields a writable reference; validate checks the bit pattern and yields a readable reference. Rust reads and writes foreign memory in place, without copying.
   Foreign references are always assumed to have aliases, and `UnsafeCell` opts out of Rust's aliasing rules. Because foreign allocations and Rust allocations are disjoint, this is sound.
   This answers both "isolation alone is not enough" and "copying is too expensive".
2. **Foreign code does not run while the host holds a reference, so the "lock" can be made fully static**
   Insight: The runtime guarantees that the foreign library never runs concurrently with a host that holds references into its memory. The only things that can invalidate a validated value are writes, foreign calls, or frees started by the host itself, which is a pure data-flow problem.
   So: Each library instance comes with two compile-time tokens (an allocation scope and an access scope). A shared borrow acts as a read lock, and an exclusive borrow acts as a write lock. The result of validate is tied to a shared borrow; writing and calling foreign functions need an exclusive borrow. The borrow checker enforces this: code that holds a stale reference does not compile, with zero runtime overhead.

Other design: rust-bindgen is modified to generate bindings automatically; trampolines that switch protection domains are generated from the C calling convention the compiler already knows.

## Evidence
- End to end (6 libraries, 2 runtimes): relative to "isolation only", Omniglot's extra overhead is 0–3.4%. 3 of them are at 0% (validation of u8 arrays is optimized away by the compiler), and LwIP is the highest. Most of the total overhead comes from isolation itself (LwIP +52.1% with small packets). libpng decode time is close to unsafe FFI, while Sandcrust's overhead grows with image size (read from the figure). A single empty call: 98.9 ns under MPK, 56.2 µs for Sandcrust.
- Novelty 1 → The two columns "isolation vs Omniglot" above isolate exactly the cost of checking. But no malicious or buggy library is injected to show violations being blocked, and there is no formal soundness proof (Rust itself has no formal semantics).
- Novelty 2 → No direct ablation: no comparison with a dynamic-lock version.
- Gaps: The MPK runtime is a weak guarantee; the foreign library can get around it with mmap, signals, or threads, so it must be trusted. Upgrade and callback costs grow linearly with the number of registered allocations (MPK upgrade: 32 ns with 1 allocation, 1.10 µs with 64). setjmp/longjmp needs a separate C wrapper.

## When it applies
Requires strong memory isolation and the ability to stop foreign code from running concurrently in the background. Data crossing the boundary must be checkable by bit pattern. It guarantees that the host has no undefined behavior, not that the foreign library computes correctly.
