#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import re
import subprocess
import threading
import time
import uuid

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HOST = "0.0.0.0"
PORT = 8088

DOWNLOAD_VIDEO = "/home/humit/.local/bin/download-video"

ALLOWED_CHILDREN = {
    "ree": "Ree",
    "dee": "Dee",
    "shared": "Shared",
}

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

MAX_SUBJECT_LENGTH = 80
MAX_OUTPUT_LENGTH = 12000

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()

# Deliberately serial: avoid multiple yt-dlp processes competing for bandwidth.
executor = ThreadPoolExecutor(max_workers=1)


def valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.hostname.lower() in ALLOWED_HOSTS
    )


def valid_subject(value: str) -> bool:
    value = value.strip()

    if not value or len(value) > MAX_SUBJECT_LENGTH:
        return False

    if value in {".", ".."}:
        return False

    if "/" in value or "\\" in value or "\x00" in value:
        return False

    return True


def update_job(job_id: str, **values) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(values)


def run_download(job_id: str, child: str, subject: str, url: str) -> None:
    update_job(
        job_id,
        state="running",
        started_at=time.time(),
    )

    command = [
        DOWNLOAD_VIDEO,
        "--homework",
        child,
        "--subject",
        subject,
        url,
    ]

    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60 * 60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        update_job(
            job_id,
            state="failed",
            message="Download timed out.",
            output=output[-MAX_OUTPUT_LENGTH:],
            finished_at=time.time(),
        )
        return
    except Exception as exc:
        update_job(
            job_id,
            state="failed",
            message=f"Could not start download: {exc}",
            finished_at=time.time(),
        )
        return

    output = result.stdout or ""

    if result.returncode == 0:
        output_lower = output.lower()

        if (
            "has already been recorded in the archive" in output_lower
            or "already been recorded in the archive" in output_lower
        ):
            message = (
                f"Already exists in {ALLOWED_CHILDREN[child]} Homework."
            )
        else:
            message = (
                f"Added to {ALLOWED_CHILDREN[child]} Homework."
            )

        update_job(
            job_id,
            state="complete",
            message=message,
            output=output[-MAX_OUTPUT_LENGTH:],
            finished_at=time.time(),
        )
    else:
        update_job(
            job_id,
            state="failed",
            message=f"download-video exited with code {result.returncode}.",
            output=output[-MAX_OUTPUT_LENGTH:],
            finished_at=time.time(),
        )


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1,viewport-fit=cover"
>
<meta name="theme-color" content="#111827">
<title>Childsafe Inbox</title>

<style>
:root {
    font-family:
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    color-scheme: light dark;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    min-height: 100vh;
    background: #111827;
    color: #f9fafb;
}

main {
    width: min(100%, 520px);
    margin: 0 auto;
    padding:
        max(22px, env(safe-area-inset-top))
        18px
        max(36px, env(safe-area-inset-bottom));
}

h1 {
    margin: 8px 0 4px;
    font-size: 28px;
}

.subtitle {
    margin: 0 0 28px;
    color: #9ca3af;
}

label {
    display: block;
    margin: 22px 0 8px;
    font-weight: 650;
}

input,
button {
    width: 100%;
    min-height: 54px;
    border-radius: 14px;
    font: inherit;
}

input {
    border: 1px solid #4b5563;
    padding: 0 14px;
    background: #1f2937;
    color: #fff;
    font-size: 16px;
}

.child-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}

.child-option {
    position: relative;
}

.child-option input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
}

.child-option span {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 54px;
    border: 1px solid #4b5563;
    border-radius: 14px;
    background: #1f2937;
    font-weight: 700;
}

.child-option input:checked + span {
    background: #2563eb;
    border-color: #60a5fa;
}

button {
    margin-top: 28px;
    border: 0;
    background: #22c55e;
    color: #052e16;
    font-weight: 800;
    font-size: 17px;
}

button:disabled {
    opacity: 0.55;
}

#status {
    display: none;
    margin-top: 20px;
    padding: 16px;
    border-radius: 14px;
    background: #1f2937;
    white-space: pre-wrap;
}

#status.visible {
    display: block;
}

#status.error {
    background: #450a0a;
}

#status.success {
    background: #052e16;
}

details {
    margin-top: 12px;
}

pre {
    overflow-wrap: anywhere;
    white-space: pre-wrap;
    font-size: 12px;
    color: #d1d5db;
}

.hint {
    margin-top: 7px;
    color: #9ca3af;
    font-size: 13px;
}
</style>
</head>

<body>
<main>
    <h1>Childsafe Inbox</h1>
    <p class="subtitle">Add a school video to Jellyfin.</p>

    <form id="form">
        <label for="url">YouTube link</label>
        <input
            id="url"
            name="url"
            type="url"
            inputmode="url"
            autocomplete="off"
            autocapitalize="off"
            placeholder="Paste link from WhatsApp"
            required
        >

        <label>For</label>
        <div class="child-grid">
            <label class="child-option">
                <input type="radio" name="child" value="ree" checked>
                <span>Ree</span>
            </label>

            <label class="child-option">
                <input type="radio" name="child" value="dee">
                <span>Dee</span>
            </label>

            <label class="child-option">
                <input type="radio" name="child" value="shared">
                <span>Shared</span>
            </label>
        </div>

        <label for="subject">Subject</label>
        <input
            id="subject"
            name="subject"
            list="subjects"
            placeholder="Matematik"
            autocomplete="off"
            required
        >

        <datalist id="subjects">
            <option value="Matematik">
            <option value="Türkçe">
            <option value="Fen Bilimleri">
            <option value="İngilizce">
            <option value="Sosyal Bilgiler">
            <option value="Ödev">
        </datalist>

        <p class="hint">
            You can also type a new subject name.
        </p>

        <button id="submit" type="submit">
            Download
        </button>
    </form>

    <div id="status"></div>
</main>

<script>
const form = document.getElementById("form");
const submit = document.getElementById("submit");
const statusBox = document.getElementById("status");
const urlBox = document.getElementById("url");

function setStatus(text, cls = "") {
    statusBox.className = "visible " + cls;
    statusBox.textContent = text;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function poll(jobId) {
    while (true) {
        const response = await fetch("/api/jobs/" + jobId);
        const job = await response.json();

        if (!response.ok) {
            throw new Error(job.error || "Could not read job status.");
        }

        if (job.state === "queued") {
            setStatus("Queued…");
        } else if (job.state === "running") {
            setStatus("Downloading…");
        } else if (job.state === "complete") {
            setStatus("✓ " + job.message, "success");
            submit.disabled = false;
            submit.textContent = "Download";
            urlBox.value = "";
            urlBox.focus();
            return;
        } else if (job.state === "failed") {
            let text = "✕ " + job.message;

            if (job.output) {
                text += "\n\n" + job.output;
            }

            setStatus(text, "error");
            submit.disabled = false;
            submit.textContent = "Try again";
            return;
        }

        await sleep(1200);
    }
}

form.addEventListener("submit", async event => {
    event.preventDefault();

    const formData = new FormData(form);

    const payload = {
        url: formData.get("url").trim(),
        child: formData.get("child"),
        subject: formData.get("subject").trim()
    };

    submit.disabled = true;
    submit.textContent = "Starting…";
    setStatus("Starting download…");

    try {
        const response = await fetch("/api/jobs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not start download.");
        }

        submit.textContent = "Downloading…";
        await poll(data.job_id);

    } catch (error) {
        setStatus("✕ " + error.message, "error");
        submit.disabled = false;
        submit.textContent = "Try again";
    }
});

urlBox.focus();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ChildsafeInbox/1.0"

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        match = re.fullmatch(r"/api/jobs/([0-9a-f]+)", self.path)

        if match:
            job_id = match.group(1)

            with jobs_lock:
                job = jobs.get(job_id)

                if job is None:
                    self.send_json(404, {"error": "Unknown job."})
                    return

                response = dict(job)

            self.send_json(200, response)
            return

        self.send_json(404, {"error": "Not found."})

    def do_POST(self):
        if self.path != "/api/jobs":
            self.send_json(404, {"error": "Not found."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 16384:
                raise ValueError("Invalid request size.")

            data = json.loads(
                self.rfile.read(length).decode("utf-8")
            )
        except Exception:
            self.send_json(400, {"error": "Invalid request."})
            return

        url = str(data.get("url", "")).strip()
        child = str(data.get("child", "")).strip().lower()
        subject = str(data.get("subject", "")).strip()

        if child not in ALLOWED_CHILDREN:
            self.send_json(400, {"error": "Invalid child."})
            return

        if not valid_subject(subject):
            self.send_json(400, {"error": "Invalid subject."})
            return

        if not valid_url(url):
            self.send_json(
                400,
                {"error": "Only YouTube links are accepted."},
            )
            return

        job_id = uuid.uuid4().hex

        with jobs_lock:
            jobs[job_id] = {
                "job_id": job_id,
                "state": "queued",
                "child": child,
                "subject": subject,
                "message": "Queued.",
                "created_at": time.time(),
            }

        executor.submit(
            run_download,
            job_id,
            child,
            subject,
            url,
        )

        self.send_json(
            202,
            {
                "job_id": job_id,
                "state": "queued",
            },
        )

    def log_message(self, fmt, *args):
        print(
            f"{self.client_address[0]} "
            f"{self.log_date_time_string()} "
            f"{fmt % args}",
            flush=True,
        )


if __name__ == "__main__":
    print(
        f"Childsafe Inbox listening on {HOST}:{PORT}",
        flush=True,
    )

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown(wait=False)
        server.server_close()
