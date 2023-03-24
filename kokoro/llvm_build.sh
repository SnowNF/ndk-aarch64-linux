#!/bin/bash
set -e

TOP=$(cd $(dirname $0)/../../.. && pwd)
OUT=$TOP/out
DIST=$TOP/dist
python_src=$TOP/toolchain/llvm_android

# Impersonate the user that owns the source directory under Docker.
if (( $EUID == 0 )); then
  LOCAL_UID=`stat -c '%u' ${TOP}`
  LOCAL_GID=`stat -c '%g' ${TOP}`
  groupadd -g ${LOCAL_GID} build
  useradd -u ${LOCAL_UID} -g ${LOCAL_GID} -d ${TOP} build
  su build -c $0 $@
  exit 0
fi

# Kokoro will rsync back everything created by the build. This can take up to 10
# minutes for our out directory. Clean up these files at the end.
function cleanup {
  rm -rf "${OUT}"
}
trap cleanup EXIT

mkdir -p "${DIST}"
if [ $LLVM_BUILD_TYPE == "linux-TOT" ]; then
  OUT_DIR="${OUT}" DIST_DIR="${DIST}" $TOP/prebuilts/python/linux-x86/bin/python3 \
  $python_src/build.py --build-llvm-next --mlgo --create-tar \
  --build-name "${KOKORO_BUILD_NUMBER}" \
  --no-build=windows --sccache
elif [ $LLVM_BUILD_TYPE == "linux-master" ]; then
  OUT_DIR="${OUT}" DIST_DIR="${DIST}" $TOP/prebuilts/python/linux-x86/bin/python3 \
  $python_src/build.py --lto --pgo --bolt --mlgo --create-tar \
  --build-name "${KOKORO_BUILD_NUMBER}" \
  --no-build=windows --sccache
elif [ $LLVM_BUILD_TYPE == "darwin-master" ]; then
  OUT_DIR="${OUT}" DIST_DIR="${DIST}" $TOP/prebuilts/python/darwin-x86/bin/python3 \
  $python_src/build.py --lto --pgo --create-tar --build-name "${KOKORO_BUILD_NUMBER}"
elif [ $LLVM_BUILD_TYPE == "windows-master" ]; then
  OUT_DIR="${OUT}" DIST_DIR="${DIST}" $TOP/prebuilts/python/linux-x86/bin/python3 \
  $python_src/build.py --mlgo --create-tar --build-name "${KOKORO_BUILD_NUMBER}" \
  --no-build=linux --sccache
else
  echo "Error: requires LLVM_BUILD_TYPE"
fi
