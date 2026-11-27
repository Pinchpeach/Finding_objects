#!/usr/bin/env bash
# Push the workflow's data commit to the branch it runs on, retrying when
# another workflow pushed in between (seen as "cannot lock ref" / non-fast-
# forward).  Used by every workflow that commits generated data.
#
# A retry cannot resolve a content conflict: when another run has rewritten the same generated file (the scientific cross validation rewrites its
# predictions and summary tables in whole), every attempt fails the same way (run 46050644800, 2026-11-27: six rebase conflicts in a row).
# PUSH_PREFER=ours makes the commit of THIS run win: instead of a rebase, each attempt starts from the remote branch and writes back the complete
# content of every file this run's commit touched, then commits it again with the same message.  A hunk-level resolution (``-X theirs``) is not
# enough: it keeps the other run's non-conflicting hunks, so a regenerated report would mix two runs (Codex review of 2.62.0).  Files the commit
# did not touch keep the remote's content.  Only for files that this run regenerates in full; the default is unchanged.
set -uo pipefail
branch="${1:-${GITHUB_REF_NAME}}"

if [ "${PUSH_PREFER:-}" = "ours" ]; then
  msg="$(git log -1 --format=%B)"
  mapfile -d '' -t paths < <(git diff -z --name-only HEAD~1 HEAD)  # NUL-separated: no quoting of unusual file names
  keep="$(mktemp -d)"
  for p in "${paths[@]}"; do
    if git cat-file -e "HEAD:$p" 2>/dev/null; then
      mkdir -p "$keep/$(dirname "$p")"
      git cat-file blob "HEAD:$p" > "$keep/$p"
    fi
  done
  for i in 1 2 3 4 5 6; do
    if git fetch -q origin "$branch" && git reset -q --hard FETCH_HEAD; then
      for p in "${paths[@]}"; do
        if [ -f "$keep/$p" ]; then
          mkdir -p "$(dirname "$p")"
          cp "$keep/$p" "$p"
          git add -- "$p"
        else
          git rm -q --ignore-unmatch -- "$p"  # the commit deleted it
        fi
      done
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
