# MAGE: Nearly Zero-Cost Virtual Memory for Secure Computation
OSDI'21 · Sam Kumar, David E. Culler, Raluca Ada Popa / UC Berkeley · Full text: https://www.usenix.org/system/files/osdi21-kumar.pdf (camera-ready) · Selected: Best Paper

**One sentence**: To avoid leaking secrets, secure computation must have a memory-access pattern that does not depend on data, so all memory accesses can be computed in advance and paging can be scheduled ahead of time with the optimal policy.

## Problem
Secure computation (SC: computing on encrypted data, such as garbled circuits and CKKS homomorphic encryption) blows up memory greatly: in a garbled circuit, one 64-bit integer takes 1 KiB.
Once a program exceeds memory, it relies on OS paging and becomes unusably slow. For example, the Obliv-C join can only handle 30,000 records, and Senate's 16-party set intersection can only handle 10,000 integers per party.

## Strawman / Baseline
- **Existing SC frameworks (EMP-toolkit, SEAL, etc.)**: Free wires (intermediate values in the circuit) promptly once they are no longer used, so memory drops to the size of "values alive at the same time". But they do not swap out; beyond memory, they leave it to the OS.
- **OS paging (or a replacement policy tuned for SC)**: Pages are swapped in only on a fault, so the CPU waits for I/O; replacement relies on guesses like LRU. Linux madvise does not help either: a page swapped in with MADV_WILLNEED still faults once more, and MADV_PAGEOUT does not swap out right away.
- **Use Belady's MIN (evict the page whose next use is farthest away; optimal in theory, but needs to know the future)**: It requires a complete memory-access trace. Measured with Pin, an SC program that runs under an hour makes trillions of memory accesses, and the trace takes several TB.
- **Change only the policy, not the timing**: Even with MIN, pages are swapped in only when used, so the program still stalls.

## Novelty
1. **SC memory-access patterns do not depend on data, so the "future" is known**
   Insight: An SC protocol must not leak data through its memory-access pattern, so the pattern must be oblivious (independent of input data). This is a security requirement, not a coincidence of one implementation. Given the program, all memory accesses can be computed before the inputs arrive.
   So: Turn paging from a passive runtime response into offline planning. A planner first unrolls the program, picks pages to evict directly with MIN, and produces a "memory program" with swap-in/swap-out instructions; the runtime executes it as written. The two root causes, OS paging that guesses and MIN that cannot be implemented, both go away.
2. **When the time of the next access is known, prefetch never guesses wrong and the buffer is small**
   Insight: MIN only decides what to evict; it does not fix the stall of "swap in only when used". But the access sequence is known, so each swap-in can be issued ℓ instructions early, with no wrong prefetch and no missed page.
   So: Reserve B page frames as a prefetch buffer. Swap-ins go asynchronously into the buffer and are copied to the target frame when used; swap-outs are also written back asynchronously through the buffer. By Little's law, SSD bandwidth 10 GB/s × latency 1 ms needs only about 10 MB, under 1% of server memory (in practice 16–32 MiB).
3. **Record only high-level operations, not each memory access**
   Insight: One integer addition expands into many AND/XOR gates and memory accesses, but most of them touch temporary values that die soon or protocol state that stays resident. Only "read two inputs, write one output" matters for paging.
   So: The DSL emits one bytecode per high-level operation, and the planner looks only at its operand addresses; at runtime the engine expands it into gates. This shrinks the trace that MIN needs from TB scale to a size that fits on disk, and also makes the planner independent of the specific protocol.

Other design: Address translation is done at planning time, and the runtime uses explicit I/O, avoiding page faults and TLB misses; variables are placed slab-style to reduce fragmentation.

## Evidence
- End to end: 10 workloads (garbled circuits and CKKS), 1 GiB memory limit: all faster than OS paging, 7 of them 4–12× faster (ljoin ≈12×, rsum ≈10×); all workloads within 60% of unlimited memory, 7 within 15%. Same trend at 16 GiB and with 4 workers in parallel. Applications: password-reuse detection scales to 2^27 users per party (1.125 TiB per party), about 3× the records of the OS in the same time; PIR about 5×.
- Novelty 1 → Only an overall comparison with the OS, no baseline of "same plan but with LRU": no direct ablation.
- Novelty 2 → No direct ablation (no experiment with prefetch turned off).
- Novelty 3 → Planning overhead: planning time is usually shorter than execution time, and peak planner memory is at most 3268 MiB; garbled-circuit memory programs are <5 GiB in the 1 GiB experiment and <65 GiB in the 16 GiB experiment. No direct comparison with a per-access trace.
- Gaps: Memory-program size is proportional to execution time; sort could not run in the 16 GiB experiment because the intermediate bytecode exceeded the local SSD. Gate execution order is not optimized.

## When it applies
Memory accesses must not depend on data, and the memory available at runtime must be known at planning time. When compute or network is itself the bottleneck (such as mvmul), the gain shrinks.
