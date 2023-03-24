//
// Copyright (C) 2020 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// +build android_llvm_next_flags

package main

// This file defines extra flags for llvm-next toolchain for Android.  Via a
// symlink from external/toolchain-utils/compiler_wrapper, this file is part of
// the compiler_wrapper's sources.  It gets included iff the
// `android_llvm_next_flags` tag is set.

// TODO: Enable test in config_test.go, once we have new llvm-next flags.
var llvmNextFlags = []string{
}

var llvmNextPostFlags = []string{
}
