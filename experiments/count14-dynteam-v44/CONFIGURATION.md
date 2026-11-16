# Configuration: endpoints, credentials and host settings

This export contains **no gateway addresses, API keys, dashboard URLs, or testbed host paths**.
Code that talks to the external model gateway, locates the provider key, or refers to the
original testbed's disks and host identity reads environment variables instead.
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
| `COUNT14_SCRATCH_ROOT` | yes | Main scratch mount that holds experiment roots, private Docker daemons, evaluation images and retained run data. Needs several TB free; do not use the root disk. Default `/srv/count14/scratch2`. | `/data/count14-scratch` |
| `COUNT14_SCRATCH1_ROOT` | if used | Secondary scratch mount (older roots and a private Docker daemon). Default `/srv/count14/scratch1`. | `/data/count14-scratch1` |
| `COUNT14_HOSTNAME` | production only | Host name (`uname -n`) of the production host. Production-only code refuses to run elsewhere, and qualification-only code refuses to run *on* it. Default `count14-host`. | `gpu-host-01` |
| `COUNT14_HOST_BOOT_ID` | production only | Expected `/proc/sys/kernel/random/boot_id` of the production host; host tools refuse to act after a reboot until it is updated. | `cat /proc/sys/kernel/random/boot_id` |
| `COUNT14_SCRATCH_FS_UUID` | production only | Filesystem UUID of `COUNT14_SCRATCH_ROOT` (`findmnt -n -o UUID --target "$COUNT14_SCRATCH_ROOT"`); guards against writing to the wrong mount. | output of that command |
| `COUNT14_RETIRED_OWNER_BOOT_ID` | historical | Boot ID recorded for one retired owner process; only used to verify that historical record. | leave unset unless verifying old runs |

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

Every file changed for publication is listed with its original and published SHA-256 in
[`CONFIGURED_FILES.json`](CONFIGURED_FILES.json). Each changed Python file adds
`import os as _count14_os` and one `_C14_* = _count14_os.environ.get('<VARIABLE>', '<placeholder>')`
line per setting it uses, and the former literal is replaced by that constant (path literals become
`_C14_SCRATCH + '/rest/of/path'`). Comments and docstrings refer to `$VARIABLE` instead of the old
values. `ops_tools/launch/count14_spawn_loop.sh` uses `${COUNT14_SCRATCH_ROOT}` /
`${COUNT14_SCRATCH1_ROOT}` directly. In `contracts/production.json` (JSON cannot read the environment)
the trajectory roots and evaluation Docker socket are written as `${COUNT14_SCRATCH_ROOT}/...`;
expand them when loading (for example `os.path.expandvars`). Nothing else in those files changed.

## Not configurable in this export

* The three paired seeds are experiment configuration and stay in the contract.
* Experiment-root directory names below the scratch root are kept as relative names.
* A few output-record field names still contain the original host label (for example
  `Dev4=False`, `actual_Dev4_smoke_pass`). They are record keys read by other components, not
  settings, so renaming them would change behaviour.

This tree is meant for reading and review, not as a portable launcher.
