#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

echo "Compiling Tailwind CSS..."
npm run build:css
echo "CSS build complete: src/hermes_cti/portal/static/portal.css"
