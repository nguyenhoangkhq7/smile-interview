"""Exercise release ordering and recovery without AWS or Vercel credentials."""
from contextlib import ExitStack
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        self.old = {"sha": "a" * 40, "web": "dpl_old", "work": "1-1"}
        self.new = {"sha": "b" * 40, "web": "dpl_new"}
        self.saved = {"current": self.old, "history": {self.old["sha"]: self.old}, "pending": None}
        self.events = []
        self.fail = None
        stack.enter_context(patch.dict(os.environ, {
            "ROLLBACK_SHA": "", "GITHUB_RUN_ID": "2", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_STEP_SUMMARY": str(Path(directory) / "summary"),
        }))
        stack.enter_context(patch.object(release, "state", side_effect=lambda: deepcopy(self.saved)))
        stack.enter_context(patch.object(release, "candidate", return_value=self.new))
        stack.enter_context(patch.object(release, "put", side_effect=self.persist))
        for name, callback in {
            "remote": lambda target, phase: self.event(phase, target["web"]),
            "api_check": lambda: self.event("api"),
            "promote": lambda target: self.event("promote", target),
            "web_check": lambda target: self.event("web", target),
        }.items():
            stack.enter_context(patch.object(release, name, side_effect=callback))

    def persist(self, key, data):
        self.assertEqual(key, "production/state.json")
        self.saved = deepcopy(data)

    def event(self, *event):
        self.events.append(event)
        if self.fail == event:
            self.fail = None
            raise RuntimeError("simulated failure")

    def test_release_order(self):
        release.main()
        self.assertEqual(self.events, [
            ("prepare", "dpl_new"), ("activate", "dpl_new"), ("api",),
            ("promote", "dpl_new"), ("web", "dpl_new")])
        self.assertEqual(self.saved["current"]["sha"], self.new["sha"])

    def test_bad_preflight_leaves_current_running(self):
        self.fail = ("prepare", "dpl_new")
        with self.assertRaises(RuntimeError):
            release.main()
        self.assertEqual(self.events, [("prepare", "dpl_new")])
        self.assertEqual(self.saved["current"], self.old)
        self.assertIsNone(self.saved["pending"])

    def test_api_failure_restores_backend_before_promotion(self):
        self.fail = ("api",)
        with self.assertRaises(RuntimeError):
            release.main()
        self.assertEqual(self.events[-3:], [("activate", "dpl_old"), ("api",), ("web", "dpl_old")])
        self.assertNotIn(("promote", "dpl_new"), self.events)

    def test_web_failure_restores_both_versions(self):
        self.fail = ("web", "dpl_new")
        with self.assertRaises(RuntimeError):
            release.main()
        self.assertEqual(self.events[-4:], [
            ("activate", "dpl_old"), ("api",), ("promote", "dpl_old"), ("web", "dpl_old")])
        self.assertIsNone(self.saved["pending"])

    def test_first_failure_remains_visible(self):
        self.saved.update(current=None, history={})
        self.fail = ("activate", "dpl_new")
        with self.assertRaises(RuntimeError):
            release.main()
        self.assertEqual(self.saved["pending"]["sha"], self.new["sha"])
        self.assertFalse(self.saved["history"])

    def test_rollback_requires_known_sha_and_reuses_artifact(self):
        os.environ["ROLLBACK_SHA"] = "c" * 40
        with self.assertRaises(ValueError):
            release.main()
        self.assertFalse(self.events)
        os.environ["ROLLBACK_SHA"] = self.old["sha"]
        release.main()
        self.assertIn(("promote", "dpl_old"), self.events)
        release.candidate.assert_not_called()


class VercelPromotionTests(unittest.TestCase):
    def test_promote_posts_to_project_in_configured_team(self):
        with patch.dict(os.environ, {
            "VERCEL_ORG_ID": "team_example",
            "VERCEL_PROJECT_ID": "prj_example",
            "VERCEL_TOKEN": "test-token",
        }), patch.object(release, "urlopen") as request:
            release.promote("dpl_example")

        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url,
                         "https://api.vercel.com/v10/projects/prj_example/promote/dpl_example?teamId=team_example")
        self.assertEqual(sent.get_method(), "POST")
        self.assertEqual(sent.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(sent.data, b"{}")

    def test_web_check_waits_for_the_expected_alias(self):
        missing = HTTPError("https://api.vercel.com", 404, "Not Found", None, None)
        with patch.dict(os.environ, {"WEB_ORIGIN": "https://smile-example.vercel.app"}), \
                patch.object(release, "vercel_api", side_effect=[
                    missing, {"deploymentId": "dpl_old"}, {"deploymentId": "dpl_new"},
                ]) as lookup, patch.object(release.time, "sleep"), \
                patch.object(release.subprocess, "run") as smoke:
            release.web_check("dpl_new")

        self.assertEqual(lookup.call_count, 3)
        lookup.assert_called_with("v4/aliases/smile-example.vercel.app")
        smoke.assert_called_once()
