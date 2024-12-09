import logging
from typing import Dict, Any

from src.agents.llm_base import LLMBase

logger = logging.getLogger(__name__)


class GithubEventAgent(LLMBase):
    """Agent for analyzing GitHub events for security implications"""

    def __init__(self):
        super().__init__()
        self.custom_prompt = """You are a security researcher analyzing GitHub events. For each analysis:

1. Provide a single paragraph summarizing the change and its potential security relevance
2. On a new line, add "Security Impact: Yes" or "Security Impact: No"

Focus on smart contract security, access control, state modifications, and potential vulnerabilities.
Be concise and direct in your analysis."""

    def _process_analysis(self, response: str) -> Dict[str, Any]:
        """Process the LLM response and extract analysis and security impact"""
        try:
            # Split on newline to separate analysis from security impact
            parts = response.strip().split("\n")

            # If we have at least one line
            if len(parts) > 0:
                # If we have multiple lines, join all but the last
                if len(parts) > 1:
                    analysis = "\n".join(parts[:-1]).strip()
                    has_security_impact = "Security Impact: Yes" in parts[-1]
                else:
                    # Single line response - need to remove the "Security Impact" part
                    text = parts[0]
                    has_security_impact = "Security Impact: Yes" in text

                    # Remove the security impact text
                    if "Security Impact: Yes" in text:
                        analysis = text.replace("Security Impact: Yes", "").strip()
                    elif "Security Impact: No" in text:
                        analysis = text.replace("Security Impact: No", "").strip()
                    else:
                        # If no security impact marker is found, this is an error
                        logger.error("No security impact marker found in response")
                        return {
                            "has_security_impact": False,
                            "analysis": "Error processing analysis: Missing security impact marker",
                        }

                # If we ended up with empty analysis after removing security impact
                if not analysis:
                    analysis = "No analysis provided"

                return {"has_security_impact": has_security_impact, "analysis": analysis}

            # Empty response
            logger.error("Empty response from LLM")
            return {"has_security_impact": False, "analysis": "Error processing analysis: Empty response"}

        except Exception as e:
            logger.error(f"Error processing analysis: {e}")
            return {"has_security_impact": False, "analysis": "Error processing analysis"}

    async def analyze_pr(self, repo_url: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a pull request for security implications"""
        # Prepare the content for analysis
        pr_content = f"""
Repository: {repo_url}
Title: {pr_data.get('title')}
Description: {pr_data.get('body', 'No description')}
Changed Files: {pr_data.get('changed_files', 0)}
Additions: {pr_data.get('additions', 0)}
Deletions: {pr_data.get('deletions', 0)}
"""
        # Get the analysis from the LLM
        prompt = (
            "Analyze this pull request and provide a single sentence summary of the "
            "change and potential security impact, if any. Always end with "
            "'Security Impact: Yes' or 'Security Impact: No':"
        )
        response = await self.chat_completion([{"role": "user", "content": f"{prompt}\n{pr_content}"}])

        return self._process_analysis(response)

    async def analyze_commit(self, repo_url: str, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a commit for security implications"""
        # Prepare the content for analysis
        commit_content = f"""
Repository: {repo_url}
Message: {commit_data.get('commit', {}).get('message', 'No message')}
Author: {commit_data.get('commit', {}).get('author', {}).get('name', 'Unknown')}
URL: {commit_data.get('html_url', '')}
"""
        # Get the analysis from the LLM
        prompt = (
            "Analyze this commit and provide a single sentence summary of the "
            "change and potential security impact, if any. Always end with "
            "'Security Impact: Yes' or 'Security Impact: No':"
        )
        response = await self.chat_completion([{"role": "user", "content": f"{prompt}\n{commit_content}"}])

        return self._process_analysis(response)
