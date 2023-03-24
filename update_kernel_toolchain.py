#!/usr/bin/env python3
#
# Copyright (C) 2019 The Android Open Source Project
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
# pylint: disable=not-callable, relative-import, line-too-long, no-else-return

import argparse
import fileinput
import os.path as path
import re
import subprocess
import xml.etree.ElementTree as ET


def green_print(to_print):
    print("\033[92m" + to_print + "\033[0m")


def is_clang_project(element):
    return element.tag == "project" and \
           element.get("path") == "prebuilts-master/clang/host/linux-x86"


class KernelToolchainUpdater():

    def __init__(self):
        self.parse_args()
        if self.clang_version_arg:
            self.clang_revision, self.clang_version = self.clang_version_arg.split(':')
        else:
            self.get_clang_versions()

        self.kernel_dir = path.normpath(path.join(self.repo_checkout, self.kernel_relpath))
        self.repo_dir = path.join(self.repo_checkout, ".repo", "manifests")
        self.topic = path.basename(self.repo_checkout) + "_" + self.clang_revision

        if path.basename(self.kernel_dir) != 'common':
            self.resync_tree()
            self.get_clang_sha()
            self.update_sha()
            self.commit_sha()
            self.push_manifest_change()

        self.resync_tree()
        self.update_kernel_toolchain()
        self.commit_kernel_toolchain()
        self.push_kernel_change()

    def parse_args(self):
        parser = argparse.ArgumentParser()
        # TODO: some validation of the command line args would be nice.
        parser.add_argument(
            "repo_checkout",
            help="Source directory of the repo checkout of the kernel.")
        parser.add_argument(
            "kernel_relpath",
            help="Path relative to repo checkout containing kernel source tree.")
        parser.add_argument(
            "clang_bin", help="Path to the new clang binary in AOSP.")
        parser.add_argument(
            "bug_number",
            help="The bug number to be included in the commit message.")
        parser.add_argument(
            "-d", action="store_true", help="Dry run and debug.")
        parser.add_argument(
            "-n", action="store_true", help="No push (but do local changes)")
        parser.add_argument(
            "--no_topic",
            action="store_true",
            help="Do not set topic on uploaded changes.")
        parser.add_argument(
            "--wip",
            action="store_true",
            help="Mark change as WIP.")
        parser.add_argument(
            "--hashtag",
            metavar="HASHTAG",
            help="Hashtags (comma-separated) to apply to pushed changes.")
        parser.add_argument(
            "--clang_version",
            metavar="REVISION:VERSION",
            help="REVISION (e.g. r1234) and VERSION (e.g. 10.0.0) to use " +\
                 "instead of fetching this from clang_bin.")
        args = parser.parse_args()
        self.bug_number = args.bug_number
        self.clang_bin = args.clang_bin
        self.repo_checkout = args.repo_checkout
        self.kernel_relpath = args.kernel_relpath
        self.dry_run = args.d
        self.no_push = args.n
        self.no_topic = args.no_topic
        self.wip = args.wip
        self.hashtag = args.hashtag
        self.clang_version_arg = args.clang_version

    def get_clang_versions(self):
        output = subprocess.check_output([self.clang_bin, "--version"]).decode("utf-8")
        self.clang_revision = re.search("based on (r[0-9]+[a-z]?)",
                                        output).groups()[0]
        self.clang_version = re.search("clang version ([0-9\.]+)",
                                       output).groups()[0]

    def get_clang_sha(self):
        clang_dir = path.dirname(self.clang_bin)
        output = subprocess.check_output(
            ["git", "--no-pager", "log", "-n", "1"], cwd=clang_dir).decode("utf-8")
        self.clang_sha = re.search("commit ([0-9a-z]+)", output).groups()[0]

    def update_sha(self):
        green_print("Updating SHA")
        xml_path = path.join(self.repo_dir, "default.xml")
        if self.dry_run:
            print("Updating %s to use\n%s." % (xml_path, self.clang_sha))
            return
        # It would be great to just use the builtin XML serializer/deserializer
        # in a sane way; unfortunately this will end up reformatting
        # indentation and reordering element attributes.
        for line in fileinput.input(xml_path, inplace=True):
            try:
                element = ET.fromstring(line)
                if is_clang_project(element):
                    line = re.sub("revision=\"[0-9a-z]+\"",
                                  "revision=\"%s\"" % self.clang_sha, line)
            except ET.ParseError:
                pass
            finally:
                print(line, end="")

    def commit_sha(self):
        green_print("Committing SHA")
        message = """
Update Clang to %s based on %s

Bug: %s
""".strip() % (self.clang_version, self.clang_revision, self.bug_number)
        command = "git commit -asm"
        if self.dry_run:
            print(command + " \"" + message + "\"")
            return
        subprocess.check_output(
            command.split(" ") + [message], cwd=self.repo_dir)

    def push_manifest_change(self):
        green_print("Pushing manifest change")
        output = subprocess.check_output(["repo", "--no-pager", "info"],
                                         cwd=self.repo_dir).decode("utf-8")
        repo_branch = output.split("\n")[1].split(" ")[3].split("/")[2]
        command = "git push origin HEAD:refs/for/" + repo_branch

        if self.wip:
            command += '%wip' # note: no preceding space needed here.
        if not self.no_topic:
            command += " -o topic=" + self.topic
        if self.hashtag:
            command += " -o hashtag=" + self.hashtag
        if self.dry_run or self.no_push:
            print(command)
            return
        subprocess.check_output(command.split(" "), cwd=self.repo_dir)

    def resync_tree(self):
        green_print("Syncing kernel tree")
        command = "repo sync -c --no-tags -q -n -j 71"
        if self.dry_run:
            print(command)
            return
        subprocess.check_output(command.split(" "), cwd=self.repo_dir)

    def update_kernel_toolchain(self):
        green_print("Updating kernel toolchain")
        config_path = path.join(self.kernel_dir, "build.config.constants")
        if self.dry_run:
            print("Updating %s to use %s." % (config_path, self.clang_revision))
            return
        for line in fileinput.input(config_path, inplace=True):
            line = re.sub("CLANG_VERSION=r[0-9a-z]+",
                          "CLANG_VERSION=" + self.clang_revision, line)
            print(line, end="")

    def commit_kernel_toolchain(self):
        green_print("Committing kernel toolchain")
        message = """
ANDROID: clang: update to %s

Bug: %s
""".strip() % (self.clang_version, self.bug_number)
        command = "git commit -asm"
        if self.dry_run:
            print(command + " \"" + message + "\"")
            return
        # TODO: it might be nice to `git checkout -b <topic>` before committing.
        subprocess.check_output(
            command.split(" ") + [message], cwd=self.kernel_dir)

    def push_kernel_change(self):
        green_print("Pushing kernel change")
        xml_path = path.join(self.repo_dir, "default.xml")
        remote = subprocess.check_output(["git", "--no-pager", "remote"],
                                         cwd=self.kernel_dir).decode("utf-8").strip()
        for project in ET.parse(xml_path).iter("project"):
            if (project.get("path") == self.kernel_relpath):
                command = "git push %s HEAD:refs/for/%s" % (
                        remote, project.get("revision"))
                if self.wip:
                    command += '%wip' # note: no preceding space needed here.
                if not self.no_topic:
                    command += " -o topic=" + self.topic
                if self.hashtag:
                    command += " -o hashtag=" + self.hashtag
                if self.dry_run or self.no_push:
                    print(command)
                    return
                subprocess.check_output(command.split(" "), cwd=self.kernel_dir)
                break


if __name__ == "__main__":
    KernelToolchainUpdater()
