from pathlib import Path
from typing import Optional


class BuildSystemDetector:
    """
    Detect the build system of a repository and create the
    DiscoPoP-compatible compile.sh and execute.sh scripts.

    Design goals (generic, not tied to any single project):

    - compile.sh always builds the REPOSITORY ROOT that was actually
      checked out for the benchmark case ("-S ." / plain `make` in the
      repo root), never a hardcoded fixture path like
      "test/discopop-workload". This is what broke fmt: the previous
      cmake/make scripts assumed a fixed example project layout that
      doesn't exist in real SWE-bench repos.

    - execute.sh tries, in order:
        1. The project's own test entrypoint (ctest for CMake,
           `make check`/`make test` for Make/autotools) — this is the
           most reliable way to exercise real code paths and produce
           meaningful dynamic dependency data.
        2. A best-effort fallback: run the most recently built
           executable with no arguments, under a timeout, so a repo
           with no discoverable test target still produces *some*
           dynamic profiling data instead of hard-failing.

    Known limitation: fully automatic, meaningful dynamic execution of
    an arbitrary C/C++ repository is inherently heuristic. For repos
    with unusual test/run conventions (custom test runners, required
    fixtures/services, GPU/hardware dependencies, etc.), a
    project-specific execute.sh may still be necessary. Treat this as a
    solid generic baseline, not a guarantee.
    """

    # ------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------

    def detect(self, repository: Path) -> Optional[str]:
        """
        Detect the build system.

        Currently supported:
        - CMake
        - Autotools
        - Make
        """
        if (repository / "CMakeLists.txt").is_file():
            return "cmake"

        if (repository / "configure").is_file():
            return "autotools"

        if (repository / "configure.ac").is_file():
            return "autotools"

        if (repository / "Makefile").is_file():
            return "make"

        if (repository / "makefile").is_file():
            return "make"

        return None

    # ------------------------------------------------------------
    # Script generation
    # ------------------------------------------------------------

    def prepare_scripts(
        self,
        repository: Path,
        build_system: str,
    ) -> None:
        """
        Create the scripts required by DiscoPoP.
        """

        config_dir = (
            repository
            / ".discopop"
            / "project"
            / "configs"
        )

        default_config_dir = config_dir / "default"

        config_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        default_config_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        compile_script = config_dir / "compile.sh"
        execute_script = default_config_dir / "execute.sh"

        if build_system == "cmake":
            self._prepare_cmake_scripts(
                compile_script,
                execute_script,
            )
        elif build_system == "autotools":
            self._prepare_autotools_scripts(
                compile_script,
                execute_script,
            )
        elif build_system == "make":
            self._prepare_make_scripts(
                compile_script,
                execute_script,
            )
        else:
            raise ValueError(
                f"Unsupported build system: {build_system}"
            )

        compile_script.chmod(0o755)
        execute_script.chmod(0o755)

    # ------------------------------------------------------------
    # Shared runtime helper injected into every execute.sh
    # ------------------------------------------------------------

    _RUN_FALLBACK = r"""
# Best-effort fallback: run the most recently modified executable
# produced by the build, if no test suite could be run. This is a
# heuristic — it does not know which binary is meaningful, it just
# picks the newest one and exercises it briefly under a timeout so a
# hang can't block the whole benchmark run.
run_newest_executable() {
    local search_dir="$1"
    local newest=""
    while IFS= read -r -d '' f; do
        if [ -z "$newest" ] || [ "$f" -nt "$newest" ]; then
            newest="$f"
        fi
    done < <(find "$search_dir" -maxdepth 6 -type f -perm -u+x \
              ! -name '*.sh' ! -name '*.so' ! -name '*.a' ! -name '*.la' \
              -print0 2>/dev/null)

    if [ -n "$newest" ]; then
        echo "[execute.sh] No test target found, running: $newest"
        timeout 120 "$newest" || true
    else
        echo "[execute.sh] No executable found to run; skipping dynamic execution."
    fi
}
"""

    # ------------------------------------------------------------
    # CMake
    # ------------------------------------------------------------

    def _prepare_cmake_scripts(
        self,
        compile_script: Path,
        execute_script: Path,
    ) -> None:
        compile_script.write_text(
            """#!/bin/bash
set -e

cmake -S . -B build \\
    -DCMAKE_C_COMPILER="$CC" \\
    -DCMAKE_CXX_COMPILER="$CXX" \\
    -DCMAKE_C_FLAGS="$CFLAGS" \\
    -DCMAKE_CXX_FLAGS="$CXXFLAGS" \\
    -DCMAKE_BUILD_TYPE=Debug \\
    -DBUILD_TESTING=ON

cmake --build build -j1
""",
            encoding="utf-8",
        )

        execute_script.write_text(
            "#!/bin/bash\n"
            "set -e\n"
            + self._RUN_FALLBACK
            + """
cd build

if command -v ctest >/dev/null 2>&1 && [ -f CTestTestfile.cmake ]; then
    echo "[execute.sh] Running ctest..."
    ctest --output-on-failure -j1 || true
else
    run_newest_executable "."
fi
""",
            encoding="utf-8",
        )

    # ------------------------------------------------------------
    # Plain Make (no configure step)
    # ------------------------------------------------------------

    def _prepare_make_scripts(
        self,
        compile_script: Path,
        execute_script: Path,
    ) -> None:
        compile_script.write_text(
            """#!/bin/bash
set -e

make -j2 CC="$CC" CXX="$CXX" CFLAGS="$CFLAGS" CXXFLAGS="$CXXFLAGS"
""",
            encoding="utf-8",
        )

        execute_script.write_text(
            "#!/bin/bash\n"
            "set -e\n"
            + self._RUN_FALLBACK
            + """
if grep -qE '^(test|check)[[:space:]]*:' Makefile 2>/dev/null; then
    target=$(grep -oE '^(test|check)[[:space:]]*:' Makefile | head -n1 | tr -d ': ')
    echo "[execute.sh] Running make $target..."
    make "$target" || true
else
    run_newest_executable "."
fi
""",
            encoding="utf-8",
        )

    # ------------------------------------------------------------
    # Autotools
    # ------------------------------------------------------------

    def _prepare_autotools_scripts(
        self,
        compile_script: Path,
        execute_script: Path,
    ) -> None:
        compile_script.write_text(
            """#!/bin/bash
set -e

autoreconf -fi
./configure --disable-maintainer-mode CC="$CC" CXX="$CXX" CFLAGS="$CFLAGS" CXXFLAGS="$CXXFLAGS"
make -j2
""",
            encoding="utf-8",
        )

        execute_script.write_text(
            "#!/bin/bash\n"
            "set -e\n"
            + self._RUN_FALLBACK
            + """
if grep -qE '^(check|test)[[:space:]]*:' Makefile 2>/dev/null; then
    target=$(grep -oE '^(check|test)[[:space:]]*:' Makefile | head -n1 | tr -d ': ')
    echo "[execute.sh] Running make $target..."
    make "$target" || true
else
    run_newest_executable "."
fi
""",
            encoding="utf-8",
        )