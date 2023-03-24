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

import re

_llvm_next = False
_version_read = False

_patch_level = '0'
_svn_revision = 'r487747'
_git_sha = 'c4c5e79dd4b4c78eee7cffd9b0d7394b5bedcf12'

# Psudo revision for top of trunk LLVM.
_svn_revision_next = 'r99999999'

def set_llvm_next(llvm_next: bool):
    if _version_read:
        raise RuntimeError('set_llvm_next() after earlier read of versions')
    # pylint:disable=global-statement
    global _llvm_next
    _llvm_next = llvm_next


def is_llvm_next() -> bool:
    _version_read = True
    return _llvm_next


def get_svn_revision():
    _version_read = True
    if _llvm_next:
        return _svn_revision_next
    return _svn_revision


def get_git_sha():
    _version_read = True
    if _llvm_next:
        return "refs/for/master"
    return _git_sha


def get_patch_level():
    _version_read = True
    if _llvm_next:
        return None
    return _patch_level


def get_svn_revision_number():
    """Get the numeric portion of the version number we are working with.
       Strip the leading 'r' and possible letter (and number) suffix,
       e.g., r383902b1 => 383902
    """
    svn_version = get_svn_revision()
    found = re.match(r'r(\d+)([a-z]\d*)?$', svn_version)
    if not found:
        raise RuntimeError(f'Invalid svn revision: {svn_version}')
    return found.group(1)
