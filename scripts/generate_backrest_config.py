#!/usr/bin/env python3
import json
import os
import re
import shlex
import sys

from tailsafe_site import expand_env, load_site, outbound_remotes, plan_id, source_destination_ids

VALID_GUID_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


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


def is_valid_guid(value: str) -> bool:
    return bool(VALID_GUID_PATTERN.match(value))


def load_existing_repo_guids(output_path: str) -> dict[str, str]:
    if not os.path.exists(output_path):
        return {}
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    guids: dict[str, str] = {}
    for repo in existing.get("repos", []):
        repo_id = repo.get("id")
        guid = repo.get("guid")
        if repo_id and isinstance(guid, str) and is_valid_guid(guid):
            guids[repo_id] = guid
    return guids


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
    existing_guid: str | None = None,
) -> dict:
    repo = {
        "id": repo_id,
        "uri": expand_env(uri, url_encode=True),
        "password": expand_env(password),
        "env": [],
        "flags": [],
        "autoUnlock": False,
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
    if existing_guid:
        repo["guid"] = existing_guid
        repo["autoInitialize"] = False
    else:
        repo["autoInitialize"] = True
    return repo


def make_plan(
    plan_name: str,
    remote_backup_repo: str,
    source: dict,
    backup_cron: str,
    base_dir: str,
) -> dict:
    hooks = [preflight_hook(source["id"], source["paths"], base_dir)]
    backup_url = source.get("healthchecks", {}).get("backup")
    if backup_url:
        hooks.append(
            healthcheck_hook(
                [
                    "CONDITION_SNAPSHOT_START",
                    "CONDITION_SNAPSHOT_SUCCESS",
                    "CONDITION_SNAPSHOT_ERROR",
                ],
                backup_url,
            )
        )

    return {
        "id": plan_name,
        "repo": remote_backup_repo,
        "paths": source["paths"],
        "excludes": source.get("excludes", []),
        "iexcludes": [],
        "schedule": schedule(source.get("backupCron", backup_cron)),
        "retention": {"policyKeepAll": True},
        "backup_flags": [],
        "skipIfUnchanged": True,
        "hooks": hooks,
    }


def main(input_path: str, output_path: str) -> None:
    site = load_site(input_path)
    remotes = outbound_remotes(site)
    defaults = site["defaults"]
    backrest_generated_dir = generated_dir()
    existing_guids = load_existing_repo_guids(output_path)
    remote_backup_repo_ids: dict[str, str] = {}
    repos: list[dict] = []

    for remote in remotes:
        remote_id = remote["id"]
        retention = remote.get("retention", defaults["retention"])
        check_cron = remote.get("checkCron", defaults["checkCron"])
        forget_cron = remote.get("forgetCron", defaults["forgetCron"])
        prune_cron = remote.get("pruneCron", defaults["pruneCron"])
        backup_repo_id = f"{remote_id}-backup"
        maintenance_repo_id = f"{remote_id}-maintenance"
        remote_backup_repo_ids[remote_id] = backup_repo_id

        maintenance_hooks = [
            healthcheck_hook(
                [
                    "CONDITION_CHECK_START",
                    "CONDITION_CHECK_SUCCESS",
                    "CONDITION_CHECK_ERROR",
                ],
                remote["healthchecks"]["check"],
            ),
            healthcheck_hook(
                [
                    "CONDITION_FORGET_START",
                    "CONDITION_FORGET_SUCCESS",
                    "CONDITION_FORGET_ERROR",
                ],
                remote["healthchecks"]["forget"],
            ),
            healthcheck_hook(
                [
                    "CONDITION_PRUNE_START",
                    "CONDITION_PRUNE_SUCCESS",
                    "CONDITION_PRUNE_ERROR",
                ],
                remote["healthchecks"]["prune"],
            ),
        ]

        repos.extend(
            [
                make_repo(
                    backup_repo_id,
                    remote["backupUri"],
                    remote["repositoryPassword"],
                    retention,
                    check_cron,
                    forget_cron,
                    prune_cron,
                    [],
                    maintenance=False,
                    existing_guid=existing_guids.get(backup_repo_id),
                ),
                make_repo(
                    maintenance_repo_id,
                    remote["maintenanceUri"],
                    remote["repositoryPassword"],
                    retention,
                    check_cron,
                    forget_cron,
                    prune_cron,
                    maintenance_hooks,
                    maintenance=True,
                    existing_guid=existing_guids.get(maintenance_repo_id),
                ),
            ]
        )

    plans: list[dict] = []
    remote_ids = [remote["id"] for remote in remotes]
    for source in site["sources"]:
        destinations = source_destination_ids(source, remote_ids)
        for destination in destinations:
            plans.append(
                make_plan(
                    plan_id(source["id"], destinations, destination),
                    remote_backup_repo_ids[destination],
                    source,
                    defaults["backupCron"],
                    backrest_generated_dir,
                )
            )

    config = {
        "modno": 1,
        "version": 4,
        "instance": site["instance"],
        "auth": {
            "disabled": site["auth"].get("disabled", False),
            "users": site["auth"].get("users", []),
        },
        "repos": repos,
        "plans": plans,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_backrest_config.py <input.json> <output.json>")
    main(sys.argv[1], sys.argv[2])
