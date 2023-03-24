#!/usr/bin/env python3
#
# Copyright (C) 2019 The Android Open Source Project
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
# pylint: disable=not-callable, relative-import

""" Update symlinks for binutils """

import argparse
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Optional

import paths
import utils


class ArgParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(description=__doc__)

        self.add_argument(
            'version', metavar='VERSION',
            help='Version of binutil prebuilt updating to (e.g. r123456a).')

        self.add_argument(
            '-b', '--bug', type=int,
            help='Bug to reference in commit message.')

        self.add_argument(
            '--use-current-branch', action='store_true',
            help='Do not repo start a new branch for the update.')


def update_binutils_symlink(prebuilt_dir: Path, version: str, use_cbr: bool):
    if not use_cbr:
        utils.unchecked_call(['repo', 'abandon', 'update-binutils-' + version, prebuilt_dir],
                             stderr=subprocess.DEVNULL)
        utils.check_call(['repo', 'start', 'update-binutils-' + version, prebuilt_dir])

    binutils_dir = prebuilt_dir / 'llvm-binutils-stable'
    binutils = [p.name for p in binutils_dir.iterdir()]
    shutil.rmtree(binutils_dir)
    binutils_dir.mkdir()

    for b in binutils:
        symlink_path = binutils_dir / b
        util_rela_path = Path('..') / ('clang-' + version) / 'bin' / b
        symlink_path.symlink_to(util_rela_path)

        if not symlink_path.exists():
            # check that the created link is valid
            raise RuntimeError(f'Created symlink, {symlink_path}, is broken')


def do_commit(prebuilt_dir: Path, version: str, bug_id: Optional[str]):
    utils.check_call(['git', 'add', 'llvm-binutils-stable'], cwd=prebuilt_dir)

    message_lines = []
    message_lines.append(f'Update LLVM binutils to {version}.')
    message_lines.append('')
    message_lines.append('Test: N/A')
    if bug_id is not None:
        message_lines.append(f'Bug: http://b/{bug_id}')
    message = '\n'.join(message_lines)
    utils.check_call(['git', 'commit', '-m', message], cwd=prebuilt_dir)


def main():
    logging.basicConfig(level=logging.DEBUG)
    args = ArgParser().parse_args()
    bug_id = args.bug
    use_cbr = args.use_current_branch
    version = args.version

    hosts = ['darwin-x86', 'linux-x86']

    for host in hosts:
        prebuilt_dir = paths.PREBUILTS_DIR / 'clang' / 'host' / host
        update_binutils_symlink(prebuilt_dir, version, use_cbr)
        do_commit(prebuilt_dir, version, bug_id)

    return 0


if __name__ == '__main__':
    main()
