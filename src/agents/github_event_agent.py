from typing import Dict, Any, Optional
from src.agents.base_agent import BaseAgent, AgentResult
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from sqlalchemy import or_


class GithubEventAgent(BaseAgent, DBSessionMixin):
    """Agent specialized in analyzing GitHub events for security implications"""

    def __init__(self):
        # Add specialized prompt for security analysis
        custom_prompt = """You are specialized in analyzing GitHub pull requests and commits for security implications.

Your responsibilities:
1. Analyze code changes for potential security impacts
2. Identify patterns that match known vulnerability types
3. Link changes to relevant bounty program scope and rules
4. Generate clear, actionable summaries for security researchers

Focus areas:
- Smart contract vulnerabilities (reentrancy, access control, etc.)
- Protocol design issues
- Integration and dependency risks
- Gas optimization problems
- Potential economic attack vectors

You have access to several commands to help with your analysis:
- /semantic_search to find similar vulnerabilities
- /grep_search to find specific code patterns
- /file_search to locate relevant files"""

        # Specify commands this agent can use
        command_names = []

        # Initialize both base classes
        BaseAgent.__init__(self, custom_prompt=custom_prompt, command_names=command_names)
        DBSessionMixin.__init__(self)

    def find_related_asset(self, repo_url: str) -> Optional[tuple[Asset, Project]]:
        """Find an asset and its project related to the given repo URL"""
        try:
            with self.get_session() as session:
                # Clean up the URL for comparison
                repo_url = repo_url.rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]

                # Query for assets with matching repo_url
                asset = (
                    session.query(Asset)
                    .filter(
                        or_(
                            Asset.source_url.like(f"{repo_url}%"),
                        )
                    )
                    .first()
                )

                if asset:
                    # Get the first associated project
                    project = session.query(Project).join(Project.assets).filter(Asset.id == asset.id).first()
                    return asset, project

                return None

        except Exception as e:
            self.logger.error(f"Error searching for related asset: {str(e)}")
            return None

    async def analyze_pr(self, repo_url: str, pr_data: Dict[str, Any]) -> str:
        """Analyze a pull request for security implications"""
        try:
            # Find related asset and project
            asset_info = self.find_related_asset(repo_url)

            # Prepare event data
            event_data = {
                "event_type": "pr",
                "event_data": {
                    "repository": repo_url,
                    "number": pr_data.get("number"),
                    "title": pr_data.get("title"),
                    "body": pr_data.get("body", ""),
                    "changes": pr_data,  # Full PR data for analysis
                },
            }

            # Add project context if available
            if asset_info:
                asset, project = asset_info
                event_data["event_data"]["project"] = {
                    "name": project.name,
                    "type": project.project_type,
                    "description": project.description,
                }

            # Execute analysis task
            result = await self.execute_task(event_data)
            if result.success and result.data:
                return result.data.get("result", {}).get("analysis", "No analysis available")
            else:
                return f"Analysis failed: {result.error}"

        except Exception as e:
            self.logger.error(f"Failed to analyze PR: {str(e)}")
            return f"Error analyzing PR: {str(e)}"

    async def analyze_commit(self, repo_url: str, commit_data: Dict[str, Any]) -> str:
        """Analyze a commit for security implications"""
        try:
            # Find related asset and project
            asset_info = self.find_related_asset(repo_url)

            # Prepare event data
            event_data = {
                "event_type": "commit",
                "event_data": {
                    "repository": repo_url,
                    "sha": commit_data.get("sha"),
                    "message": commit_data.get("commit", {}).get("message", ""),
                    "changes": commit_data,  # Full commit data for analysis
                },
            }

            # Add project context if available
            if asset_info:
                asset, project = asset_info
                event_data["event_data"]["project"] = {
                    "name": project.name,
                    "type": project.project_type,
                    "description": project.description,
                }

            # Execute analysis task
            result = await self.execute_task(event_data)
            if result.success and result.data:
                return result.data.get("result", {}).get("analysis", "No analysis available")
            else:
                return f"Analysis failed: {result.error}"

        except Exception as e:
            self.logger.error(f"Failed to analyze commit: {str(e)}")
            return f"Error analyzing commit: {str(e)}"

    async def execute_step(self) -> AgentResult:
        """Execute a single step based on current state"""
        current_state = self.state
        event_type = current_state.get("event_type")
        event_data = current_state.get("event_data", {})

        try:

            # Build analysis context
            context = [
                f"Analyzing {'PR' if event_type == 'pr' else 'commit'} in {event_data.get('repository')}",
                f"Message: {event_data.get('message', 'No message')}",
                f"Changes: {event_data.get('changes', 'No changes provided')}",
            ]

            # Add project context if available
            if "project" in event_data:
                context.extend(
                    [
                        "\nProject Context:",
                        f"Name: {event_data['project']['name']}",
                        f"Type: {event_data['project']['type']}",
                        f"Description: {event_data['project']['description']}",
                    ]
                )

            # Get AI analysis
            prompt = "\n".join(
                [
                    f"Analyze this {event_type} for security implications. Consider:",
                    "1. What is the purpose of these changes?",
                    "2. Are there any potential security impacts?",
                    "3. What specific vulnerabilities should be checked?",
                    "\nContext:",
                    "\n".join(context),
                ]
            )

            messages = [{"role": "user", "content": prompt}]
            analysis = await self.chat_completion(messages)

            # Record the step
            self.record_step(
                action=f"analyze_{event_type}",
                input_data=event_data,
                output_data={"analysis": analysis},
                reasoning="Analyzing changes to identify security implications",
                next_action="complete",
            )

            # Store result
            self.state["result"] = {"type": event_type, "analysis": analysis}

            return AgentResult(success=True)

        except Exception as e:
            return AgentResult(success=False, error=str(e))

    def is_task_complete(self) -> bool:
        """Check if the analysis is complete"""
        return "result" in self.state

    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        if "result" not in current_state:
            event_type = current_state.get("event_type")
            if event_type in ["commit", "pr"]:
                return {"action": f"analyze_{event_type}"}
        return {"action": "complete"}
