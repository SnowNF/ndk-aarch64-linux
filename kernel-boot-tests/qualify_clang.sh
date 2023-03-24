#!/bin/bash
# Usage: ./qualify_clang.sh path/to/clang
set -exu

clang=$1

test -n $clang
./check-dependencies.sh
./arm64.build-kernel.sh $clang
./arm64.boot-test.sh linux/arch/arm64/boot/Image.gz
