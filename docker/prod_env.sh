#!/bin/bash
set -e

LOCAL_UID=$(id -u)
LOCAL_GID=$(id -g)
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname ${SCRIPT_PATH})
BASE_DIR=$(dirname ${SCRIPT_DIR})/../..
WORK_DIR=/tmpfs/src/git/

echo build:x:${LOCAL_UID}:${LOCAL_GID}:Build:${WORK_DIR}:/bin/bash > /tmp/passwd.docker
echo build:*:${LOCAL_GID}: > /tmp/group.docker

docker_img=us-west1-docker.pkg.dev/google.com/android-llvm-kokoro/android-llvm-ubuntu/llvm-ubuntu

docker pull ${docker_img}:latest
docker run -it \
  --rm \
  --user ${LOCAL_UID}:${LOCAL_GID} \
  --volume /tmp/passwd.docker:/etc/passwd:ro \
  --volume /tmp/group.docker:/etc/group:ro \
  --volume ${BASE_DIR}:${WORK_DIR} \
  --workdir ${WORK_DIR} \
  ${docker_img} \
  /bin/bash
