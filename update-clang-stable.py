#!/usr/bin/env python3
#
# Copyright (C) 2022 The Android Open Source Project
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

""" Update clang-stable """

import argparse
import logging
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional

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


class ClangStableBuilder:
    def __init__(self, prebuilt_dir: Path, version: str):
        self.version = version
        self.clang_dir = prebuilt_dir / ('clang-' + version)
        self.stable_dir = prebuilt_dir / 'clang-stable'

    def build(self):
        shutil.rmtree(self.stable_dir)
        self.stable_dir.mkdir()
        (self.stable_dir / 'bin').mkdir()
        (self.stable_dir / 'lib').mkdir()
        (self.stable_dir / 'share').mkdir()

        self.copy_file(self.clang_dir / 'bin' / 'clang-format', self.stable_dir / 'bin')
        self.copy_file(self.clang_dir / 'bin' / 'git-clang-format', self.stable_dir / 'bin')

        self.copy_files((self.clang_dir / 'lib').glob('libclang.*'), self.stable_dir / 'lib')
        self.copy_dir(self.clang_dir / 'lib' / 'python3', self.stable_dir / 'lib')
        self.copy_dir(self.clang_dir / 'lib' / 'x86_64-unknown-linux-gnu', self.stable_dir / 'lib')
        self.copy_dir(self.clang_dir / 'share' / 'clang', self.stable_dir / 'share')

        (self.stable_dir / 'README.md').write_text(
            f'All contents in clang-stable are copies of clang-{self.version}.')

    def copy_file(self, src_file: Path, dst_dir: Path):
        shutil.copy(src_file, dst_dir, follow_symlinks=False)

    def copy_files(self, src_files: List[Path], dst_dir: Path):
        for src_file in src_files:
            self.copy_file(src_file, dst_dir)

    def copy_dir(self, src_dir: Path, dst_parent_dir: Path):
        shutil.copytree(src_dir, dst_parent_dir / src_dir.name,
                        symlinks=True, ignore_dangling_symlinks=True)

    def test(self):
        utils.check_call([self.stable_dir / 'bin' / 'clang-format', '-h'],
                         stdout=subprocess.DEVNULL)
        utils.check_call([self.stable_dir / 'bin' / 'git-clang-format', '-h'],
                         stdout=subprocess.DEVNULL)


def update_clang_stable(prebuilt_dir: Path, version: str, use_cbr: bool):
    if not use_cbr:
        utils.unchecked_call(['repo', 'abandon', 'update-clang-stable-' + version, prebuilt_dir],
                             stderr=subprocess.DEVNULL)
        utils.check_call(['repo', 'start', 'update-clang-stable-' + version, prebuilt_dir])

    builder = ClangStableBuilder(prebuilt_dir, version)
    builder.build()
    builder.test()


def do_commit(prebuilt_dir: Path, version: str, bug_id: Optional[str]):
    utils.check_call(['git', 'add', 'clang-stable'], cwd=prebuilt_dir)

    message_lines = []
    message_lines.append(f'Update clang-stable to {version}.')
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

    prebuilt_dir = paths.PREBUILTS_DIR / 'clang' / 'host' / 'linux-x86'
    update_clang_stable(prebuilt_dir, version, use_cbr)
    do_commit(prebuilt_dir, version, bug_id)


if __name__ == '__main__':
    main()
