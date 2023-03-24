#
# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""APIs for accessing toolchains."""

import functools
from pathlib import Path
from typing import List

from builder_registry import BuilderRegistry
import paths
import version

class Toolchain:
    """Base toolchain."""

    path: Path
    build_path: Path

    def __init__(self, path: Path, build_path: Path) -> None:
        self.path = path
        self.build_path = build_path

    @property
    def cc(self) -> Path:  # pylint: disable=invalid-name
        """Returns the path to c compiler."""
        return self.path / 'bin' / 'clang'

    @property
    def cxx(self) -> Path:
        """Returns the path to c++ compiler."""
        return self.path / 'bin' / 'clang++'

    @property
    def cl(self) -> Path:
        """Returns the path to windows c++ compiler."""
        return self.path / 'bin' / 'clang-cl'

    @property
    def ar(self) -> Path:
        """Returns the path to llvm-ar."""
        return self.path / 'bin' / 'llvm-ar'

    @property
    def lipo(self) -> Path:
        """Returns the path to llvm-lipo."""
        return self.path / 'bin' / 'llvm-lipo'

    @property
    def lld(self) -> Path:
        """Returns the path to ld.lld."""
        return self.path / 'bin' / 'ld.lld'

    @property
    def lld_link(self) -> Path:
        """Returns the path to lld-link."""
        return self.path / 'bin' / 'lld-link'

    @property
    def rc(self) -> Path:
        """Returns the path to llvm-windres."""
        return self.path / 'bin' / 'llvm-windres'

    @property
    def ranlib(self) -> Path:
        """Returns the path to llvm-ranlib."""
        return self.path / 'bin' / 'llvm-ranlib'

    @property
    def addr2line(self) -> Path:
        """Returns the path to llvm-addr2line."""
        return self.path / 'bin' / 'llvm-addr2line'

    @property
    def nm(self) -> Path:
        """Returns the path to llvm-nm."""
        return self.path / 'bin' / 'llvm-nm'

    @property
    def objcopy(self) -> Path:
        """Returns the path to llvm-objcopy."""
        return self.path / 'bin' / 'llvm-objcopy'

    @property
    def objdump(self) -> Path:
        """Returns the path to llvm-objdump."""
        return self.path / 'bin' / 'llvm-objdump'

    @property
    def readelf(self) -> Path:
        """Returns the path to llvm-readelf."""
        return self.path / 'bin' / 'llvm-readelf'

    @property
    def mt(self) -> Path:
        """Returns the path to llvm-mt."""
        return self.path / 'bin' / 'llvm-mt'

    @property
    def strip(self) -> Path:
        """Returns the path to llvm-strip."""
        return self.path / 'bin' / 'llvm-strip'

    @property
    def lib_dirs(self) -> List[Path]:
        """Returns the paths to lib dirs."""
        return [self.path / 'lib', self.path / 'lib' / 'x86_64-unknown-linux-gnu', self.path / 'lib' / 'x86_64-unknown-linux-musl']

    @property
    def _version_file(self) -> Path:
        return self.path / 'include' / 'clang' / 'Basic'/ 'Version.inc'

    @functools.cached_property
    def version(self) -> version.Version:
        return version.Version(self._version_file)

    @property
    def clang_lib_dir(self) -> Path:
        return self.lib_dirs[0] / 'clang' / self.version.major_version()

    @property
    def clang_builtin_header_dir(self) -> Path:
        return self.clang_lib_dir / 'include'

    @property
    def libcxx_headers(self) -> Path:
        return self.path / 'include' / 'c++' / 'v1'


def get_prebuilt_toolchain() -> Toolchain:
    """Returns the prebuilt toolchain."""
    # Prebuilt toolchain doesn't have a build path. Use a temp path instead.
    return Toolchain(paths.CLANG_PREBUILT_DIR, Path('.'))
