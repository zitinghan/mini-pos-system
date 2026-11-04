#!/usr/bin/env bash
# Run as your normal, GitHub-authenticated user. No password or token arguments needed.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
bundle_path="$project_root/artifacts/mini-pos-system.bundle"
remote_url='https://github.com/zitinghan/mini-pos-system.git'
command -v gh >/dev/null || { echo 'GitHub CLI is required: install gh and run gh auth login.' >&2; exit 1; }
test -f "$bundle_path" || { echo 'Prepared Git bundle not found.' >&2; exit 1; }
gh auth status --hostname github.com
gh auth setup-git --hostname github.com
publish_dir="$(mktemp -d "${TMPDIR:-/tmp}/keke-publish.XXXXXXXX")"
# Retain this checkout on failure so nothing prepared for publication is lost.
printf 'Upload checkout: %s\n' "$publish_dir"
git clone --branch codex/initial-pos-mvp "$bundle_path" "$publish_dir"
git -C "$publish_dir" remote set-url origin "$remote_url"
snapshot_sha="$(git -C "$publish_dir" rev-parse HEAD)"
remote_heads="$(git -C "$publish_dir" ls-remote --heads origin)"
if [[ -z "$remote_heads" ]]; then
  publish_branch='main'
else
  git -C "$publish_dir" fetch origin
  default_ref="$(git -C "$publish_dir" ls-remote --symref origin HEAD | awk '/^ref:/ {print $2; exit}')"
  if [[ -z "$default_ref" ]]; then
    echo 'Remote default branch could not be determined. No remote changes made.' >&2
    exit 1
  fi
  default_branch="${default_ref#refs/heads/}"
  publish_branch="upload/keke-mvp-$(date -u +%Y%m%d%H%M%S)-${snapshot_sha:0:8}"
  git -C "$publish_dir" ls-tree -rz --name-only "$snapshot_sha" > "$publish_dir/.git/publish-files"
  git -C "$publish_dir" switch --create "$publish_branch" "refs/remotes/origin/$default_branch"
  # Overlay only prepared source files. Other remote files remain in the new branch.
  git -C "$publish_dir" restore --source "$snapshot_sha" --staged --worktree --pathspec-from-file="$publish_dir/.git/publish-files" --pathspec-file-nul
  if ! git -C "$publish_dir" diff --cached --quiet; then
    author_login="$(gh api user --jq .login)"
    author_email="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
    git -C "$publish_dir" -c "user.name=$author_login" -c "user.email=$author_email" commit -m 'Add KEKE WANTAN MEE POS implementation and documentation'
  fi
fi
# No force update; a conflicting remote update is rejected by Git.
git -C "$publish_dir" push --set-upstream origin "HEAD:refs/heads/$publish_branch"
local_sha="$(git -C "$publish_dir" rev-parse HEAD)"
remote_sha="$(git -C "$publish_dir" ls-remote origin "refs/heads/$publish_branch" | awk '{print $1}')"
[[ "$local_sha" == "$remote_sha" ]] || { echo 'Remote verification failed.' >&2; exit 1; }
python3 - "$project_root/artifacts/upload-status.json" "$publish_branch" "$remote_sha" <<'PY'
import json,sys
from pathlib import Path
path=Path(sys.argv[1])
status=json.loads(path.read_text())
status.update(uploaded=True, published_branch=sys.argv[2], published_commit=sys.argv[3])
status.pop('upload_error',None)
path.write_text(json.dumps(status,indent=2)+'\n')
PY
printf 'Verified upload: %s\nBranch: %s\nCommit: %s\n' "$remote_url" "$publish_branch" "$remote_sha"
