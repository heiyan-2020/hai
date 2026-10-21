# NetBricks: Taking the V out of NFV
OSDI'16 · Aurojit Panda, Sangjin Han, Keon Jang, Sylvia Ratnasamy, Scott Shenker et al. / UC Berkeley, Google, ICSI · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-panda.pdf (camera-ready) · Selected: Highly cited (248 citations)

**One sentence**: The cost of NF isolation comes from every packet crossing a hardware boundary. Let the type system guarantee memory isolation and "let go once sent" at compile time instead, and NFs can be chained in one process with zero copies.

## Problem
NFV aims to replace middleboxes such as firewalls and NATs with software NFs (network functions) on commodity servers. NFs from many vendors and tenants are consolidated on one machine, and packets pass through a chain of NFs. Latency must be tens of µs, and throughput tens of Gbps.
Four years after it was proposed, operators had only run pilots with at most a few hundred users: NFs are hard to write, and isolation is too expensive.

## Strawman / Baseline
- **VMs / containers + vSwitch (OVS-DPDK, SoftNIC)**: MMU isolation; packets are forwarded between NFs through the vSwitch → every packet needs a context switch or a cross-core hop. With 64B packets, single-core throughput is 3× (containers) / 7× (VMs) lower than a single process that owns the NIC. Chained, it is 7×/11× lower. Even giving each NF its own core cannot catch up with a single process.
- **Copy packets to guarantee packet isolation** (an NF cannot change a packet after sending it) → copying along the chain cuts throughput by up to 3×.
- **Zero copy by unmapping pages (Container Shipping) / immutable buffers (IO-Lite)**: → the former traps into the kernel every time; the latter copies on every write.
- **Single-process frameworks (xOMB, CoMB)**: → no memory isolation, so NFs from many vendors cannot run together.
- **Click / DPDK**: Click elements can only be tuned by parameters, and new features need new elements. DPDK handles only packet I/O → every developer must redo optimizations such as batching.

## Novelty
1. **Memory isolation does not need a hardware boundary. A type-safe language can provide it, and it is no longer slow**
   Insight: The cost of simple NFs is mainly each packet crossing processes and cores. A safe language forbids pointer arithmetic and checks bounds and null pointers, giving memory isolation equivalent to the MMU (the Singularity idea). In the past it was rejected for GC jitter and check overhead. Rust has no GC, and LLVM can remove most bounds checks.
   So: Write all NFs in Rust and put them in one process. A lint forbids unsafe pointer arithmetic. NFs pass packets by function calls, and the whole chain runs to completion on one core.
2. **Packet isolation is in essence "only one NF holds the packet at any moment", which is exactly what ownership types can prove statically**
   Insight: Unique types (one piece of data can have only one owner) were designed to prevent data races. They are checked at compile time with zero runtime cost.
   So: A call between NFs transfers ownership of the packet, and the sender can never reach it again. Packet isolation holds without copies (ZCSI, zero-copy software isolation).
3. **Common NFs can be broken into a few operators with clear semantics, so the framework can do the optimizations once**
   Insight: Like Spark, parse/transform/filter, group-by, per-core shuffle, TCP window reassembly and per-core partitioned state cover common NFs.
   So: The framework provides optimized operators (batching, lazy parsing), and users customize with UDFs. Network operators also chain NFs in Rust, so LLVM can do whole-program optimization across NFs.

## Evidence
- End to end (40G NIC, 64B packets): on NF chains it is up to 7× faster than containers connected by SoftNIC and 11× faster than VMs. Even with only one core for NetBricks, it is 4×/6× faster.
- Novelty 1 → single NF: a SoftNIC container without copies (only the boundary-crossing cost remains) uses 3 cores and is still 1.6× slower than single-core NetBricks. Cost of the safe language: TTL NF 23.2 vs 23.3 Mpps for C; with 1–8 random accesses per packet, bounds checks cut throughput by 20%; LPM routing is 14% slower (15.73 vs 18.03 Mpps). Beyond 300 cycles per packet, single-core NetBricks no longer wins.
- Novelty 2 → SoftNIC with/without copies: a single NF is 2.7×/1.6× slower than NetBricks; copying along a chain costs up to 3×; growing packets from 64B to 1500B adds only about 15%. ZCSI itself is not compared with "NetBricks + copying".
- Novelty 3 → 4 NFs rewritten: firewall/NAT/signature matching/monitoring per core 0.66/8.52/2.62/5 vs 0.093/2.7/0.983/1.785 Mpps. Maglev in 150 lines, 2.9–3.5× higher than the original paper's reported numbers (different hardware). No direct ablation: the gains come from optimizations such as batching that the original implementations lacked.
- Gaps: performance isolation and fault isolation are not evaluated. Safety depends on the Rust compiler and the lint.

## When it applies
NFs must be rewritable in Rust (clean-slate). The heavier an NF's computation, the smaller the share of the boundary-crossing cost that is saved.
