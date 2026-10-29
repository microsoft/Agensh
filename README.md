<h1 align="center">Agensh: A Decentralized, Scalable Multiagent Harness</h1>

<p align="center">
  <a href="https://aka.ms/Agensh"><img src="https://img.shields.io/badge/Project-Page-blue?logo=githubpages" alt="Project Page"></a>
  <a href="agensh.pdf"><img src="https://img.shields.io/badge/Paper-PDF-yellow?logo=arxiv" alt="Paper PDF"></a>
  <a href="https://arxiv.org/abs/2609.26781"><img src="https://img.shields.io/badge/arXiv-Report-red?logo=arxiv" alt="arXiv Report"></a>
  <a href="https://x.com/zhan8855/status/2102784066957500650"><img src="https://img.shields.io/badge/X-Post-black?logo=x" alt="X Post"></a>
</p>

### News

⚙️ **2026-10-29:** **Agensh** now supports [Copilot](https://github.com/github/copilot-cli), [Codex](https://github.com/openai/codex), [Claude Code](https://github.com/anthropics/claude-code), and [Pi](https://github.com/earendil-works/pi) as single-agent backends.

🚀 **2026-10-24:** We open-sourced **Agensh**, including the harness, experiment launch
scripts, and [reproduction guide](REPRODUCE.md).

📢 **2026-09-22:** We published the **Agensh** [preprint](https://arxiv.org/abs/2609.26781) on arXiv.

## Overview

**Agensh is a self-organized multi-agent harness that scales to 1,024 agents.**
Agents discover and claim sub-tasks, share findings, verify results and
merge progress asynchronously, without a central orchestrator. A shared
workspace, message interface and shared context connect each agent's local
progress to the team.

We evaluated Agensh on the five hardest ProgramBench tasks
using GPT-5.6-sol with high reasoning effort, a six-hour budget and no Internet access.
Agents rebuild reference programs from behavioral observations and bundled
documentation. Across the 5 evaluated tasks, the mean final test-pass rate rises
from **19.31% with 1 agent** to **28.78% with 128 agents**, an improvement of
approximately **49% relative**. Larger teams also reach comparable pass rates
sooner. On **Pandoc**, the final test-pass rate rises from **33.89% with 1 agent**
to **50.94% with 128 agents** and **55.06% with 1,024 agents** under the same
six-hour budget. We find that self-organized peer coordination, integration
workflows and specialized roles gradually emerge as the team grows.

With GPT-6.1-sol at high reasoning effort, the six-hour Pandoc test-pass
rate rises from **56.19% with 1 agent** to **79.59% with 32 agents**, a relative
improvement of **41.64%**.

![Pandoc scaling results for GPT-5.6-sol and GPT-6.1-sol at high reasoning effort, with emergent coordination workflows and specialized roles](demo/pandoc_results.png)

## Watch 1,024 agents work together

[![Animated replay of 1,024 agents cooperating through Gitea, Mattermost and shared context](demo/agensh_demo_1024.gif)](https://agens-harness.github.io/project/replay.html)

## How it works

![Agensh cooperation loop: gather context, claim a sub-task, take action, verify results and merge progress asynchronously through shared workspace, messaging and context](demo/loop.png)

**Agensh defines the multi-agent cooperation loop.**
Workers concurrently gather context, claim sub-tasks, take action, verify results
and merge progress in a self-organized manner, repeating until the user’s goal
is achieved. All workers proceed asynchronously and share progress through the
infrastructure.
[Gitea](https://about.gitea.com/) provides the shared workspace,
[Mattermost](https://mattermost.com/) provides the messaging interface, and the
shared context mechanism is adapted from [DeLM](https://github.com/yuzhenmao/DeLM).
In our 1.0 experiments, we integrate Agensh on top of the per-agent agentic loop
of [Copilot harness](https://github.com/github/copilot-cli).
We also support [Pi](https://github.com/earendil-works/pi),
[Codex](https://github.com/openai/codex), and
[Claude Code](https://github.com/anthropics/claude-code) as underlying single-agent harnesses.

## Reproducing the experiments

This release includes a single-node team setup using Docker Compose and a
standalone single-agent baseline. Copilot is the default. Select Pi, Codex, or
Claude Code with `--agent-harness pi`, `--agent-harness codex`, or `--agent-harness claude`
when preparing and launching runs.
Pass `--harness-version VERSION` to choose a harness release.
Each worker image includes only the selected harness. All expose ACP to the
existing infrastructure; Pi, Codex, and Claude Code use adapters to their native runtimes.
Copilot is the harness used for the 1.0 experiments.

- [Reproduction guide](REPRODUCE.md): prerequisites, configuration, image builds,
  launch commands, evaluation, recovery and release differences.
- [Repository layout](REPRODUCE.md#repository-layout): component and folder guides.
- [Harness configuration](agent/config/harness.json): model, reasoning effort,
  prompt/output budgets and compaction settings.
- [Team launcher](scripts/launch_single_node.sh) and
  [single-agent launcher](scripts/launch_single_agent.py): experiment entrypoints.

## Citation

```bibtex
@article{zhan2026agensh,
  title   = {Agensh: Scaling Organizational Intelligence to 1,024 Agents},
  author  = {Zhan, Zhihao and Song, Ting and Dong, Li and Huang, Shaohan and Lian, Jianxun and Xia, Yan and Wei, Furu},
  journal = {arXiv preprint arXiv:2609.26781},
  year    = {2026},
  url     = {https://arxiv.org/abs/2609.26781}
}
```

## License and contributing

Code is licensed under the [MIT License](LICENSE). See the
[contribution guidelines](REPRODUCE.md#contributing),
[security policy](SECURITY.md),
[support information](REPRODUCE.md#security-and-support), and
[trademark guidance](REPRODUCE.md#trademarks).
