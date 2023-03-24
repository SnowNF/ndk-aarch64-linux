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
"""A class to represent clang version."""

from pathlib import Path
import re

class Version():
    """Parse and save clang version from version file."""

    def __init__(self, version_file: Path) -> None:
        self._parse_version_file(version_file)

    @staticmethod
    def _parse(text: str, key: str) -> str:
        return re.findall(rf'{key}\s+(\d+)', text)[0]

    def _parse_version_file(self, version_file: Path) -> None:
        with version_file.open() as vfile:
            text = vfile.read()
        self.major = self._parse(text, 'CLANG_VERSION_MAJOR')
        self.minor = self._parse(text, 'CLANG_VERSION_MINOR')
        self.patch = self._parse(text, 'CLANG_VERSION_PATCHLEVEL')

    def long_version(self) -> str:
        """Returns a long version including major, minor and patch level."""
        return '.'.join([self.major, self.minor, self.patch])

    def short_version(self) -> str:
        """Returns a short version including major and minor."""
        return '.'.join([self.major, self.minor])

    def major_version(self) -> str:
        """Returns only the major version."""
        return str(self.major)
