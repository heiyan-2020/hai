# SCONE: Secure Linux Containers with Intel SGX
OSDI'16 · Arnautov et al. / TU Dresden, Imperial College London, TU Braunschweig · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-arnautov.pdf (USENIX camera-ready) · Selected: Highly cited (588 citations)

**One sentence**: Services in containers exchange data with the outside only through fds, so encrypting on the fds is secure enough. An enclave can read and write outside memory for free, so system calls can be sent asynchronously.

## Problem
Tenants want container data kept secret from root, the kernel and physical attackers. An SGX enclave (a CPU-protected memory region, the EPC, only 64–128 MB) can do this, but an enclave cannot issue system calls.
The goal is to run unmodified Linux services (Redis, NGINX and others) in an enclave, with a small TCB and low overhead.

## Strawman / Baseline
- **Put a whole library OS in the enclave (Haven)**: only 22 calls remain on the outside interface. → The TCB reaches millions of lines. The authors built a Linux version with LKL to measure it: 5× the TCB, 4× the latency, half the throughput.
- **Put only a shim in the enclave and forward all libc calls outside**: smallest TCB. → The interface is too wide, and the data and pointers returned by read/write cannot be trusted.
- **Synchronous system calls (SGX SDK)**: each call must copy arguments, EEXIT, then EENTER, and also flush the TLB. → pwrite's rate is an order of magnitude below native.
- **Put all application data in the EPC**: on L3 misses, random access is up to 12× slower. Beyond the EPC, pages must be swapped, which is three orders of magnitude slower.

## Novelty
1. **An attacker can only touch data flowing through fds, so encrypting on the fds puts the boundary at the system call layer**
   Insight: Network services in containers use only sockets, standard input/output and a temporary file system, and do not touch devices directly. All the untrusted kernel can tamper with is the bytes passing through fds and the pointers it returns.
   So: Put only a modified musl libc in the enclave, with "shields" attached per fd: files get block-wise authenticated encryption (AES-GCM), TLS terminates inside the enclave, and console streams are also encrypted. Check lengths on values the kernel returns, and reject pointers into the enclave (Iago attacks).
   The kernel only moves ciphertext, so no library OS is needed (the root cause of Haven's TCB), and the untrusted return data of the shim approach is blocked.
2. **An enclave pays no penalty to read and write outside memory, so system calls need not leave the enclave**
   Insight: What is expensive is switching in and out of the enclave. Accessing memory outside the enclave has no extra cost by itself.
   So: Copy arguments to outside memory and hand them through lock-free queues to resident system call threads in a kernel module. Inside the enclave, use M:N user-level threads: after an application thread issues a call, it yields, and the same OS thread goes on to run another application thread. The number of OS threads is about the number of cores, and they rarely leave the enclave. This removes exactly the switching cost of synchronous calls.
3. **Ciphertext does not need the EPC for protection**
   Insight: Data that is already encrypted and authenticated does not leak when placed outside the enclave.
   So: Network buffers and the temporary file system sit outside the enclave, while the blocks' MACs stay inside the enclave to prevent rollback. This uses no EPC, and reading and writing temporary files needs no system calls.

## Evidence
- End to end: SCONE-async throughput is 0.6–1.2× glibc: Apache 0.8×, Redis 0.6×, NGINX 0.8×, Memcached 1.2×. Binary size is 0.6–2× the glibc version.
- Novelty 1 → no direct ablation. There is only the motivating comparison with the authors' own LKL library OS, with no comparison against Haven.
- Novelty 2 → SCONE-sync vs SCONE-async: Apache 32k vs 38k req/s (glibc 48k); Redis 40k (21% of glibc) vs 116k (61%); NGINX gets only 18k synchronous, while asynchronous reaches 80% of native. pwrite microbenchmark: asynchronous with 1 OS thread is close to glibc.
- Novelty 3 → IOZone: the temporary FS outside the enclave is faster than tmpfs; with encryption on, throughput drops an order of magnitude. Shielded SQLite reaches about 80% of unprotected, SQLCipher about 35%, but the gap comes mainly from the difference between GCM and CBC.
- Gaps: Memcached beats native because the native setup uses an external Stunnel for TLS, so it is not a like-for-like comparison. The prototype does not support remote attestation or fork; it does not defend against side channels; file metadata is not protected; "TCB" is measured by binary size.

## When it applies
The service interacts with the outside only through fds, needs no fork/exec, and its memory working set fits in the EPC. Single-threaded services (Redis) get no benefit from M:N and are left at 0.6×.
