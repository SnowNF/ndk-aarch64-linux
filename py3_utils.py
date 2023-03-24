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
"""Starts a script with prebuilt python3."""

import os
import subprocess
import sys

THIS_DIR = os.path.realpath(os.path.dirname(__file__))
def get_host_tag():
    if sys.platform.startswith('linux'):
        return 'linux-x86'
    if sys.platform.startswith('darwin'):
        return 'darwin-x86'
    raise RuntimeError('Unsupported host: {}'.format(sys.platform))


def run_with_py3(script_name):
    python_bin = os.path.join(THIS_DIR, '..', '..', 'prebuilts', 'build-tools',
                              'path', get_host_tag(), 'python3')
    python_bin = os.path.abspath(python_bin)
    subprocess.check_call(
        [python_bin, os.path.join(THIS_DIR, script_name)] + sys.argv[1:])
