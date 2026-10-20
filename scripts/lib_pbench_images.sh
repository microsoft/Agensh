#!/usr/bin/env bash
# Keep reference extraction on the same recommended cleanroom as workers/eval.
pbench_cleanroom_tag() {  # profile path -> validated reference tag
    local configured tag
    configured=$(awk -F= '$1=="PBENCH_CLEANROOM_TAG" {sub(/\r$/, ""); print substr($0, index($0, "=")+1); exit}' "$1") || return 1
    tag="${PBENCH_CLEANROOM_TAG:-${configured:-task_cleanroom_v6}}"
    if [ "$tag" != task_cleanroom_v6 ]; then
        echo "FATAL: PBENCH_CLEANROOM_TAG=$tag conflicts with worker/grader task_cleanroom_v6" >&2
        return 1
    fi
    printf '%s\n' "$tag"
}
