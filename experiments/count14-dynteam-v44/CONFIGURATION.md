# Configuration: endpoints and credentials

This export contains **no gateway addresses, API keys, or dashboard URLs**. Code that talks to
the external model gateway, or locates the provider key, reads environment variables instead.
Copy [`count14.env.example`](count14.env.example), fill it in for your environment, and export it
before running any component:

```bash
cp count14.env.example count14.env   # keep count14.env out of version control
$EDITOR count14.env
set -a; . ./count14.env; set +a
```

If a variable is unset, the code falls back to an obviously invalid placeholder
(`*.example.invalid` or `/path/to/...`), so a missing setting fails loudly at the first request
instead of silently reaching some other host.

## Variables

| Variable | Required | What it is | Example |
| --- | --- | --- | --- |
| `COUNT14_GLM_BASE_URL` | yes | OpenAI-compatible base URL of the GLM model gateway, **including** the `/v1` suffix. All SEARCH, AUX/FINAL and SYSTEM-probe requests go here. The model-list URL is derived as `$COUNT14_GLM_BASE_URL/models`. | `https://glm-gateway.example.com/v1` |
| `COUNT14_GLM_LEGACY_BASE_URL` | no | Base URL of the gateway route used before the provider migration. Only provider-alias/migration checks and the original pilot probe refer to it. If you never had a second route, set it to the same value as `COUNT14_GLM_BASE_URL`. | `https://glm-gateway.example.com/old-route/v1` |
| `COUNT14_GLM_KEY_RELPATH` | no | Path of the provider-key file **relative to the experiment root**. Default: `config/glm-provider-key`. | `config/glm-provider-key` |
| `COUNT14_GLM_KEY_SOURCE_FILE` | production only | Absolute path of the key file that `framework/startup/prepare_fresh48.py` copies into a new experiment root in production mode. | `/secure/glm-provider-key` |

### Provider-key file

* Plain text, containing only the bearer token (no `Bearer ` prefix, no trailing data).
* Owner-only permissions (`chmod 600`). It is read at request time and sent as
  `Authorization: Bearer <token>`; it is never logged or copied into ledgers.
* Never commit it. Nothing in this tree contains a real key.

### Request format the gateway must accept

* `POST $COUNT14_GLM_BASE_URL/chat/completions` with `"stream": true` (every call streams,
  including health probes).
* Header `X-Session-ID`: stable within one conversation and different across conversations.
  The gateway uses it for session affinity / KV-cache reuse.
* Model id `GLM-5.3-FP8` (fixed in the frozen contracts under `contracts/`, not an environment
  setting).
* No `max_tokens` is sent by default; the per-request budget reservation uses the gateway's
  `max_model_len` (524,288 in the original run) minus the request's input.

### Admission health metrics

The admission gate samples a Prometheus-style `/metrics` endpoint (TTFT p95, in-flight requests).
In this export that URL is not hard-coded: it is passed in through the resource plan
(`metrics_url`) or the host config key `gateway_base` used by `ops_tools/host/task-host.py`. Point it
at whatever metrics endpoint your gateway exposes. No monitoring dashboard is referenced anywhere.

## Which files read these variables

The 15 files changed for publication are listed with their original and published SHA-256 in
[`CONFIGURED_FILES.json`](CONFIGURED_FILES.json). Each one adds a single line,
`import os as _count14_os`, and replaces the former literal with
`_count14_os.environ.get('<VARIABLE>', '<placeholder>')`. Nothing else in those files changed.

## Not configurable in this export

The frozen code still contains host-specific filesystem paths of the original testbed (scratch
mounts, experiment-root names) and the three paired seeds. They are inventoried in the README
section "Frozen host/path/root/seed references". They are not credentials, but you will need to
adapt them to run anything outside the original environment. This tree is meant for reading and
review, not as a portable launcher.
