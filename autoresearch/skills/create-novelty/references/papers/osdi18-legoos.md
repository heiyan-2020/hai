# LegoOS: A Disseminated, Distributed OS for Hardware Resource Disaggregation
OSDI'18 · Yizhou Shan, Yutong Huang, Yilun Chen, Yiying Zhang / Purdue University · Full text: https://www.usenix.org/system/files/osdi18-shan.pdf (USENIX camera-ready) · Selected: Best Paper

**One sentence**: Datacenter applications have strong memory access locality, and processes do not share writable memory. So the CPU side needs only a virtually addressed cache, and memory management can move entirely to the other end of the network.

## Problem
In a monolithic server, a job's CPU and memory must come from the same machine. In Google and Alibaba traces, only about half of CPU and memory is used. Motherboard, memory, CPU and power supply failures are 50–82% of hardware failures, and if any one breaks, the whole machine is unusable.
Hardware disaggregation makes CPU, memory and storage into separate network-attached devices. The network is already close to the memory bus (only 2–4× slower). But no OS can manage such hardware.

## Strawman / Baseline
- **Run Linux on the CPU and manage memory and storage remotely (the soNUMA idea)**: every memory/device management operation crosses the network → heavy traffic, high latency. If the CPU breaks, all other devices become unusable.
- **Send all memory accesses over the network**: both the authors and prior studies show that today's network cannot carry all memory accesses.
- **Swap out to remote memory from one machine (InfiniSwap)**: still the monolithic model, with a heavy paging path. It does not solve the failure domain and heterogeneity problems.
- **Disaggregate with a coherent interconnect (HP The Machine)**: keeping cache coherence across devices at cluster scale uses too much network bandwidth.
- **Multikernel OSes (Barrelfish, Helios)**: one kernel per core with message passing, but they still assume local shared memory and NICs, and do not handle distributed resources or device failures.
- **Full memory replication**: once a process's memory is spread over several memory devices, the chance of failure goes up. Full replication needs 2× memory.

## Novelty
1. **Strong access locality → split processor and memory by "performance" and "capacity"**
   Insight: 90% of PowerGraph's memory accesses fall on 0.06% of its memory (22% for TensorFlow).
   So: The processor side keeps only a small DRAM (such as 4 GB), used as a cache level below the LLC, called ExCache. Page tables, TLB, virtual-to-physical mapping and allocation all move to the memory devices. Hot accesses hit locally, and the memory devices provide capacity. The processor side no longer manages memory. This answers two failures: "all over the network is too slow" and "the CPU manages remotely".
2. **Processes do not share writable memory → no cross-device coherence is needed**
   Insight: Among the datacenter applications the authors surveyed, they saw not one case of writable sharing across processes.
   So: All cache levels are indexed and tagged by virtual address (plus an ASID to separate address spaces). With no sharing, there is no synonym problem (one physical address mapped by several virtual addresses). Devices communicate only by messages, with no cache coherence, which avoids the bandwidth cost of a coherent interconnect. For the same reason, anonymous memory is zero-filled directly in ExCache on first access, with no remote fetch.
3. **Lost memory is not persistent data → memory reliability needs only best effort**
   Insight: A memory device failure does not lose the user's persistent data.
   So: Each vma has one primary memory device. When dirty lines are written back, they are written in parallel to the primary device and to a small log on another device. The log is flushed in the background to a file on a storage device. When the log is full, replication pauses. The space cost is far below 2× replication.

Other design: one monitor per device type, with no shared state between them (storage requests carry the full path, similar to NFS v2); two-level virtual memory management (1 GB vRegions are assigned to different memory devices, each managing fine-grained allocation itself); the global manager does only coarse-grained placement; a custom RDMA RPC.

## Evidence
- End to end (10 servers emulating the device types, 40 Gbps IB): with ExCache at about 25% of the working set, TensorFlow and Phoenix are 1.68× and 1.34× slower than Linux with enough memory. With the same local memory, compared with swapping to local SSD/ramdisk and InfiniSwap, performance is 0.8–3.2× theirs.
- Novelty 1 → ExCache size sweep (read from figures). One ExCache miss fetching from remote takes about 6.5 µs. The hardware design of the cache hit path has no real hardware and can only be emulated with 4 KB pages and page fault exceptions.
- Novelty 2 → no direct ablation (shared memory support was implemented but removed for complexity; no data). The zero-fill-on-first-access optimization improves performance by at most 5%.
- Novelty 3 → replication costs 2–23% in performance, with a fixed 1 MB log space. No failure recovery experiment.
- Gaps: resource packing and elasticity are not measured. The 17–49% MTTF improvement is computed from device failure rates and assumes utilization doubles. Going from 1 to 4 memory devices instead lowers performance by up to 6%. A single memory device's worker thread is the bottleneck. Processor device failures are not handled.

## When it applies
The application must have strong memory access locality, and processes must not share writable memory (MAP_SHARED must be changed to message passing). A process must fit in one processor device.
