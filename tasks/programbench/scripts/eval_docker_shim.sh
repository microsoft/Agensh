#!/usr/bin/env bash
# Docker executable shim for ProgramBench evaluation: cap memory and optionally
# select a profile network or append pytest options, preserving existing options.
set -u

CAP="${PBENCH_EVAL_MEM_CAP:-128g}"

NET="${PBENCH_EVAL_NETWORK:-}"
case "$NET" in
    ""|omcgitea-*) ;;
    *) echo "pbench-docker-sudo: PBENCH_EVAL_NETWORK must name an omcgitea-* network, not '$NET'" >&2
       exit 2 ;;
esac

sub=""; idx=0
for a in "$@"; do
    idx=$((idx + 1))
    case "$a" in
        -*) continue ;;
        *)  sub="$a"; break ;;
    esac
done

if [ "$sub" = "run" ]; then
    # Inject run flags immediately after the subcommand; leave other commands intact.
    extra=(--memory="$CAP" --memory-swap="$CAP")
    [ -n "$NET" ] && extra+=(--network="$NET")
    if [ -n "${PBENCH_EVAL_PYTEST_ADDOPTS:-}" ]; then
        # Extend an existing PYTEST_ADDOPTS value rather than replacing evaluator flags.
        pytest_args=("$@")
        pytest_found=0
        for ((pytest_index=idx; pytest_index<${#pytest_args[@]}; pytest_index++)); do
            case "${pytest_args[$pytest_index]}" in
                --env|-e)
                    if [ $((pytest_index + 1)) -lt "${#pytest_args[@]}" ] \
                        && [[ "${pytest_args[$((pytest_index + 1))]}" = PYTEST_ADDOPTS=* ]]; then
                        pytest_args[$((pytest_index + 1))]+=" $PBENCH_EVAL_PYTEST_ADDOPTS"
                        pytest_found=1
                    fi ;;
                --env=PYTEST_ADDOPTS=*|-ePYTEST_ADDOPTS=*)
                    pytest_args[$pytest_index]+=" $PBENCH_EVAL_PYTEST_ADDOPTS"
                    pytest_found=1 ;;
            esac
        done
        set -- "${pytest_args[@]}"
        [ "$pytest_found" = 1 ] || extra+=(--env "PYTEST_ADDOPTS=$PBENCH_EVAL_PYTEST_ADDOPTS")
    fi
    set -- "${@:1:$idx}" "${extra[@]}" "${@:$((idx + 1))}"
fi

if [ -n "${PBENCH_DOCKER_SHIM_DRYRUN:-}" ]; then
    echo "sudo HOME=/tmp docker $*"
    exit 0
fi

exec sudo HOME=/tmp docker "$@"
