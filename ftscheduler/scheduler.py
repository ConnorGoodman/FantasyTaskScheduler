from __future__ import annotations

import argparse
import datetime as dt
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

LOGGER = logging.getLogger("ftscheduler")


class MissingConfigError(ValueError):
    pass


def load_config(config_path: str) -> dict[str, Any]:
    with Path(config_path).open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file) or {}

    leagues = data.get("leagues")
    if not isinstance(leagues, list) or not leagues:
        raise MissingConfigError("Config must include a non-empty 'leagues' list")

    return data


def parse_cron_expression(expression: str) -> CronTrigger:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression '{expression}'")

    minute, hour, day, month, day_of_week = fields
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )


def _render(template: str, context: dict[str, Any]) -> str:
    return template.format_map(context)


def run_command(command: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    LOGGER.info("Running command: %s", command)
    return subprocess.run(
        shlex.split(command),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _build_context(league: dict[str, Any]) -> dict[str, Any]:
    timestamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    context = {
        "timestamp": timestamp,
        "league_name": league.get("name", "unknown"),
        "league_id": league.get("league_id", ""),
    }
    context.update(league)
    return context


def run_export(league: dict[str, Any]) -> None:
    exporter = league.get("exporter", {})
    command = exporter.get("command")
    if not command:
        raise MissingConfigError(f"League '{league.get('name')}' missing exporter.command")

    context = _build_context(league)
    rendered = _render(command, context)
    run_command(rendered, cwd=exporter.get("working_dir"))


def push_data_repo(league: dict[str, Any], github_defaults: dict[str, Any]) -> None:
    push = league.get("push", {})
    if not push.get("enabled", True):
        LOGGER.info("Push disabled for league '%s'", league.get("name"))
        return

    repo_path = push.get("repo_path")
    if not repo_path:
        raise MissingConfigError(f"League '{league.get('name')}' missing push.repo_path")

    branch = push.get("branch", "main")
    context = _build_context(league)
    commit_message = _render(
        push.get("commit_message", "Refresh fantasy data for {league_name} @ {timestamp}"),
        context,
    )

    user_name = push.get("user_name") or github_defaults.get("user_name")
    user_email = push.get("user_email") or github_defaults.get("user_email")

    if user_name:
        run_command(f"git -C {shlex.quote(repo_path)} config user.name {shlex.quote(user_name)}")
    if user_email:
        run_command(f"git -C {shlex.quote(repo_path)} config user.email {shlex.quote(user_email)}")

    run_command(f"git -C {shlex.quote(repo_path)} add .")

    staged = subprocess.run(
        ["git", "-C", repo_path, "diff", "--cached", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )

    if staged.returncode == 0:
        LOGGER.info("No changes to commit for league '%s'", league.get("name"))
        return

    run_command(f"git -C {shlex.quote(repo_path)} commit -m {shlex.quote(commit_message)}")
    run_command(f"git -C {shlex.quote(repo_path)} push origin {shlex.quote(branch)}")


def run_ai_agents(league: dict[str, Any]) -> None:
    ai = league.get("ai", {})
    commands = ai.get("commands", [])
    context = _build_context(league)

    for command in commands:
        rendered = _render(command, context)
        run_command(rendered, cwd=ai.get("working_dir"))


def execute_action(action: str, league: dict[str, Any], github_defaults: dict[str, Any]) -> None:
    if action == "refresh_and_push":
        run_export(league)
        push_data_repo(league, github_defaults)
    elif action == "run_ai_agents":
        run_ai_agents(league)
    else:
        raise MissingConfigError(f"Unknown action '{action}' for league '{league.get('name')}'")


def schedule_jobs(config: dict[str, Any], run_once: bool = False) -> None:
    scheduler = BlockingScheduler(timezone=config.get("timezone", "UTC"))
    github_defaults = config.get("github", {})

    for league in config["leagues"]:
        jobs = league.get("jobs", [])
        if not jobs:
            raise MissingConfigError(f"League '{league.get('name')}' must include a non-empty jobs list")

        for job in jobs:
            action = job.get("action")
            cron = job.get("cron")
            name = job.get("name", action)
            if not action or not cron:
                raise MissingConfigError(
                    f"League '{league.get('name')}' job '{name}' requires action and cron"
                )

            if run_once:
                LOGGER.info("Run-once mode: executing %s for %s", name, league.get("name"))
                execute_action(action, league, github_defaults)
                continue

            trigger = parse_cron_expression(cron)
            scheduler.add_job(
                execute_action,
                trigger=trigger,
                args=[action, league, github_defaults],
                id=f"{league.get('name', 'league')}:{name}",
                replace_existing=True,
            )

    if run_once:
        return

    LOGGER.info("Starting scheduler with %s jobs", len(scheduler.get_jobs()))
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fantasy league cron jobs")
    parser.add_argument("--config", default="/app/config.yml", help="Path to YAML config file")
    parser.add_argument("--run-once", action="store_true", help="Run all configured jobs once and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = load_config(args.config)
    schedule_jobs(config, run_once=args.run_once)


if __name__ == "__main__":
    main()
