#!/bin/bash -e

# Copyright 2022 Google Inc. All rights reserved.

# Wrapper of clang-tidy

# Use case #1: by RBE input processor to get resource dir.
# Command:
#   clang-tidy.sh --version -- -print-resource-dir
# Outputs:
#   same as clang-tidy --version -- -print-resource-dir

# Use case #2: by soong generated ninja build rules.
#   Calls clang-tidy and touch output .tidy file.
#   Calls clang or clang++ to generate .tidy.d file.
# Environment:
#   CLANG_CMD: 'clang' or 'clang++'
#   TIDY_FILE: path to output .tidy file
#   TIDY_TIMEOUT: optional for clang-tidy
# Arguments: # same as clang-tidy
#   <in-file-path>         (required, input file)
#   <clang-tidy flags>     (optional)
#   "--"                   (required to separate arguments)
#   <clang/clang++ flags>  (optional)
# Outputs:
#   .../*.tidy   (the output file)
#   .../*.tidy.d (the dependent file is output file plus .d suffix)
#   stdout and stderr from clang-tidy
#   stdout and stderr from clang/clang++ if clang-tidy succeeds

BIN_DIR=`dirname $0`
for x in "$@"; do
  if [ "$x" == "--version" ]; then
    exec "${BIN_DIR}/clang-tidy" "$@"
  fi
done

usage() {
    cat <<EOF
Environment Variable:
  required: CLANG_CMD={clang|clang++}
  required: TIDY_FILE=<path to the output .tidy file>
  optional: TIDY_TIMEOUT=<seconds>
Usage: clang-tidy.sh <file> <clang-tidy flags> -- <clang/clang++ flags>
EOF
    exit 1
}

INF="$1"
if [ -z "${CLANG_CMD}" ]; then
  echo "ERROR: CLANG_CMD environment variable must be set"
  usage
fi
if [ "${CLANG_CMD}" != "clang" -a "${CLANG_CMD}" != "clang++" ]; then
  echo "ERROR: CLANG_CMD must be 'clang' or 'clang++'"
  usage
fi
if [ -z "${TIDY_FILE}" ]; then
  echo "ERROR: TIDY_FILE environment variable must be set"
  usage
fi

ARGS=("$@")
NARGS=${#@}
# call clang-tidy with all arguments
TIDY_CLANG_FLAGS=("${ARGS[@]}")

# find "--" in ARGS and set CLANG_FLAGS
LONGDASH=""
for idx in ${!ARGS[@]}; do
  if [ "${ARGS[$idx]}" == "--" ]; then
    LONGDASH=$idx
  fi
done
if [ -z "${LONGDASH}" ]; then
  echo "ERROR: missing '--' argument"
  usage
fi
# call clang with clang flags, after INF
N=$(expr $LONGDASH + 1)
CLANG_FLAGS=("${ARGS[@]:$N:$NARGS}")
# add more flags to generate .tidy.d file
CLANG_FLAGS+=("-E" "-o" "/dev/null" "-MQ" "${TIDY_FILE}" "-MD" "-MF" "${TIDY_FILE}.d")

TIDY_STDOUT="${TIDY_FILE}.stdout"
TIDY_STDERR="${TIDY_FILE}.stderr"
CLANG_STDOUT="${TIDY_FILE}.d.stdout"
CLANG_STDERR="${TIDY_FILE}.d.stderr"

OUT_DIR=`dirname ${TIDY_FILE}`
mkdir -p ${OUT_DIR}

call_clang() {
  "${BIN_DIR}/${CLANG_CMD}" "${INF}" "${CLANG_FLAGS[@]}" \
    > ${CLANG_STDOUT} 2> ${CLANG_STDERR} & \
  CLANG_PID=$!
}

call_clang_tidy() {
  "${BIN_DIR}/clang-tidy" "${TIDY_CLANG_FLAGS[@]}" \
    > ${TIDY_STDOUT} 2> ${TIDY_STDERR} & \
  TIDY_PID=$!
}

rm -f ${TIDY_FILE} ${TIDY_STDOUT} ${TIDY_STDERR} ${CLANG_STDOUT} ${CLANG_STDERR}
call_clang
call_clang_tidy

CLANG_RESULT=0
TIDY_RESULT=0
wait ${CLANG_PID} || CLANG_RESULT=$?
if [ "${CLANG_RESULT}" == 0 ]; then
  # RBE put some files in /b/f/w/, which should be removed in .d files.
  # Or ninja dependency check will not find them and run this script again.
  sed -i -e 's:/b/f/w/::' ${TIDY_FILE}.d
fi
wait ${TIDY_PID} || TIDY_RESULT=$?

cat ${TIDY_STDOUT}
cat ${TIDY_STDERR} 1>&2
if [ "${TIDY_RESULT}" == 0 ]; then
  touch ${TIDY_FILE}
  # dump clang/clang++ output and use its exit code
  cat ${CLANG_STDOUT}
  cat ${CLANG_STDERR} 1>&2
  TIDY_RESULT=${CLANG_RESULT}
else
  # ignore clang/clang++ output
  rm -f ${TIDY_FILE}.d
fi

rm -f ${TIDY_STDOUT} ${TIDY_STDERR} ${CLANG_STDOUT} ${CLANG_STDERR}
exit ${TIDY_RESULT}
