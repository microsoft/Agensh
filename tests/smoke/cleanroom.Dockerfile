# Minimal stand-in for a ProgramBench cleanroom: a Debian userland with Python and
# a /workspace holding docs plus an ELF "reference" (mode 0111 needs a real binary).
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace \
    && cp /bin/echo /workspace/executable \
    && printf '%s\n' '# Smoke task' '' 'The reference prints its arguments.' > /workspace/README.md
WORKDIR /workspace
