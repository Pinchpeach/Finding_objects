#!/usr/bin/env bash
# Push the workflow's data commit to the branch it runs on, retrying when
# another workflow pushed in between (seen as "cannot lock ref" / non-fast-
# forward).  Used by every workflow that commits generated data.
#
# A retry cannot resolve a content conflict: when another run has rewritten the same generated file (the scientific cross validation rewrites its
# predictions and summary tables in whole), every attempt fails the same way (run 46050644800, 2026-11-27: six rebase conflicts in a row).
# PUSH_PREFER=ours makes the commit of THIS run win such a conflict (``git pull --rebase -X theirs``: during a rebase "theirs" is the commit being
# replayed, i.e. ours).  Only for files that this run regenerates in full; the default is unchanged.
set -uo pipefail
branch="${1:-${GITHUB_REF_NAME}}"
strategy=()
if [ "${PUSH_PREFER:-}" = "ours" ]; then
  strategy=(-X theirs)
fi
for i in 1 2 3 4 5 6; do
  if git pull --rebase ${strategy[@]+"${strategy[@]}"} --autostash origin "$branch" && git push origin "HEAD:$branch"; then
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep $(( i * 10 + RANDOM % 10 ))
done
echo "push to $branch failed after 6 attempts" >&2
exit 1
