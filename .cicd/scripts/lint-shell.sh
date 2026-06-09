#!/usr/bin/env bash
set -euo pipefail
shellcheck .cicd/scripts/*.sh scripts/*.sh containers/configurator/entrypoint.sh
