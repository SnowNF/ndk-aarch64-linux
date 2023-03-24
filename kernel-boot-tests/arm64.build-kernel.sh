#!/bin/bash
# Usage: ./arm64.build-kernel.sh path/to/clang
set -exu

clang=$(readlink -f $1)

if [[ -d linux ]]; then
  cd linux
  git fetch origin --depth 1
  git checkout origin/master
else
  rm -rf linux
  git clone --depth 1 \
    git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
  cd linux
fi

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
make mrproper CC=$clang
make CC=$clang defconfig
make CC=$clang -j`nproc`
cd ..
