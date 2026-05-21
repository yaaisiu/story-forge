# Thin wrapper around the upstream ollama/ollama image. The upstream image
# runs as root and stores models at /root/.ollama; this wrapper creates an
# unprivileged user, relocates the models directory, and switches USER so
# the container drops privileges before `ollama serve` starts.
#
# Pin bumped 2026-05-21 (Issue #4): 0.24.0 was built 2026-05-14, 7 days old,
# satisfying the ≥7-day image age policy. Bumped from 0.22.1 because that pin
# went CVE-stale (the security CI Trivy step flagged compiled-in Go stdlib CVEs
# in the ollama binary). 0.24.0 is the freshest aged stable; residual stdlib
# CVEs no ollama tag can fix (they need an upstream rebuild on patched Go) are
# waived with justification in infra/trivy/ollama.trivyignore.
FROM ollama/ollama:0.24.0

ARG OLLAMA_UID=10001
ARG OLLAMA_GID=10001

ENV OLLAMA_MODELS=/var/lib/ollama \
    HOME=/var/lib/ollama

RUN groupadd --system --gid ${OLLAMA_GID} ollama \
 && useradd  --system --uid ${OLLAMA_UID} --gid ${OLLAMA_GID} \
             --home-dir /var/lib/ollama --shell /usr/sbin/nologin ollama \
 && mkdir -p /var/lib/ollama \
 && chown -R ollama:ollama /var/lib/ollama

USER ollama:ollama
# Entrypoint and CMD are inherited from the upstream image ("ollama serve").
