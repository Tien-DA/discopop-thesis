# Particle scatter pipeline

Particle records are transformed by a fixed pipeline and then scattered into
spatial cells.  The cell mass is reduced into partial summaries and fed back
into each particle record.  Several particles can target the same cell, so
the cell accumulator needs a correct parallel ownership or synchronization
strategy.

Keep the OpenMP scatter loops and all existing arithmetic.  Correctness means
that the digest is repeatable for all tested thread counts.
