# Thin wrapper around the upstream ollama/ollama image. The upstream image
# runs as root and stores models at /root/.ollama; this wrapper creates an
# unprivileged user, relocates the models directory, and switches USER so
# the container drops privileges before `ollama serve` starts.
#
# Pin chosen 2026-05-19: released 2026-04-28, 21 days old, satisfies the
# project's ≥14-day age policy with comfortable buffer. See ADR 0001 /
# docker-compose.yml for the policy.
FROM ollama/ollama:0.22.1

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
