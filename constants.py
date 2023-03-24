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
"""Configs for the build."""

from typing import Set

# Minimum macOS version to support.
MAC_MIN_VERSION: str = '10.14'

# This is the baseline stable version of Clang to start our stage-1 build.
CLANG_PREBUILT_VERSION: str = 'clang-r487747'

# This is the ndk version used to build runtimes.
NDK_VERSION: str = 'r25'

# Targets for host.
HOST_TARGETS: Set[str] = set(['X86'])
DARWIN_HOST_TARGETS: Set[str] = set(['X86', 'AArch64'])

# Targets for Android.
ANDROID_TARGETS: Set[str] = set(['AArch64', 'ARM', 'BPF', 'RISCV', 'WebAssembly', 'X86'])
