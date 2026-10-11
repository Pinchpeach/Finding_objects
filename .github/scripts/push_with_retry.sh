#!/usr/bin/env bash
# Push the workflow's data commit to the branch it runs on, retrying when
# another workflow pushed in between (seen as "cannot lock ref" / non-fast-
# forward).  Used by every workflow that commits generated data.
set -uo pipefail
branch="${1:-${GITHUB_REF_NAME}}"
for i in 1 2 3 4 5 6; do
  if git pull --rebase --autostash origin "$branch" && git push origin "HEAD:$branch"; then
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep $(( i * 10 + RANDOM % 10 ))
done
echo "push to $branch failed after 6 attempts" >&2
exit 1
