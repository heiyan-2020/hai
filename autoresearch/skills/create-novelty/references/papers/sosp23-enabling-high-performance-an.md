# Enabling High-Performance and Secure Userspace NVM File Systems with the Trio Architecture
SOSP'23 · Diyu Zhou et al. / EPFL, Rutgers · Full text: https://rs3lab.github.io/assets/papers/2023/zhou:trio.pdf (camera-ready on the author lab home page) · Selected: Best Paper

**One sentence**: Most file system state can be rebuilt from a small amount of "ground truth", so only this ground truth needs to be defined and checked; the rest can be customized freely by each application.

## Problem
NVM (persistent memory such as Intel Optane, accessed directly with load/store and with permissions controlled by the MMU) lets a file system be a library inside the application (LibFS): it skips the kernel to read and write directly, and can be customized per workload.
But an application may be buggy or malicious, and changing metadata directly can harm other applications that share the same file. And once each LibFS is customized, its data structures differ, so a trusted party cannot understand them and has no way to check them.

## Strawman / Baseline
- **Let a trusted party do metadata updates (Strata, SplitFS, Aerie, KucoFS)**: every metadata update needs IPC or a kernel trap; ZoFS measured 44% more for a 4KB append and 68% more for create; NOVA spends at least 42% of create time in the VFS. The file system design is fixed in the trusted party; customization needs privilege and affects all applications.
- **Allow direct metadata changes (ZoFS, ctFS, MadFS)**: metadata integrity is not guaranteed. ZoFS lets several applications share a group of pages (a coffer) and the same LibFS: an attacker can point an index pointer at a victim's DRAM to leak it, delete non-empty directories, create directory cycles, or hold a lock forever.
- **Have the trusted party check each LibFS's structures on every operation**: each LibFS has different structures that the trusted party cannot understand, and per-operation checking falls back to the overhead of the first approach.

## Novelty
1. **Only the "ground truth" state needs agreement; everything else is rebuildable soft state**
   Insight: file contents, file names, permissions and the directory hierarchy are ground truth that cannot be recovered once lost (core state); the fd table, caches, indexes, free bitmaps and so on can all be rebuilt from the ground truth (auxiliary state).
   So: the system defines only one minimal ground-truth layout, which all LibFSes and the trusted party agree on. Each LibFS builds its private structures only in auxiliary state and rebuilds them from the ground truth when it reads a file. The trusted party only needs to understand the ground truth to check any customized LibFS; customization needs no privilege and does not affect others.
   So that MMU page permissions map directly to file permissions, an inode is placed on the same page as its directory entry, and creating or deleting a file only needs write permission on the parent directory; chmod/chown go through a shadow inode table in the kernel.
2. **Check only this one file, only when write permission changes hands**
   Insight: when one application corrupts metadata, it only causes harm when another application uses that file. With a rule of "many readers or one writer", the check point can be placed only at the handoff.
   So: a LibFS normally reads and writes NVM directly, with no trusted party involved. When write permission passes from one application to another, a verifier checks only that file's ground truth (fields are valid, no page is referenced twice, the directory tree is connected), taking a few to a few hundred µs. Before write permission is granted, the metadata is checkpointed, and on a failed check it is rolled back.
   This removes the per-operation mediation overhead and also closes ZoFS's security holes.

Other design: ArckFS reuses OdinFS's delegation threads for NVM access, with per-directory hash tables and per-CPU allocators; mutually trusting processes can form a trust group to skip the handoff overhead.

## Evidence
- End to end (Optane with 224 cores and 8 NUMA nodes): LevelDB up to 3.1× faster than the runner-up WineFS and 1.5–17× faster than ext4. In Filebench, Varmail is 2.4–34.2× faster and Webproxy 2.2–8.0× faster. At 224 threads, open is 5.4–334× faster than other systems, and data operations are 3.2× faster than OdinFS.
- Novelty 1 → two customized LibFSes, KVFS and FPFS, change nothing in the trusted party and are another 1.3× (Webproxy) and 1.2× (Varmail, 20-level directories) faster than ArckFS. Gain from "direct access": 10–12% faster 4KB reads and writes on a single NUMA node, 1.3× faster than OdinFS at 224 threads. Mediated and direct approaches were not compared on the same system.
- Novelty 2 → 11 hand-written attacks plus automatically injected corruption, 134 scenarios in total, all detected and recovered. Handoff cost: <5 µs for small files; when two applications alternate writes to a 1GB file, throughput drops from 1.91 to 0.25 GiB/s (670 ms per map/unmap); alternating create in a directory with 100 files is 20.4× slower, with checking taking 81%.
- Gaps: ZoFS, KucoFS and Aerie could not be run, so there is no comparison. Much of the speedup comes from borrowed delegation threads and data structures, not from Trio itself. Crash consistency only has unit tests. Whether the verifier is complete is only tested with attack cases.

## When it applies
Mutually distrusting applications must rarely write the same file concurrently; frequent alternating writes to large files make the handoff cost large. Customization can only change auxiliary state; changing the ground-truth layout (e.g. to a log-structured file system) still needs privilege.
