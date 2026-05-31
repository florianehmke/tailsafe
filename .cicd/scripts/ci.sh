#!/usr/bin/env bash
set -euo pipefail
mise run lint:yaml
mise run lint:shell
mise run lint:actions
mise run test
mise run validate:compose
mise run smoke:configurator
