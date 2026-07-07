#!/bin/bash
pkill -9 -f connection_api:connection_app 2>/dev/null
sleep 1
cd /home/apps/web-b-revendedores
source venv/bin/activate
set -a
source .env
set +a
echo KEY=$WEBB_API_KEY
echo DB=$DATABASE_PATH
gunicorn -w 2 -b 127.0.0.1:5004 connection_api:connection_app --name connection-api --error-logfile /var/log/gunicorn-connection-error.log --access-logfile /var/log/gunicorn-connection-access.log --pid /var/run/gunicorn-connection.pid --daemon
echo started
