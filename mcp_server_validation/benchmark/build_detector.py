from pathlib import Path
from typing import Optional


class BuildSystemDetector:
    """
    Detect the build system of a repository and create the
    DiscoPoP-compatible compile.sh and execute.sh scripts.
    """

    def detect(self, repository: Path) -> Optional[str]:
        """
        Detect the build system.

        Currently supported:
        - CMake
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

    def _prepare_cmake_scripts(
            self,
            compile_script: Path,
            execute_script: Path,
    ) -> None:
        compile_script.write_text(
            """#!/bin/bash
    set -e

    cmake -S test/discopop-workload -B test/discopop-workload/build \
        -DCMAKE_C_COMPILER="$CC" \
        -DCMAKE_CXX_COMPILER="$CXX" \
        -DCMAKE_C_FLAGS="$CFLAGS" \
        -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
        -DCMAKE_BUILD_TYPE=Debug

    cmake --build test/discopop-workload/build \
        --target discopop-workload \
        -j1
    """,
            encoding="utf-8",
        )

        execute_script.write_text(
            """#!/bin/bash
    set -e

    ./test/discopop-workload/build/discopop-workload
    """,
            encoding="utf-8",
        )

    def _prepare_make_scripts(
        self,
        compile_script: Path,
        execute_script: Path,
    ) -> None:
        """
        Create Make build and execution scripts.
        """

        compile_script.write_text(
            """#!/bin/bash
        set -e

        cmake -S . -B build \
            -DCMAKE_C_COMPILER="$CC" \
            -DCMAKE_CXX_COMPILER="$CXX" \
            -DCMAKE_C_FLAGS="$CFLAGS" \
            -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
            -DCMAKE_BUILD_TYPE=Debug

        cmake --build build --target assert-test -j1
        """,
            encoding="utf-8",
        )

        execute_script.write_text(
            """#!/bin/bash
        set -e

        ./build/bin/assert-test
        """,
            encoding="utf-8",
        )

    def _prepare_autotools_scripts(
            self,
            compile_script: Path,
            execute_script: Path,
    ) -> None:
        compile_script.write_text(
            """#!/bin/bash
        set -e

        autoreconf -fi
        ./configure --disable-maintainer-mode
        make -j2
        """,
            encoding="utf-8",
        )

        execute_script.write_text(
            """#!/bin/bash
    set -e

    echo '{"name":"test","value":42}' | ./jq '.value' >/dev/null
    ./jq -n '1 + 2' >/dev/null
    """,
            encoding="utf-8",
        )

