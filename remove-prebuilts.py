#!/usr/bin/env python3
#
# Copyright (C) 2023 The Android Open Source Project
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

""" Remove unused prebuilt clang version. """

import argparse
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Optional

import paths
import utils

def get_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', metavar='VERSION',
                        help='Version of clang to remove (e.g. r475365).')
    parser.add_argument('-b', '--bug', type=int, help='Bug to reference in commit message.')
    parser.add_argument('--use-current-branch', action='store_true',
                        help='Do not repo start a new branch for the update.')
    parser.add_argument('--repo-upload', action='store_true',
                        help='Upload prebuilts CLs to gerrit using \'repo upload\'')
    return parser.parse_args()


def remove_prebuilt(prebuilt_dir: Path, version: str, use_cbr: bool) -> None:
    if not use_cbr:
        utils.unchecked_call(['repo', 'abandon', 'remove-clang-' + version, prebuilt_dir],
                             stderr=subprocess.DEVNULL)
        utils.check_call(['repo', 'start', 'remove-clang-' + version, prebuilt_dir])

    clang_dir = prebuilt_dir / f'clang-{version}'
    assert clang_dir.is_dir(), f"{clang_dir} doesn't exist"
    shutil.rmtree(clang_dir)


def do_commit(prebuilt_dir: Path, version: str, bug_id: Optional[str]) -> None:
    utils.check_call(['git','rm', '-r', f'clang-{version}'], cwd=prebuilt_dir)

    message_lines = []
    message_lines.append(f'Remove unused clang-{version}.')
    message_lines.append('')
    message_lines.append('Test: N/A')
    if bug_id:
        message_lines.append(f'Bug: http://b/{bug_id}')
    else:
        message_lines.append('Bug: None')
    message = '\n'.join(message_lines)
    utils.check_call(['git', 'commit', '-m', message], cwd=prebuilt_dir)


def main():
    args = get_args()
    logging.basicConfig(level=logging.DEBUG)

    hosts = ['darwin-x86', 'linux-x86', 'windows-x86']
    for host in hosts:
        prebuilt_dir = paths.PREBUILTS_DIR / 'clang' / 'host' / host
        remove_prebuilt(prebuilt_dir, args.version, args.use_current_branch)
        do_commit(prebuilt_dir, args.version, args.bug)

    if args.repo_upload:
        for host in hosts:
            utils.prebuilt_repo_upload(host, f'remove-clang-{args.version}', None, False)
    return 0


if __name__ == '__main__':
    main()
