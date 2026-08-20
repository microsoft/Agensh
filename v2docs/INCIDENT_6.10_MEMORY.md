# Sweep 6.10 — what overloaded the machine

**Date of incident:** 2026-08-06 20:02 PDT (03:02 UTC 08-07), ~7h20m into the sweep.
**Effect:** system-wide OOM, machine down, and four further reboots over the next five days.
**Cause:** a single ProgramBench `executable` process holding **474 GB of the machine's 503 GB.**

Everything below is from the persistent journal (`journalctl -b -5`) and the kernel's own
task dumps. Nothing here is inferred from the sweep logs alone.

---

## 1. The machine genuinely ran out of memory

In the boot that died there were **41,821 `CONSTRAINT_MEMCG` OOM kills and 11
`CONSTRAINT_NONE`**. The distinction is the whole finding:

- `CONSTRAINT_MEMCG` = a cgroup hit *its own* limit. All of these belong to another project's
  `kind` clusters (kubelet pod slices, victims almost all `nginx`). They are self-limiting and
  were not our doing.
- `CONSTRAINT_NONE` = **no cgroup constraint — the machine itself had no memory left.** Eleven
  of these, all inside the half hour before the crash.

The last kernel task dump is truncated at 24 processes: the machine died while writing it.

## 2. One process held 94% of the machine

From the last *complete* task dump before the crash (1,363 processes, total RSS 492.6 GB of
503 GB — the machine was full):

| RSS | process |
|---|---|
| **474.21 GB** | **`executable`** |
| 4.49 GB | containerd-shim |
| 2.45 GB | claude |
| 2.18 GB | mysqld |
| 1.43 GB | kube-apiserver |

Broken down, `executable` was **three processes, and one of them was 474.13 GB**:

```
pid 2362312   474.13 GB
pid 2994567     0.05 GB
pid 3060827     0.02 GB
```

`executable` is ProgramBench's binary — either `/opt/pbench/executable` (the mounted
reference) or `./executable` (the team's build). At 20:02 PDT lane A was on **typst** and
lane B on **quickjs**, both started ~2h earlier.

## 3. Why nothing stopped it

The fatal allocation was **not** the 6.6 failure mode. 6.6 was fan-out — `xargs -P $(nproc)`
with `nproc=256` multiplying modest processes until PIDs and memory ran out. What killed the
machine here was one process, one allocation, and sequential execution would not have
prevented a single case from requesting 474 GB.

**But 6.6's fan-out was also live, in three of the four stacks, the whole time.** Post-incident
analysis of the leads' own `tests/run.sh` on the `tests` branch:

```
ctags     JOBS=${JOBS:-$(nproc || 4)}   -> 256
pandoc    JOBS=${JOBS:-$(nproc || 4)}   -> 256
gromacs   JOBS=${JOBS:-$(nproc || 4)}   -> 256
ffmpeg    JOBS=${JOBS:-8}               -> 8
```

This is not disobedience: the `-P 8` bound and the "run the cases one at a time" line were both
cut from the lead prompt before launch (commit 8f06b38, 10:26 UTC; sweep started 12:41 UTC), so
the prompt those leads received says nothing about width at all. Left unguided, three of four
reached for every core on the box — inside agent containers that had no memory limit.

So two independent unbounded hazards were running side by side, and the single-allocation one
happened to fire first. The slice bounds both (`MemoryMax=80%`, `TasksMax=20000`), but a bound
is not guidance: 256 concurrent copies of a heavy binary thrash inside the cap rather than run
well. The fan-out width is a property of the HOST, not of the task, and the measured behaviour
is that leads pick `nproc` when the prompt is silent.

Three ceilings existed and none applied:

| layer | ceiling | applied here? |
|---|---|---|
| CI job containers | `--memory=8g --pids-limit=512 --cpus=4` (`ACT_JOB_LIMITS`) | no — workers run the suite *inside the agent container*, not in CI |
| agent containers | **none** — 0 `mem_limit`/`pids_limit`/`cpus` keys in `gen-compose-prod.py` | no ceiling to apply |
| docker.service slice | `MemoryMax=infinity` | none |

The per-case timeout was `timeout -k 2 30`. Thirty seconds is ample to allocate 474 GB on a
machine with this memory bandwidth, so the timeout was never reached — the kernel OOMed first.
**A time limit does not bound memory.**

Swap is an 8 GB file, i.e. 1.6% of RAM. It could not absorb any meaningful part of this.

## 4. The second failure: the sweep resurrected itself, headless, for 4.5 days

The reboot killed the lane drivers (`nohup`'d bash — nothing restarts them). But every agent
and mini-router carries **`restart: unless-stopped`** (`tools/gen-compose-prod.py:93,120`), as
do gitea, mysql, mattermost, act-runner. So on each boot Docker brought the *stacks* back and
nothing brought the *supervisor* back.

`HOURS=6` is enforced by the driver, not by the stack. With the driver gone there was nothing
to stop a task, advance a lane, or tear anything down.

Boot history — the machine went down five times:

```
-5  Aug 03 13:42 -> Aug 06 20:02   <- died mid-sweep (this incident)
-4  Aug 07 08:55 -> Aug 07 10:49
-3  Aug 07 11:31 -> Aug 09 01:59
-2  Aug 10 08:34 -> Aug 10 14:03
-1  Aug 11 07:48 -> Aug 11 08:00
 0  Aug 11 08:19 -> (current)
```

Stacks `s610c` (typst) and `s610g` (quickjs) were still running, with agents actively
executing test cases, when they were torn down on Aug 11 at ~10:30 — **~4.5 days unsupervised**,
burning API quota the whole time.

## 5. What the sweep actually completed

Four of eight tasks finished their full 6 hours before the crash and are scoreable
(`SKIP_EVAL=1`, so nothing has been evaluated):

```
ffmpeg   12:41 -> 18:55 UTC  (6h14m)
gromacs  12:51 -> 18:57 UTC  (6h06m)
ctags    18:55 -> 01:03 UTC  (6h08m)
pandoc   18:57 -> 01:12 UTC  (6h15m)
```

typst and quickjs started but their runs are meaningless — they continued for days past their
budget, across five reboots.

## 6. Conclusions

1. **The binding constraint is per-process memory, not concurrency.** Any fix framed as "fewer
   parallel cases" does not address the 474 GB allocation. But concurrency was ALSO unbounded
   (§3): 3 of 4 leads chose `nproc`=256. Both need a ceiling; neither substitutes for the other.
2. **The agent container is the unprotected layer.** CI jobs are capped; the place workers
   actually run the suite is not.
3. **A timeout is not a memory bound.** They fail independently and the memory one fires first.
4. **`restart: unless-stopped` without a supervisor is a runaway.** Either the supervisor must
   survive reboots, or the stack must carry its own deadline.

Items 1–3 are addressed by the 80%-of-RAM ceiling (`docker/pbench.slice`, commit 4847967).

**Two things remain open:**

- **Item 4, the supervisor.** A stack that outlives its driver still runs forever. `HOURS`
  lives in a `nohup`'d process; the containers restart without it.
- **Fan-out guidance.** The slice caps the damage, but the lead prompt still says nothing about
  width, and the measured behaviour is that 3 of 4 leads take every core. Unlike the locale and
  capture rules that were cut as task-specific, the right width is a property of the host.
