#!/bin/bash

DEEPAAS_URL=${DEEPAAS_IP}:${DEEPAAS_PORT}

# Check if we are inside a Nomad job, then replace the URL+PORT with the proper address
if [ -n "$NOMAD_HOST_ADDR_api" ]; then \
    export DEEPAAS_URL=$NOMAD_HOST_ADDR_api; \
fi

# Use the "-u" flag to show Python print in Docker logs
# Use "||[...]" to capture the exit code of timeout (124) and return a success code
timeout $DURATION \
python -u launch.py --api_url http://${DEEPAAS_URL}/ --ui_port $UI_PORT \
|| [[ $? -eq 124 ]]
