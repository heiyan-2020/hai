# Network Requirements for Resource Disaggregation
OSDI'16 · Peter X. Gao, Akshay Narayan et al. / UC Berkeley, Cornell, ICSI · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-gao.pdf (camera-ready) · Selected: Highly cited (279 citations)

**One sentence**: After disaggregation, application performance is bound by remote access latency, not bandwidth, and most of that latency is in host software. So there is no need to wait for new network hardware.

## Problem
A disaggregated datacenter (DDC) makes CPU, memory and disk into separate blades connected by a network. CPU–memory traffic that used to stay inside the chassis (20ns, 500Gbps) must cross the network.
How fast must the network be for applications to barely slow down? No one had quantified this. So prototypes assumed a special-purpose network and disaggregated only within one to a few racks.

## Strawman / Baseline
- **Copy in-chassis metrics and deploy a special-purpose network (FireBox, Intel RSA, HP The Machine, SeaMicro, Huawei DC3.0)**: 1Tbps silicon photonic links, high-radix switches and proprietary interconnects inside the rack, with gateways converting to TCP/IP between racks → the requirements were never validated. A two-layer heterogeneous network is complex, and disaggregation is tied to the schedule of new hardware.
- **Early measurement (Han et al., HotNets'13)**: measured the effect of remote memory latency on one machine → few workloads, did not cover the more latency-sensitive class of applications, and ignored queueing and transport protocols.
- **Existing datacenter transports (TCP, DCTCP)**: designed for the heavy-tailed traffic of today's datacenters, with no priority by flow size → DDC traffic comes from paging. Many short flows arrive together within a few microseconds and queue behind each other, so latency targets are missed.

## Novelty
1. **What decides slowdown is latency, not bandwidth**
   Finding: measured on 10 workloads with 25% local memory, adding bandwidth above 40Gbps gives almost no benefit. Latency matters a lot: at 5µs/40Gbps, Class A (Hadoop, GraphLab, memcached) has average slowdown below 5%. Class B (Spark, SparkSQL, Timely, HERD) needs 3µs and 40–100Gbps to stay within 8%. Slowdown is strongly correlated with the application's memory bandwidth, which can be used for a rough estimate.
   So: The bandwidth target can be met with off-the-shelf 40/100G NICs and switches. Only latency remains hard.
2. **Most of the latency budget is in endpoint software, not in switching and links**
   Finding: breaking down the round trip of one 4KB page fetch, the unavoidable parts (transmission, propagation, switching) total 3.14µs across racks and 1.38µs within a rack. The kernel network stack plus data copies take about 3.9µs, which is 55% of the cross-rack total and 73% of the within-rack total.
   So: Invest in RDMA (removes the kernel) and NIC integration (cuts copies to about 0.5µs). Cross-rack latency can drop to 4.14µs and within-rack to 2.38µs. Class A can be disaggregated across the whole datacenter; Class B must stay within the rack. Tbps links and all-optical switching can only optimize a very small part, which refutes the premise that "the network must be replaced".
3. **Queueing can only be held down by a "short flows first" transport plus 100G links**
   Finding: DDC traffic generated from real application traces was used to simulate 5 protocols. pFabric (switches forward first the flow with the fewest remaining bytes, approximating shortest job first) is best. It and pHost (the same scheduling done at end hosts, with commodity switches) reach the needed latency; TCP/DCTCP do not.
   So: Paging creates many short flows that arrive together, and the transport must let short flows cut the line. Even so, waiting behind 4 packets still costs 4×0.82µs of transmission time, and only faster links can shorten it. Injecting pFabric's flow completion times back into the applications gives average slowdown of 14% (whole datacenter) / 11% (within rack) at 40G, dropping to 1–8.5% / 0.4–3.5% at 100G.

Other design: emulate remote memory with a memory-backed swap device and inject latency on page faults; an RDMA block device as swap has 3–4µs request latency and 3.3GB/s throughput.

## Evidence
- End to end: a measurement paper. The main result is the requirements above: 40–100Gbps, 3–5µs, 20–30% local memory (FireBox has 1.28GB/core, which matches). Raising local memory from 20% to 30% cuts Class B slowdown from about 15% to 7%. Beyond 40% there is no further gain.
- Novelty 1 → bandwidth/latency sweep (5 EC2 machines, median of 10 runs per point). Memory bandwidth is only correlated with slowdown; there is no prediction model.
- Novelty 2 → the breakdown in Table 4 is estimated from numbers in the literature. The RDMA swap prototype measures 3–4µs. NIC integration is only an estimate.
- Novelty 3 → only in simulation (9 racks, 144 endpoints). The main text gives no slowdown numbers per protocol, only their ranking.
- Gaps: the injected latency is constant, with no tail latency, and the software cost of page faults is not counted. The authors measured this part at 2.46µs or more, which is already close to the 3µs budget. The introduction says endpoints take 66%/81%, while §3.3 computes 55%/73%; the two do not match. Conclusions cover only these 10 unmodified workloads.

## When it applies
It assumes partial disaggregation (CPU blades keep local memory, and cache coherence stays inside the blade) and page-granularity access to remote memory. With full disaggregation or cache-line-granularity access, coherence traffic goes onto the network, and special-purpose hardware may become necessary again.
