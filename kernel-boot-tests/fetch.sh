#!/bin/bash
# Usage: ./fetch.sh url output_filename [sha]
# Note: the sha should be of the raw download, not post-gunzipped.
#       sha's change after each boot of a fs image.
set -exu

fetch() {
  local url=$1
  local output_filename=$2
  local sha=$3

  # if the file does not exist, fetch it
  if [[ ! -e $output_filename ]]; then
    wget $url -O "$output_filename.gz"

    # if a sha was provided, verify it
    if [[ -n "$sha" ]]; then
      echo "$sha $output_filename.gz" | sha1sum -c -
    fi

    gunzip "$output_filename.gz"
  fi
}

fetch $@
