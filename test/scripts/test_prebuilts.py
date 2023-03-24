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
"""Test Clang prebuilts on Android"""

from typing import List, NamedTuple, Optional, Set, Tuple
import argparse
import inspect
import logging
import pathlib
import sys
import yaml

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from data import CNSData, KernelCLRecord, PrebuiltCLRecord, SoongCLRecord, WorkNodeRecord
import forrest
import gerrit
import test_paths
import utils

CODE_NAMES = [
    'RELEASE_BRANCH_1', 'RELEASE_BRANCH_2', 'RELEASE_BRANCH_3',
    'DEVICE_TARGET_1'
]


class TestConfig(NamedTuple):
    branch_private: str  # use branch property instead
    target_private: str  # use branch property instead
    groups: List[str]
    tests: List[str]

    def __str__(self):
        return f'{self.branch}:{self.target}'

    @property
    def branch(self):
        if self.branch_private in CODE_NAMES:
            return test_paths.internal_names()[self.branch_private]
        return self.branch_private

    @property
    def target(self):
        if self.target_private in CODE_NAMES:
            return test_paths.internal_names()[self.target_private]
        return self.target_private

    @property
    def is_kernel_branch(self):
        return self.branch.startswith('aosp_kernel')


def _load_configs() -> List[TestConfig]:
    with open(test_paths.CONFIGS_YAML) as infile:
        configs = yaml.safe_load(infile)
    result = []
    for branch, targets in configs.items():
        for target, target_config in targets.items():
            if target_config:
                # groups and tests can be empty.
                groups = target_config.get('groups', '').split()
                tests = target_config.get('tests', list())
            else:
                groups, tests = list(), list()
            result.append(
                TestConfig(
                    branch_private=branch,
                    target_private=target,
                    groups=groups,
                    tests=tests))

    return result


def _find_groups(all_configs: List[TestConfig]) -> Set[str]:
    groups = set()
    for config in all_configs:
        groups.update(config.groups)
    return groups


TEST_CONFIGS = _load_configs()
TEST_GROUPS = _find_groups(TEST_CONFIGS)


class ToolchainBuild(NamedTuple):
    """Record of a toolchain build."""
    build_number: str
    branch: str


def get_toolchain_build(build) -> ToolchainBuild:
    """Return ToolchainBuild record for a build."""
    toolchain_branches = ('aosp-llvm-toolchain', 'aosp-llvm-toolchain-testing')
    output = utils.check_output([
        '/google/data/ro/projects/android/ab',
        'get',
        '--raw',  # prevent color text
        f'--bid={build}',
        '--target=linux'
    ])
    # Example output is:
    #   aosp-llvm-toolchain linux 6732143 complete True
    branch, _, _, complete, success = output.split()
    is_testable = branch in toolchain_branches and complete == 'complete' and \
                  success == 'True'
    if not is_testable:
        raise RuntimeError(f'Build {build} is not testable.  '
                           f'Build info is {output}')
    return ToolchainBuild(build, branch)


def do_prechecks():
    # ensure build/soong is present.
    # TODO(pirama) build/soong is only necessary if we're uploading a new CL.
    # Consider moving this deeper.
    if not (test_paths.ANDROID_DIR / 'build' / 'soong').exists():
        raise RuntimeError('build/soong does not exist.  ' +\
                           'Execute this script in master-plus-llvm branch.')

    utils.check_gcertstatus()


def prepareCLs(args):
    """Prepare CLs for testing.

    Upload new CLs to gerrit if matching CLs not found in CNS data.
    """
    build = get_toolchain_build(args.build)

    prebuiltCL = getPrebuiltCL(build, args.prebuilt_cl)
    cls = {'prebuiltsCL': prebuiltCL}

    if TestKindConfig.platform:
        cls['soongCL'] = getSoongCL(prebuiltCL.revision, prebuiltCL.version,
                                    args.soong_cl)
    if TestKindConfig.kernel:
        cls['kernelCL'] = getKernelCL(prebuiltCL.revision, prebuiltCL.version,
                                      args.kernel_cl, args.kernel_repo_path)

    return cls


def getPrebuiltCL(build: ToolchainBuild,
                  cl_number: Optional[str]) -> gerrit.PrebuiltCL:
    """Get clang prebuilts CL for testing.

    Upload new CLs to gerrit if matching CLs not found in CNS data.
    """
    prebuiltRow = CNSData.Prebuilts.getPrebuilt(build.build_number, cl_number)
    if prebuiltRow:
        prebuiltCL = gerrit.PrebuiltCL.getExistingCL(prebuiltRow.cl_number)
        if not prebuiltCL.equals(prebuiltRow):
            raise RuntimeError('Mismatch between CSV Data and Gerrit CL. \n' +
                               f'  {prebuiltRow}\n  {prebuiltCL}')
    else:
        # Prebuilt record not found.  Create record (from cl_number or new
        # prebuilts) and update records.
        if cl_number:
            prebuiltCL = gerrit.PrebuiltCL.getExistingCL(cl_number)
            if prebuiltCL.build_number != build.build_number:
                raise RuntimeError(
                    f'Input CL {cl_number} does not correspond to build {build}'
                )
        else:
            prebuiltCL = gerrit.PrebuiltCL.getNewCL(build.build_number,
                                                    build.branch)
        is_llvm_next = build.branch == 'aosp-llvm-toolchain-testing'
        prebuiltRow = PrebuiltCLRecord(
            revision=prebuiltCL.revision,
            version=prebuiltCL.version,
            build_number=prebuiltCL.build_number,
            cl_number=prebuiltCL.cl_number,
            is_llvm_next=str(is_llvm_next))
        CNSData.Prebuilts.addPrebuilt(prebuiltRow)
    return prebuiltCL


def getSoongCL(revision: str, version: str,
               cl_number: Optional[str]) -> gerrit.SoongCL:
    """Get build/soong switchover CL for testing.

    Upload new CLs to gerrit if matching CLs not found in CNS data.
    """
    soongRow = CNSData.SoongCLs.getCL(revision, version, cl_number)
    if soongRow:
        soongCL = gerrit.SoongCL.getExistingCL(soongRow.cl_number)
        if not soongCL.equals(soongRow):
            raise RuntimeError('Mismatch between CSV Data and Gerrit CL. \n' +
                               f'  {soongRow}\n  {soongCL}')
    else:
        # Soong CL record not found.  Create record (from cl_number or new
        # switchover change) and update records.
        if cl_number:
            soongCL = gerrit.SoongCL.getExistingCL(cl_number)
        else:
            soongCL = gerrit.SoongCL.getNewCL(revision, version)
        if soongCL.revision != revision or soongCL.version != version:
            raise RuntimeError(f'Clang version mismatch: \n  {soongCL}\n' +
                               f'Requested: {revision} ({version})')
        soongRow = SoongCLRecord(
            version=soongCL.version,
            revision=soongCL.revision,
            cl_number=soongCL.cl_number)
        CNSData.SoongCLs.addCL(soongRow)
    return soongCL


def getKernelCL(revision: str, version: str, cl_number: Optional[str],
                kernel_repo_path: Optional[str]) -> gerrit.KernelCL:
    """Get kernel/common switchover CL for testing.

    Upload new CLs to gerrit if matching CLs not found in CNS data.
    """
    kernelRow = CNSData.KernelCLs.getCL(revision, cl_number)
    if kernelRow:
        kernelCL = gerrit.KernelCL.getExistingCL(kernelRow.cl_number)
        if not kernelCL.equals(kernelRow):
            raise RuntimeError('Mismatch between CSV Data and Gerrit CL. \n' +
                               f'  {kernelRow}\n  {kernelCL}')
    else:
        # Kernel CL record not found.  Create record (cl_number or new
        # switchover change) and update records.
        if cl_number:
            kernelCL = gerrit.KernelCL.getExistingCL(cl_number)
        else:
            if not kernel_repo_path:
                raise RuntimeError(
                    'Kernel switchover CL not found in CNS or not provided ' +
                    'in command line.  Provide a path to kernel repo using ' +
                    '--kernel_repo_path to upload a new switchover CL.')
            kernelCL = gerrit.KernelCL.getNewCL(revision, version,
                                                kernel_repo_path)
        if kernelCL.revision != revision:
            raise RuntimeError(f'Clang version mismatch:\n  {kernelCL}\n' +
                               f'  Requested: {revision}')
        kernelRow = KernelCLRecord(
            revision=kernelCL.revision, cl_number=kernelCL.cl_number)
        CNSData.KernelCLs.addCL(kernelRow)
    return kernelCL


def evaluateConfig(retry_policy: str, build: str, tag: str, branch: str,
                   target: str, tests: List[str]) -> str:
    pending_row = CNSData.PendingWorkNodes.find(build, tag, branch, target)
    completed_row = CNSData.CompletedWorkNodes.find(build, tag, branch, target)

    if not (pending_row or completed_row):
        # No previously-scheduled run - We should schedule.
        return 'run'
    if not retry_policy or retry_policy == 'none':
        # Previously scheduled run and no retry policy.  We should skip.
        return 'skip'

    result_records = []
    if retry_policy == 'failed':
        node_id = pending_row.invocation_id if pending_row else completed_row.invocation_id
        result_records = CNSData.TestResults.getResultsForWorkNode(node_id)

        all_pass = True
        for record in result_records:
            if record.result == 'failed':
                all_pass = False
        if all_pass:
            # All tests passed - no need to retry.
            return 'skip'

    # either retry_policy == 'all' or we have a failed run.  Delete data and
    # retry.
    if pending_row:
        CNSData.PendingWorkNodes.remove(pending_row)
    if completed_row:
        CNSData.CompletedWorkNodes.remove(completed_row)
    for record in result_records:
        CNSData.TestResults.remove(record)
    return 'retry'


def invokeForrestRuns(cls, args):
    """Submit builds/tests to Forrest for provided CLs and args."""
    build, tag = args.build, args.tag

    to_run = set(args.groups) if args.groups else set()

    def _should_run(config):
        # Do not run test if this config is disabled in TestKindConfig.
        if config.is_kernel_branch:
            testKindFlag = TestKindConfig.kernel
        else:
            testKindFlag = TestKindConfig.platform
        if not testKindFlag:
            return False

        if not to_run:
            # if args.groups is empty, run all tests (note: some tests may not
            # be part of any group.)
            return True

        # Run test if it is a part of a group specified in args.groups
        return any(g in to_run for g in config.groups)

    def _get_cl_numbers(config):
        cl_numbers = []
        if not cls['prebuiltsCL'].merged:
            cl_numbers.append(cls['prebuiltsCL'].cl_number)
        if config.is_kernel_branch:
            cl_numbers.append(cls['kernelCL'].cl_number)
        else:
            cl_numbers.append(cls['soongCL'].cl_number)
            if args.extra_cls_platform:
                cl_numbers.extend(args.extra_cls_platform)
        return cl_numbers

    for config in TEST_CONFIGS:
        if not _should_run(config):
            logging.info(f'Skipping disabled config {config}')
            continue
        cl_numbers = _get_cl_numbers(config)

        branch = config.branch
        target = config.target
        tests = config.tests

        evaluation = evaluateConfig(args.retry_policy, build, tag, branch,
                                    target, tests)
        if evaluation == 'skip':
            logging.info(f'Skipping previously-scheduled config {config}')
            continue
        if evaluation == 'retry':
            logging.info(
                f'Retrying {config} based on retry policy \'{args.retry_policy}\''
            )

        invocation_id = forrest.invokeForrestRun(branch, target, cl_numbers,
                                                 tests, args.tag)
        logging.info(f'Submitted {config} to forrest: {invocation_id}')
        record = WorkNodeRecord(
            prebuilt_build_number=build,
            invocation_id=invocation_id,
            tag=tag,
            branch=branch,
            target=target)
        CNSData.PendingWorkNodes.addInvocation(record)


def parse_args():
    parser = argparse.ArgumentParser(
        description=inspect.getdoc(sys.modules[__name__]))

    parser.add_argument(
        '--build', help='Toolchain build number (from go/ab/).', required=True)
    parser.add_argument(
        '--prebuilt_cl',
        help='Prebuilts CL (to prebuilts/clang/host/linux-x86)')
    parser.add_argument(
        '--soong_cl', help='build/soong/ CL to switch compiler version')
    parser.add_argument(
        '--kernel_cl', help='kernel/common CL to switch compiler version')
    parser.add_argument(
        '--prepare-only',
        action='store_true',
        help='Prepare/validate CLs.  Don\'t initiate tests')
    parser.add_argument(
        '--tag',
        help=('Tag to group Forrest invocations for this test ' +
              '(and avoid duplicate submissions).'))
    parser.add_argument(
        '--groups',
        metavar='GROUP',
        choices=TEST_GROUPS,
        nargs='+',
        action='extend',
        help=f'Run tests from specified groups.  Choices: {TEST_GROUPS}')
    test_kind_choices = ['platform', 'kernel']
    parser.add_argument(
        '--test_kind',
        metavar='KIND',
        choices=test_kind_choices,
        nargs='+',
        action='extend',
        help=('Prepare CLs and run tests for specified test kinds.  ' +
              'Omit this parameter to run all test kinds.  ' +
              f'Choices: {test_kind_choices}'))
    parser.add_argument(
        '--kernel_repo_path',
        help='Kernel tree to use when uploading switcover CLs')
    parser.add_argument(
        '--extra_cls_platform',
        metavar='CL_NUMBER',
        nargs='+',
        action='extend',
        help='Additional CLs to include for platform tests')
    parser.add_argument(
        '--retry-policy',
        choices=('none', 'failed', 'all'),
        help='Specify which tests with a given tag to retry')
    parser.add_argument(
        '--verbose', '-v', action='store_true', help='Print verbose output')

    args = parser.parse_args()
    if not args.prepare_only and not args.tag:
        raise RuntimeError('Provide a --tag argument for Forrest invocations' +
                           ' or use --prepare-only to only prepare Gerrit CLs.')
    if not args.test_kind:
        args.test_kind = test_kind_choices

    return args


class TestKindConfig():
    platform: bool = False
    kernel: bool = False


def main():
    args = parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level)
    do_prechecks()

    CNSData.loadCNSData()

    TestKindConfig.platform = 'platform' in args.test_kind
    TestKindConfig.kernel = 'kernel' in args.test_kind

    cls = prepareCLs(args)
    if args.prepare_only:
        return

    invokeForrestRuns(cls, args)


if __name__ == '__main__':
    main()
