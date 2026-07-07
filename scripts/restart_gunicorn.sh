#!/bin/bash
PID=$(pgrep -f "gunicorn.*web-a-inefablestore" | head -1)
if [ -n "$PID" ]; then
    kill -HUP $PID
    echo "Sent HUP to PID $PID"
    sleep 1
else
    echo "No gunicorn process found"
fi
pgrep -f "gunicorn.*web-a-inefablestore" | wc -l
echo "processes running"
