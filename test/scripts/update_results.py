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
"""Monitor forrest runs and update status of completed runs."""

import logging
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from data import CNSData
import ab_client
import utils


def main():
    logging.basicConfig(level=logging.INFO)
    utils.check_gcertstatus()

    if len(sys.argv) > 1:
        print(f'{sys.argv[0]} doesn\'t accept any arguments')
        sys.exit(1)

    CNSData.loadCNSData()
    build_client = ab_client.AndroidBuildClient()

    completed = list()
    for pending in CNSData.PendingWorkNodes.records:
        inv = pending.invocation_id
        # Remove the pending record if it already exists in CNSData.Forrest or
        # if its invocation has finished execution.
        complete = CNSData.CompletedWorkNodes.findByInvocation(inv)

        if not complete:
            complete, results = build_client.get_worknode_status(
                inv, pending.tag)
            for result in results:
                CNSData.TestResults.addResult(result, writeBack=False)

        if complete:
            completed.append(pending)

    for record in completed:
        CNSData.CompletedWorkNodes.addInvocation(record, writeBack=False)
        CNSData.PendingWorkNodes.remove(record, writeBack=False)

    CNSData.TestResults.write()
    CNSData.CompletedWorkNodes.write()
    CNSData.PendingWorkNodes.write()


if __name__ == '__main__':
    main()
