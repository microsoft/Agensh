# ⚙️ Current task: ProgramBench reverse rebuild

## Goal

You are given a **pre-compiled reference program** (binary), mounted at `/opt/pbench/executable` in every container.
Task: **rebuild from scratch a complete codebase that reproduces its behavior**, so that it can be compiled and pass the hidden tests.

- You **can run** this binary to observe its behavior: `/opt/pbench/executable --help`, feed various inputs and inspect the output,
  compare boundary cases. This is the **only** information source for understanding the target behavior (plus docs / assets in the repo).
- You **cannot read its bytes**: it is `root:root 0111`, `cat` / `od` / `objdump` will get Permission denied.
  This is a rule, not a fault — **do not try to decompile or dump it**; that is cheating, and even if you try, you can't read it.

## Iron rules (violating any = the entire task is voided)

1. **Fully autonomous**: the whole team defines requirements itself, breaks down work itself, decides itself, and finishes itself. There is no external input;
   do not wait for instructions, do not ask on mattermost "what to do next" — the answer is always: **push the rebuild forward**.
2. **No internet**: the whole cluster is offline. `git clone` of the original project source, `pip install`, `npm i` of remote packages
   **will all fail**. Do not waste time trying to fetch the original source over the network — that is both impossible and cheating. Only the toolchain
   already available in the container (gcc / make / python / node etc. installed locally) is usable.
3. **Hard delivery constraint**: the repo **root directory** must have an executable `compile.sh`; running it must produce an executable file
   named `./executable` at the **root directory**. The evaluator will `tar` your repo HEAD → unpack → **delete any committed `./executable`** → run `./compile.sh`
   → run the hidden tests using the produced `./executable`. `compile.sh` must therefore create `./executable`, not just `chmod` it.
   **No root-directory compile.sh = 0 points**.

## The first step is always

**Run `/opt/pbench/executable` and observe what it does.** Every rebuild starts from understanding its actual behavior.
