#!/usr/bin/env bash
set -euo pipefail

./.cicd/scripts/ci.sh
python3 -m json.tool .tmp/generated/backrest-config.json >/dev/null
