import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from server import APP_SERVICES, Handler, Manager, REPOSITORY, ThreadingHTTPServer


class FakeDocker:
    def __init__(self):
        self.calls = []
        self.fail_on = None
        self.image_id = "sha256:new"
        self.active_oneoff = ""
        self.inputs = []

    def __call__(self, args, env, quiet=False, input_text=None):
        self.calls.append((args, env))
        self.inputs.append(input_text)
        if self.fail_on and self.fail_on in args:
            raise RuntimeError("Simulated failure: " + self.fail_on)
        if args[1:3] == ["image", "inspect"]:
            return json.dumps([{"Id": self.image_id, "RepoDigests": [REPOSITORY + "@sha256:new"]}])
        if args[1:2] == ["ps"]:
            return self.active_oneoff
        if "compose" in args and "ps" in args:
            return json.dumps([{"Service": "backend", "State": "running", "Health": ""}])
        return ""


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.docker = FakeDocker()
        self.manager = Manager(self.temp.name, "dashboard-password", self.docker)
        self.payload = dict(site="invite.localhost", port=8080, tag="latest",
                            db_password="database-password", admin_password="admin-password")
        self.manager.configure(self.payload)

    def installed(self):
        self.manager.config.update(installed=True, image_id="sha256:old",
                                   active_image=REPOSITORY + "@sha256:old")
        self.manager.save()

    def test_install_pins_all_services_and_hides_credentials(self):
        self.manager.install()
        self.assertTrue(self.manager.config["installed"])
        compose_calls = [env for args, env in self.docker.calls if "compose" in args]
        self.assertTrue(all(env["INVITE_IMAGE"] == REPOSITORY + "@sha256:new" for env in compose_calls))
        result = json.dumps(self.manager.status())
        for key in ["db_password", "admin_password"]:
            self.assertNotIn(self.payload[key], result)
        self.assertEqual(os.stat(self.manager.config_file).st_mode & 0o777, 0o600)

    def test_update_stops_writers_before_backup_then_migrates(self):
        self.installed()
        self.manager.update()
        commands = [args for args, _ in self.docker.calls]
        stop = next(i for i, args in enumerate(commands) if "stop" in args)
        backup = next(i for i, args in enumerate(commands) if "backup" in args)
        migrate = next(i for i, args in enumerate(commands) if "migrate" in args)
        restart = next(i for i, args in enumerate(commands) if "--force-recreate" in args)
        self.assertLess(stop, backup)
        self.assertLess(backup, migrate)
        self.assertLess(migrate, restart)
        self.assertTrue(all(service in commands[stop] for service in APP_SERVICES))
        self.assertEqual(self.docker.calls[backup][1]["INVITE_IMAGE"], REPOSITORY + "@sha256:old")
        self.assertEqual(self.docker.calls[migrate][1]["INVITE_IMAGE"], REPOSITORY + "@sha256:new")
        self.assertNotIn("pending_image", self.manager.config)

    def test_no_update_does_not_pause_or_restart_site(self):
        self.installed()
        self.docker.image_id = "sha256:old"
        self.manager.update()
        self.assertFalse(any("compose" in args for args, _ in self.docker.calls))
        self.assertFalse(self.manager.update_available)

    def test_backup_failure_never_runs_migration_or_starts_new_image(self):
        self.installed()
        self.docker.fail_on = "backup"
        with self.assertRaises(RuntimeError):
            self.manager.update()
        commands = [args for args, _ in self.docker.calls]
        self.assertFalse(any("migrate" in args or "--force-recreate" in args for args in commands))
        self.assertNotIn("pending_image", self.manager.config)
        self.assertEqual(self.manager.config["image_id"], "sha256:old")

    def test_failed_migration_is_retryable_after_dashboard_restart(self):
        self.installed()
        self.docker.fail_on = "migrate"
        with self.assertRaises(RuntimeError):
            self.manager.update()
        self.assertFalse(any("--force-recreate" in args for args, _ in self.docker.calls))
        self.docker.calls.clear()
        self.docker.fail_on = None
        recovered = Manager(self.temp.name, "dashboard-password", self.docker)
        recovered.update()
        self.assertFalse(any("pull" in args or "backup" in args for args, _ in self.docker.calls))
        self.assertEqual(recovered.config["image_id"], "sha256:new")

    def test_failed_health_probe_pauses_new_site_and_stops_services(self):
        self.installed()
        self.docker.fail_on = "exec"
        with self.assertRaises(RuntimeError):
            self.manager.update()
        last_args, env = self.docker.calls[-1]
        self.assertIn("stop", last_args)
        self.assertEqual(env["INVITE_IMAGE"], REPOSITORY + "@sha256:new")
        self.assertIn("pending_image", self.manager.config)

    def test_setup_retry_preserves_database_password(self):
        self.manager.configure({**self.payload, "db_password": "different-password"})
        self.assertEqual(self.manager.config["db_password"], "database-password")

    def test_redaction_and_input_validation(self):
        self.manager.log("database-password admin-password dashboard-password")
        self.assertEqual(self.manager.logs[-1], "[redacted] [redacted] [redacted]")
        for field, value in [("site", "--bad"), ("site", "a..b"), ("tag", "latest;echo bad"),
                             ("port", 8090), ("admin_password", "short")]:
            with self.subTest(field=field, value=value):
                manager = Manager(Path(self.temp.name) / (field + str(len(value)) if isinstance(value, str) else field),
                                  "dashboard-password", self.docker)
                manager.config = None
                with self.assertRaises(ValueError):
                    manager.configure({**self.payload, field: value})

    def test_overlapping_actions_are_rejected(self):
        self.manager.job["running"] = True
        with self.assertRaisesRegex(ValueError, "already running"):
            self.manager.start("check", {})

    def test_previous_migration_is_not_run_concurrently_after_restart(self):
        self.docker.active_oneoff = "running-container"
        with self.assertRaisesRegex(ValueError, "still running"):
            self.manager.start("update", {})
        self.assertFalse(self.manager.job["running"])

    def test_registry_token_is_passed_on_stdin_and_not_saved_in_site_config(self):
        token = "github-test-token-for-private-images"
        self.manager.registry(dict(username="santhosh3279", token=token))
        args, env = self.docker.calls[-1]
        self.assertIn("--password-stdin", args)
        self.assertNotIn(token, str(args) + str(env))
        self.assertEqual(self.docker.inputs[-1], token + "\n")
        self.assertNotIn(token, self.manager.config_file.read_text())
        self.assertNotIn(token, str(self.manager.logs))
        self.assertEqual(self.manager.registry_token, "")


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = Manager(self.temp.name, "dashboard-password", FakeDocker())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.manager = self.manager
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.host = f"127.0.0.1:{self.server.server_port}"

    def request(self, path, payload=None, cookie="", origin=None):
        connection = http.client.HTTPConnection(self.host)
        headers = {"Cookie": cookie, "Origin": origin or "http://" + self.host}
        body = json.dumps(payload) if payload is not None else None
        connection.request("POST" if payload is not None else "GET", path, body, headers)
        response = connection.getresponse()
        data = response.read()
        result = response.status, json.loads(data), response.getheader("Set-Cookie")
        connection.close()
        return result

    def test_login_required_and_cookie_invalid_after_logout(self):
        self.assertEqual(self.request("/api/status")[0], 401)
        self.assertEqual(self.request("/api/login", {"password": "wrong"})[0], 401)
        status, _, cookie = self.request("/api/login", {"password": "dashboard-password"})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", cookie)
        self.assertEqual(self.request("/api/status", cookie=cookie)[0], 200)
        _, _, cleared = self.request("/api/logout", {}, cookie)
        self.assertIn("Max-Age=0", cleared)
        self.assertEqual(self.request("/api/status", cookie=cookie)[0], 401)
        self.assertEqual(self.request("/api/status", cookie=cleared)[0], 401)

    def test_cross_origin_and_unauthenticated_mutation_are_rejected(self):
        self.assertEqual(self.request("/api/install", {})[0], 401)
        cookie = "invite_dashboard=" + self.manager.session()
        self.assertEqual(self.request("/api/install", {}, cookie, "http://evil.example")[0], 403)
        self.assertFalse(self.manager.job["running"])

    def test_malformed_session_and_payload_do_not_crash_handler(self):
        self.assertEqual(self.request("/api/status", cookie="invite_dashboard=broken")[0], 401)
        cookie = "invite_dashboard=" + self.manager.session()
        self.assertEqual(self.request("/api/install", [], cookie)[0], 400)
        self.assertEqual(self.request("/api/install", {}, cookie)[0], 400)


if __name__ == "__main__":
    unittest.main()
