from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.actions.result import ActionResult
from src.jobs.base import Job, JobResult
from src.util.logging import Logger
from src.jobs.manager import JobManager
from src.models.base import Asset
from src.backend.database import DBSessionMixin
import json
import os
import pathlib
import asyncio


class SemgrepJob(Job):
    """Job that runs a semgrep scan on a specified path"""

    def __init__(self, path: str):
        super().__init__(job_type="semgrep")
        self.path = path
        self.logger = Logger("SemgrepJob")

        # Get path to rules directory relative to this file
        module_dir = pathlib.Path(__file__).parent
        self.rules_path = os.path.join(module_dir, "semgrep-rules")

    async def start(self) -> None:
        """Start the semgrep scan"""
        try:
            # Build semgrep command
            cmd = ["semgrep", "--config", self.rules_path, "--json", self.path]

            # Run semgrep
            self.logger.info(f"Running semgrep on {self.path} with rules from {self.rules_path}")
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                await self.fail(f"Semgrep failed: {error_msg}")
                return

            # Parse JSON output
            try:
                results = json.loads(stdout.decode())
                findings = results.get("results", [])
                total = len(findings)

                # Create result message
                if total > 0:
                    message = f"Found {total} potential issue(s) in {self.path}"
                    # Add severity counts
                    severity_counts = {}
                    for finding in findings:
                        severity = finding.get("extra", {}).get("severity", "unknown")
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

                    if severity_counts:
                        message += "\nSeverity breakdown:"
                        for severity, count in severity_counts.items():
                            message += f"\n- {severity}: {count}"
                else:
                    message = f"No issues found in {self.path}"

                # Create job result
                result = JobResult(success=True, message=message, data=results)

                # Add detailed outputs for each finding
                for finding in findings:
                    output = (
                        f"Finding in {finding.get('path')}:\n"
                        f"Rule: {finding.get('check_id')}\n"
                        f"Severity: {finding.get('extra', {}).get('severity', 'unknown')}\n"
                        f"Line: {finding.get('start', {}).get('line')}\n"
                        f"Message: {finding.get('extra', {}).get('message')}\n"
                        f"Code: {finding.get('extra', {}).get('lines')}\n"
                    )
                    result.add_output(output)

                await self.complete(result)

            except json.JSONDecodeError as e:
                await self.fail(f"Failed to parse semgrep output: {e}")

        except Exception as e:
            self.logger.error(f"Error in semgrep job: {e}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Stop the job - nothing to do for semgrep"""
        pass


class SemgrepAction(BaseAction, DBSessionMixin):
    """Action that runs a semgrep scan on a specified asset"""

    spec = ActionSpec(
        name="semgrep",
        description="Run a semgrep scan on a specified asset",
        help_text="Runs semgrep security scanner on the specified asset using configured rules",
        agent_hint="Use this to scan code for potential security issues",
        arguments=[ActionArgument(name="asset", description="Asset to scan", required=True)],
    )

    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("SemgrepAction")
        self.job_manager = JobManager()

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the semgrep scan action"""
        try:
            # Get asset name from args
            asset_id = args[0]

            # Get asset from database
            with self.get_session() as session:
                asset = session.query(Asset).filter(Asset.id == asset_id).first()
                if not asset:
                    return ActionResult.error(f"Asset not found: {asset_id}")

                # Get local file path
                local_path = asset.local_path
                if not local_path:
                    return ActionResult.error(f"Asset {asset_id} has no local file path")

            # Create and submit the semgrep job
            job = SemgrepJob(local_path)
            job_id = await self.job_manager.submit_job(job)

            return ActionResult.text(f"Semgrep scan started with job ID: {job_id}\nUse 'job {job_id}' to check results.")

        except Exception as e:
            self.logger.error(f"Failed to start semgrep scan: {str(e)}")
            return ActionResult.error(f"Failed to start semgrep scan: {str(e)}")
