import subprocess
import unittest
from unittest.mock import patch

from ftscheduler.scheduler import parse_cron_expression, push_data_repo


class SchedulerTests(unittest.TestCase):
    def test_parse_cron_expression_rejects_invalid(self):
        with self.assertRaises(ValueError):
            parse_cron_expression("* * *")

    @patch("ftscheduler.scheduler.run_command")
    @patch("ftscheduler.scheduler.subprocess.run")
    def test_push_data_repo_pushes_when_staged_changes(self, mock_subprocess_run, mock_run_command):
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=1, stdout="", stderr=""
        )

        league = {
            "name": "test-league",
            "push": {
                "repo_path": "/tmp/repo",
                "branch": "main",
                "commit_message": "Refresh {league_name}",
            },
        }

        push_data_repo(league, github_defaults={})

        executed = [call.args[0] for call in mock_run_command.call_args_list]
        self.assertIn("git -C /tmp/repo add .", executed)
        self.assertIn("git -C /tmp/repo commit -m 'Refresh test-league'", executed)
        self.assertIn("git -C /tmp/repo push origin main", executed)


if __name__ == "__main__":
    unittest.main()
