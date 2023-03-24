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
"""Helpers for paths."""

import os
from pathlib import Path
import string
from typing import Optional

import android_version
import constants
import hosts

SCRIPTS_DIR: Path = Path(__file__).resolve().parent
ANDROID_DIR: Path = SCRIPTS_DIR.parents[1]
OUT_DIR: Path = Path(os.environ.get('OUT_DIR', ANDROID_DIR / 'out')).resolve()
SYSROOTS: Path = OUT_DIR / 'sysroots'
LLVM_PATH: Path = OUT_DIR / 'llvm-project'
PREBUILTS_DIR: Path = ANDROID_DIR / 'prebuilts'
EXTERNAL_DIR: Path = ANDROID_DIR / 'external'
TOOLCHAIN_DIR: Path = ANDROID_DIR / 'toolchain'
TOOLCHAIN_UTILS_DIR: Path = EXTERNAL_DIR / 'toolchain-utils'
TOOLCHAIN_LLVM_PATH: Path = TOOLCHAIN_DIR / 'llvm-project'

CLANG_PREBUILT_DIR: Path = (PREBUILTS_DIR / 'clang' / 'host' / hosts.build_host().os_tag
                            / constants.CLANG_PREBUILT_VERSION)
CLANG_PREBUILT_LIBCXX_HEADERS: Path = CLANG_PREBUILT_DIR / 'include' / 'c++' / 'v1'
WINDOWS_CLANG_PREBUILT_DIR: Path = (PREBUILTS_DIR / 'clang' / 'host' / 'windows-x86'
                                    / constants.CLANG_PREBUILT_VERSION)


BIONIC_HEADERS: Path = ANDROID_DIR / 'bionic' / 'libc' / 'include'
BIONIC_KERNEL_HEADERS: Path = ANDROID_DIR / 'bionic' / 'libc' / 'kernel' / 'uapi'

GO_BIN_PATH: Path = PREBUILTS_DIR / 'go' / hosts.build_host().os_tag / 'bin'
CMAKE_BIN_PATH: Path = PREBUILTS_DIR / 'cmake' / hosts.build_host().os_tag / 'bin' / 'cmake'
BUILD_TOOLS_DIR: Path = PREBUILTS_DIR / 'build-tools'
MAKE_BIN_PATH: Path = BUILD_TOOLS_DIR / hosts.build_host().os_tag / 'bin' / 'make'
# Use the musl version of ninja on Linux, it is statically linked and avoids
# problems with LD_LIBRARY_PATH causing ninja to use the wrong libc++.so.
NINJA_BIN_PATH: Path = BUILD_TOOLS_DIR / hosts.build_host().os_tag_musl / 'bin' / 'ninja'

LIBEDIT_SRC_DIR: Path = EXTERNAL_DIR / 'libedit'
LIBNCURSES_SRC_DIR: Path = EXTERNAL_DIR / 'libncurses'
LIBXML2_SRC_DIR: Path = EXTERNAL_DIR / 'libxml2'
SWIG_SRC_DIR: Path = EXTERNAL_DIR / 'swig'
XZ_SRC_DIR: Path = TOOLCHAIN_DIR / 'xz'
ZSTD_SRC_DIR: Path = EXTERNAL_DIR / 'zstd'

NDK_BASE: Path = TOOLCHAIN_DIR / 'prebuilts' /'ndk' / constants.NDK_VERSION
NDK_LIBCXX_HEADERS: Path = NDK_BASE / 'sources' / 'cxx-stl' / 'llvm-libc++'/ 'include'
NDK_LIBCXXABI_HEADERS: Path = NDK_BASE / 'sources' / 'cxx-stl' / 'llvm-libc++abi' / 'include'
NDK_SUPPORT_HEADERS: Path = NDK_BASE / 'sources' / 'android' / 'support' / 'include'

RISCV64_ANDROID_SYSROOT: Path = TOOLCHAIN_DIR / 'prebuilts' / 'sysroot' / 'platform' / 'riscv64-linux-android'

GCC_ROOT: Path = PREBUILTS_DIR / 'gcc' / hosts.build_host().os_tag
GO_ROOT: Path = PREBUILTS_DIR / 'go' / hosts.build_host().os_tag
MINGW_ROOT: Path = PREBUILTS_DIR / 'gcc' / 'linux-x86' / 'host' / 'x86_64-w64-mingw32-4.8' / 'x86_64-w64-mingw32'

_WIN_ZLIB_PATH: Path = (PREBUILTS_DIR / 'clang' / 'host' / 'windows-x86' /
                        'toolchain-prebuilts' / 'zlib')
WIN_ZLIB_INCLUDE_PATH: Path = _WIN_ZLIB_PATH / 'include'
WIN_ZLIB_LIB_PATH: Path = _WIN_ZLIB_PATH / 'lib'

KYTHE_RUN_EXTRACTOR = (PREBUILTS_DIR / 'build-tools' / hosts.build_host().os_tag / 'bin' /
                       'runextractor')
KYTHE_CXX_EXTRACTOR = (PREBUILTS_DIR / 'clang-tools' / hosts.build_host().os_tag / 'bin' /
                       'cxx_extractor')
KYTHE_OUTPUT_DIR = OUT_DIR / 'kythe-files'
KYTHE_VNAMES_JSON = SCRIPTS_DIR / 'kythe_vnames.json'

_PYTHON_VER = '3.10'
_PYTHON_VER_SHORT = _PYTHON_VER.replace('.', '')

def pgo_profdata_filename() -> str:
    svn_revision = android_version.get_svn_revision_number()
    return f'r{svn_revision}.profdata'


def pgo_profdata_tarname() -> str:
    svn_revision = android_version.get_svn_revision_number()
    return f'pgo-r{svn_revision}.tar.bz2'


def pgo_profdata_tar() -> Optional[Path]:
    profile = (PREBUILTS_DIR / 'clang' / 'host' / 'linux-x86' / 'profiles' /
               pgo_profdata_tarname())
    return profile if profile.exists() else None


def bolt_fdata_tarname() -> str:
    svn_revision = android_version.get_svn_revision_number()
    return f'bolt-r{svn_revision}.tar.bz2'


def bolt_fdata_tar() -> Optional[Path]:
    profile = (PREBUILTS_DIR / 'clang' / 'host' / 'linux-x86' / 'profiles' /
               bolt_fdata_tarname())
    return profile if profile.exists() else None


def mlgo_model(filename: str) -> Optional[Path]:
    model = (PREBUILTS_DIR / 'clang' / 'host' / 'linux-x86' / 'mlgo-models' /
            filename)
    return model if model.exists() else None


def get_package_install_path(host: hosts.Host, package_name) -> Path:
    return OUT_DIR / 'install' / host.os_tag / package_name

def get_python_dir(host: hosts.Host) -> Path:
    """Returns the path to python for a host."""
    return PREBUILTS_DIR / 'python' / host.os_tag

def get_python_executable(host: hosts.Host) -> Path:
    """Returns the path to python executable for a host."""
    python_root = get_python_dir(host)
    return {
        hosts.Host.Linux: python_root / 'bin' / f'python{_PYTHON_VER}',
        hosts.Host.Darwin: python_root / 'bin' / f'python{_PYTHON_VER}',
        hosts.Host.Windows: python_root / 'python.exe',
    }[host]

def get_python_include_dir(host: hosts.Host) -> Path:
    """Returns the path to python include dir for a host."""
    python_root = get_python_dir(host)
    return {
        hosts.Host.Linux: python_root / 'include' / f'python{_PYTHON_VER}',
        hosts.Host.Darwin: python_root / 'include' / f'python{_PYTHON_VER}',
        hosts.Host.Windows: python_root / 'include',
    }[host]

def get_python_lib(host: hosts.Host) -> Path:
    """Returns the path to python lib for a host."""
    python_root = get_python_dir(host)
    return {
        hosts.Host.Linux: python_root / 'lib' / f'libpython{_PYTHON_VER}.so',
        hosts.Host.Darwin: python_root / 'lib' / f'libpython{_PYTHON_VER}.dylib',
        hosts.Host.Windows: python_root / 'libs' / f'python{_PYTHON_VER_SHORT}.lib',
    }[host]

def get_python_dynamic_lib(host: hosts.Host) -> Path:
    """Returns the path to python runtime dynamic lib for a host."""
    python_root = get_python_dir(host)
    return {
        hosts.Host.Linux: python_root / 'lib' / f'libpython{_PYTHON_VER}.so.1.0',
        hosts.Host.Darwin: python_root / 'lib' / f'libpython{_PYTHON_VER}.dylib',
        hosts.Host.Windows: python_root / f'python{_PYTHON_VER_SHORT}.dll',
    }[host]
