#!/bin/bash
PID=$(pgrep -f 'gunicorn.*connection-api' | head -1)
if [ -n "$PID" ]; then
    kill -HUP $PID
    echo "HUP sent to PID $PID"
    sleep 2
else
    echo "No gunicorn connection-api process found"
fi
ss -tlnp | grep ':5004'
echo "---done---"
