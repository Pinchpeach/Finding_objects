#!/usr/bin/env bash
# Push the workflow's data commit to the branch it runs on, retrying when
# another workflow pushed in between (seen as "cannot lock ref" / non-fast-
# forward).  Used by every workflow that commits generated data.
#
# A retry cannot resolve a content conflict: when another run has rewritten the same generated file (the scientific cross validation rewrites its
# predictions and summary tables in whole), every attempt fails the same way (run 46050644800, 2026-11-27: six rebase conflicts in a row).
# PUSH_PREFER=ours makes the commit of THIS run win: instead of a rebase, each attempt starts from the remote branch and writes back the complete
# content of the paths this run owns (PUSH_PATHS, else the files its commit touched), then commits it again with the same message.  A hunk-level resolution (``-X theirs``) is not
# enough: it keeps the other run's non-conflicting hunks, so a regenerated report would mix two runs (Codex review of 2.62.0).  Files the commit
# did not touch keep the remote's content.  Only for files that this run regenerates in full; the default is unchanged.
set -uo pipefail
branch="${1:-${GITHUB_REF_NAME}}"

if [ "${PUSH_PREFER:-}" = "ours" ]; then
  ours="$(git rev-parse HEAD)"
  msg="$(git log -1 --format=%B)"
  # The paths this run owns: PUSH_PATHS (space-separated) names every product it regenerates, so that a product that came out the same as in the
  # trigger commit is written back as well (without it, the commit's changed files only; Codex review of 2.62.0: an unchanged summary kept another
  # run's summary next to this run's predictions).
  if [ -n "${PUSH_PATHS:-}" ]; then
    read -r -a specs <<< "$PUSH_PATHS"
  else
    mapfile -d '' -t specs < <(git diff -z --name-only HEAD~1 HEAD)  # NUL-separated: no quoting of unusual file names
  fi
  for i in 1 2 3 4 5 6; do
    if git fetch -q origin "$branch" && git reset -q --hard FETCH_HEAD; then
      git rm -r -q --ignore-unmatch -- "${specs[@]}" > /dev/null  # the remote's versions of these paths go ...
      mapfile -d '' -t present < <(git ls-tree -r -z --name-only "$ours" -- "${specs[@]}")
      if [ "${#present[@]}" -gt 0 ]; then
        git checkout -q "$ours" -- "${present[@]}"  # ... and this run's complete files take their place (a file it deleted stays deleted)
      fi
      if git diff --cached --quiet || git commit -q -m "$msg"; then
        if git push origin "HEAD:$branch"; then
          exit 0
        fi
      fi
    fi
    sleep $(( i * 10 + RANDOM % 10 ))
  done
  echo "push to $branch failed after 6 attempts" >&2
  exit 1
fi

for i in 1 2 3 4 5 6; do
  if git pull --rebase --autostash origin "$branch" && git push origin "HEAD:$branch"; then
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep $(( i * 10 + RANDOM % 10 ))
done
echo "push to $branch failed after 6 attempts" >&2
exit 1
