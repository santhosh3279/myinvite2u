# syntax=docker/dockerfile:1
ARG FRAPPE_VERSION=version-16
FROM frappe/build:${FRAPPE_VERSION} AS builder

ARG FRAPPE_BRANCH=version-16
USER frappe
WORKDIR /home/frappe
RUN bench init --frappe-branch="${FRAPPE_BRANCH}" \
    --no-procfile --no-backups --skip-redis-config-generation --skip-assets \
    /home/frappe/frappe-bench

WORKDIR /home/frappe/frappe-bench
# Build the exact checkout, including pull request changes.
COPY --chown=frappe:0 . apps/invite
ENV CI=1
RUN env/bin/pip install --no-cache-dir -e apps/invite \
    && printf 'frappe\ninvite\n' > sites/apps.txt \
    && cd apps/invite && yarn install --frozen-lockfile
RUN bench build --production
RUN test -f apps/invite/invite/www/invite.html \
    && test -d apps/invite/invite/public/frontend \
    && printf '{}\n' > sites/common_site_config.json \
    && find apps -type d -name .git -prune -exec rm -rf '{}' +

FROM frappe/base:${FRAPPE_VERSION} AS runtime
USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --from=builder --chown=frappe:0 /home/frappe/frappe-bench /home/frappe/frappe-bench
RUN mv sites/assets assets && chmod -R g=u sites logs
COPY --chown=frappe:0 --chmod=755 deploy/docker-entrypoint.sh /usr/local/bin/invite-entrypoint.sh
EXPOSE 8000 8080 9000
VOLUME ["/home/frappe/frappe-bench/sites", "/home/frappe/frappe-bench/logs"]
ENTRYPOINT ["invite-entrypoint.sh"]
CMD ["/home/frappe/frappe-bench/env/bin/gunicorn", "--chdir=/home/frappe/frappe-bench/sites", "--bind=0.0.0.0:8000", "--workers=2", "--threads=4", "--worker-class=gthread", "--worker-tmp-dir=/dev/shm", "--timeout=120", "--preload", "frappe.app:application"]
