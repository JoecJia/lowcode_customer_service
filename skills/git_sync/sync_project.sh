set -euo pipefail

mode="${1:-sync}"
commit_message="${2:-Update}"
remote_url="${3:-git@github.com:JoecJia/lowcode_customer_service.git}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/../.." && pwd)"
cd "${project_root}"

command -v git >/dev/null 2>&1

if [ ! -d ".git" ]; then
  git init >/dev/null
fi

git branch -M main >/dev/null 2>&1 || true

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "${remote_url}" >/dev/null
else
  git remote add origin "${remote_url}" >/dev/null
fi

if [ "${mode}" = "pull" ]; then
  git pull --rebase --autostash origin main
  printf "%s\n" ">>> Pull Complete!"
  exit 0
fi

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "${commit_message}"
fi

git pull --rebase origin main

if [ "${mode}" = "push" ] || [ "${mode}" = "sync" ]; then
  git push origin main
  printf "%s\n" ">>> Sync Complete!"
fi
