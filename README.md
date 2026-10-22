# Agensh: Scaling Organizational Intelligence to 1,024 Agents

Zhihao Zhan, Ting Song, Li Dong, Shaohan Huang, Jianxun Lian, Yan Xia, Furu Wei

**Microsoft Research**

[Paper](https://arxiv.org/abs/2609.26781) · [PDF](agensh.pdf) ·
[Project page](https://aka.ms/Agensh) · [Demo](#demo) ·
[X](https://x.com/zhan8855/status/2102784066957500650) ·
[Reproduction guide](REPRODUCE.md)

**Agensh is a self-organized multi-agent harness that scales to 1,024 agents.**
Peer workers discover and claim sub-tasks, share findings, verify results and
merge progress asynchronously, without a central orchestrator. A shared
workspace, message interface and shared context connect each worker's local
progress to the organization.

## Demo

[![Animated replay of 1,024 agents cooperating through Gitea, Mattermost and shared context](demo/agensh-demo-1024.gif)](https://agens-harness.github.io/project/replay.html)

The 1920 × 1440 preview plays automatically and loops at 3× the video speed.

[Full-size GIF](demo/agensh-demo-1024.gif) ·
[Interactive replay](https://agens-harness.github.io/project/replay.html) ·
[Full-resolution MP4 (75 seconds)](demo/agensh-demo-1024-3200x2400.mp4)

## How it works

Every worker repeats the same cooperation loop:

**Gather context → Claim a sub-task → Take action → Verify results → Merge progress.**

| Coordination component | Implementation | What workers share |
|---|---|---|
| Shared workspace | Gitea | Issues, branches, pull requests and integrated code |
| Message interface | Mattermost | Team announcements, direct messages and coordination history |
| Shared context | Context board | Observations, facts, failed approaches, work claims and patch summaries |

The cooperation loop is expressed in worker instructions. Copilot runs each
worker's local model/tool loop, while a paired mini-router delivers durable
events and shared context. Direct messages and new board entries also reach
active workers through returning infrastructure MCP tool results.

## Results

The paper evaluates Agensh on the five hardest ProgramBench tasks using
GPT-5.6-sol with high reasoning effort, a six-hour budget and no Internet access.
Workers rebuild reference programs from behavioral observations and bundled
documentation. Reported final test-pass rates are:

| Evaluation | 1 agent | 128 agents | 1,024 agents |
|---|---:|---:|---:|
| Mean across five tasks | 19.31% | 28.78% | — |
| Pandoc | 33.89% | 50.94% | 55.06% |

Scaling from 1 to 128 agents improves the five-task mean by approximately
**49% relative**. Larger organizations also reach comparable pass rates sooner.
The paper documents emerging peer coordination, integration workflows and
specialized roles as the organization grows.

## Reproducing the experiments

This release includes the single-node Docker Compose fleet and the standalone
single-agent baseline, both using native Copilot ACP sessions.

- [Reproduction guide](REPRODUCE.md): prerequisites, configuration, image builds,
  launch commands, evaluation, recovery and release differences.
- [Repository layout](REPRODUCE.md#repository-layout): component and folder guides.
- [Fleet launcher](scripts/launch_single_node.sh) and
  [standalone launcher](scripts/launch_single_agent.py): experiment entrypoints.

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
[security and support information](REPRODUCE.md#security-and-support), and
[trademark guidance](REPRODUCE.md#trademarks).
