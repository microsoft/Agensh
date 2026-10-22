#!/usr/bin/env bash
# Resolve the reference cleanroom tag from environment/profile and require v6.
# Reference extraction, worker builds and evaluation must use the same tag family.
pbench_cleanroom_tag() {
    local configured tag
    configured=$(awk -F= '$1=="PBENCH_CLEANROOM_TAG" {sub(/\r$/, ""); print substr($0, index($0, "=")+1); exit}' "$1") || return 1
    tag="${PBENCH_CLEANROOM_TAG:-${configured:-task_cleanroom_v6}}"
    if [ "$tag" != task_cleanroom_v6 ]; then
        echo "FATAL: PBENCH_CLEANROOM_TAG=$tag conflicts with worker/grader task_cleanroom_v6" >&2
        return 1
    fi
    printf '%s\n' "$tag"
}
