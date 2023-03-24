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
"""Upload and query CLs on Gerrit"""

from typing import Any, Dict, NamedTuple
import base64
import contextlib
import json
import logging
import os
import random
import re
import string
import urllib.parse

import test_paths
import utils

AOSP_GERRIT_ENDPOINT = 'https://android-review.googlesource.com'


def gerrit_request(request: str) -> str:
    """Return JSON output of gerrit REST request.

    (https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html)
    """
    return utils.check_output([
        'gob-curl', '--no-progress-meter', '--request', 'GET',
        f'{AOSP_GERRIT_ENDPOINT}/{request}'
    ])


def gerrit_request_json(request: str):
    """Make gerrit request and parse the result into JSON."""
    return json.loads(gerrit_request(request)[5:])


def gerrit_query_change(query: str):
    """Return JSON output of gerrit changes that match 'query'.

    (https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#list-changes)
    """
    quoted = urllib.parse.quote(query)
    return gerrit_request_json(f'changes/?q={quoted}')


def gerrit_change_info(cl_number) -> Dict[str, Any]:
    """Return JSON output for gerrit change number"""
    json_output = gerrit_query_change(f'change:{cl_number}')
    if len(json_output) != 1:
        raise RuntimeError(f'Expected one output for change {cl_number}.' +
                           'Got: ' + json.dumps(json_output, indent=4))
    return json_output[0]


PREBUILTS_PROJECT = 'platform/prebuilts/clang/host/linux-x86'
SOONG_PROJECT = 'platform/build/soong'
KERNEL_COMMON_PROJECT = 'kernel/common'


class PrebuiltCL(NamedTuple):
    """Gerrit CL info for clang prebuilts for linux-x86."""
    revision: str
    version: str
    build_number: str
    cl_number: str
    merged: bool

    @staticmethod
    def getExistingCL(cl_number):
        """Extract prebuilt CL info from an existing CL."""
        info = gerrit_change_info(cl_number)

        # Validate that the CL is in the correct project and doesn't have merge
        # conflicts.  (It's OK for the CL to be merged though.)
        if not info['project'].startswith(PREBUILTS_PROJECT):
            raise RuntimeError(
                f'Prebuilt CL {cl_number} not in {PREBUILTS_PROJECT}')

        if info['status'] != 'MERGED':
            mergeable_info = gerrit_request_json(
                f'changes/{cl_number}/revisions/current/mergeable')
            if not mergeable_info['mergeable']:
                raise RuntimeError(
                    f'Prebuilt CL {cl_number} has merge conflicts')

        # Extract the revision, version, build from the commit message.  The
        # prebuilts are uploaded using the update-prebuilts.py script so we can
        # rely on it's commit message format.
        commit = gerrit_request_json(
            f'changes/{cl_number}/revisions/current/commit')
        clang_info = re.search(
            r'clang (?P<ver>\d\d.\d.\d) \(based on (?P<rev>r\d+[a-z]?)\) ' +
            r'from build (?P<bld>\d+).', commit['message'])
        if not clang_info:
            raise RuntimeError('Cannot parse clang details from following ' +
                               'commit message for CL {cl_number}:\n' +
                               commit['message'])
        logging.info(f'Using prebults/clang CL {cl_number} for build ' +
                     clang_info.group('bld'))
        return PrebuiltCL(
            revision=clang_info.group('rev'),
            version=clang_info.group('ver'),
            build_number=clang_info.group('bld'),
            cl_number=cl_number,
            merged=(info['status'] == 'MERGED'))

    @staticmethod
    def getNewCL(build_number, branch):
        """Upload prebuilts from a particular build number."""

        logging.info(f'Uploading prebuilts CL for build {build_number}')
        # Add a random hashtag so we can discover the CL number.
        hashtag = 'chk-' + ''.join(random.sample(string.digits, 8))
        utils.check_call([
            str(test_paths.LLVM_ANDROID_DIR / 'update-prebuilts.py'),
            f'--branch={branch}',
            '--overwrite',
            '--host=linux-x86',
            '--repo-upload',
            f'--hashtag={hashtag}',
            build_number,
        ])

        json_output = gerrit_query_change(f'hashtag:{hashtag}')
        if len(json_output) != 1:
            raise RuntimeError('Upload failed; or hashtag not unique.  ' +
                               f'Gerrit query returned {json_output}')
        return PrebuiltCL.getExistingCL(str(json_output[0]['_number']))

    def equals(self, other) -> bool:
        return self.build_number == other.build_number and \
            self.revision == other.revision and \
            self.version == other.version and \
            self.build_number == other.build_number and \
            self.cl_number == other.cl_number


class SoongCL(NamedTuple):
    """Gerrit CL for changing toolchain in build/soong project."""

    revision: str
    version: str
    cl_number: str

    @staticmethod
    def _switch_clang_version(soong_filepath, revision, version) -> None:
        """Set Clang versions in soong_filepath."""

        def rewrite(line):
            # Rewrite clang info in go initialization code of the form
            # ClangDefaultVersion           = "clang-r399163"
            # ClangDefaultShortVersion      = "11.0.4"
            replace = None
            if 'ClangDefaultVersion' in line and '=' in line:
                replace = 'clang-' + revision
            elif 'ClangDefaultShortVersion' in line and '=' in line:
                replace = version
            if replace:
                prefix, _, post = line.split('"')
                return f'{prefix}"{replace}"{post}'
            return line

        with open(soong_filepath) as soong_file:
            contents = soong_file.readlines()
        contents = list(map(rewrite, contents))
        with open(soong_filepath, 'w') as soong_file:
            soong_file.write(''.join(contents))

    @staticmethod
    def uploadCL(revision, version, changeId=None):
        """Upload switchover CL with provided parameters.

        If changeId is not none, any existing CL with that ChangeId gets
        updated.
        """
        branch = f'clang-prebuilt-{revision}'
        message = (f'[DO NOT SUBMIT] Switch to clang {revision} ' +
                   f'{version}.\n\n' + 'For testing\n' + 'Test: N/A\n')
        if changeId is not None:
            message += (f'\nChange-Id: {changeId}\n')
        hashtag = 'chk-' + ''.join(random.sample(string.digits, 8))

        @contextlib.contextmanager
        def chdir_context(directory):
            prev_dir = os.getcwd()
            try:
                os.chdir(directory)
                yield
            finally:
                os.chdir(prev_dir)

        # Create change:
        #   - repo start
        #   - update clang version in soong
        #   - git commit
        with chdir_context(test_paths.ANDROID_DIR / 'build' / 'soong'):
            utils.unchecked_call(['repo', 'abandon', branch, '.'])
            utils.check_call(['repo', 'sync', '-c', '.'])
            utils.check_call(['repo', 'start', branch, '.'])

            soong_filepath = 'cc/config/global.go'
            SoongCL._switch_clang_version(soong_filepath, revision, version)
            utils.check_call(['git', 'add', soong_filepath])
            utils.check_call(['git', 'commit', '-m', message])

            utils.check_call([
                'repo',
                'upload',
                '.',
                '--current-branch',
                '--yes',  # Answer yes to all safe prompts
                '--verify',  # Run upload hooks without prompting.
                '--wip',  # work in progress
                '--label=Code-Review-2',  # code-review -2
                f'--hashtag={hashtag}',
            ])

        json_output = gerrit_query_change(f'hashtag:{hashtag}')
        if len(json_output) != 1:
            raise RuntimeError('Upload failed; or hashtag not unique.  ' +
                               f'Gerrit query returned {json_output}')
        return SoongCL.getExistingCL(
            str(json_output[0]['_number']),
            revision,
            version,
            try_resolve_conflict=False)

    @staticmethod
    def _is_trivial_switchover(cl_number: str):
        """Does this change only switch clang version strings?

        Return true if every changed line contains either
        'ClangDefaultShortVersion' or 'ClangDefaultVersion'.
        """
        diff_b64 = gerrit_request(
            f'changes/{cl_number}/revisions/current/patch')
        diff = base64.b64decode(diff_b64).decode('utf-8')

        for line in diff.splitlines():
            if line.startswith('-') or line.startswith('+'):
                if line.startswith('---') or line.startswith('+++'):
                    continue
                if 'ClangDefaultVersion' not in line and \
                    'ClangDefaultShortVersion' not in line:
                    return False
        return True

    @staticmethod
    def _parse_clang_info(cl_number: str):
        """Parse clang info for a CL.

        Unlike prebuilts, the switchover CL may be created manually and the
        commit message may not have the info in a deterministic format.  Use the
        diff to cc/config/global.go to extract this info.
        """
        regex_rev = r'\+\tClangDefaultVersion\s+= "clang-(?P<rev>r\d+)"'
        regex_ver = r'\+\tClangDefaultShortVersion\s+= "(?P<ver>\d\d.\d.\d)"'

        go_file = 'cc/config/global.go'
        diff_b64 = gerrit_request(
            f'changes/{cl_number}/revisions/current/patch?path={go_file}')
        diff = base64.b64decode(diff_b64).decode('utf-8')

        match_rev = re.search(regex_rev, diff)
        match_ver = re.search(regex_ver, diff)
        if match_rev is None or match_ver is None:
            raise RuntimeError(f'Parsing clang info failed for {cl_number}')
        return match_rev.group('rev'), match_ver.group('ver')

    @staticmethod
    def getNewCL(revision, version):
        """Create and upload a build/soong switchover CL."""
        logging.info(f'Uploading new CL for switching to {revision}')
        return SoongCL.uploadCL(revision, version)

    @staticmethod
    def getExistingCL(cl_number,
                      revision=None,
                      version=None,
                      try_resolve_conflict=True):
        """Find/parse build/soong switchover CL info from a gerrit CL."""
        info = gerrit_change_info(cl_number)

        # Validate that the CL is in the correct project and doesn't have merge
        # conflicts.  The CL should not be merged either.
        if info['project'] != SOONG_PROJECT:
            raise RuntimeError(
                f'Switchover CL {cl_number} not in {SOONG_PROJECT}')

        if info['status'] == 'MERGED':
            raise RuntimeError(f'Switchover CL {cl_number} already merged.')

        if revision is None or version is None:
            revision, version = SoongCL._parse_clang_info(cl_number)

        mergeable_info = gerrit_request_json(
            f'changes/{cl_number}/revisions/current/mergeable')
        if not mergeable_info['mergeable']:
            resolvable = SoongCL._is_trivial_switchover(cl_number)
            if resolvable and try_resolve_conflict:
                logging.info(f'Resolving conflicts in {cl_number} for ' +
                             f'switching to {revision}')
                newCL = SoongCL.uploadCL(
                    revision, version, changeId=info['change_id'])
                if newCL.cl_number != cl_number:
                    raise RuntimeError(
                        f'CL number changed from {cl_number} to ' +
                        f'{newCL.cl_number} when resolving conflicts')
                return newCL
            else:
                raise RuntimeError(f'Soong CL {cl_number} has merge conflicts')

        logging.info(f'Using soong CL {cl_number} for switching to {revision}')
        return SoongCL(revision=revision, version=version, cl_number=cl_number)

    def equals(self, other) -> bool:
        return self.revision == other.revision and \
            self.version == other.version and \
            self.cl_number == other.cl_number


class KernelCL(NamedTuple):
    """Gerrit CL info for changing toolchain in kernel/common project."""
    revision: str
    cl_number: str

    @staticmethod
    def getNewCL(revision: str, version: str, kernel_repo_path: str):
        """Upload kernel/common CL to switch clang version."""

        logging.info(f'Uploading Kernel CL to switch to clang-{revision}')
        # Add a random hashtag so we can discover the CL number.
        hashtag = 'chk-' + ''.join(random.sample(string.digits, 8))
        utils.check_call([
            str(test_paths.LLVM_ANDROID_DIR / 'update_kernel_toolchain.py'),
            kernel_repo_path,
            'common',
            'NA',  # no clang_bin.  We're using --clang_revision instead.
            'NA',  # no bug
            f'--clang_version={revision}:{version}',
            f'--hashtag={hashtag}',
            '--no_topic',
            '--wip',
        ])

        json_output = gerrit_query_change(f'hashtag:{hashtag}')
        if len(json_output) != 1:
            raise RuntimeError('Upload failed; or hashtag not unique.  ' +
                               f'Gerrit query returned {json_output}')
        return KernelCL.getExistingCL(str(json_output[0]['_number']))

    @staticmethod
    def getExistingCL(cl_number):
        """Find/parse kernel/common switchover CL info from a gerrit CL."""
        info = gerrit_change_info(cl_number)

        # Validate that the CL is in the correct project and doesn't have merge
        # conflicts.  The CL should not be merged either.
        if info['project'] != KERNEL_COMMON_PROJECT:
            raise RuntimeError(
                f'Switchover CL {cl_number} not in {KERNEL_COMMON_PROJECT}')

        diff_b64 = gerrit_request(
            f'changes/{cl_number}/revisions/current/patch')
        diff = base64.b64decode(diff_b64).decode('utf-8')
        match = re.search('\+.*clang-(?P<rev>r[0-9]+)/bin', diff)
        if not match:
            raise RuntimeError(
                f'Cannot parse clang version from {cl_number}\'s diff: {diff}')
        revision = match.group('rev')

        logging.info(
            f'Using kernel/common CL {cl_number} for switching to {revision}')
        return KernelCL(revision=match.group('rev'), cl_number=cl_number)

    def equals(self, other) -> bool:
        return self.revision == other.revision and \
            self.cl_number == other.cl_number
