#!/usr/bin/env python3
#
# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# pylint: disable=invalid-name
"""Parse new compiler warnings reported by the wrapper.

Prebuilts from llvm-toolchain-testing branch have a compiler
wrapper that reports new warnings from a compiler update.
These warnings are reported in JSON format to the build log
($OUT/verbose.log.gz).  This script scrapes and summarizes
these warnings.

The parameters to this script identify the build logs to scrape.
"""

from typing import List, NamedTuple
import argparse
import gzip
import inspect
import json
import logging
import pathlib
import re
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from data import TestResultsTable
import ab_client
import test_paths

# TODO(pirama) instantiate BUILD_CLIENT only when necessary.
BUILD_CLIENT = ab_client.AndroidBuildClient()


class Warning(NamedTuple):
    filename: str
    line: str
    warning: str
    text: str


def _process_log(log: str) -> List[Warning]:
    matches = re.findall(
        r'<LLVM_NEXT_ERROR_REPORT>(?P<report>.*?)</LLVM_NEXT_ERROR_REPORT>',
        log,
        flags=re.DOTALL)

    warning_re = re.compile(
        r'^(?P<file>.*?):(?P<line>.*?):.*\[(?P<flag>.*?)\]')

    results = set()
    failed = 0
    for match in matches:
        try:
            report = json.loads(match[match.find('{'):])
        except Exception:
            failed += 1
            continue
        for warning in warning_re.finditer(report['stdout']):
            # TODO(pirama) Parse the text specific to this warning.  Currently,
            # report['stdout'] will have *all* the warnings for this invocation.
            results.add(
                Warning(
                    filename=warning.group('file'),
                    line=warning.group('line'),
                    warning=warning.group('flag'),
                    text=report['stdout']))
    if failed:
        logging.error(f'Failed to process {failed} records.')
    return results


def process_local_file(filename: str) -> None:
    with open(filename, 'rb') as infile:
        contents = infile.read()
    log = str(
        gzip.decompress(contents), encoding='utf-8', errors='backslashreplace')
    return _process_log(log)


def process_one_run(build, target):
    logging.info(f'processing {build}:{target}')
    log_bytes = BUILD_CLIENT.get_artifact(build, target, 'logs/verbose.log.gz')
    if not log_bytes:
        return list()
    log = str(
        gzip.decompress(log_bytes), encoding='utf-8', errors='backslashreplace')
    return _process_log(log)


def process_tag(tag):
    warnings = set()
    cns_path = test_paths.cns_path()
    testResults = TestResultsTable(f'{cns_path}/{test_paths.TEST_RESULTS_CSV}')
    for record in testResults.records:
        if record.tag != tag or record.work_type != 'BUILD':
            continue
        if 'userdebug' not in record.target:
            continue
        warnings.update(process_one_run(record.build_id, record.target))

    return warnings


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=inspect.getdoc(sys.modules[__name__]))

    params = parser.add_mutually_exclusive_group(required=True)
    params.add_argument(
        '--tag',
        help=('Test TAG whose warnings will be reported.  ' +
              'TAG must match the --tag parameter to test_prebuilts.py.  ' +
              'Build IDs for this TAG will be fetched from CNS data.'),
        metavar='TAG')
    params.add_argument(
        '--file',
        help=('Report warnings in FILE.  ' +
              'Should be Android build output (verbose.log.gz)'),
        metavar='FILE')
    params.add_argument(
        '--build',
        help=('Build number (from go/ab) that uses prebuilts from ' +
              'llvm-toolchain-testing branch.  Also requires a --target.'))
    parser.add_argument(
        '--target', help='Target in go/ab/.  Also requires a --build.')
    parser.add_argument(
        '--verbose', '-v', action='store_true', help='Print verbose output')

    args = parser.parse_args()
    if args.build and not args.target:
        parser.error('--build requires --target')
    if args.target and not args.build:
        parser.error('--target only compatible with --build option')

    return args


def main():
    args = parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level)

    if args.tag:
        warnings = process_tag(args.tag)
    elif args.file:
        warnings = process_local_file(args.file)
    elif args.build:
        warnings = process_one_run(args.build, args.target)

    for warning in sorted(warnings):
        print(warning.text)
        print('=' * 80)


if __name__ == '__main__':
    main()
