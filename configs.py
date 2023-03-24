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
"""APIs for build configurations."""

from pathlib import Path
from typing import Dict, List, Optional
import functools
import json

import hosts
import paths
import toolchains
import win_sdk

class Config:
    """Base configuration."""

    name: str
    target_os: hosts.Host
    target_arch: hosts.Arch = hosts.Arch.X86_64
    sysroot: Optional[Path] = None

    """Additional config data that a builder can specify."""
    extra_config = None

    @property
    def llvm_triple(self) -> str:
        raise NotImplementedError()

    def get_c_compiler(self, toolchain: toolchains.Toolchain) -> Path:
        """Returns path to c compiler."""
        return toolchain.cc

    def get_cxx_compiler(self, toolchain: toolchains.Toolchain) -> Path:
        """Returns path to c++ compiler."""
        return toolchain.cxx

    def get_linker(self, toolchain: toolchains.Toolchain) -> Optional[Path]:
        """Returns the path to linker."""
        return None

    @property
    def cflags(self) -> List[str]:
        """Returns a list of flags for c compiler."""
        return []

    @property
    def cxxflags(self) -> List[str]:
        """Returns a list of flags used for cxx compiler."""
        return self.cflags

    @property
    def ldflags(self) -> List[str]:
        """Returns a list of flags for static linker."""
        return []

    @property
    def env(self) -> Dict[str, str]:
        return {}

    def __str__(self) -> str:
        return self.target_os.name

    @property
    def output_suffix(self) -> str:
        """The suffix of output directory name."""
        return f'-{self.target_os.value}'

    @property
    def cmake_defines(self) -> Dict[str, str]:
        """Additional defines for cmake."""
        return dict()


class _BaseConfig(Config):  # pylint: disable=abstract-method
    """Base configuration."""

    use_lld: bool = True
    target_os: hosts.Host
    # Assume most configs are cross compiling
    is_cross_compiling: bool = True

    @property
    def cflags(self) -> List[str]:
        cflags: List[str] = [f'-ffile-prefix-map={paths.ANDROID_DIR}/=']
        cflags.extend(f'-B{d}' for d in self.bin_dirs)
        return cflags

    @property
    def ldflags(self) -> List[str]:
        ldflags: List[str] = []
        for lib_dir in self.lib_dirs:
            ldflags.append(f'-B{lib_dir}')
            ldflags.append(f'-L{lib_dir}')
        if self.use_lld:
            ldflags.append('-fuse-ld=lld')
        return ldflags

    @property
    def bin_dirs(self) -> List[Path]:
        """Paths to binaries used in cflags."""
        return []

    @property
    def lib_dirs(self) -> List[Path]:
        """Paths to libraries used in ldflags."""
        return []

    def get_linker(self, toolchain: toolchains.Toolchain) -> Optional[Path]:
        if self.use_lld:
            return toolchain.lld
        return None


class BaremetalConfig(_BaseConfig):
    """Configuration for baremetal targets."""

    target_os: hosts.Host = hosts.Host.Baremetal

    @property
    def cmake_defines(self) -> Dict[str, str]:
        defines = super().cmake_defines
        defines['COMPILER_RT_BAREMETAL_BUILD'] = 'ON'
        return defines

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append(f'--target={self.llvm_triple}')
        return cflags


class BaremetalAArch64Config(BaremetalConfig):
    """Configuration for baremetal targets."""

    target_arch: hosts.Arch = hosts.Arch.AARCH64

    @property
    def llvm_triple(self) -> str:
        return 'aarch64-elf'


class DarwinConfig(_BaseConfig):
    """Configuration for Darwin targets."""

    target_os: hosts.Host = hosts.Host.Darwin
    use_lld: bool = False
    is_cross_compiling: bool = False

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        # Fails if an API used is newer than what specified in -mmacosx-version-min.
        cflags.append('-Werror=unguarded-availability')
        return cflags

    @property
    def llvm_triple(self) -> str:
        # x86_64-apple-darwin is another choice
        return 'arm64-apple-darwin'

class _GccConfig(_BaseConfig):  # pylint: disable=abstract-method
    """Base config to use gcc libs."""

    gcc_root: Path
    gcc_triple: str
    gcc_ver: str

    def __init__(self, is_32_bit: bool = False):
        self.is_32_bit = is_32_bit

    @property
    def bin_dirs(self) -> List[Path]:
        return [self.gcc_root / self.gcc_triple / 'bin']

    @property
    def gcc_lib_dir(self) -> Path:
        gcc_lib_dir = self.gcc_root / 'lib' / 'gcc' / self.gcc_triple / self.gcc_ver
        if self.is_32_bit:
            gcc_lib_dir = gcc_lib_dir / '32'
        return gcc_lib_dir

    @property
    def gcc_builtin_dir(self)-> Path:
        base = self.gcc_root / self.gcc_triple
        if self.is_32_bit:
            return base / 'lib32'
        else:
            return base / 'lib64'

    @property
    def lib_dirs(self) -> List[Path]:
        return [self.gcc_lib_dir, self.gcc_builtin_dir]


class LinuxConfig(_GccConfig):
    """Configuration for Linux targets."""

    target_os: hosts.Host = hosts.Host.Linux
    sysroot: Optional[Path] = (paths.GCC_ROOT / 'host' / 'x86_64-linux-glibc2.17-4.8' / 'sysroot')
    gcc_root: Path = (paths.GCC_ROOT / 'host' / 'x86_64-linux-glibc2.17-4.8')
    gcc_triple: str = 'x86_64-linux'
    gcc_ver: str = '4.8.3'
    is_cross_compiling: bool = False
    is_musl: bool = False

    @property
    def llvm_triple(self) -> str:
        return 'i386-unknown-linux-gnu' if self.is_32_bit else 'x86_64-unknown-linux-gnu'

    @property
    def cflagsS(self) -> List[str]:
        cflags = super().cflags
        if self.is_32_bit and not self.is_musl:
            # compiler-rt/lib/gwp_asan uses PRIu64 and similar format-specifier macros.
            # Add __STDC_FORMAT_MACROS so their definition gets included from
            # inttypes.h.  This explicit flag is only needed here.  64-bit host runtimes
            # are built in stage1/stage2 and get it from the LLVM CMake configuration.
            # These are defined unconditionaly in bionic and newer glibc
            # (https://sourceware.org/git/gitweb.cgi?p=glibc.git;h=1ef74943ce2f114c78b215af57c2ccc72ccdb0b7)
            cflags.append('-D__STDC_FORMAT_MACROS')
            cflags.append('-march=i686')


    @property
    def ldflags(self) -> List[str]:
        return super().ldflags + [
            '-Wl,--hash-style=both',
        ]


class LinuxMuslConfig(LinuxConfig):
    """Config for Musl sysroot bootstrapping"""
    target_os: hosts.Host = hosts.Host.Linux
    target_arch: hosts.Arch
    is_cross_compiling: bool
    is_musl: bool = True

    def __init__(self, arch: hosts.Arch = hosts.Arch.X86_64, is_cross_compiling: bool = True):
        self.triple = arch.llvm_arch + '-unknown-linux-musl'
        if arch is hosts.Arch.ARM:
            self.triple += 'eabihf'
        self.target_arch = arch
        self.is_cross_compiling = is_cross_compiling

    @property
    def is_32_bit(self):
        return self.target_arch in [hosts.Arch.ARM, hosts.Arch.I386]

    @property
    def llvm_triple(self) -> str:
        return self.triple

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags + [
                f'--target={self.llvm_triple}',
                '-D_LIBCPP_HAS_MUSL_LIBC',
                # gcc does this automatically and glibc includes it in features.h
                # Neither clang nor musl include it, so add it here.  Otherwise
                # libedit fails with error: wchar_t must store ISO 10646 characters
                '-include stdc-predef.h',
        ]
        if self.target_arch is hosts.Arch.ARM:
            cflags.append('-march=armv7-a')

        return cflags

    @property
    def cxxflags(self) -> List[str]:
        cxxflags = super().cxxflags + [
            # -stdlib=libc++ prevents the "Check for working CXX compiler"
            # step from failing when it can't find libstdc++.
            # -Wno-unused-command-line-argument is necessary for commands that
            # use -Werror -nostdinc++.
            '-stdlib=libc++',
            '-Wno-unused-command-line-argument',
        ]

        return cxxflags

    @property
    def ldflags(self) -> List[str]:
        return super().ldflags + [
            '-rtlib=compiler-rt',
            '-Wl,-z,stack-size=2097152',
        ]

    @property
    def sysroot(self) -> Path:
        return paths.BUILD_TOOLS_DIR / 'sysroots' / self.triple

    @property
    def output_suffix(self) -> str:
        """The suffix of output directory name."""
        return f'-{self.llvm_triple}'

    @property
    def lib_dirs(self) -> List[Path]:
        """Override gcc libdirs."""
        return []

    @property
    def bin_dirs(self) -> List[Path]:
        """Override gcc bindirs."""
        return []

    @property
    def cmake_defines(self) -> Dict[str, str]:
        defines = super().cmake_defines
        defines['LIBCXX_USE_COMPILER_RT'] = 'TRUE'
        defines['LIBCXXABI_USE_COMPILER_RT'] = 'TRUE'
        defines['LIBUNWIND_USE_COMPILER_RT'] = 'TRUE'

        # The musl sysroots contain empty libdl.a, libpthread.a and librt.a to
        # satisfy the parts of the LLVM build that hardcode -lpthread, etc.,
        # but that causes LLVM to mis-detect them as libpthread.so, etc.
        # Hardcoded them as disabled to prevent references from .deplibs
        # sections.
        defines['LIBCXX_HAS_RT_LIB'] = 'FALSE'
        defines['LIBCXX_HAS_PTHREAD_LIB'] = 'FALSE'
        defines['LIBCXXABI_HAS_PTHREAD_LIB'] = 'FALSE'
        defines['LIBUNWIND_HAS_DL_LIB'] = 'FALSE'
        defines['LIBUNWIND_HAS_PTHREAD_LIB'] = 'FALSE'

        defines['LLVM_DEFAULT_TARGET_TRIPLE'] = self.llvm_triple

        return defines


class LinuxMuslHostConfig(LinuxMuslConfig):
    """Config for Musl as the host"""
    def __init__(self, arch: hosts.Arch = hosts.Arch.X86_64):
        super().__init__(arch=arch, is_cross_compiling=False)

    @property
    def env(self) -> Dict[str, str]:
        env = super().env
        env['LD_LIBRARY_PATH'] = str(self.sysroot / 'lib')
        return env


class MinGWConfig(_GccConfig):
    """Configuration for MinGW targets."""

    target_os: hosts.Host = hosts.Host.Windows
    gcc_root: Path = (paths.GCC_ROOT / 'host' / 'x86_64-w64-mingw32-4.8')
    gcc_triple: str = 'x86_64-w64-mingw32'
    gcc_ver: str = '4.8.3'
    sysroot: Optional[Path] = paths.SYSROOTS / gcc_triple

    @property
    def llvm_triple(self) -> str:
        return 'x86_64-pc-windows-gnu'

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append(f'--target={self.llvm_triple}')
        cflags.append('-D_LARGEFILE_SOURCE')
        cflags.append('-D_FILE_OFFSET_BITS=64')
        cflags.append('-D_WIN32_WINNT=0x0600')
        cflags.append('-DWINVER=0x0600')
        cflags.append('-D__MSVCRT_VERSION__=0x1400')
        return cflags

    @property
    def ldflags(self) -> List[str]:
        ldflags = super().ldflags
        ldflags.append('-Wl,--dynamicbase')
        ldflags.append('-Wl,--nxcompat')
        ldflags.append('-Wl,--high-entropy-va')
        ldflags.append('-Wl,--Xlink=-Brepro')
        return ldflags

    @property
    def lib_dirs(self) -> List[Path]:
        # No need for explicit lib_dirs.  We copy them into the sysroot.
        return []


class MSVCConfig(Config):
    """Configuration for MSVC toolchain."""
    target_os: hosts.Host = hosts.Host.Windows

    # We still use lld but don't want -fuse-ld=lld in linker flags.
    use_lld: bool = False

    def get_c_compiler(self, toolchain: toolchains.Toolchain) -> Path:
        return toolchain.cl

    def get_cxx_compiler(self, toolchain: toolchains.Toolchain) -> Path:
        return toolchain.cl

    def get_linker(self, toolchain: toolchains.Toolchain) -> Optional[Path]:
        return toolchain.lld_link

    @functools.cached_property
    def _read_env_setting(self) -> Dict[str, str]:
        sdk_path = win_sdk.get_path()
        assert sdk_path is not None
        base_path = sdk_path / 'bin'
        with (base_path / 'SetEnv.x64.json').open('r') as env_file:
            env_setting = json.load(env_file)
        return {key: ';'.join(str(base_path.joinpath(*v)) for v in value)
                for key, value in env_setting['env'].items()}

    @property
    def llvm_triple(self) -> str:
        return 'x86_64-pc-windows-msvc',

    @property
    def cflags(self) -> List[str]:
        return super().cflags + [
            '-w',
            '-fuse-ld=lld',
            '--target={self.llvm_triple}',
            '-fms-compatibility-version=19.10',
            '-D_HAS_EXCEPTIONS=1',
            '-D_CRT_STDIO_ISO_WIDE_SPECIFIERS'
        ]

    @property
    def ldflags(self) -> List[str]:
        return super().ldflags + [
            '/MANIFEST:NO',
            '/dynamicbase',
            '/nxcompat',
            '/highentropyva',
            '/Brepro',
        ]

    @property
    def env(self) -> Dict[str, str]:
        return self._read_env_setting

    @property
    def cmake_defines(self) -> Dict[str, str]:
        defines = super().cmake_defines
        defines['CMAKE_POLICY_DEFAULT_CMP0091'] = 'NEW'
        defines['CMAKE_MSVC_RUNTIME_LIBRARY'] = 'MultiThreaded'
        return defines


class AndroidConfig(_BaseConfig):
    """Config for Android targets."""

    target_os: hosts.Host = hosts.Host.Android

    target_arch: hosts.Arch
    _toolchain_path: Optional[Path]

    static: bool = False
    platform: bool = False
    suppress_libcxx_headers: bool = False
    override_api_level: Optional[int] = None

    @property
    def base_llvm_triple(self) -> str:
        """Get base LLVM triple (without API level)."""
        return f'{self.target_arch.llvm_arch}-linux-android'

    @property
    def llvm_triple(self) -> str:
        """Get LLVM triple (with API level)."""
        return f'{self.base_llvm_triple}{self.api_level}'

    @property
    def ndk_arch(self) -> str:
        """Converts to ndk arch."""
        return {
            hosts.Arch.ARM: 'arm',
            hosts.Arch.AARCH64: 'arm64',
            hosts.Arch.I386: 'x86',
            hosts.Arch.RISCV64: 'riscv64',
            hosts.Arch.X86_64: 'x86_64',
        }[self.target_arch]

    @property
    def ndk_sysroot_triple(self) -> str:
        """Triple used to identify NDK sysroot."""
        if self.target_arch == hosts.Arch.ARM:
            return 'arm-linux-androideabi'
        return self.base_llvm_triple

    @property
    def sysroot(self) -> Path:  # type: ignore
        """Returns sysroot path."""
        platform_or_ndk = 'platform' if self.platform else 'ndk'
        return paths.SYSROOTS / platform_or_ndk / self.ndk_arch

    @property
    def ldflags(self) -> List[str]:
        ldflags = super().ldflags
        ldflags.append('-rtlib=compiler-rt')
        ldflags.append('-Wl,-z,defs')
        ldflags.append('-Wl,--gc-sections')
        ldflags.append('-Wl,--build-id=sha1')
        ldflags.append('-pie')
        if self.static:
            ldflags.append('-static')
        return ldflags

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append(f'--target={self.llvm_triple}')

        if self._toolchain_path:
            toolchain_bin = paths.GCC_ROOT / self._toolchain_path / 'bin'
            cflags.append(f'-B{toolchain_bin}')

        cflags.append('-ffunction-sections')
        cflags.append('-fdata-sections')
        return cflags

    @property
    def _libcxx_header_dirs(self) -> List[Path]:
        # For the NDK, the sysroot has the C++ headers.
        assert self.platform
        if self.suppress_libcxx_headers:
            return []
        # <prebuilts>/include/c++/v1 includes the cxxabi headers
        return [
            paths.CLANG_PREBUILT_LIBCXX_HEADERS,
            # The platform sysroot also has Bionic headers from an NDK release,
            # but override them with the current headers.
            paths.BIONIC_HEADERS,
            paths.BIONIC_KERNEL_HEADERS,
        ]

    @property
    def cxxflags(self) -> List[str]:
        cxxflags = super().cxxflags
        if self.platform:
            # For the NDK, the sysroot has the C++ headers, but for the
            # platform, we need to add the headers manually.
            cxxflags.append('-nostdinc++')
            cxxflags.extend(f'-isystem {d}' for d in self._libcxx_header_dirs)
        return cxxflags

    @property
    def api_level(self) -> int:
        if self.override_api_level:
            return self.override_api_level
        if self.target_arch == hosts.Arch.RISCV64:
            return 10000
        if self.static or self.platform:
            # Set API level for platform to to 29 since these runtimes can be
            # used for apexes targeting that API level.
            return 29
        if self.target_arch in [hosts.Arch.ARM, hosts.Arch.I386]:
            return 19
        return 21

    def __str__(self) -> str:
        return (f'{self.target_os.name}-{self.target_arch.name} ' +
                f'(platform={self.platform} static={self.static} {self.extra_config})')

    @property
    def output_suffix(self) -> str:
        suffix = f'-{self.target_arch.value}'
        if not self.platform:
            suffix += '-ndk-cxx'
        return suffix


class AndroidARMConfig(AndroidConfig):
    """Configs for android arm targets."""
    target_arch: hosts.Arch = hosts.Arch.ARM
    _toolchain_path: Optional[Path] = Path('arm/arm-linux-androideabi-4.9/arm-linux-androideabi')

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append('-march=armv7-a')
        return cflags


class AndroidAArch64Config(AndroidConfig):
    """Configs for android arm64 targets."""
    target_arch: hosts.Arch = hosts.Arch.AARCH64
    _toolchain_path: Optional[Path] = Path('aarch64/aarch64-linux-android-4.9/aarch64-linux-android')

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append('-mbranch-protection=standard')
        return cflags


class AndroidRiscv64Config(AndroidConfig):
    """Configs for android riscv64 targets."""
    target_arch: hosts.Arch = hosts.Arch.RISCV64
    _toolchain_path: Optional[Path] = None

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append(f'-isystem {self.sysroot}/usr/include/{self.ndk_sysroot_triple}')

        return cflags


class AndroidX64Config(AndroidConfig):
    """Configs for android x86_64 targets."""
    target_arch: hosts.Arch = hosts.Arch.X86_64
    _toolchain_path: Optional[Path] = Path('x86/x86_64-linux-android-4.9/x86_64-linux-android')


class AndroidI386Config(AndroidConfig):
    """Configs for android x86 targets."""
    target_arch: hosts.Arch = hosts.Arch.I386
    _toolchain_path: Optional[Path] = Path('x86/x86_64-linux-android-4.9/x86_64-linux-android')

    @property
    def cflags(self) -> List[str]:
        cflags = super().cflags
        cflags.append('-m32')
        return cflags


def host_config(musl: bool=False) -> Config:
    """Returns the Config matching the current machine."""
    return {
        hosts.Host.Linux: LinuxMuslHostConfig if musl else LinuxConfig,
        hosts.Host.Darwin: DarwinConfig,
        hosts.Host.Windows: MinGWConfig
    }[hosts.build_host()]()

def host_32bit_config(musl: bool=False) -> Config:
    if hosts.build_host().is_darwin:
        raise RuntimeError("host_32bit config only needed for Windows or Linux")
    if musl:
        return LinuxMuslHostConfig(hosts.Arch.I386)
    if hosts.build_host().is_windows:
        return MinGWConfig(is_32_bit=True)
    else:
        return LinuxConfig(is_32_bit=True)


def android_configs(platform: bool=True,
                    static: bool=False,
                    suppress_libcxx_headers: bool=False,
                    extra_config=None) -> List[Config]:
    """Returns a list of configs for android builds."""
    configs = [
        AndroidARMConfig(),
        AndroidAArch64Config(),
        AndroidI386Config(),
        AndroidX64Config(),
    ]
    # There is no NDK for riscv64, only include it in platform configs.
    if platform:
        configs.append(AndroidRiscv64Config())
    for config in configs:
        config.static = static
        config.platform = platform
        config.suppress_libcxx_headers = suppress_libcxx_headers
        config.extra_config = extra_config
    # List is not covariant. Explicit convert is required to make it List[Config].
    return list(configs)


def android_ndk_tsan_configs() -> List[Config]:
    """Returns a list of configs for android builds."""
    configs = [
        AndroidAArch64Config(),
        AndroidX64Config(),
    ]
    for config in configs:
        config.override_api_level = 24
    # List is not covariant. Explicit convert is required to make it List[Config].
    return list(configs)
