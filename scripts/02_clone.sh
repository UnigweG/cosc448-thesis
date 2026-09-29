#!/usr/bin/env bash
# Full clones (with history) of the repos in config/repo_selection.txt.
# Existing clones are fetched instead. Every clone is made push-proof.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SELECTION="$ROOT/config/repo_selection.txt"
LOG_DIR="$ROOT/logs"
FAIL_LOG="$LOG_DIR/clone_failures.log"
mkdir -p "$LOG_DIR"

year_of() {
  case "$1" in
    COSC-499-W2023) echo 2023 ;;
    COSC-499-W2024) echo 2024 ;;
    COSC-499-W2025) echo 2025 ;;
    *) echo unknown ;;
  esac
}

lock_push() {
  local dir="$1" remote
  # gh adds an "upstream" remote for forks, so lock every remote, not just origin
  for remote in $(git -C "$dir" remote); do
    git -C "$dir" remote set-url --push "$remote" DISABLED
  done
  printf '#!/bin/sh\necho "push disabled for this clone" >&2\nexit 1\n' > "$dir/.git/hooks/pre-push"
  chmod +x "$dir/.git/hooks/pre-push"
}

fetch_prs() {
  # the head of every pull request, including PRs whose branch was deleted; kept under
  # refs/pull/ so HEAD and the branch list do not change
  local full="$1" dest="$2" out
  out="$(git -C "$dest" fetch --quiet origin '+refs/pull/*/head:refs/pull/*/head' 2>&1)" || {
    echo "$full PR fetch failed: $(echo "$out" | tail -1)" >> "$FAIL_LOG"
    echo "FAIL $full"
    return 1
  }
}

clone_one() {
  local full="$1" org repo year dest out
  org="${full%%/*}"
  repo="${full#*/}"
  year="$(year_of "$org")"
  dest="$ROOT/data/repos/$year/$repo"
  if [ -d "$dest/.git" ]; then
    lock_push "$dest"
    out="$(git -C "$dest" fetch --all --tags --prune 2>&1)" || {
      echo "$full fetch failed: $(echo "$out" | tail -1)" >> "$FAIL_LOG"
      echo "FAIL $full"
      return 0
    }
    fetch_prs "$full" "$dest" || return 0
    echo "fetched $full"
  else
    mkdir -p "$(dirname "$dest")"
    out="$(gh repo clone "$full" "$dest" -- --quiet 2>&1)" || {
      echo "$full clone failed: $(echo "$out" | tail -1)" >> "$FAIL_LOG"
      echo "FAIL $full"
      return 0
    }
    lock_push "$dest"
    fetch_prs "$full" "$dest" || return 0
    echo "cloned $full"
  fi
}
export -f clone_one fetch_prs lock_push year_of
export ROOT FAIL_LOG

run_list() {
  xargs -P 8 -I{} bash -c 'clone_one "$@"' _ {}
}

: > "$FAIL_LOG"
grep -vE '^\s*(#|$)' "$SELECTION" | run_list

if [ -s "$FAIL_LOG" ]; then
  # private repos the account can't read: git says "Repository not found", gh says
  # "Could not resolve to a Repository"
  auth='auth|permission denied|could not read username|repository not found'
  auth="$auth|could not resolve to a repository|403|401"
  if grep -qiE "$auth" "$FAIL_LOG"; then
    echo "authentication problem, stopping (see logs/clone_failures.log)" >&2
    exit 2
  fi
  echo "retrying $(wc -l < "$FAIL_LOG" | tr -d ' ') failed repo(s) once"
  failed="$(cut -d' ' -f1 "$FAIL_LOG" | sort -u)"
  mv "$FAIL_LOG" "$FAIL_LOG.first"
  : > "$FAIL_LOG"
  for full in $failed; do
    # a half-finished clone would block the retry; only remove it inside data/repos
    org="${full%%/*}"; repo="${full#*/}"
    dest="$ROOT/data/repos/$(year_of "$org")/$repo"
    if [ -n "$repo" ] && [ -d "$dest" ] && [ ! -d "$dest/.git" ]; then
      rm -rf -- "$dest"
    fi
  done
  printf '%s\n' $failed | run_list
fi

failures="$(grep -c . "$FAIL_LOG" || true)"
echo "failures after retry: $failures"
[ "$failures" -eq 0 ] || exit 1
