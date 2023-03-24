#!/bin/bash
set -e

TOP=$(cd $(dirname $0)/../../.. && pwd)
OUT=$TOP/out
DIST=$TOP/dist

# Kokoro will rsync back everything created by the build. Since we don't care
# about any artifacts on this build, nuke EVERYTHING at the end of the build.
function cleanup {
  rm -rf "${TOP}"/*
}
trap cleanup EXIT

# Fetch aosp-plus-llvm-master repo
(cd $TOP; \
  repo init -u https://android.googlesource.com/platform/manifest -b master --depth=1 < /dev/null; \
  repo sync -c -j8)

mkdir "${DIST}"
DIST_DIR="${DIST}" OUT_DIR="${OUT}" $TOP/prebuilts/python/linux-x86/bin/python3 \
  $TOP/toolchain/llvm_android/test_compiler.py --build-only --target aosp_arm64-userdebug \
  --clang-package-path ${KOKORO_GFILE_DIR} $TOP
