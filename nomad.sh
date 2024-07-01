#!/bin/bash
# This is the file that is ran from Nomad, when we launch a "try-it" job from PAPI

DURATION="${DURATION:-10m}"
UI_PORT="${UI_PORT:-8888}"

git clone -b nomad https://github.com/ai4os/deepaas_ui
cd deepaas_ui

#  Defaut installation leads to:
# ```
# ERROR: Cannot uninstall 'blinker'. It is a distutils installed project and
# thus we cannot accurately determine which files belong to it which
# would lead to only a partial uninstall.
# ```
# So we need to add the ignore flag.
# https://stackoverflow.com/questions/53807511/pip-cannot-uninstall-package-it-is-a-distutils-installed-project
pip install -r requirements.txt --ignore-installed blinker

nohup deep-start --deepaas &
# sleep 10s to let `deepaas` start before launching the UI
sleep 10
# Use timeout to automatically kill the job after a given duration
# We capture the timeout exit code (124) to return 0 instead, so that the task does not restart (job_type=batch)
timeout ${DURATION} python launch.py --api_url http://0.0.0.0:5000/ --ui_port ${UI_PORT} || [[ $? -eq 124 ]]
