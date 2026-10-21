# Ray: A Distributed Framework for Emerging AI Applications
OSDI'18 · Philipp Moritz, Robert Nishihara et al. / UC Berkeley · Full text: https://www.usenix.org/system/files/osdi18-moritz.pdf (USENIX camera-ready) · Selected: Highly cited (1826 citations)

**One sentence**: RL must mix millisecond-scale simulation and stateful training in one closed loop. Actor calls are serial and their arguments are immutable, so they can enter the same graph as tasks. With control state moved out, scheduling can be distributed.

## Problem
Reinforcement learning (RL) does simulation (a few ms to minutes, CPU), training (GPU, stateful), and serving (low latency) in one loop. What to compute next depends on which simulation finishes first.
This needs millions of tasks per second and millisecond-level scheduling. At the time, one had to write a special system for each algorithm.

## Strawman / Baseline
- **Glue special systems together (Horovod + Clipper + CIEL)**: The three are tightly coupled in one loop, and the latency of moving data and making calls across systems is too high.
- **BSP systems (Spark, MPI written synchronously)**: All tasks of a round must finish and pass a barrier before the next round. Simulation times vary a lot, so fast ones wait for slow ones.
- **Dynamic task graphs (CIEL, Dask)**: A single master stores lineage (which task and which inputs computed each object, used for recomputation), object locations, and scheduling decisions. It sits on the critical path of every task. Dask tops out at about 3k tasks/s, allreduce adds about 5 ms per round, and completion time is up to 2 times longer. There are only stateless tasks, so models on the GPU and simulator handles cannot stay resident.
- **Actor systems (Orleans, Akka)**: Stateful but have no lineage. Recovery relies on user checkpoints. An actor is fixed in one place and cannot move to the node where a large input is.
- **Distributed schedulers**: Work stealing ignores data locality. Sparrow assumes tasks come from independent jobs. Canary requires knowing the whole graph in advance.

## Novelty
1. **An actor's state is fully determined by its call sequence**
   Insight: Actor methods run serially, and arguments and return values are immutable objects.
   So: Each method call is a task in the same dynamic task graph. A "stateful edge" is added between consecutive calls of the same actor. Tasks and actors share the scheduler, the object store, and lineage replay. Actors use checkpoints to shorten the replay chain.
   Simulation uses tasks for load balancing and locality-aware placement. Training and serving use actors to hold state. This answers both "gluing is too slow" and "actors have no lineage, tasks cannot hold state".
2. **The master is a bottleneck because it alone owns the control state, but that state is just key-value data indexed by ID**
   Insight: Lineage, object locations, and the function table are all single-key reads and writes by task/object ID, independent of each other.
   So: All control state goes into a global store, GCS, sharded by ID, with each shard chain-replicated (a write passes through a chain of replicas in order). The scheduler and object store are both stateless and read state back from GCS after a crash. Data transfer does not go through the scheduler, so storage and scheduling can scale separately. This removes the throughput limit and critical path of a single master.
3. **Most tasks can run directly on the node that submitted them**
   Insight: Nested tasks are launched by each node itself, and their inputs are often local. Only tasks that are overloaded or lack resources (such as a GPU) need a global view.
   So: Tasks go first to the local scheduler. Only when the queue passes a threshold or resources are missing are they forwarded to the global scheduler. The global scheduler picks a node by "queueing time + transfer time of remote inputs", and can run several replicas that share GCS. This handles both locality and the dynamic graph.

Other design: ray.wait returns the first k to finish; tasks declare resources; GCS flushes to disk periodically.

## Evidence
- End to end: Empty-task throughput scales linearly, above 1.8 million/s at 100 nodes. ES scales to 8192 cores with a median of 3.7 minutes (best published is about 10 minutes); the special implementation cannot finish on 2048 cores. PPO beats the MPI implementation with fewer GPUs, cutting cost 4.5×, and 18× with spot instances. Training matches Horovod. Serving throughput is 1.4–24× that of Clipper. Simulation is 1.8× higher than BSP-style MPI on 256 cores.
- Novelty 1 → With placement that ignores locality (equivalent to actors), task latency for 10–100 MB inputs is 1–2 orders of magnitude higher. Actor recovery replays only 500 calls with a checkpoint, versus 10,000 without. "Unified in one graph" has no direct ablation.
- Novelty 2 → Maximum client latency during GCS chain reconfiguration is <30 ms. There is no comparison with a single-master version of Ray. Adding a few ms to scheduling by hand makes allreduce nearly 2× slower, which is only an indirect argument.
- Novelty 3 → No direct ablation.
- Gaps: Scalability uses independent empty tasks. The Dask numbers are quoted from the other side, not measured. Lineage garbage collection is not implemented.

## When it applies
Remote functions must be deterministic and side-effect free, and actor methods must be serial, for replay to be correct. A single object must fit on one machine. The scheduler cannot see the whole graph, so it cannot do whole-graph optimization.
