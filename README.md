# FantasyTaskScheduler

Container-friendly scheduler that runs configurable cron jobs per fantasy league.

It supports three core tasks from config:
- refresh Sleeper league data by running commands from [`ConnorGoodman/SleeperLeagueExporter`](https://github.com/ConnorGoodman/SleeperLeagueExporter)
- commit + push refreshed data to a configured Git repository
- run follow-up AI agent commands over the saved data

## Configuration

Use `config.example.yml` as a template and mount your real config as `/app/config.yml` in the container.

Each league defines:
- `league_id` and metadata
- `jobs` with cron expressions and actions (`refresh_and_push`, `run_ai_agents`)
- `exporter.command` for refreshes
- `push.repo_path`/`branch` details for git pushes
- `ai.commands` for agent steps

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m ftscheduler --config ./config.example.yml --run-once
```

## Container usage

```bash
docker build -t fantasy-task-scheduler .
docker run --rm \
  -v $(pwd)/config.yml:/app/config.yml:ro \
  fantasy-task-scheduler
```
