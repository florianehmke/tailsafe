#!/usr/bin/env python3
import json
import os
import re
import shlex
import sys
import uuid
from urllib.parse import quote

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def expand_env(value: str, *, url_encode: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in os.environ:
            raise KeyError(f"missing environment variable: {key}")
        env_value = os.environ[key]
        if url_encode:
            return quote(env_value, safe="")
        return env_value

    return ENV_PATTERN.sub(replace, value)


def schedule(cron: str) -> dict:
    return {"cron": cron, "clock": "CLOCK_LOCAL"}


def disabled_schedule() -> dict:
    return {"disabled": True, "clock": "CLOCK_LOCAL"}


def retention_policy(retention: dict) -> dict:
    return {
        "policyTimeBucketed": {
            "daily": retention["daily"],
            "weekly": retention["weekly"],
            "monthly": retention["monthly"],
            "yearly": retention["yearly"],
        }
    }


def healthcheck_hook(conditions: list[str], url: str) -> dict:
    return {
        "conditions": conditions,
        "onError": "ON_ERROR_IGNORE",
        "actionHealthchecks": {"webhookUrl": url},
    }


def generated_dir() -> str:
    return os.environ.get("TAILSAFE_BACKREST_GENERATED_DIR", "/generated")


def preflight_hook(source_id: str, paths: list[str], base_dir: str) -> dict:
    quoted_paths = " ".join(shlex.quote(path) for path in paths)
    return {
        "conditions": ["CONDITION_SNAPSHOT_START"],
        "onError": "ON_ERROR_FATAL",
        "actionCommand": {
            "command": f"{base_dir}/bin/preflight.sh {shlex.quote(source_id)} {quoted_paths}"
        },
    }


def make_repo(
    repo_id: str,
    uri: str,
    password: str,
    retention: dict,
    check_cron: str,
    forget_cron: str,
    prune_cron: str,
    hooks: list[dict],
    maintenance: bool,
) -> dict:
    return {
        "id": repo_id,
        "guid": str(uuid.uuid5(uuid.NAMESPACE_DNS, repo_id)),
        "uri": expand_env(uri, url_encode=True),
        "password": expand_env(password),
        "env": [],
        "flags": [],
        "autoUnlock": False,
        "autoInitialize": True,
        "commandPrefix": {"ioNice": "IO_BEST_EFFORT_LOW", "cpuNice": "CPU_LOW"},
        "hooks": hooks,
        "checkPolicy": {
            "schedule": schedule(check_cron) if maintenance else disabled_schedule(),
            "readDataSubsetPercent": 10,
        },
        "prunePolicy": {
            "schedule": schedule(prune_cron) if maintenance else disabled_schedule(),
            "maxUnusedPercent": 10,
        },
        "forgetPolicy": {
            "schedule": schedule(forget_cron) if maintenance else disabled_schedule(),
            "retention": retention_policy(retention),
        },
    }


def make_plan(remote_backup_repo: str, source: dict, backup_cron: str, base_dir: str) -> dict:
    return {
        "id": source["id"],
        "repo": remote_backup_repo,
        "paths": source["paths"],
        "excludes": source.get("excludes", []),
        "iexcludes": [],
        "schedule": schedule(source.get("backupCron", backup_cron)),
        "retention": {"policyKeepAll": True},
        "backup_flags": [],
        "skipIfUnchanged": True,
        "hooks": [
            preflight_hook(source["id"], source["paths"], base_dir),
            healthcheck_hook(
                [
                    "CONDITION_SNAPSHOT_START",
                    "CONDITION_SNAPSHOT_SUCCESS",
                    "CONDITION_SNAPSHOT_ERROR",
                ],
                source["healthchecks"]["backup"],
            ),
        ],
    }


def main(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as handle:
        site = json.load(handle)

    remote_id = site["remote"]["id"]
    defaults = site["defaults"]
    retention = defaults["retention"]
    backup_repo_id = f"{remote_id}-backup"
    maintenance_repo_id = f"{remote_id}-maintenance"
    backrest_generated_dir = generated_dir()

    maintenance_hooks = [
        healthcheck_hook(
            ["CONDITION_CHECK_START", "CONDITION_CHECK_SUCCESS", "CONDITION_CHECK_ERROR"],
            site["healthchecks"]["check"],
        ),
        healthcheck_hook(
            ["CONDITION_FORGET_START", "CONDITION_FORGET_SUCCESS", "CONDITION_FORGET_ERROR"],
            site["healthchecks"]["forget"],
        ),
        healthcheck_hook(
            ["CONDITION_PRUNE_START", "CONDITION_PRUNE_SUCCESS", "CONDITION_PRUNE_ERROR"],
            site["healthchecks"]["prune"],
        ),
    ]

    config = {
        "modno": 1,
        "version": 4,
        "instance": site["instance"],
        "auth": {
            "disabled": site["auth"].get("disabled", False),
            "users": site["auth"].get("users", []),
        },
        "repos": [
            make_repo(
                backup_repo_id,
                site["remote"]["backupUri"],
                site["remote"]["repositoryPassword"],
                retention,
                defaults["checkCron"],
                defaults["forgetCron"],
                defaults["pruneCron"],
                [],
                maintenance=False,
            ),
            make_repo(
                maintenance_repo_id,
                site["remote"]["maintenanceUri"],
                site["remote"]["repositoryPassword"],
                retention,
                defaults["checkCron"],
                defaults["forgetCron"],
                defaults["pruneCron"],
                maintenance_hooks,
                maintenance=True,
            ),
        ],
        "plans": [
            make_plan(
                backup_repo_id,
                source,
                defaults["backupCron"],
                backrest_generated_dir,
            )
            for source in site["sources"]
        ],
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_backrest_config.py <input.json> <output.json>")
    main(sys.argv[1], sys.argv[2])
