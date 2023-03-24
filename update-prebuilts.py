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
# pylint: disable=not-callable

"""Update the prebuilt clang from the build server."""

import argparse
import inspect
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import utils

import paths

def logger():
    """Returns the module level logger."""
    return logging.getLogger(__name__)


class ArgParser(argparse.ArgumentParser):
    def __init__(self) -> None:
        super(ArgParser, self).__init__(
            description=inspect.getdoc(sys.modules[__name__]))

        self.add_argument(
            'build', metavar='BUILD',
            help='Build number to pull from the build server.')

        self.add_argument(
            '-b', '--bug', help='Bug to reference in commit message.')

        self.add_argument(
            '-br', '--branch', help='Branch to fetch from (or automatic).')

        self.add_argument(
            '--use-current-branch', action='store_true',
            help='Do not repo start a new branch for the update.')

        self.add_argument(
            '--skip-fetch',
            '-sf',
            action='store_true',
            default=False,
            help='Skip the fetch, and only do the extraction step')

        self.add_argument(
            '--skip-cleanup',
            '-sc',
            action='store_true',
            default=False,
            help='Skip the cleanup, and leave intermediate files')

        self.add_argument(
            '--overwrite', action='store_true',
            help='Remove/overwrite any existing prebuilt directories.')

        self.add_argument(
            '--no-validity-check', action='store_true',
            help='Skip validity checks on the prebuilt binaries.')

        host_choices = ['darwin-x86', 'linux-x86', 'windows-x86']
        self.add_argument(
            '--host', metavar='HOST_OS',
            choices=host_choices,
            help=f'Update prebuilts only for HOST_OS (one of {host_choices}).')

        self.add_argument(
            '--repo-upload', action='store_true',
            help='Upload prebuilts CLs to gerrit using \'repo upload\'')

        self.add_argument(
            '--hashtag', metavar='HASHTAGS',
            help='Extra hashtags (comma separated) during \'repo upload\'')


def fetch_artifact(branch, target, build, pattern):
    fetch_artifact_path = '/google/data/ro/projects/android/fetch_artifact'
    cmd = [fetch_artifact_path, f'--branch={branch}',
           f'--target={target}', f'--bid={build}', pattern]
    utils.check_call(cmd)


def extract_package(package, install_dir, args=[]):
    cmd = ['tar', 'xf', package, '-C', install_dir] + args
    utils.check_call(cmd)


def extract_clang_info(clang_dir):
    version_file_path = os.path.join(clang_dir, 'AndroidVersion.txt')
    with open(version_file_path) as version_file:
        # e.g. for contents: ['7.0.1', 'based on r326829']
        contents = [l.strip() for l in version_file.readlines()]
        version = contents[0]
        revision = contents[1].split()[-1]
        return version, revision


def symlink_to_linux_resource_dir(install_dir):
    # Assume we're in a Darwin (non-linux) prebuilt dir.  Find the Clang version
    # string.  Pick the longest string, if there's more than one.
    version_dirs = os.listdir(os.path.join(install_dir, 'lib', 'clang'))
    if version_dirs:
        version_dirs.sort(key=len)
    version_dir = version_dirs[-1]

    symlink_dir = os.path.join(install_dir, 'lib', 'clang', version_dir,
                               'lib')
    link_src = os.path.join('/'.join(['..'] * 6), 'linux-x86', symlink_dir,
                            'linux')
    link_dst = 'linux'

    # 'cd' to symlink_dir and create a symlink from link_dst to link_src
    prebuilt_dir = os.getcwd()
    os.chdir(symlink_dir)
    os.symlink(link_src, link_dst)
    os.chdir(prebuilt_dir)


def validity_check(host, install_dir, clang_version_major):
    # Make sure the official toolchain (non llvm-next) is built with PGO
    # profiles.
    if host == 'linux-x86':
      realClangPath = os.path.join(install_dir, 'bin', 'clang-' + clang_version_major)
      strings = utils.check_output(['strings', realClangPath])
      llvm_next = strings.find('ANDROID_LLVM_NEXT') != -1

      no_pgo_profile = strings.find('NO PGO PROFILE') != -1
      if no_pgo_profile and not llvm_next:
          logger().error('The Clang binary is not built with PGO profiles.')
          return False

      no_bolt_profile = strings.find('NO BOLT PROFILE') != -1
      if no_bolt_profile and not llvm_next:
          logger().error('The Clang binary is not built with BOLT profiles.')
          return False

    # Check that all the files listed in remote_toolchain_inputs are valid
    if host == 'linux-x86':
      with open(os.path.join(install_dir, 'bin', 'remote_toolchain_inputs')) as inputs_file:
        files = [line.strip() for line in inputs_file.readlines()]
        fail = False
        for f in files:
          if not os.path.exists(os.path.join(install_dir, 'bin', f)):
            logger().error(f'remote_toolchain_inputs malformed, {f} does not exist')
            fail = True
        if fail:
          return False

    return True


def format_bug(bug):
    """Formats a bug for use in a commit message.

    Bugs might be a number, in which case they're a buganizer reference to be
    formatted. If not, assume the user knows what they're doing and just return
    the string as-is.
    """
    if bug.isnumeric():
        return f'http://b/{bug}'
    return bug


def update_clang(host, build_number, use_current_branch, download_dir, bug,
                 manifest, overwrite, do_validity_check, is_testing):
    prebuilt_dir = paths.PREBUILTS_DIR / 'clang' / 'host' / host
    os.chdir(prebuilt_dir)

    if not use_current_branch:
        branch_name = f'update-clang-{build_number}'
        utils.unchecked_call(
            ['repo', 'abandon', branch_name, '.'])
        utils.check_call(
            ['repo', 'start', branch_name, '.'])

    package = f'{download_dir}/clang-{build_number}-{host}.tar.bz2'

    # Handle legacy versions of packages (like those from aosp/llvm-r365631).
    if not os.path.exists(package) and host == 'windows-x86':
        package = f'{download_dir}/clang-{build_number}-windows-x86-64.tar.bz2'
    manifest_file = f'{download_dir}/{manifest}'

    extract_package(package, prebuilt_dir)

    extract_subdir = 'clang-' + build_number
    clang_version, svn_revision = extract_clang_info(extract_subdir)

    # Install into clang-<svn_revision>.  Suffixes ('a', 'b', 'c' etc.), if any,
    # are included in the svn_revision.
    install_subdir = 'clang-' + svn_revision
    install_clang_directory(extract_subdir, install_subdir, overwrite)

    # Linux prebuilts need to include a few libraries from the linux_musl artifacts
    if host == 'linux-x86':
        musl_install_subdir = install_subdir + '/musl'
        musl_package = f'{download_dir}/clang-{build_number}-linux_musl-x86.tar.bz2'
        if os.path.exists(extract_subdir):
            shutil.rmtree(extract_subdir)
        extract_package(musl_package, prebuilt_dir, [
            "--wildcards",
            "*/lib/libclang.so*",
            "*/lib/*/libc++.so*",
            "*/lib/libc_musl.so"])
        install_clang_directory(extract_subdir, musl_install_subdir, overwrite)

        kleaf_parent = pathlib.Path("kleaf") / "parent"
        os.makedirs(kleaf_parent, exist_ok=True)
        try:
            os.unlink(kleaf_parent / install_subdir)
        except FileNotFoundError:
            pass
        os.symlink(
            os.path.relpath(install_subdir, kleaf_parent),
            kleaf_parent / install_subdir)

    # Some platform tests (e.g. system/bt/profile/sdp) build directly with
    # coverage instrumentation and rely on the driver to pick the correct
    # profile runtime.  Symlink the Linux resource dir from the Linux toolchain
    # into the Darwin toolchain so the runtime is found by the Darwin Clang
    # driver.
    if host == 'darwin-x86':
        symlink_to_linux_resource_dir(install_subdir)

    if do_validity_check:
        if not validity_check(host, install_subdir, clang_version.split('.')[0]):
            sys.exit(1)

    shutil.copy(manifest_file, str(prebuilt_dir / install_subdir))

    utils.check_call(['git', 'add', install_subdir])

    # If there is no difference with the new files, we are already done.
    diff = utils.unchecked_call(['git', 'diff', '--cached', '--quiet'])
    if diff == 0:
        logger().info('Bypassed commit with no diff')
        return

    message_lines = [
        f'Update prebuilt Clang to {svn_revision} ({clang_version}).',
        '',
        f'clang {clang_version} (based on {svn_revision}) from build {build_number}.'
    ]
    if is_testing:
        message_lines.append('Note: This prebuilt is from testing branch.')
    if bug is not None:
        message_lines.append('')
        message_lines.append(f'Bug: {format_bug(bug)}')
    message_lines.append('Test: N/A')
    message = '\n'.join(message_lines)
    utils.check_call(['git', 'commit', '-m', message])


def install_clang_directory(extract_subdir: str, install_subdir: str, overwrite: bool):
    if os.path.exists(install_subdir):
        if overwrite:
            logger().info('Removing/overwriting existing path: %s',
                          install_subdir)
            shutil.rmtree(install_subdir)
        else:
            logger().info('Cannot remove/overwrite existing path: %s',
                          install_subdir)
            sys.exit(1)
    os.rename(extract_subdir, install_subdir)


def main():
    args = ArgParser().parse_args()
    logging.basicConfig(level=logging.DEBUG)

    do_fetch = not args.skip_fetch
    do_cleanup = not args.skip_cleanup

    if do_fetch or args.repo_upload:
        utils.check_gcertstatus()

    download_dir = os.path.realpath('.download')
    if do_fetch:
        if os.path.isdir(download_dir):
            shutil.rmtree(download_dir)
        os.makedirs(download_dir)

    os.chdir(download_dir)

    targets_map = {'darwin-x86': 'darwin_mac',
                   'linux-x86': 'linux',
                   'windows-x86': 'windows_x86_64'}
    hosts = [args.host] if args.host else targets_map.keys()
    targets = [targets_map[h] for h  in hosts]
    if 'linux-x86' in hosts:
        targets.append('linux_musl')
    clang_pattern = 'clang-*.tar.bz2'
    manifest = f'manifest_{args.build}.xml'

    branch = args.branch
    if branch is None:
        output = utils.check_output(['/google/data/ro/projects/android/ab',
                                     'get',
                                     '--raw', # prevent color text
                                     '--bid', args.build,
                                     '--target', 'linux'])
        # Example output is:
        #   aosp-llvm-toolchain linux 6732143 complete True
        branch = output.split()[0]

    logger().info('Using branch: %s', branch)
    is_testing = (branch == 'aosp-llvm-toolchain-testing')

    try:
        if do_fetch:
            fetch_artifact(branch, targets[0], args.build, manifest)
            for target in targets:
                fetch_artifact(branch, target, args.build, clang_pattern)

        for host in hosts:
            update_clang(host, args.build, args.use_current_branch,
                         download_dir, args.bug, manifest, args.overwrite,
                         not args.no_validity_check, is_testing)

        if args.repo_upload:
            topic = f'clang-prebuilt-{args.build}'
            if is_testing:
                topic = topic.replace('prebuilt', 'testing-prebuilt')

            for host in hosts:
                utils.prebuilt_repo_upload(host, topic, args.hashtag, is_testing)
    finally:
        if do_cleanup:
            shutil.rmtree(download_dir)

    return 0


if __name__ == '__main__':
    main()
