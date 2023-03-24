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

import os
import string
import subprocess

import android_version
import hosts
import paths
import utils
import source_manager
import sys

_LLVM_ANDROID_PATH = paths.SCRIPTS_DIR
_PATCH_DIR = os.path.join(_LLVM_ANDROID_PATH, 'patches')
_PATCH_JSON = os.path.join(_PATCH_DIR, 'PATCHES.json')

_SVN_REVISION = (android_version.get_svn_revision_number())


def get_removed_patches(output):
    """Parse the list of removed patches from patch_manager.py's output."""
    marker = 'removed from the patch metadata file:\n'
    marker_start = output.find(marker)
    if marker_start == -1:
        return None
    removed = output[marker_start + len(marker):].splitlines()
    return [p.strip() for p in removed]


def trim_patches_json():
    """Invoke patch_manager.py with failure_mode=remove_patches."""
    source_dir = paths.TOOLCHAIN_LLVM_PATH
    output = source_manager.apply_patches(source_dir, _SVN_REVISION,
                                          _PATCH_JSON, _PATCH_DIR,
                                          'remove_patches')
    return get_removed_patches(output)


def main():
    if len(sys.argv) > 1:
        print(f'Usage: {sys.argv[0]}')
        print('  Script to remove downstream patches no longer needed for ' +
              'Android LLVM version.')
        return

    def _get_patch_path(patch):
        # Find whether the basename printed by patch_manager.py is a cherry-pick
        # (patch/cherry/<PATCH>) or a local patch (patch/<PATCH>).
        cherry = os.path.join(_PATCH_DIR, 'cherry', patch)
        local = os.path.join(_PATCH_DIR, patch)
        if os.path.exists(cherry):
            return cherry
        elif os.path.exists(local):
            return local
        raise RuntimeError(f'Cannot find patch file {patch}')

    # Start a new repo branch before trimming patches.
    os.chdir(_LLVM_ANDROID_PATH)
    branch_name = f'trim-patches-before-{_SVN_REVISION}'
    utils.unchecked_call(['repo', 'abandon', branch_name, '.'])
    utils.check_call(['repo', 'start', branch_name, '.'])

    removed_patches = trim_patches_json()
    if not removed_patches:
        print('No patches to remove')
        return

    removed_patch_paths = [_get_patch_path(p) for p in removed_patches]

    # Apply the changes to git and commit.
    utils.check_call(['git', 'add', _PATCH_JSON])
    for patch in removed_patch_paths:
        utils.check_call(['git', 'rm', patch])

    message_lines = [
        f'Remove patch entries older than {_SVN_REVISION}.',
        '',
        'Removed using: python3 trim_patch_data.py',
        'Test: N/A',
    ]
    utils.check_call(['git', 'commit', '-m', '\n'.join(message_lines)])


if __name__ == '__main__':
    main()
