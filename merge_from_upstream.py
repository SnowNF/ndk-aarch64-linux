#!/usr/bin/env python3
#
# Copyright (C) 2017 The Android Open Source Project
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

"""Update toolchain/llvm-project by merging a given upstream SHA."""

import argparse
from functools import lru_cache
import subprocess
import sys

import paths
import utils

sys.path.append(str(paths.TOOLCHAIN_UTILS_DIR / 'llvm_tools'))
#pylint: disable=wrong-import-position,wrong-import-order
import git_llvm_rev
#pylint: enable=wrong-import-position,wrong-import-order

# do not require docstring for small functions
# pylint: disable=missing-function-docstring


def parse_args():
    parser = argparse.ArgumentParser(description="""
        Update toolchain/llvm-project to a selected revision of upstream-main.

        With one of sha and rev, both can be get by using external/toolchain-utils/git_llvm_rev.py.

        The merge of cherry-picked patches (which are in patches/) are delayed
        to when building with build.py.
    """)
    parser.add_argument('--sha', help='aosp/upstream-main SHA to be merged')
    parser.add_argument('--rev', help='the svn revision number for update')
    parser.add_argument(
        '--bug',
        default=0,
        help='bug number to include in the commit message')
    parser.add_argument(
        '--create-new-branch',
        action='store_true',
        default=False,
        help='Create new branch using `repo start` before '
        'merging from upstream.')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Dry run, does not actually commit changes to local workspace.')
    args = parser.parse_args()
    if not args.rev and not args.sha:
        parser.error('at least one of --sha and --rev required')
    return args


def sync_branch(path):
    subprocess.check_call(['repo', 'sync', '.'], cwd=path)


@lru_cache
def fetch_upstream():
    # Fetching upstream may take a long time. So print something.
    print('fetch upstream...')
    subprocess.check_call(['git', 'fetch', 'aosp'],
                          cwd=paths.TOOLCHAIN_LLVM_PATH)


def sha_to_revision(sha: str) -> int:
    fetch_upstream()
    git_llvm_rev.MAIN_BRANCH = 'upstream-main'
    llvm_config = git_llvm_rev.LLVMConfig(remote='aosp',
                                          dir=str(paths.TOOLCHAIN_LLVM_PATH))
    rev = git_llvm_rev.translate_sha_to_rev(llvm_config, sha)
    return rev.number


def revision_to_sha(rev: int) -> str:
    fetch_upstream()
    git_llvm_rev.MAIN_BRANCH = 'upstream-main'
    llvm_config = git_llvm_rev.LLVMConfig(remote='aosp',
                                          dir=str(paths.TOOLCHAIN_LLVM_PATH))
    return git_llvm_rev.translate_rev_to_sha(
        llvm_config, git_llvm_rev.Rev.parse(f'r{rev}'))


def merge_projects(sha, revision, bug_id, create_new_branch, dry_run):
    path = paths.TOOLCHAIN_LLVM_PATH
    if not dry_run:
        sync_branch(path)
    fetch_upstream()
    print(f'Project llvm-project svn: {revision}  sha: {sha}')

    if create_new_branch:
        branch_name = f'merge-upstream-r{revision}'
        utils.check_call(['repo', 'start', branch_name, '.'],
                         cwd=path,
                         dry_run=dry_run)

    # Merge upstream revision
    commit_msg = f'Merge {sha} for LLVM update to {revision}\n\n'
    if bug_id != 0:
        commit_msg += f'Bug: {bug_id}\n'
    commit_msg += 'Test: presubmit'
    utils.check_call(['git', 'config', 'merge.renameLimit', '0'],
                     cwd=path, dry_run=dry_run)
    utils.check_call(['git', 'config', '--add', 'secrets.allowed', '...'],
                     cwd=path, dry_run=dry_run)
    utils.check_call(['git', 'merge', '--quiet', sha,
                      '-m', commit_msg], cwd=path, dry_run=dry_run)


def main():
    args = parse_args()
    if args.rev:
        revision = int(args.rev[1:] if args.rev.startswith('r') else args.rev)
        sha = revision_to_sha(revision)
        if args.sha:
            assert sha == args.sha, "revision and sha don't match"
    else:
        sha = args.sha
        revision = sha_to_revision(sha)

    merge_projects(sha, revision, int(args.bug),
                   args.create_new_branch, args.dry_run)


if __name__ == '__main__':
    main()
