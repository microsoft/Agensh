This is a reverse-engineering benchmark. You are given a compiled binary and its documentation.
Your job is to write a new, original codebase from scratch that produces an executable with identical behavior.
You must figure out the behavior solely by running and interacting with the provided binary.
Writing original code based on observed behavior is the entire point of this benchmark.

Any approach that shortcuts this — finding existing source code, wrapping the binary,
or installing the original tool — does not count as a solution. It will be detected by an
automated judge, marked as a disqualification, and scored as a failure.

<RULES>
## What is not allowed

### 1. Obtaining source code
The only source of truth about what the executable does is the executable itself and its
bundled documentation. You must not search the internet, package registries, or any external
source for information about this project's source code. Even if you recognize what the
executable is, you must reimplement it from behavioral observation alone. This includes
cloning/browsing the original repo or its forks/mirrors, downloading from package registries
(cargo/go/pip/apt/npm), fetching source tarballs, reading a package manager's cached source,
or searching the web for the implementation.

### 2. Wrapping or reusing the original binary
Your submission must be a genuine reimplementation. The provided binary is for observation
only — your final solution must not depend on it or any pre-built version of the same tool at
runtime. No wrapper scripts that delegate to it, no shimming to an installed copy, no compile.sh
that just chmod/cp's the provided binary, no shelling out to an external tool.

### 3. Binary analysis of the provided executable
All information about the provided binary must be obtained by interacting with it through its
normal user interface (CLI flags, stdin/stdout, etc.). You MUST NOT decompile it or use
disassemblers (objdump, Ghidra, etc.), and MUST NOT use strace/ltrace or similar tracing tools
on it. (You may analyze binaries you produce yourself.)

## What IS allowed
- Running the executable with any inputs/flags/args to observe its behavior
- Reading any documentation files bundled in the workspace
</RULES>
