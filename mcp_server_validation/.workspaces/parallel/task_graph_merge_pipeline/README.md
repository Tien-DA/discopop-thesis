# Task graph merge pipeline

The final graph stage merges predecessor contributions into a frontier for
each parent task, then uses those frontier totals to annotate task records.
Many independent tasks can share one parent.  The merge must therefore remain
correct under the existing OpenMP task-processing loops.

Preserve the graph arithmetic and stage sequence.  The completed program must
give the sequential reference digest for every tested parallel execution.
