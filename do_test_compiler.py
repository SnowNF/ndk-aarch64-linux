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
# pylint: disable=not-callable, relative-import

import argparse
import logging
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
from typing import Dict, List, Optional

import hosts
import paths
import utils
import version

STDERR_REDIRECT_KEY = 'ANDROID_LLVM_STDERR_REDIRECT'
PREBUILT_COMPILER_PATH_KEY = 'ANDROID_LLVM_PREBUILT_COMPILER_PATH'
DISABLED_WARNINGS_KEY = 'ANDROID_LLVM_FALLBACK_DISABLED_WARNINGS'

# We may introduce some new warnings after rebasing and we need to disable them
# before we fix those warnings.
DISABLED_WARNINGS = [
]


class ProfileHandler(object):

    def getProfileFileEnvVars(self):
        return []

    def mergeProfiles(self):
        return


class PgoProfileHandler(ProfileHandler):

    def __init__(self):
        self.profiles_dir = paths.OUT_DIR / 'clang-profiles'
        self.profiles_format = os.path.join(self.profiles_dir, '%4m.profraw')

    def getProfileFileEnvVars(self):
        return [('LLVM_PROFILE_FILE', self.profiles_format)]

    def mergeProfiles(self):
        stage1_install = paths.OUT_DIR / 'stage1-install'
        profdata_tool = stage1_install / 'bin' / 'llvm-profdata'

        profdata_dir = paths.OUT_DIR
        profdata_filename = paths.pgo_profdata_filename()
        utils.check_call([
            str(profdata_tool), 'merge', '-o',
            str(profdata_dir / profdata_filename),
            str(self.profiles_dir)
        ])

        dist_dir = Path(os.environ.get('DIST_DIR', paths.OUT_DIR))
        utils.check_call([
            'tar', '-cjC',
            str(profdata_dir), profdata_filename, '-f',
            str(dist_dir / paths.pgo_profdata_tarname())
        ])


class BoltProfileHandler(ProfileHandler):

    def __init__(self):
        self.profiles_dir = paths.OUT_DIR / 'bolt-profiles'

    def mergeProfiles(self):
        stage2_install = paths.OUT_DIR / 'stage2-install'
        merge_fdata_tool = stage2_install / 'bin' / 'merge-fdata'

        bolt_collection_path = paths.OUT_DIR / 'bolt_collection'
        clang_fdata_filename = 'clang.fdata'
        clang_fdata_path = bolt_collection_path / clang_fdata_filename
        utils.check_call([
            merge_fdata_tool, '-o', str(clang_fdata_path), str(bolt_collection_path / 'clang')
        ])

        dist_dir = Path(os.environ.get('DIST_DIR', paths.OUT_DIR))
        utils.check_call([
            'tar', '-cjC',
            str(bolt_collection_path), clang_fdata_filename, '-f',
            str(dist_dir / paths.bolt_fdata_tarname())
        ])


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('android_path', help='Android source directory.')
    parser.add_argument(
        '--clang-path',
        nargs='?',
        help='Directory with a previously built Clang.')
    parser.add_argument(
        '--clang-package-path',
        nargs='?',
        help='Directory of a pre-packaged (.tar.bz2) Clang. '
        'Toolchain extracted from the package will be used.')
    parser.add_argument(
        '-k',
        '--keep-going',
        action='store_true',
        default=False,
        help='Keep going when some targets '
        'cannot be built.')
    parser.add_argument(
        '-j',
        action='store',
        dest='jobs',
        type=int,
        default=multiprocessing.cpu_count(),
        help='Number of executed jobs.')
    parser.add_argument(
        '--build-only',
        action='store_true',
        default=False,
        help='Build default targets only.')
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        default=False,
        help='Build with --skip-tests option.')
    parser.add_argument(
        '--flashall-path',
        nargs='?',
        help='Use internal '
        'flashall tool if the path is set.')
    parser.add_argument(
        '-t',
        '--target',
        nargs='?',
        help='Build for specified '
        'target. This will work only when --build-only is '
        'enabled.')
    parser.add_argument(
        '--module',
        action='append',
        help='Build the specified modules, default is dist.')
    parser.add_argument(
        '--with-tidy',
        action='store_true',
        default=False,
        help='Enable clang tidy for Android build.')
    clean_built_target_group = parser.add_mutually_exclusive_group()
    clean_built_target_group.add_argument(
        '--clean-built-target',
        action='store_true',
        default=True,
        help='Clean output for each target that is built.')
    clean_built_target_group.add_argument(
        '--no-clean-built-target',
        action='store_false',
        dest='clean_built_target',
        help='Do not remove target output.')
    fallback_group = parser.add_mutually_exclusive_group()
    fallback_group.add_argument(
        '--enable-fallback',
        action='store_true',
        default=False,
        help='Enable clang wrapper fallback to older prebuilts.')
    fallback_group.add_argument(
        '--disable-fallback',
        action='store_false',
        dest='enable_fallback',
        help='Disable clang wrapper fallback to older prebuilts.')

    profile_generate_group = parser.add_mutually_exclusive_group()
    profile_generate_group.add_argument(
        '--generate-clang-profile',
        action='store_true',
        default=False,
        dest='profile',
        help='Build instrumented compiler and gather profiles')
    profile_generate_group.add_argument(
        '--generate-bolt-profile',
        action='store_true',
        default=False,
        dest='bolt',
        help='Build BOLT instrumented compiler and gather profiles')

    args = parser.parse_args()
    if args.clang_path and args.clang_package_path:
        parser.error('Only one of --clang-path and --clang-package-path must'
                     'be specified')
    if args.build_only and not args.target:
        parser.error('Build target is not specified in build only mode.')

    return args


def link_clang(android_base: Path, clang_path: Path) -> None:
    android_clang_path = (android_base / 'prebuilts' / 'clang' / 'host' /
                          hosts.build_host().os_tag / 'clang-dev')
    if android_clang_path.is_symlink() or android_clang_path.is_file():
        android_clang_path.unlink()
    elif android_clang_path.is_dir():
        shutil.rmtree(android_clang_path)
    android_clang_path.symlink_to(clang_path.resolve())


def get_connected_device_list() -> List[List[str]]:
    try:
        # Get current connected device list.
        out = subprocess.check_output(['adb', 'devices', '-l'], text=True)
        devices = [x.split() for x in out.strip().split('\n')[1:]]
        return devices
    except subprocess.CalledProcessError:
        # If adb is not working properly. Return empty list.
        return []


def rm_current_product_out():
    if 'ANDROID_PRODUCT_OUT' in os.environ:
        product_out = Path(os.environ['ANDROID_PRODUCT_OUT'])
        if product_out.isdir():
            shutil.rmtree(product_out)


def extract_clang_version(clang_install: Path) -> version.Version:
    version_file = (Path(clang_install) / 'include' / 'clang' / 'Basic' /
                    'Version.inc')
    return version.Version(version_file)


def build_target(android_base: Path, clang_version: version.Version,
                 target: str, modules: List[str],
                 max_jobs: int, enable_fallback: bool, with_tidy: bool,
                 profiler: Optional[ProfileHandler]=None) -> None:
    jobs = '-j{}'.format(max(1, min(max_jobs, multiprocessing.cpu_count())))
    try:
        env_out = subprocess.check_output(
            [
                'bash', '-c', '. ./build/envsetup.sh;'
                'lunch ' + target + ' >/dev/null && env'
            ],
            text=True,
            cwd=android_base)
    except subprocess.CalledProcessError:
        raise RuntimeError('Failed to lunch ' + target)

    env: Dict[str, str] = {}
    for line in env_out.splitlines():
        if not line:
            continue
        (key, _, value) = line.partition('=')
        value = value.strip()
        env[key] = value

    # Set ALLOW_NINJA_ENV so that soong propagates environment variables to
    # Ninja.  We use it for disabling warnings in the compiler wrapper and for
    # setting path to write PGO profiles.
    env['ALLOW_NINJA_ENV'] = 'true'

    if enable_fallback:
        redirect_key = STDERR_REDIRECT_KEY
        if 'DIST_DIR' in env:
            redirect_path = Path(env['DIST_DIR']) / 'logs' / 'clang-error.log'
        else:
            redirect_path = (android_base / 'out' / 'clang-error.log').resolve()
            redirect_path.unlink(missing_ok=True)
        env[redirect_key] = str(redirect_path)
        fallback_path = str(paths.CLANG_PREBUILT_DIR / 'bin')
        env[PREBUILT_COMPILER_PATH_KEY] = fallback_path
        env[DISABLED_WARNINGS_KEY] = ' '.join(DISABLED_WARNINGS)

    env['LLVM_PREBUILTS_VERSION'] = 'clang-dev'
    env['LLVM_RELEASE_VERSION'] = clang_version.long_version()
    env['LLVM_NEXT'] = 'true'

    # TODO(b/260809113): Remove this when the bug is fixed
    env['BUILD_BROKEN_DISABLE_BAZEL'] = '1'

    if with_tidy:
        env['WITH_TIDY'] = '1'

    if profiler is not None:
        # lld calls _Exit as a speedup, which prevents it from writing the PGO
        # profiles.
        env['LLD_IN_TEST'] = '1'
        # Build only a subset of targets and collect profiles
        env['CLANG_ANALYZER_CHECKS'] = '1'
        modules = ['libart', 'libc', 'adb-tidy']

        # Set the environment variable specifying where the profile file gets
        # written.
        for key, val in profiler.getProfileFileEnvVars():
            env[key] = val

    modulesList = ' '.join(modules)
    print('Start building target %s and modules %s.' % (target, modulesList))
    subprocess.check_call(
        ['/bin/bash', '-c', 'build/soong/soong_ui.bash --make-mode ' + jobs + \
         ' -k100 ' + modulesList],
        cwd=android_base,
        env=env)


def test_device(android_base: Path, clang_version: version.Version, device: List[str],
                modules: List[str], max_jobs: int, clean_output: str, flashall_path: Optional[Path],
                enable_fallback: bool, with_tidy: bool) -> bool:
    [label, target] = device[-1].split(':')
    # If current device is not connected correctly we will just skip it.
    if label != 'device':
        print('Device %s is not connecting correctly.' % device[0])
        return True
    else:
        target = 'aosp_' + target + '-eng'
    try:
        build_target(android_base, clang_version, target, modules, max_jobs,
                     enable_fallback, with_tidy)
        if flashall_path is None:
            bin_path = (android_base / 'out' / 'host' /
                        hosts.build_host().os_tag / 'bin')
            subprocess.check_call(
                ['./adb', '-s', device[0], 'reboot', 'bootloader'],
                cwd=bin_path)
            subprocess.check_call(
                ['./fastboot', '-s', device[0], 'flashall'], cwd=bin_path)
        else:
            os.environ['ANDROID_SERIAL'] = device[0]
            subprocess.check_call(['./flashall'], cwd=flashall_path)
        result = True
    except subprocess.CalledProcessError:
        print('Flashing/testing android for target %s failed!' % target)
        result = False
    if clean_output:
        rm_current_product_out()
    return result


def extract_packaged_clang(package_path: Path) -> Path:
    # Find package to extract
    tarballs: List[Path] = sorted(package_path.rglob('*-linux-*.tar.bz2'))
    if len(tarballs) != 1:
        raise RuntimeError(
            f'No clang packages (.tar.bz2) found in {package_path}')

    tarball = tarballs[0]

    # Extract package to $OUT_DIR/extracted
    extract_dir = paths.OUT_DIR / 'extracted'
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    args: List[str] = ['tar', '-xjC', str(extract_dir), '-f', str(tarball)]
    subprocess.check_call(args)

    # Find and return a singleton subdir
    extracted: List[Path] = list(extract_dir.iterdir())
    if len(extracted) != 1:
        raise RuntimeError(
            f'Expected one file from package.  Found: {extracted}')

    clang_path = extracted[0]
    if not clang_path.is_dir():
        raise RuntimeError(f'Extracted path is not a dir: {clang_path}')

    return clang_path


def main():
    logging.basicConfig(level=logging.DEBUG)

    args = parse_args()
    modules = ['dist']
    if args.module:
        modules = args.module
    if args.clang_path is not None:
        clang_path = Path(args.clang_path)
    elif args.clang_package_path is not None:
        clang_path = extract_packaged_clang(Path(args.clang_package_path))
    else:
        cmd = [paths.SCRIPTS_DIR / 'build.py', '--no-build=windows,lldb']
        if args.profile:
            cmd.append('--build-instrumented')
            cmd.append('--skip-tests')
        elif args.bolt:
            cmd.append('--pgo')
            cmd.append('--lto')
            cmd.append('--bolt-instrument')
            cmd.append('--no-strip')
            cmd.append('--skip-tests')
        elif args.skip_tests:
            cmd.append('--skip-tests')
        utils.check_call(cmd)
        clang_path = paths.get_package_install_path(hosts.build_host(), 'clang-dev')
    clang_version = extract_clang_version(clang_path)
    link_clang(Path(args.android_path), clang_path)

    if args.build_only:
        if args.profile:
            profiler = PgoProfileHandler()
        elif args.bolt:
            profiler = BoltProfileHandler()
        else:
            profiler = None

        build_target(Path(args.android_path), clang_version, args.target,
                     modules, args.jobs,
                     args.enable_fallback, args.with_tidy, profiler)

        if profiler is not None:
            profiler.mergeProfiles()

    else:
        devices = get_connected_device_list()
        if len(devices) == 0:
            print("You don't have any devices connected.")
        for device in devices:
            result = test_device(Path(args.android_path), clang_version, device,
                                 modules, args.jobs, args.clean_built_target,
                                 Path(args.flashall_path) if args.flashall_path else None,
                                 args.enable_fallback, args.with_tidy)
            if not result and not args.keep_going:
                break


if __name__ == '__main__':
    main()
