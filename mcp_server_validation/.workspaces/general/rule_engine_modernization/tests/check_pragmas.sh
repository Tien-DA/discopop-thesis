#!/bin/sh
# Fails if a source file has fewer OpenMP pragmas than listed in
# tests/pragma_baseline.txt ("<file> <minimum count>" per line).
status=0
while read -r file minimum; do
    [ -z "$file" ] && continue
    count=$(grep -Ec '^[[:space:]]*#pragma omp' "$file")
    if [ "$count" -lt "$minimum" ]; then
        echo "[FAIL] $file has $count OpenMP pragma(s), expected at least $minimum"
        status=1
    fi
done < tests/pragma_baseline.txt
exit $status
