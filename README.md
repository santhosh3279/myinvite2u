### Invitation

Invitation

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app invite
```

### Frontend (Frappe UI)

The Vue frontend uses [Frappe UI](https://github.com/frappe/frappe-ui), Vite,
and Tailwind CSS. Node.js 20.19+ (or 22.12+) and Yarn 1.22 are required.

From this repository:

```bash
yarn install --frozen-lockfile
yarn dev
```

Open the URL printed by Vite at `/invite`. The development server proxies
Frappe requests to the bench web server and reads its port from
`sites/common_site_config.json`. Keep `bench start` running, and use your site's
hostname when accessing Vite if your bench hosts multiple sites.

Vite uses polling for live reload because bench can exhaust Linux file watchers
(`ENOSPC`). Source changes still reload automatically. Vite listens on `0.0.0.0` by default,
so you can access it from another machine using the server's IP address.

Build for Frappe:

```bash
yarn build
```

This generates assets in `invite/public/frontend` and the website page
`invite/www/invite.html`. With the app installed on your site, open `/invite`
on the Frappe web server. `bench build --app invite` also runs this build.
Generated files are ignored by Git and must be built after installation.

### Docker image and GitHub Actions

`.github/workflows/docker.yml` builds a Linux amd64 image on pushes to
`version-16` or `main`, `v*` tags, pull requests, and manual runs from the
Actions tab. It checks that Frappe and Invite import and that frontend assets
were built before publishing to `ghcr.io/santhosh3279/myinvite2u` with the
workflow's `GITHUB_TOKEN`; no additional registry secret is required. Pull
requests only build and verify. Pushes and manual runs publish branch and
`sha-<commit>` tags; default branch builds also publish `latest`. Version tags
such as `v1.0.0` publish `1.0.0`.

The multi-stage `Dockerfile` uses the official Frappe v16 build/runtime bases,
initializes a Frappe bench, installs this checkout of Invite, and builds both
apps' assets. It follows Frappe's
[layered image setup](https://github.com/frappe/frappe_docker/blob/main/images/layered/Containerfile).
Database-backed site installation happens when Compose starts.

Build and run from this repository:

```bash
docker build -t invite:local .
cp deploy/docker.env.example .env
# Edit .env and replace DB_ROOT_PASSWORD and ADMIN_PASSWORD.
docker compose --env-file .env -f deploy/compose.yml up -d
docker compose --env-file .env -f deploy/compose.yml logs -f setup
```

To use the published image instead of building locally, run
`docker pull ghcr.io/santhosh3279/myinvite2u:latest` and set
`INVITE_IMAGE=ghcr.io/santhosh3279/myinvite2u:latest` in `.env` before starting
Compose. If the GHCR package is private, log in with `docker login ghcr.io`
using a token with `read:packages` permission.

Compose starts MariaDB, Redis, the backend, Nginx, websocket, worker, and
scheduler services. Its setup service waits for the database and Redis, creates
`SITE_NAME` (default `invite.localhost`), and runs `--install-app invite` on
first startup. Existing sites are preserved. Open `http://localhost:8080/invite`
and log in as `Administrator` with your configured `ADMIN_PASSWORD`.
Database data, sites/files, logs, and queued jobs use persistent Docker volumes.

After rebuilding for an app update, recreate the services and migrate the site:

```bash
docker build -t invite:local .
docker compose --env-file .env -f deploy/compose.yml up -d --force-recreate
docker compose --env-file .env -f deploy/compose.yml exec backend \
  bench --site invite.localhost migrate
```

Replace `invite.localhost` with your `SITE_NAME` if you changed it. For invitation
subdomains, point your reverse proxy to the published HTTP port and preserve
the request's `Host`; Compose fixes `X-Frappe-Site-Name` to `SITE_NAME` so the
existing invitation domain routing can resolve the hostname.

Frontend source lives in `frontend/src`. `/invite` provides shortcuts to create
wedding invitations and review responses in Frappe Desk.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/invite
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit

### Wedding invitations

On a site with Invite installed, run `bench --site <site> migrate`. Open
`/app/wedding-invitation` as a System Manager and create an invitation. Set the
bride and groom names, wedding date/time, timezone, and at least one event.
Add family details, invitation text, story milestones, venue directions, photos,
travel notes, contact details, and optional background music. Upload photos and
music as **public files** so guests can access them.

Save the record to generate its Website Address. Check **Publish Invitation**
and save to make the page public, then click **Open Invitation**. For example,
Anna and James marrying on February 14, 2027 get `/anna&james-2027-02-14`.
Names are lowercased and spaces become hyphens. Changing either name or the
wedding date changes the URL; share the new address after editing. Unchecking
Publish removes public access. No frontend build is required for invitation
pages, which use Frappe's native website generator.

Event date/time fields use the invitation's IANA timezone (default:
`Asia/Kolkata`). The countdown uses a timezone-aware timestamp. Enable RSVP,
set an optional deadline, and choose the maximum party size. Responses are
stored in **Wedding RSVP**, linked to the invitation, and can be reviewed using
the **View RSVPs** button. Guests cannot read the invitation records or RSVP
data through the resource API. Submissions check publication, deadline,
attendance, guest count, and field lengths and are rate limited per IP.

Design reference: [Japh09066/wedding-invitation](https://github.com/Japh09066/wedding-invitation).
The envelope reveal, story, countdown, gallery, music and RSVP experience are
implemented in Frappe; no Google Sheets or Next.js service is required.

### Invitation subdomains

Each invitation supports **Enable Subdomain** and **Custom Domain**. The domain
is autofilled from the bride and groom names, for example Anna and James become
`anna-james.myinvite2u.in`. Automatically generated domains follow name edits;
a manually edited domain is preserved. Clearing the field regenerates it on save.
The field is visible even before enabling subdomains. Enter
one full hostname, such as `anna-james.myinvite2u.in`, enable the checkbox, and
publish the invitation. **Public Invitation URL** becomes
`https://anna-james.myinvite2u.in/`, and **Open Invitation** opens that URL.
The original bride/groom/date path still works on the main site. Unknown,
disabled, and unpublished invitation subdomains return 404. An assigned
subdomain serves only its own invitation, and RSVP submissions on that hostname
must belong to that invitation. Domain names are normalized, validated, and
unique, including when reserved by a disabled invitation.

The default wildcard base is `myinvite2u.in`. For another base, set
`invitation_base_domain` in the site's configuration, and configure matching DNS,
proxy and certificates. Only one subdomain label is accepted because a wildcard
certificate for `*.myinvite2u.in` covers `anna-james.myinvite2u.in`, not nested
names. Names must contain letters, numbers and hyphens; `&` is not valid in the
subdomain. Hostnames do not include `https://`, a port, or a path.

GoDaddy DNS setup:

| Type | Name | Value |
| --- | --- | --- |
| A | `*` | Server's public IPv4 address |
| A | `@` | Server's public IPv4 address, if the apex should reach this server |

Use DNS records rather than URL forwarding to `IP:port`. A records contain an IP
address; they do not select a web port. Serve HTTPS on port 443 with a reverse
proxy forwarding to the configured bench backend (currently port 8002). Preserve
`Host` and override `X-Frappe-Site-Name` to `myinvite2u` so every invitation
hostname selects this existing Frappe site before the app resolves the invitation.
There is no need to create a separate Frappe site for each invitation. A proxy
that replaces `Host` with the site name cannot support this domain lookup.

The app changes do not configure public DNS, install certificates, or alter the
running reverse proxy. An Nginx example is provided in
`deploy/nginx-invitations.conf.example`; merge/adapt it to your existing deployment
and replace certificate paths before enabling it. If using another proxy, use
the same host preservation and fixed Frappe site header. Obtain a wildcard
certificate for `*.myinvite2u.in`; add `myinvite2u.in` to the certificate if it
will also serve the apex. Let's Encrypt wildcard certificates require DNS-01
validation and automated renewal should use your DNS provider's supported API.

References: [GoDaddy A records](https://www.godaddy.com/help/add-or-edit-an-a-record-42546),
[Nginx proxy headers](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header),
[Let's Encrypt DNS-01](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge).

### Invitation animations

Invitation pages include a wax-seal release, opening envelope flap and rising
card, followed by staggered hero text. Floating petals, botanical line drawing,
cover photo parallax, scroll reveals for the story/events/gallery, a reading
progress indicator, animated countdown updates and lightbox transitions bring
the page to life. Successful RSVP submissions show a short confetti celebration.
Decorative motion respects `prefers-reduced-motion`; the envelope opens
immediately and all content stays visible when motion is reduced. Content is
also visible when JavaScript is unavailable. These effects use native browser
APIs and CSS without an additional animation dependency or frontend build.

The story alternates between left and right cards on desktop. A dotted curved
path links numbered milestones and traces downward as the viewport reaches each
chapter, from the first story entry to the last. Mobile uses full-width cards
beside the dotted path. The path recalculates when images load or the layout
changes; reduced-motion visitors see the complete path without scroll animation.
Story entries retain their order from the invitation's Our Story table.

### Invitation templates

Choose **Light** or **Dark** in the Wedding Invitation's **Invitation Template**
field, save, and use **Open Invitation** to view the selected design. Light is
the default. Dark uses deep navy surfaces, champagne accents and light text,
including the envelope, event cards, story timeline, photo lightbox and RSVP form.
Both templates share the invitation content, animations, public route and domain
routing. The template is selected per invitation and applies to every guest; it
is independent of the guest's device appearance setting.
