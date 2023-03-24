#!/bin/bash
set -eu

red="\e[31m"
reset="\e[39m"

# Multiple invocations allow for easier debugging which command failed.
if ! which qemu-system-aarch64 ; then
  echo -e "${red}unable to find qemu!\nsudo apt install qemu-system\n${reset}"
  exit 1
fi

which timeout
which wget
which sha1sum
which unbuffer
