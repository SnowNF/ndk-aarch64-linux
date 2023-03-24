#!/bin/bash
# Usage ./arm64.boot-test.sh path/to/linux/Image
set -exu

run_qemu() {
  local kernel_image=$1
  local rootfs=$2

  # verify images exist.
  test -e $kernel_image
  test -e $rootfs

  # -no-reboot is expected for the rootfs, as it just runs a reboot if booted
  # sucessfully.
  timeout 10s unbuffer qemu-system-aarch64 \
    -kernel $kernel_image \
    -machine virt \
    -cpu cortex-a57 \
    -hda $rootfs \
    -append "console=ttyAMA0 earlyprintk=ttyAMA0 root=/dev/vda" \
    -m 512 \
    -nographic \
    -no-reboot
}

rootfs=arm64.rootfs.ext2
./fetch.sh https://github.com/groeck/linux-build-test/blob/1105ee4079c78c576c3d88e33cf95420f620c116/rootfs/arm64/rootfs.ext2.gz?raw=true $rootfs dbe4136f0b4a0d2180b93fd2a3b9a784f9951d10
run_qemu $1 $rootfs
