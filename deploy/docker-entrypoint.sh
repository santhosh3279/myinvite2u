#!/bin/sh
set -eu
umask 0002

cd /home/frappe/frappe-bench
mkdir -p sites logs
# Share persistent sites while serving assets baked into this image.
ln -sfnT /home/frappe/frappe-bench/assets sites/assets
exec "$@"
