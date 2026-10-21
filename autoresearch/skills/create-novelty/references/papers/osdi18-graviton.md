# Graviton: Trusted Execution Environments on GPUs
OSDI'18 · Stavros Volos, Kapil Vaswani, Rodrigo Bruno / Microsoft Research, INESC-ID/IST Lisbon · Full text: https://www.usenix.org/system/files/osdi18-volos.pdf (USENIX camera-ready) · Selected: Highly cited (284 citations)

**One sentence**: GPU memory inside the package cannot be snooped, so GPU memory need not be encrypted. It is enough to let the command processor manage page tables on the driver's behalf and block MMIO, and to encrypt data and commands on PCIe.

## Problem
TEEs like SGX (trusted execution environments; even the OS and hypervisor cannot see the code and data inside) exist only on CPUs.
Data and kernels offloaded to a GPU must pass through an untrusted driver and PCIe.

## Strawman / Baseline
- **CPU TEE + ordinary GPU**: the application goes in an enclave, but the driver controls the GPU page tables and MMIO. → A compromised driver can (a) map the victim's physical pages into a malicious channel (a queue for submitting commands on the GPU, at least one per context); (b) read GPU memory directly through MMIO; (c) tamper with data and kernel launch commands in DMA buffers.
- **Copy SGX's approach to the GPU**: add an encryption engine and a Merkle tree to memory, and do access checks during address translation. → This eats the GPU's scarcest resources, memory capacity and bandwidth. GPUs are sensitive to translation latency, so checks slow computation. It also requires changing the cores, MMU and memory controller.
- **Partition resources statically in hardware (SR-IOV style)**: → low utilization, and multiple channels of one context cannot share pages (CUDA streams need this).
- **PixelVault (cryptographic operations on the GPU)**: → does not clear pages on allocation, does not isolate kernels from each other, and a debugger can attach to read registers. It has been broken.

## Novelty
1. **Stacked GPU memory is inside the package and can be drawn inside the trust boundary**
   Insight: The 3D-stacked memory of server GPUs connects to the cores through a silicon interposer. CPU memory uses PCB traces, which are easy to snoop. To snoop the interposer, you must open the package.
   So: Trust GPU memory, with no memory encryption or integrity tree, and protect only traffic on PCIe. All changes are in peripheral parts (command processor, PCI controller); the cores, MMU and memory controller are untouched. This avoids the capacity, bandwidth and translation latency costs of "copying SGX".
2. **The driver decides only "where to put it"; hardware writes and checks the page tables for it**
   Insight: The danger of the driver is not its allocation policy, but that it can write page tables and access GPU memory directly.
   So: The driver still chooses addresses and physical pages, but page table updates must be handed to the command processor to execute. The command processor records the owner of each 4 KB page in hidden memory that the host cannot see (6 GB of GPU memory needs only 12 MB, about 0.2%), and guarantees: a page cannot be mapped to another context; unmapping needs a MAC signed with the user's key; the protected region cannot be accessed through MMIO; a page is zeroed before it changes owner.
   This blocks (a)(b), and also closes PixelVault's holes of not clearing pages and not isolating. The debugger problem is solved by "the GPU runtime is inside the CPU TEE, and the attestation includes the state of the debug switch". Channels of the same context can still share pages, which avoids static partitioning.
3. **Put encryption and decryption in GPU kernels, and prove by measurement that they were not swapped**
   Obstacle: The most direct fix for (c) is to add cryptographic hardware to the copy engine, but that changes hardware and fixes the algorithm. Decrypting with a software kernel instead means the kernel itself must be copied into GPU memory through the untrusted driver.
   So: The command processor computes an HMAC over a given GPU memory region and hands it to the enclave, confirming that the decryption kernel was not tampered with. After that, data is encrypted in the enclave and sent by DMA, and this kernel verifies and decrypts it. Commands are decrypted by the command processor with AES-GCM plus a counter, preventing tampering, replay and reordering. The algorithm can be changed at any time.

## Evidence
- End to end (GTX Titan Black, nouveau/gdev, new commands emulated on the host with interrupts): overhead on Cifar-10, MNIST and BlackScholes is 17–33%. Under pure emulation, Cifar-10 testing and training are 57% and 53% slower, of which 66% and 77% come from command authentication. Estimated with a hardware AES engine, this drops to 17%.
- Novelty 1 → no direct ablation; no comparison with a GPU memory encryption design.
- Novelty 2 → invariant checks mostly take tens to hundreds of µs; CH_DESTROY takes 10.6 ms; cuMemAlloc grows from 0.02 ms to 0.19 ms (mostly emulation overhead). No comparison with static partitioning.
- Novelty 3 → a 64 MB secure copy takes 177 ms vs 11 ms for an ordinary copy; over 75% is spent on SHA-3 on the CPU and AES on the GPU.
- Gaps: no real hardware, and it did not run inside SGX. No attack experiment validates isolation. Side channels, DoS and trojan dies inside the package are outside the threat model.

## When it applies
GPU memory must be inside the package (HBM-like). GPUs with external GDDR do not satisfy item 1 and still need memory encryption.
