# My VM is Lighter (and Safer) than your Container
SOSP'17 · Filipe Manco, Costin Lupu, Florian Schmidt et al. / NEC Laboratories Europe, Univ. Politehnica of Bucharest · Full text: https://www.cs.utexas.edu/~witchel/S25-380L/papers/manco17sosp-lightvm.pdf (camera-ready, archived on a course website) · Selected: Highly cited (334 citations)

**One sentence**: VMs are not slow because of isolation itself, but because of a bloated guest and control plane. Cut both, and VM boot is in the same range as fork.

## Problem
Multi-tenant uses such as edge firewalls and Lambda-style functions need millisecond startup, thousands of instances per machine, and strong isolation.
Containers meet the first two, but their isolation boundary is about 400 syscalls, and growing, so in practice containers are often wrapped in a VM as well.

## Strawman / Baseline
- **Standard Xen + Debian VM**: image 1.1 GB, creation 500 ms, then boot 1.5 s; each VM needs at least 111 MB of memory.
- **Replace the guest with a unikernel, keep xl/libxl as the toolstack**: the toolstack is the program in Dom0 (Xen's privileged management VM) that builds VMs. For every creation, xl redoes from scratch: reserving hypervisor resources, allocating vCPUs, reserving and preparing memory, creating virtual devices, and then running bash hotplug scripts to attach the virtual NIC to the switch (tens of ms each time). Even with no other VMs on the machine, a unikernel that boots in 3 ms takes 80 ms to create, mostly spent on device creation.
- **Same as above, now with a growing number of VMs**: creating the 1000th unikernel takes 700 ms (Tinyx 10 s, Debian 42 s), while container creation time does not depend on how many exist. The root cause is XenStore, the centralized registry in Dom0. Each read or write is "message plus acknowledgment", triggering 2–4 software interrupts and cross-domain switches. Building one VM touches more than 30 entries. A new name is compared against all existing VMs. Conflicting concurrent transactions are retried.
- **Intel Clear Containers**: uses a 70 MB guest for Docker compatibility; boot 500 ms.

## Novelty
1. **Most instances run one application; the "weight" of a VM comes from the guest, not from isolation**
   Insight: A VM's image and memory are sized for a general-purpose OS, which a single-application instance does not need. And boot time grows linearly with image size.
   So: The guest keeps only what the application needs: a unikernel (the application links directly against a minimal OS; image 480 KB, memory 3.6 MB), or Tinyx, which automatically trims a single-application Linux and needs no porting of the application.
2. **The hypervisor already has the information needed for boot; no centralized registry is needed**
   Insight: The frontend/backend driver handshake needs only a little information, such as event channel numbers and grant references (handles to shared memory pages). Metadata such as the VM id is already stored by the hypervisor, and things like names are not needed.
   So: Remove XenStore (noxs). The hypervisor gives each VM one read-only device page. The toolstack writes the backend information into it, and the guest maps it at boot and handshakes with the backend directly. With no registry, there are no messages, comparisons or transaction conflicts that grow with the number of VMs.
3. **Most of the work xl redoes each time does not depend on the specific VM**
   Insight: Reserving resources, allocating CPUs and preparing memory are the same for all VMs of the same size.
   So: Split the toolstack. A background daemon builds a pool of VM shells in advance, so creation is left with only parsing the config, loading the kernel and initializing devices. Hotplug is done directly by the daemon xendevd instead of bash scripts.

Other design: Replace xl/libxl with the lean chaos.

## Evidence
- End to end: a noop unikernel boots in 2.3 ms (fork/exec about 1 ms). A 64-core machine runs up to 8000 VMs with boot time nearly constant; Docker grows from about 150 ms to about 1 s at the 3000th container. save/restore 30/20 ms (xl 128/550 ms).
- Novelty 1 → 1000 instances: Tinyx uses 27 GB, Docker 5 GB, Debian 114 GB.
- Novelty 2, 3 → ablation over combinations of mechanisms (daytime unikernel): xl about 100 ms for the first, close to 1 s for the 1000th; chaos 15–80 ms; chaos + split toolstack at most about 25 ms; chaos + noxs 8–15 ms; all three 4–4.1 ms. No separate ablation of xendevd.
- Gaps: "Safer" is argued only from interface size, with no security evaluation. TLS unikernel throughput is only 1/5 of Tinyx. Tinyx boot still takes hundreds of ms.

## When it applies
Instances must run a single application, and the guest must be modifiable (a unikernel needs porting; noxs needs driver changes). noxs targets XenStore, which is specific to Xen; porting to KVM stays at the discussion level.
