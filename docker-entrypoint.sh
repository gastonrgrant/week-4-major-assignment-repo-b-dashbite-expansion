#!/bin/sh
set -eu
mkdir -p "${DASHBITE_DATA_ROOT}"
chown -R dashbite:dashbite "${DASHBITE_DATA_ROOT}"
export HOME=/home/dashbite
export USER=dashbite
export LOGNAME=dashbite
# setpriv execs the command. runuser stays in front and kills the session
# before the worker can finish the pass Docker's SIGTERM interrupted.
exec setpriv --reuid=dashbite --regid=dashbite --init-groups -- "$@"
