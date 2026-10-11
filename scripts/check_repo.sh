#!/bin/bash
# Run from the project root BEFORE the first commit/push.
cd "$(dirname "$0")/.." || exit 1
echo "== Looking for API keys in tracked-able files =="
grep -rnE "[A-Za-z0-9]{40}" --include="*.py" --include="*.md" --include="*.yaml" --include="*.txt" --include="*.sh" . 2>/dev/null | grep -v "^./cache\|^./output" | head
echo "(nothing listed above = good)"
echo
echo "== Hard-coded key patterns =="
grep -rniE "api_key\s*=\s*['\"][A-Za-z0-9]+['\"]" --include="*.py" . | head
echo "(nothing listed above = good)"
echo
echo "== Files git would publish =="
if [ -d .git ]; then
  git add -n . | sed 's/^add //'
else
  echo "No git repo yet. Run: git init && ./scripts/check_repo.sh"
fi
echo
echo "== Must NOT appear above: cache/, output/, config/vendor_categories.yaml =="
