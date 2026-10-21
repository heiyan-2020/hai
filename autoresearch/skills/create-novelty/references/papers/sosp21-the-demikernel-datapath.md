# The Demikernel Datapath OS Architecture for Microsecond-scale Datacenter Systems
SOSP'21 · Irene Zhang, Amanda Raybuck et al. / Microsoft Research, UT Austin, UW, et al. · Full text: https://irenezhang.net/papers/demikernel-sosp21.pdf (author home page, camera-ready) · Selected: Community favorite (4 sources: Micah Lerner blog, UCSD CSE 221 2024, UIUC CS523 2025, UW CSE 551 2024)

**One sentence**: Kernel-bypass devices already do protection in hardware; what is left is only management, so the library OS can be swapped per device while sharing one API.

## Problem
Network round trips and disk accesses now take single-digit microseconds, leaving the OS less than 1 µs per I/O. Kernel-bypass devices (RDMA, DPDK, SPDK) let applications skip the kernel and do I/O directly, but nothing replaces the kernel.
Clouds have many generations and kinds of devices at once, so applications must be rewritten per device and must do zero-copy memory coordination and scheduling themselves.

## Strawman / Baseline
- **Go through the Linux kernel**: kernel traps plus copies; echo round trip 30.4 µs.
- **Program the device directly (ib_verbs, DPDK)**: the application is locked to one device. A DPDK application must bring a whole TCP stack; an RDMA application does not need one.
- **User-space stacks that keep POSIX (mTCP, F-stack, etc.)**: POSIX does not support zero-copy, and one epoll event wakes several workers; latency is in the tens of microseconds.
- **Kernel-bypass schedulers / RPC libraries (Shenango, Caladan, eRPC)**: support only specific NICs and do not handle storage. Shenango's packets pass through two cores.
- **Hand-written zero-copy**: I/O memory must first be registered or allocated the device's way; the application cannot free a buffer before TCP gets the ACK, or retransmission is impossible. TxnStore's own RDMA layer gave up zero-copy for this reason.

## Novelty
1. **Protection is already in hardware; the OS is left with management only and can be a replaceable library**
   Insight: the device's IOMMU already provides isolation and address translation; the application and the OS library share one process and trust each other.
   So: one library OS per device, using software only for what the device does not offload (the RDMA version relies on the NIC for reliable transport; the DPDK version brings its own TCP). On top, they share one queue-centric API (PDPIX). Changing devices does not change application code.
2. **The memory allocator can answer both questions zero-copy has to answer**
   Insight: zero-copy needs to know "can this memory be DMAed" and "is anyone still using it". The allocator owns the whole heap and knows both.
   So: the library OS takes over the application's allocator, makes the whole heap DMA-capable memory, keeps a 1-bit reference count per object, and only really frees it after TCP gets the ACK. The API says ownership is handed over at push and returned on completion. Applications that do not modify data in place (such as Redis) get zero-copy without code changes. It only guards against use-after-free, not against writes.
3. **OS work and application work must share a thread, and most of the time they are blocked**
   Insight: ns-scale overhead requires the two to alternate on one thread; Rust compiles coroutines into state machines, and a switch takes only about 12 cycles.
   So: the protocol stack, background tasks and application workers are all cooperative coroutines; blocked coroutines are skipped with a ready bitmap. After a packet arrives, it is processed on the same core all the way to the application and back out. wait_* returns the data directly and wakes only one worker.

## Evidence
- End to end: after porting, 4 applications have about the same code size as their POSIX versions (Redis 54,332 vs. 52,954 lines). A non-expert in kernel-bypass ported a TURN relay in 1 day (io_uring and Seastar took 2 days each). Overhead per I/O 125–250 ns. Echo round trip: the DPDK version is 3.1 µs faster than Shenango and 1.7 µs slower than Caladan; the RDMA version is 0.2 µs slower than eRPC. 256 kB throughput is 17–26% lower than bare testpmd/perftest.
- Novelty 1 → the same echo runs unchanged on Windows (RDMA 27× faster than WSL) and on an Azure VM (DPDK 5× faster than Linux). No direct ablation.
- Novelty 2 → Redis throughput: RDMA version 2×, DPDK version 20% higher; even with a synchronous disk write on every SET, it stays within 10% of the original Redis that does not write to disk. The RDMA version beats TxnStore's own copying RDMA layer. No direct ablation of zero-copy on/off.
- Novelty 3 → a TCP packet goes from arrival to the application coroutine in 53 ns. No direct ablation of the scheduler.
- Gaps: single core only; peak throughput is only 70% of Caladan and 46% of eRPC.

## When it applies
The application must trust the library OS and enter the I/O loop at least once per millisecond (cooperative scheduling). For systems that need device-specific features such as one-sided RDMA, the unified API hides them.
