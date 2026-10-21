# Ensō: A Streaming Interface for NIC-Application Communication
OSDI'23 · Hugo Sadok et al. / CMU, Intel, Microsoft, NYU · Full text: https://www.usenix.org/system/files/osdi23-sadok.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Steering is already done by the NIC and software processes data in arrival order, so a separate buffer plus descriptor per packet is no longer useful; a contiguous data stream is enough.

## Problem
The interface between NIC and software has not changed in decades: each packet goes in a fixed-size packet buffer and is handed over with a descriptor (holding length, flag bits, and a pointer).
At 100 Gbps, a DPDK ping/pong program reaches only 40 Gbps on one core; the bottleneck is cache misses and PCIe.
Data produced by TSO, LRO, and transport offload spans multiple packets; forcing it into packet buffers means splitting it and copying it again.

## Strawman / Baseline
- **Packetized interface (E810 + DPDK)**: Buffers come from a free pool, so neighboring packets are not neighbors in memory → the prefetcher fails, L1d/L2 miss rates are 6%/55%; one descriptor per packet means that for small packets 39% of PCIe read bandwidth carries metadata. 59 Mpps on one core; at 88 Mpps on two cores it is capped by PCIe.
- **MPRQ, U-Net, NICA**: Deliver several buffers at once, or exchange messages directly → still per-packet notifications or descriptors plus scattered buffers, so the cost remains.
- **Lay data out contiguously and tell software the tail pointer through a shared memory address**: Each NIC write invalidates the cache line the CPU is polling, and small-packet throughput is below 5 Gbps.
- **Send one notification for each chunk of data that arrives**: The notifications themselves eat PCIe bandwidth, and it only reaches 50 Gbps.

## Novelty
1. **"One packet, one buffer" was designed for software steering, and steering has moved to the NIC**
   Insight: The packetized interface lets software steer packets to different sockets or VMs by moving only pointers. Today, with kernel bypass, each thread owns a NIC queue directly, steering is done by hardware such as RSS, and software mostly processes data in arrival order.
   So: Put the data directly in a ring buffer (an Ensō Pipe); the NIC writes packets or messages end to end into it, with no rule on content or size. Sequential reads and writes let the prefetcher work again; per-packet descriptors are no longer needed, so the metadata cost disappears. This matches exactly the two root causes of the packetized interface.
2. **Once data is opaque, the sync signal must be kept separate, and coalesced**
   Obstacle: Data has no fixed format, so flag bits cannot be embedded as in descriptors; sharing one pointer address contends for a cache line.
   So: Pass the tail pointer through a separate notification queue, shared by several Pipes. One notification covers all data that arrived before it; while the CPU processes a large batch, the NIC has already written later cache lines, so the two rarely touch the same line.
3. **The NIC already knows how far software has consumed**
   Insight: Each time software advances the head pointer it writes an MMIO register, so the NIC can see the consumption pace directly.
   So: Each Pipe uses only 1 bit of state: send one notification when the Pipe goes from empty to non-empty, then send again only after software advances the head pointer and there is still data not yet announced. Notification frequency follows software speed automatically, with no prediction and very little hardware state. The extra latency is offset by "notification prefetch" (software asks early for the next Pipe's notification).

Other design: The same physical buffer is mapped twice in virtual address space to handle wraparound; RX/TX can map to the same memory, for zero-copy forwarding.

## Evidence
- End to end (Stratix 10 FPGA NIC vs E810, PCIe 3.0): echo reaches 148.8 Mpps line rate on one core, versus 59 Mpps for E810 on one core. Maglev on one core 138 vs 23 Mpps (6×); NitroSketch 3.5× with 64B packets, 21% higher on a CAIDA trace; MICA 31% higher on one core, latency down up to 43%; log monitoring nearly 2× for some targets. Even with one extra copy when forwarding, 64B packets still get 91.7 vs 39.6 Gbps.
- Novelty 1 → Chaotic Ensō (only shuffles message spacing): drops from 148.8 to 56.5 Mpps, L1d misses 557M vs 22.8M. PCIe metadata overhead <1.2%, versus 39% for E810.
- Novelty 2 → Only a comparison with the rejected design (shared pointer <5 Gbps); no direct ablation of whether the notification queue is shared.
- Novelty 3 → Per-packet notifications reach only 50 Gbps, reactive reaches 100 Gbps; but latency rises with load, and with prefetch on it matches E810.
- Gaps: The comparison is an FPGA prototype against an ASIC NIC, so the hardware differs. TSO/LRO/transport offload from the motivation is not tested; only simple offloads such as RSS and checksum are on. Throughput drops above 32 Pipes per core.

## When it applies
Software must consume data roughly in arrival order. Applications that must dispatch packets out of order in software (such as virtual switches) need one extra copy per packet.
