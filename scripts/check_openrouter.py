#!/usr/bin/env python3
"""OpenRouter connectivity smoke test (M2 cloud_strong / paid-route egress).

The sibling of check_ollama_cloud.py, for the OpenRouter adapter. One real call
to a configured model via OpenRouter's OpenAI-compatible /chat/completions, to
confirm the key + model + real egress work before the manual key-leak smoke
(see backend/AGENTS.md "Manual real-provider smoke").

OpenRouter is NOT wired into the running app (main.py configures only the
cloud_free tier — an unconfigured tier raises rather than misroutes, a deliberate
YAGNI until a heavy task needs cloud_strong). So this standalone script is how the
OpenRouter adapter's real egress is exercised at M2 close.

Model: from OPENROUTER_MODEL. No default — free model ids churn, so pass one
explicitly (a ":free" id keeps this zero-cost), e.g.
  OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

Exit codes:
  0 - OPENROUTER_API_KEY is unset (silently OK on forks / unset secrets)
  1 - OPENROUTER_API_KEY set but OPENROUTER_MODEL unset (nothing to call)
  0 - request returns HTTP 200 and parseable JSON
  1 - any failure (connectivity, auth, parse)

stdlib only. See ADR 0003 (OpenRouter = preferred paid route).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://openrouter.ai/api/v1/chat/completions"


def main() -> int:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY not set - skipping smoke test (OK on forks).")
        return 0

    model = os.environ.get("OPENROUTER_MODEL", "").strip()
    if not model:
        print(
            "OPENROUTER_API_KEY is set but OPENROUTER_MODEL is not - set it to a "
            "(free) model id, e.g. meta-llama/llama-3.3-70b-instruct:free",
            file=sys.stderr,
        )
        return 1

    payload = json.dumps(
        {
            "model": model,
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
            "User-Agent": "story-forge-openrouter-smoke",
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

    print(f"OK - OpenRouter reachable, model {model!r} returned 200 with parseable JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
