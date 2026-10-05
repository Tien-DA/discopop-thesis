# Iterative stencil orchestrator

This workload evolves a field through a fixed stage schedule.  Its stencil
orchestrator derives a halo window for each cell and merges that window into
the cell state.  Every worker must observe storage private to its cell while
the OpenMP iteration remains parallel.

The required result is invariant across thread counts.  Preserve the stage
order, recurrence arithmetic, and existing OpenMP loops while repairing the
shared-state defect.
