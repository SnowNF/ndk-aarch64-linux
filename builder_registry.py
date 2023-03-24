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
"""A class to manage existing builders, so that they are discoverable."""

import logging
from typing import Callable, Dict, List, Iterable


def logger():
    """Returns the module level logger."""
    return logging.getLogger(__name__)


class BuilderRegistry:
    """A class to manage existing builders, so that they are discoverable."""
    _builders: Dict[str, object] = dict()

    # A lambda to decide whether we should build or skip a builder."""
    _filters: List[Callable[[str], bool]] = []

    @classmethod
    def add_filter(cls, new_filter: Callable[[str], bool]) -> None:
        """Adds a filter function. A target will be built if all filters return true."""
        cls._filters.append(new_filter)

    @classmethod
    def add_builds(cls, builds: Iterable[str]) -> None:
        """Adds a filter to only allow listed targets."""
        build_set = set(builds)
        cls.add_filter(lambda name: name in build_set)

    @classmethod
    def add_skips(cls, skips: Iterable[str]) -> None:
        """Adds a filter to not allow listed targets."""
        skip_set = set(skips)
        cls.add_filter(lambda name: name not in skip_set)

    @classmethod
    def should_build(cls, name: str) -> bool:
        """Tests whether we will build a target."""
        for filter_func in cls._filters:
            if not filter_func(name):
                return False
        return True

    @classmethod
    def register_and_build(cls, function):
        """A decorator to wrap a build() method for a Builder."""
        def wrapper(builder, *args, **kwargs) -> None:
            name = builder.name
            cls._builders[name] = builder
            if cls.should_build(name):
                logger().info("Building %s.", name)
                function(builder, *args, **kwargs)
            else:
                logger().info("Skipping %s.", name)
        return wrapper
