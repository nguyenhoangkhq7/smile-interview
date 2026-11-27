"""Publish or restore one matched EC2 / Vercel release from the main workflow."""
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ENV = os.environ


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def aws(*args):
    return output("aws", *args)


def put(key, value):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        json.dump(value, f)
    try:
        aws("s3api", "put-object", "--bucket", ENV["RELEASE_BUCKET"], "--key", key, "--body", f.name)
    finally:
        os.unlink(f.name)


def state():
    key = "production/state.json"
    listing = json.loads(aws("s3api", "list-objects-v2", "--bucket", ENV["RELEASE_BUCKET"], "--prefix", key))
    if any(item["Key"] == key for item in listing.get("Contents", [])):
        return json.loads(aws("s3", "cp", f"s3://{ENV['RELEASE_BUCKET']}/{key}", "-"))
    return {"current": None, "history": {}, "pending": None}


def vercel(*args):
    result = subprocess.run(["vercel", *args, "--token", ENV["VERCEL_TOKEN"]],
                            stdout=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(f"Vercel {args[0]} failed with exit code {result.returncode}")
    return result.stdout.strip()


def vercel_api(path, *, data=None):
    query = urlencode({"teamId": ENV["VERCEL_ORG_ID"]}) if ENV["VERCEL_ORG_ID"].startswith("team_") else ""
    req = Request(f"https://api.vercel.com/{path}?{query}", data=data,
                  headers={"Authorization": "Bearer " + ENV["VERCEL_TOKEN"]})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=30) as response:
        if data is None:
            return json.load(response)


def promote(deployment_id):
    project = ENV["VERCEL_PROJECT_ID"]
    vercel_api(f"v10/projects/{project}/promote/{deployment_id}", data=b"{}")


def candidate():
    sha = ENV["GITHUB_SHA"]
    release = f"{sha}-{ENV['GITHUB_RUN_ID']}-{ENV['GITHUB_RUN_ATTEMPT']}"
    url = vercel("deploy", "--prebuilt", "--prod", "--skip-domain", "--yes")
    host = urlsplit(url).hostname
    if not host or not host.endswith(".vercel.app"):
        raise RuntimeError("Unexpected Vercel deployment URL")
    deployment = vercel_api(f"v13/deployments/{host}")
    if deployment["projectId"] != ENV["VERCEL_PROJECT_ID"] or deployment["readyState"] != "READY":
        raise RuntimeError("Staged web deployment is not ready in the expected project")
    manifest = dict(sha=sha, release=release, web=deployment["id"], backend=ENV["BACKEND_IMAGE"],
                    ai=ENV["AI_IMAGE"], code_runner=ENV["CODE_RUNNER_IMAGE"],
                    checkpoint=Path("deploy/gnn-v4.sha256").read_text().split()[0])
    Path("manifest.json").write_text(json.dumps(manifest))
    bundle = "release.tar.gz"
    subprocess.run(["tar", "-czf", bundle, "manifest.json", "deploy/docker-compose.staging.yml",
                    "deploy/nginx/staging.conf", "deploy/gnn-v4.sha256", "deploy/production/compose.yml",
                    "deploy/production/host.sh", "deploy/production/smoke-gnn.py"], check=True)
    manifest["bundle_sha256"] = output("sha256sum", bundle).split()[0]
    aws("s3", "cp", bundle, f"s3://{ENV['RELEASE_BUCKET']}/releases/{release}.tar.gz")
    return manifest


class RemoteFailure(RuntimeError):
    pass


def remote(target, operation):
    work = target["work"]
    if not re.fullmatch(r"[0-9]+-[0-9]+", work):
        raise ValueError("Invalid transaction ID")
    directory = "/var/lib/smile/releases/" + work
    script = ["set -eu", "umask 077", "mkdir -p /var/lib/smile/releases",
              "exec 9>/var/lib/smile/deploy.lock", "flock -w 2100 9"]
    if operation == "prepare":
        uri = f"s3://{ENV['RELEASE_BUCKET']}/releases/{target['release']}.tar.gz"
        script += [f"mkdir -p {directory}", f"cd {directory}",
                   "aws s3 cp " + shlex.quote(uri) + " release.tgz",
                   "echo " + shlex.quote(target["bundle_sha256"] + "  release.tgz") + " | sha256sum -c -",
                   "tar -xzf release.tgz"]
    script += [f"cd {directory}", "bash deploy/production/host.sh " + operation]
    instance = ENV["EC2_INSTANCE_ID"]
    cmd = aws("ssm", "send-command", "--document-name", "AWS-RunShellScript", "--instance-ids", instance,
              "--timeout-seconds", "120", "--parameters",
              json.dumps({"commands": ["\n".join(script)], "executionTimeout": ["2700"]}),
              "--query", "Command.CommandId", "--output", "text")
    print(f"SSM {operation} {cmd}", flush=True)
    deadline = time.monotonic() + 2900
    while time.monotonic() < deadline:
        try:
            rows = json.loads(aws("ssm", "list-command-invocations", "--command-id", cmd)).get("CommandInvocations", [])
        except subprocess.CalledProcessError:
            # A polling failure says nothing about the command still running on EC2.
            time.sleep(10)
            continue
        if rows:
            status = rows[0]["Status"]
            if status == "Success":
                return
            if status not in {"Pending", "InProgress", "Delayed", "Cancelling"}:
                raise RemoteFailure(f"SSM {operation} {cmd} ended with {status}")
        time.sleep(5)
    raise TimeoutError(f"Verify SSM command {cmd} before recovering the pending release")


def api_check():
    subprocess.run(["curl", "-fsS", "--retry", "4", "--retry-all-errors", "--max-time", "20",
                    ENV["API_ORIGIN"] + "/actuator/health", "-o", "health.json"], check=True)
    if json.loads(Path("health.json").read_text()).get("status") != "UP":
        raise RuntimeError("Public API is unhealthy")
    headers = output("curl", "-fsS", "--max-time", "20", "-D", "-", "-o", "/dev/null", "-X", "OPTIONS",
                     "-H", "Origin: " + ENV["WEB_ORIGIN"], "-H", "Access-Control-Request-Method: POST",
                     ENV["API_ORIGIN"] + "/api/auth/login")
    if ("access-control-allow-origin: " + ENV["WEB_ORIGIN"]).lower() not in headers.lower().splitlines():
        raise RuntimeError("CORS preflight did not allow the production web origin")


def web_check(expected_id):
    alias_path = "v4/aliases/" + urlsplit(ENV["WEB_ORIGIN"]).hostname
    for _ in range(36):
        try:
            alias = vercel_api(alias_path)
        except HTTPError as error:
            if error.code != 404:
                raise
        else:
            if alias["deploymentId"] == expected_id:
                break
        time.sleep(5)
    else:
        raise RuntimeError(f"Production domain did not point to {expected_id} within 3 minutes")
    subprocess.run(["curl", "-fsSL", "--retry", "4", "--retry-all-errors", "--max-time", "30",
                    ENV["WEB_ORIGIN"], "-o", "/dev/null"], check=True)


def main():
    saved = state()
    old = saved["current"]
    rollback = ENV.get("ROLLBACK_SHA")
    if rollback:
        if not re.fullmatch("[a-f0-9]{40}", rollback) or rollback not in saved["history"]:
            raise ValueError("Choose a full SHA from successful release history")
        target = dict(saved["history"][rollback])
    else:
        if saved["pending"] and old:
            raise RuntimeError("Recover the pending transaction using manual rollback first")
        target = candidate()
    target["work"] = ENV["GITHUB_RUN_ID"] + "-" + ENV["GITHUB_RUN_ATTEMPT"]
    remote(target, "prepare")
    saved["pending"] = target
    put("production/state.json", saved)
    promotion_attempted = False
    try:
        remote(target, "activate")
        api_check()
        promotion_attempted = True
        promote(target["web"])
        web_check(target["web"])
    except TimeoutError:
        raise
    except Exception:
        if old:
            remote(old, "activate")
            api_check()
            if promotion_attempted:
                promote(old["web"])
            web_check(old["web"])
            saved["pending"] = None
            put("production/state.json", saved)
        raise
    saved["history"][target["sha"]] = target
    saved.update(current=target, pending=None)
    put("production/state.json", saved)
    with open(ENV["GITHUB_STEP_SUMMARY"], "a") as f:
        print("Production release\n\n```json\n" + json.dumps(target, indent=2) + "\n```", file=f)


if __name__ == "__main__":
    main()
