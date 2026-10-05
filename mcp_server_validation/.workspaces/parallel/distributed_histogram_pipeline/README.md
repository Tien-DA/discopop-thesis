# Distributed histogram pipeline

Event records flow through a fixed sequence of enrichment stages.  The final
histogram stage assigns each record to a bucket, folds bucket totals into the
global partials, and annotates records with the matching total.  A correct
implementation must produce the same digest for one and many OpenMP workers.

The pipeline stages, buffer count, arithmetic, and OpenMP work-sharing remain
part of the contract.  The task is to repair unsafe concurrent state access,
not to replace the parallel computation with sequential work.
