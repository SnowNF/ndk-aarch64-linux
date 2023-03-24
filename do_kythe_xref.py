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

import logging
import os
import re
import shutil
import sys

import android_version
import builders
import configs
import hosts
import paths
import utils

def build_llvm() -> builders.Stage2Builder:
    host_configs = [configs.host_config()]
    stage2 = builders.Stage2Builder(host_configs)
    stage2.toolchain_name = 'prebuilt'
    stage2.build_name = 'stage2'
    stage2.svn_revision = android_version.get_svn_revision()

    # Differences from production toolchain:
    #   - sources are built directly from toolchain/llvm-project
    #   - built from prebuilt instead of a stage1 toolchain.
    #   - assertions enabled since some code is enabled only with assertions.
    #   - LTO is unnecessary.
    #   - skip lldb since it depends on several other libraries.
    #   - extra targets so we get cross-references for more sources.
    stage2.src_dir = paths.TOOLCHAIN_LLVM_PATH / 'llvm'
    stage2.enable_assertions = True
    stage2.lto = False
    stage2.build_lldb = False
    stage2.ninja_targets = ['all', 'UnitTests']
    stage2.build()
    return stage2

# runextractor is expected to fail on these sources.
EXPECTED_ERROR_DIRS = [
    'out/stage2/tools/clang/tools/extra/clangd/unittests',
    'toolchain/llvm-project/clang-tools-extra/clangd/unittests',
    'toolchain/llvm-project/compiler-rt/lib/scudo/standalone/benchmarks',
    'toolchain/llvm-project/libcxx/benchmarks',
]

def build_kythe_corpus(builder: builders.Stage2Builder) -> None:
    kythe_out_dir = paths.KYTHE_OUTPUT_DIR
    if paths.KYTHE_OUTPUT_DIR.exists():
        shutil.rmtree(paths.KYTHE_OUTPUT_DIR)
    os.makedirs(paths.KYTHE_OUTPUT_DIR)

    json = builder.output_dir / 'compile_commands.json'
    env = {
        'KYTHE_OUTPUT_DIRECTORY': kythe_out_dir,
        'KYTHE_ROOT_DIRECTORY': paths.ANDROID_DIR,
        'KYTHE_CORPUS': 'android.googlesource.com/toolchain/llvm-project//master-legacy',
        'KYTHE_VNAMES': paths.KYTHE_VNAMES_JSON
    }

    # Capture the output of runextractor and validate that it fails in an
    # expected fashion.
    extractor = utils.subprocess_run([str(paths.KYTHE_RUN_EXTRACTOR),
                                      'compdb',
                                      f'-extractor={paths.KYTHE_CXX_EXTRACTOR}',
                                      f'-path={json}'],
                                     env=env,
                                     capture_output=True)

    if extractor.returncode == 0:
        raise RuntimeError('runextractor is expected to fail')

    def get_rel_path(full_path: str) -> str:
        return full_path[len(str(paths.ANDROID_DIR))+1:]

    def in_expected_dir(path: str) -> bool:
        return any(path.startswith(d) for d in EXPECTED_ERROR_DIRS)

    failed_srcs = re.findall('(?P<file>\\S+)\': error running extractor',
                             extractor.stderr)
    srcSet = set(get_rel_path(f) for f in failed_srcs)
    unexpected = [f for f in srcSet if not in_expected_dir(f)]
    if unexpected:
        print(extractor.stderr)
        raise RuntimeError('Runextractor failed on unexpected source' +\
                           f'Unexpected failures: {unexpected}\n')


def package(build_name: str) -> None:
    # Use SHA of toolchain/llvm-project in output file.  Fail build if we cannot
    # find the SHA.
    out_prefix = utils.check_output([
        'git', f'--git-dir={paths.ANDROID_DIR}/toolchain/llvm-project/.git',
        'rev-parse', 'HEAD'
    ]).strip()

    # Build merge_kzips using soong
    utils.check_call(['build/soong/soong_ui.bash',
                      '--build-mode', '--all-modules',
                      f'--dir={paths.ANDROID_DIR}',
                      '-k', 'merge_zips'])
    merge_zips_path = (paths.OUT_DIR / 'host' / hosts.build_host().os_tag /
                       'bin' / 'merge_zips')

    # Call: merge_zips $DIST_DIR/<build_name>.kzip <kzip files>
    output = os.path.join(utils.ORIG_ENV.get('DIST_DIR', paths.OUT_DIR),
                          out_prefix + '.kzip')

    kythe_out_dir = paths.KYTHE_OUTPUT_DIR
    kzip_files = [os.path.join(kythe_out_dir, kzip)
                  for kzip in os.listdir(kythe_out_dir)]

    utils.check_call([str(merge_zips_path), output] + kzip_files)


def main():
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 2:
        print(f'Usage: {sys.argv[0]} BUILD_NAME')
        sys.exit(1)
    build_name = sys.argv[1] if len(sys.argv) == 2 else 'dev'

    if not (paths.ANDROID_DIR / 'build' / 'soong').exists():
        raise RuntimeError('build/soong does not exist.  ' +
                           'Execute this script in master-plus-llvm branch.')

    builder = build_llvm()
    build_kythe_corpus(builder)
    package(build_name)


if __name__ == '__main__':
    main()
