#!/usr/bin/env python3
"""Ollama Cloud connectivity smoke test.

Exit codes:
  0 - OLLAMA_CLOUD_API_KEY is unset (silently OK on forks / unset secrets)
  0 - request returns HTTP 200 and parseable JSON
  1 - any failure (connectivity, auth, parse)

stdlib only. See ADR 0001.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://ollama.com/api/chat"
MODEL = "gpt-oss:20b-cloud"  # the cloud_free default; match what the app actually calls


def main() -> int:
    api_key = os.environ.get("OLLAMA_CLOUD_API_KEY", "").strip()
    if not api_key:
        print("OLLAMA_CLOUD_API_KEY not set - skipping smoke test (OK on forks).")
        return 0

    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        }
    ).encode()

    req = urllib.request.Request(
        URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "story-forge-cloud-smoke",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            body = resp.read()
            if resp.status != 200:
                print(f"FAIL: status {resp.status}", file=sys.stderr)
                return 1
            try:
                json.loads(body)
            except json.JSONDecodeError as e:
                print(f"FAIL: response not JSON-parseable: {e}", file=sys.stderr)
                return 1
    except urllib.error.HTTPError as e:
        snippet = e.read().decode(errors="replace")[:300]
        print(f"FAIL: HTTP {e.code} - {snippet}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"FAIL: URL error: {e}", file=sys.stderr)
        return 1

    print("OK - Ollama Cloud reachable, returned 200 with parseable JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
