# Security policy

## Supported versions

Only the latest commit on `main` (and the latest tagged release, once releases are tagged) receives fixes.

## Reporting a vulnerability

Please report privately through GitHub: **Security → Report a vulnerability** on this repository (private vulnerability
reporting). Do not open a public issue for a vulnerability, and do not attach client pictures, keys or job folders to a report.
Expect a first answer within a week.

## What the web studio is (threat model)

The studio (`python web/server/run.py`) is a **single-user tool for your own computer**:

- It listens on `127.0.0.1` only and refuses requests whose `Host` is not that address, and state-changing requests whose `Origin`
  is another site (so a web page you visit cannot drive it through your browser).
- It has **no login**. Do not expose it on a network, put it behind a public reverse proxy or forward its port to other people.
  To use it from another machine of your own, tunnel it: `ssh -L 8800:127.0.0.1:8800 you@that-machine`.
- File names from requests are checked before any file-system access; job files are served only from inside the job folder.
- A second copy cannot bind the same port.

## Your API key

- The key comes from the environment variable `OPENAI_API_KEY`, or you paste it on the page. It is kept **in the server process's
  memory only**: never written to a job folder, a log, a status file or an API response. Error texts are scrubbed of the key and of
  anything that looks like one. Child processes (Blender) do not inherit it.
- Do not commit a `.env` file; `.gitignore` already ignores it.

## Your pictures

- Pictures and every result stay on your disk under `output/studio/<job>/` (git-ignored).
- A picture is sent to a large-model service **only** when you use the automatic reading step, **only** to the service you
  configured (`OPENAI_BASE_URL`, OpenAI by default), and **only** after you tick the consent box for that picture. That service's
  terms apply to what you send.
- The request and reply of a reading are kept in `output/studio/<job>/reader/` without the picture bytes and without the key.
- The standalone editor (`web/app/index.html`) uploads nothing: it works entirely in the browser.

## The skill

The skill's scripts read and write files in the working directory you run them from and start Blender as a separate process
(`--factory-startup --disable-autoexec`, so scripts embedded in `.blend` files are not run). They make no network calls.
