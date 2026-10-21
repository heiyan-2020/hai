# hXDP: Efficient Software Packet Processing on FPGA NICs
OSDI'20 · Marco Spaziani Brunella et al. / Axbryd, University of Rome Tor Vergata, CNIT, NEC Labs Europe · Full text: https://www.usenix.org/system/files/osdi20-brunella.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Many instructions in eBPF programs exist only for the kernel environment, and the remaining parallelism can be found fully at compile time. So a small FPGA processor can keep up with a CPU core.

## Problem
An FPGA NIC must share its chip with other accelerators (ML, 5G), so few resources are left for packet processing, and hardware development is hard.
Goal: run unmodified Linux XDP programs (driver-level eBPF packet processing programs) directly on the FPGA, using only a small part of the chip, loadable at run time, with throughput close to one high-end CPU core.

## Strawman / Baseline
- **Pipelined FPGA packet processing (P4→NetFPGA, FlowBlaze)**: Unrolls the program into a hardware pipeline → Resources grow with program complexity (each FlowBlaze stage takes about 16% of logic; a firewall needs 2 stages, a load balancer 4–5). Changing the program means burning a new bitstream, and it cannot be shared with other accelerators.
- **Implement a soft core on the FPGA that executes eBPF sequentially**: Fixed resources, loadable at run time → The FPGA clock is only 156 MHz, 5–10× lower than a CPU. A firewall runs 55 instructions per packet, for an optimistic limit of 2.8 Mpps, while a 3.7 GHz x86 core can do 7.4 Mpps.
- **Make the soft core superscalar (find parallelism at run time)**: → Dependency-checking hardware grows exponentially with the number of instructions checked at once, so resources are too expensive.
- **eBPF offload on Netronome SmartNICs**: Supports only part of eBPF (no redirect, so it cannot run the firewall).

## Novelty
1. **At a low clock, throughput depends only on instructions per packet, and many eBPF instructions serve the kernel and x86**
   Insight: Bounds checks are required by the kernel verifier (19% of the firewall). Zeroing variables is for safety. The two-operand format is for easy JIT to x86. A dedicated executor is not in the kernel, so hardware can do all of these almost for free.
   So: Remove bounds checks (hardware checks packet buffer overflow) and zeroing (hardware clears the stack and registers at the start of each packet). Extend the ISA with three-operand instructions, 6-byte load/store (exactly one MAC address), and exit with a return code.
   This directly lowers the instructions per packet on the sequential soft core.
2. **XDP programs are short, have no unbounded loops, and are fully known at load time, so parallelism can be found fully at compile time**
   Insight: The verifier already guarantees the program is bounded. When parsing headers, many operations do not depend on each other, and consecutive protocol branches are also independent. Finding parallelism at run time costs hardware; finding it at compile time costs only software.
   So: The compiler statically schedules instructions by data dependency into a 4-lane VLIW (several parallel instructions in one instruction word), and fills empty slots early with instructions from following blocks that will surely run. The hardware does no branch prediction and no out-of-order execution. Adjacent branches are evaluated at once on the 4 lanes, and the jump target is chosen by lane priority.
   This avoids the resource cost of superscalar, while keeping the soft core's advantages of "fixed resources, loadable at run time".

Other design: helpers and maps are built as dedicated hardware; execution starts before the whole packet arrives; exit is recognized at the fetch stage to finish early.

## Evidence
- End to end (NetFPGA, 156.25 MHz, compared with one core of a Xeon E5-1630v3): the hXDP core takes 9.91% of logic, 2.09% of registers, 3.4% of BRAM (18.53% in total with the reference NIC). The firewall does 6.53 Mpps, 12% slower than a 3.7 GHz core and 55% faster than a 2.1 GHz core, with about 10× lower latency. Katran is 38% slower than a 3.7 GHz core and 8% faster than a 2.1 GHz core. hXDP is faster on forwarding programs; x86 is faster on pure drop and on long programs (283 instructions).
- Novelty 1 → Turning compiler optimizations on and off one by one: 6-byte load/store cuts 18% of instructions in xdp_adjust_tail; exit with a return code cuts 5–10% (only one instruction saved at run time). XDP_DROP reaches 52 Mpps (x86 38, Netronome 32), and drops to 22 Mpps with exit-with-return-code and early finish turned off. The other items report only static instruction counts.
- Novelty 2 → Sweep of 2–8 lanes: VLIW instruction count drops clearly up to 3 lanes, the 4th lane cuts another 5%, and more lanes change almost nothing. Together, the VLIW instruction count is often 2–3× smaller than the original program. Static IPC is 1.70–2.83, comparable to x86 runtime IPC of 2.16–2.81. There is no single-lane throughput comparison.
- Gaps: x86 must go through PCIe while the FPGA does not go through the host, so part of the latency advantage comes from this. The FlowBlaze firewall does 60 Mpps versus 6.5 Mpps; hXDP wins only on resources and flexibility.

## When it applies
The program must be handled entirely on the NIC and be only a few dozen VLIW instructions. The longer the program, the more the low clock hurts. Large maps crowd out the BRAM of other accelerators.
