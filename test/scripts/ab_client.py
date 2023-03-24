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
"""Utility to interact with the Android build API (go/ab)."""

try:
    import apiclient.discovery
    import apiclient.http
    from oauth2client import client as oauth2_client
except ImportError:
    missingImportString = """
  Missing necessary libraries. Try doing the following:
  $ sudo apt-get install python-pip3
  $ sudo pip3 install --upgrade google-api-python-client
  $ sudo pip3 install --upgrade oauth2client
"""
    raise ImportError(missingImportString)

from typing import Tuple, List
import getpass
import io
import logging

from data import WorkNodeRecord, TestResultRecord
import utils

ANDROID_BUILD_API_SCOPE = (
    'https://www.googleapis.com/auth/androidbuild.internal')
ANDROID_BUILD_API_NAME = 'androidbuildinternal'
ANDROID_BUILD_API_VERSION = 'v3'
CHUNK_SIZE = 10 * 1024 * 1024  # 10M


STUBBY_COMMAND_PATH = '/google/data/ro/teams/android-llvm/tests/sso_stubby_cmd.sh'
STUBBY_REQUEST = """
target: {{
  scope: GAIA_USER
  name: "{user}@google.com"
}}
target_credential: {{
  type: OAUTH2_TOKEN
  oauth2_attributes: {{
    scope: '{scope}'
  }}
}}
"""


def _get_oauth2_token():
    request = STUBBY_REQUEST.format(
        user=getpass.getuser(), scope=ANDROID_BUILD_API_SCOPE)
    with open(STUBBY_COMMAND_PATH) as stubby_command_file:
        stubby_command = stubby_command_file.read().strip().split()
    output = utils.check_output(stubby_command, input=request)
    # output is of the format:
    # oauth2_token: "<TOKEN>"
    return output.split('"')[1]


class AndroidBuildClient():
    """Helper class to query the Android build API."""

    def __init__(self):
        creds = oauth2_client.AccessTokenCredentials(
                access_token=_get_oauth2_token(), user_agent='unused/1.0')

        self.client = apiclient.discovery.build(
            ANDROID_BUILD_API_NAME,
            ANDROID_BUILD_API_VERSION,
            credentials=creds,
            discoveryServiceUrl=apiclient.discovery.DISCOVERY_URI,
            cache_discovery=False)

    @staticmethod
    def _worknode_parse_general(workNodeData):
        if 'isFinal' not in workNodeData:
            return False, 'Error: isFinal field not present'
        isFinal = workNodeData['isFinal']
        if not isinstance(isFinal, bool):
            return False, 'Error: isFinal expected to be a bool'
        if not isFinal:
            return False, 'incomplete'

        return True, workNodeData['workExecutorType']

    def get_worknode_status(self, forrest_invocation_id: str,
                            tag: str) -> Tuple[bool, List[TestResultRecord]]:
        """Return completion status and results from a Forrest invocation."""
        resultStr = lambda res: 'passed' if res else 'failed'

        request = self.client.worknode().list(workPlanId=forrest_invocation_id)
        response = request.execute()

        results = []
        workDone = False
        for worknode in response['workNodes']:
            ok, msg = AndroidBuildClient._worknode_parse_general(worknode)
            if not ok:
                if msg != 'incomplete':
                    logging.warning(f'Parsing worknode failed: {msg}\n' +
                                    str(worknode))
                continue

            if msg == 'trybotFinished':
                # Status of trybotFinished worknode tells if work for an
                # invocation is completed.
                workDone = worknode['status'] == 'complete'
                continue
            if msg == 'forrestRun':
                # Book keeping about a forrest invocation.  Safe to ignore.
                continue

            workOutput = worknode.get('workOutput', None)
            success = workOutput and workOutput['success']
            if msg == 'pendingChangeBuild':
                work_type = 'BUILD'
                params = worknode['workParameters']['submitQueue']

                # If workOutput is absent, Try to get build Id from
                # workParameters.
                if workOutput:
                    build_id = workOutput['buildOutput']['buildId']
                elif 'buildIds' in worknode['workParameters']['submitQueue']:
                    # Just pick the first build Id.
                    build_id = worknode['workParameters']['submitQueue'][
                        'buildIds'][0]
                else:
                    build_id = 'NA'
                test_name = 'NA'
                ants_id = 'NA'
                display_message = 'NA'
            elif msg == 'atpTest':
                work_type = 'TEST'
                params = worknode['workParameters']['atpTestParameters']
                build_id, ants_id, display_message = 'NA', 'NA', 'NA'
                # workOutput may not be available if the test did not run due to
                # build failure
                if workOutput:
                    if 'testOutput' in workOutput:
                        build_id = workOutput['testOutput']['buildId']
                        ants_id = workOutput['testOutput']['antsInvocationId']
                    display_message = workOutput.get('displayMessage', 'NA')
                test_name = params['testName']
            else:
                raise RuntimeError(f'Unexpected workExecutorType {msg} with ' +
                                   f'worknode data:\n{worknode}')

            branch = params['branch']
            target = params['target']

            results.append(
                TestResultRecord(
                    tag=tag,
                    worknode_id=worknode['id'],
                    work_type=work_type,
                    branch=branch,
                    target=target,
                    build_id=build_id,
                    result=resultStr(success),
                    test_name=test_name,
                    ants_invocation_id=ants_id,
                    display_message=display_message))

        return workDone, results

    def get_artifact(self, buildId: str, target: str, resource: str) -> bytes:
        """Download an artifact from the buildbot."""
        request = self.client.buildartifact().get_media(
            buildId=buildId,
            target=target,
            attemptId='latest',
            resourceId=resource)

        stream = io.BytesIO()
        try:
            downloader = apiclient.http.MediaIoBaseDownload(
                stream, request, chunksize=CHUNK_SIZE)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        except apiclient.errors.HttpError as e:
            logging.error(f'Download failed: {resource} for {buildId}:{target}')
            return None
        return stream.getvalue()
