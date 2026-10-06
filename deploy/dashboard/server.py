"""Local Docker installer for Invite. Uses only the Python standard library."""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import threading
import time
from collections import deque
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPOSITORY = "ghcr.io/santhosh3279/myinvite2u"
APP_SERVICES = ["backend", "frontend", "websocket", "worker", "scheduler"]
COMPOSE = Path(__file__).resolve().parents[1] / "compose.yml"


class Manager:
    def __init__(self, data_dir, password, runner=None):
        if not password:
            raise ValueError("DASHBOARD_PASSWORD must be set")
        self.password = password
        self.secret = secrets.token_bytes(32)
        self.revoked_sessions = set()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.config_file = self.data_dir / "config.json"
        self.config = json.loads(self.config_file.read_text()) if self.config_file.exists() else None
        self.lock = threading.RLock()
        self.job = {"running": False, "action": "", "error": "", "logs": []}
        self.logs = deque(maxlen=250)
        self.update_available = None
        self.registry_token = ""
        self.runner = runner or self.execute

    def save(self):
        temporary = self.config_file.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(self.config, stream)
        os.replace(temporary, self.config_file)

    def log(self, message):
        for value in [self.password, self.registry_token] + [self.config.get(key, "") for key in
                                       ("db_password", "admin_password") if self.config]:
            if value:
                message = message.replace(value, "[redacted]")
        with self.lock:
            self.logs.append(message[-2000:])

    def execute(self, args, env, quiet=False, input_text=None):
        # No shell: form values are never interpreted as commands.
        process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True,
                                   stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL)
        if input_text is not None:
            process.stdin.write(input_text)
            process.stdin.close()
        lines = []
        for line in process.stdout:
            lines.append(line)
            if not quiet:
                self.log(line.rstrip())
        if process.wait():
            raise RuntimeError("Docker command failed. Check the operation log and retry.")
        return "".join(lines)

    def docker(self, *args, quiet=False):
        return self.runner(["docker", *args], os.environ.copy(), quiet=quiet)

    def compose(self, *args, image=None, quiet=False):
        config = self.config
        env = os.environ.copy()
        env.update(INVITE_IMAGE=image or config.get("active_image", config["image"]),
                   SITE_NAME=config["site"], HTTP_PORT=str(config["port"]),
                   DB_ROOT_PASSWORD=config["db_password"], ADMIN_PASSWORD=config["admin_password"],
                   COMPOSE_DISABLE_ENV_FILE="1")
        return self.runner(["docker", "compose", "--ansi", "never", "--env-file", "/dev/null",
                            "-p", "invite-managed", "-f", str(COMPOSE), *args], env, quiet=quiet)

    def bench(self, *args, image=None):
        return self.compose("run", "--rm", "--no-deps", "-T", "backend",
                            "bench", "--site", self.config["site"], *args, image=image)

    def configure(self, payload):
        if self.config:
            return  # A retry must preserve the database credentials and volumes.
        site = str(payload.get("site", "")).strip().lower()
        if len(site) > 253 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", site):
            raise ValueError("Enter a valid site hostname")
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
               for label in site.split(".")):
            raise ValueError("Enter a valid site hostname")
        tag = str(payload.get("tag", "latest")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
            raise ValueError("Enter a valid image tag")
        try:
            port = int(payload.get("port", 8080))
        except (TypeError, ValueError):
            raise ValueError("Enter a port between 1024 and 65535") from None
        if not 1024 <= port <= 65535 or port == 8090:
            raise ValueError("Use a port between 1024 and 65535 other than 8090")
        passwords = [str(payload.get(key, "")) for key in ("db_password", "admin_password")]
        if any(not value or len(value) > 256 or any(ord(c) < 32 for c in value)
               for value in passwords):
            raise ValueError("Enter non-empty passwords of up to 256 characters without control characters")
        self.config = dict(site=site, port=port, image=f"{REPOSITORY}:{tag}",
                           db_password=passwords[0], admin_password=passwords[1], installed=False)
        self.save()

    def pull(self):
        self.log("Downloading the selected image…")
        self.docker("pull", self.config["image"])
        info = json.loads(self.docker("image", "inspect", self.config["image"], quiet=True))[0]
        digest = next((value for value in info.get("RepoDigests", [])
                       if value.startswith(REPOSITORY + "@sha256:")), None)
        if not digest:
            raise RuntimeError("The image has no GHCR digest; installation was not changed.")
        return digest, info["Id"]

    def check(self):
        _, image_id = self.pull()
        self.update_available = image_id != self.config.get("image_id")
        self.log("A new image is available." if self.update_available else "Your image is up to date.")

    def registry(self, payload):
        username = str(payload.get("username", "")).strip()
        token = str(payload.get("token", ""))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
            raise ValueError("Enter your GitHub username")
        if not 20 <= len(token) <= 256 or any(ord(c) < 33 for c in token):
            raise ValueError("Enter a GitHub token with read:packages permission")
        self.registry_token = token
        try:
            self.log("Signing in to GitHub Container Registry…")
            self.runner(["docker", "login", "ghcr.io", "--username", username, "--password-stdin"],
                        os.environ.copy(), input_text=token + "\n")
            self.log("Registry sign-in saved. You can install or update your site.")
        finally:
            self.registry_token = ""

    def ready(self, image):
        self.compose("up", "-d", "--no-deps", "--force-recreate", *APP_SERVICES, image=image)
        # Check Frappe itself, not only whether the containers started.
        probe = (
            "import time, urllib.request\n"
            f"req=urllib.request.Request('http://127.0.0.1:8000/api/method/ping', headers={{'Host': {self.config['site']!r}}})\n"
            "for attempt in range(60):\n"
            " try:\n"
            "  with urllib.request.urlopen(req, timeout=3) as response:\n"
            "   assert response.status == 200\n"
            "  break\n"
            " except Exception:\n"
            "  if attempt == 59: raise\n"
            "  time.sleep(2)\n"
        )
        self.compose("exec", "-T", "backend", "env/bin/python", "-c", probe, image=image)

    def install(self):
        if self.config.get("installed"):
            raise ValueError("This site is already installed. Use Update instead.")
        image, image_id = self.pull()
        self.log("Starting the database and Redis…")
        self.compose("up", "-d", "--wait", "--wait-timeout", "180",
                     "db", "redis-cache", "redis-queue", image=image)
        self.log("Creating the site and installing Invite…")
        self.compose("run", "--rm", "-T", "setup", image=image)
        self.bench("migrate", image=image)  # Also completes a previously interrupted setup.
        self.bench("enable-scheduler", image=image)
        self.bench("set-maintenance-mode", "off", image=image)
        self.ready(image)
        self.config.update(active_image=image, image_id=image_id, installed=True)
        self.save()
        self.update_available = False
        self.log("Site installed. Sign in as Administrator with your chosen password.")

    def update(self):
        if not self.config.get("installed"):
            raise ValueError("Install the site first")
        pending = self.config.get("pending_image")
        if pending:
            image, image_id = pending["digest"], pending["id"]
            self.log("Resuming the interrupted update with the same image…")
        else:
            image, image_id = self.pull()
            if image_id == self.config.get("image_id"):
                self.update_available = False
                self.log("Your image is up to date; no services were changed.")
                return
            self.log("Pausing the site and background jobs…")
            self.bench("set-maintenance-mode", "on")
            self.bench("disable-scheduler")
            self.compose("stop", *APP_SERVICES)
            self.log("Backing up the database and public/private files…")
            # Writers are stopped before the backup. A failure leaves maintenance on.
            self.bench("backup", "--with-files")
            self.config["pending_image"] = dict(digest=image, id=image_id)
            self.save()
        self.log("Applying site migrations with the new image…")
        self.compose("run", "--rm", "--no-deps", "-T", "setup", image=image)
        self.bench("migrate", image=image)
        self.bench("enable-scheduler", image=image)
        self.bench("set-maintenance-mode", "off", image=image)
        try:
            self.ready(image)
        except Exception:
            self.bench("set-maintenance-mode", "on", image=image)
            self.bench("disable-scheduler", image=image)
            self.compose("stop", *APP_SERVICES, image=image)
            raise
        self.config.update(active_image=image, image_id=image_id)
        self.config.pop("pending_image", None)
        self.save()
        self.update_available = False
        self.log("Update complete. Your site is ready.")

    def start(self, action, payload):
        if action not in ("install", "check", "update", "registry"):
            raise ValueError("Unknown action")
        with self.lock:
            if self.job["running"]:
                raise ValueError("An operation is already running")
            try:
                active = self.docker("ps", "--filter", "label=com.docker.compose.project=invite-managed",
                                     "--filter", "label=com.docker.compose.oneoff=True",
                                     "--format", "{{.ID}}", quiet=True).strip()
            except (RuntimeError, OSError):
                raise ValueError("Cannot reach Docker. Check that Docker is running and accessible.") from None
            if active:
                raise ValueError("A previous setup or migration is still running. Wait before retrying.")
            if action == "install":
                self.configure(payload)
            if not self.config and action != "registry":
                raise ValueError("Install the site first")
            self.logs.clear()
            self.job = dict(running=True, action=action, error="")
        def work():
            try:
                if action == "registry":
                    self.registry(payload)
                else:
                    getattr(self, action)()
            except Exception as error:
                self.log(str(error))
                self.job["error"] = "Operation failed. Review the log and retry. If an update was interrupted, the site remains paused."
            finally:
                self.job["running"] = False
        threading.Thread(target=work, daemon=True).start()

    def status(self):
        config = self.config or {}
        with self.lock:
            result = dict(config={key: config.get(key) for key in
                                  ("site", "port", "image", "installed", "active_image")},
                          configured=bool(config), pending_update=bool(config.get("pending_image")),
                          update_available=self.update_available, job={**self.job, "logs": list(self.logs)},
                          services=[], docker_error="")
        if self.config and not self.job["running"]:
            try:
                output = self.compose("ps", "--all", "--format", "json", quiet=True).strip()
                rows = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines()]
                result["services"] = [dict(name=row["Service"], state=row["State"],
                                           health=row.get("Health", "")) for row in rows]
            except Exception:
                result["docker_error"] = "Cannot read Docker status. Check Docker access on this host."
        return result

    def session(self):
        token = f"{int(time.time()) + 43200}.{secrets.token_hex(16)}"
        return token + "." + hmac.new(self.secret, token.encode(), hashlib.sha256).hexdigest()

    def authorized(self, cookie):
        try:
            cookies = SimpleCookie(cookie)
            value = cookies["invite_dashboard"].value
            if value in self.revoked_sessions:
                return False
            token, signature = value.rsplit(".", 1)
            return int(token.split(".")[0]) > time.time() and hmac.compare_digest(
                signature, hmac.new(self.secret, token.encode(), hashlib.sha256).hexdigest())
        except (KeyError, ValueError, CookieError):
            return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, data, cookie=None):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if isinstance(data, bytes) else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.reply(200, Path(__file__).with_name("index.html").read_bytes())
        elif self.path == "/api/status":
            if not self.server.manager.authorized(self.headers.get("Cookie", "")):
                self.reply(401, {"error": "Sign in to continue"})
            else:
                self.reply(200, self.server.manager.status())
        else:
            self.reply(404, {"error": "Not found"})

    def do_POST(self):
        # Reject cross-origin requests even if a browser supplies a session cookie.
        if self.headers.get("Origin") not in {f"http://{self.headers.get('Host')}",
                                              f"https://{self.headers.get('Host')}"}:
            self.reply(403, {"error": "Request must come from this dashboard"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 4096:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Invalid request")
            if self.path == "/api/login":
                if not hmac.compare_digest(str(payload.get("password", "")).encode(), self.server.manager.password.encode()):
                    self.reply(401, {"error": "Incorrect password"})
                    return
                cookie = "invite_dashboard=" + self.server.manager.session() + "; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"
                self.reply(200, {"ok": True}, cookie)
            elif not self.server.manager.authorized(self.headers.get("Cookie", "")):
                self.reply(401, {"error": "Sign in to continue"})
            elif self.path == "/api/logout":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                self.server.manager.revoked_sessions.add(cookie["invite_dashboard"].value)
                self.reply(200, {"ok": True}, "invite_dashboard=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
            elif self.path in ("/api/install", "/api/check", "/api/update", "/api/registry"):
                self.server.manager.start(self.path.rsplit("/", 1)[1], payload)
                self.reply(202, {"ok": True})
            else:
                self.reply(404, {"error": "Not found"})
        except (ValueError, json.JSONDecodeError) as error:
            self.reply(400, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--data-dir", default=str(COMPOSE.parent.parent / ".dashboard"))
    args = parser.parse_args()
    manager = Manager(args.data_dir, os.environ.get("DASHBOARD_PASSWORD", ""))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.manager = manager
    print(f"Invite dashboard listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
