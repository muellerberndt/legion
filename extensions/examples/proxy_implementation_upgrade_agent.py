from src.agents.base_agent import BaseAgent
from src.util.logging import Logger
from typing import Dict, Any
import json

__all__ = ["ProxyImplementationUpgradeAgent"]


class ProxyImplementationUpgradeAgent(BaseAgent):
    """Agent for analyzing proxy implementation upgrades"""

    def __init__(self):
        # Add specialized prompt for analyzing proxy upgrades
        custom_prompt = """You are specialized in analyzing proxy implementation upgrades.

Your responsibilities:
1. Analyze new implementation code for changes
2. Identify potential security implications
3. Compare with previous implementations
4. Generate clear summaries for security researchers"""

        # Specify commands this agent can use
        command_names = []

        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        self.logger = Logger("ProxyImplementationUpgradeAgent")

    async def analyze_implementation(self, source_code: str) -> Dict[str, Any]:
        """Analyze implementation source code

        Args:
            source_code: The verified source code to analyze

        Returns:
            Dictionary containing analysis results
        """
        self.logger.info("Starting implementation analysis")

        # Create prompt for code analysis
        prompt = f"""Please analyze this smart contract implementation code and provide:
1. A brief summary of the main functionality
2. Any potential security concerns or critical bugs

Source code:
{source_code}

Please format your response in plain text with clear sections:

SUMMARY:
(Write a brief description of the main functionality)

SECURITY CONCERNS:
- First concern
- Second concern
(etc.)

RISK LEVEL: (low|medium|high)"""

        self.logger.info("Sending prompt to OpenAI")
        # Get analysis from OpenAI
        response = await self.chat_completion([{"role": "user", "content": prompt}])
        self.logger.info("Received response from OpenAI", extra_data={"response": response})

        # Parse the response into sections
        sections = response.split("\n\n")
        analysis = {"summary": "", "security_concerns": [], "risk_level": "unknown"}

        for section in sections:
            if section.startswith("SUMMARY:"):
                analysis["summary"] = section.replace("SUMMARY:", "").strip()
            elif section.startswith("SECURITY CONCERNS:"):
                concerns = section.replace("SECURITY CONCERNS:", "").strip().split("\n")
                analysis["security_concerns"] = [c.strip("- ").strip() for c in concerns if c.strip("- ").strip()]
            elif section.startswith("RISK LEVEL:"):
                risk_level = section.replace("RISK LEVEL:", "").strip().lower()
                if risk_level in ["low", "medium", "high"]:
                    analysis["risk_level"] = risk_level

        self.logger.info("Parsed analysis", extra_data={"analysis": analysis})
        return analysis

    def format_message(self, proxy_address: str, new_implementation: str, tx_hash: str, in_scope: bool = False) -> str:
        """Format the initial notification message

        Args:
            proxy_address: The proxy contract address
            new_implementation: The new implementation address
            tx_hash: The transaction hash
            in_scope: Whether the contract is in bounty scope

        Returns:
            Formatted message string
        """
        scope_text = "In Bounty Scope " if in_scope else ""
        message = [
            f"🔄 Proxy Implementation Upgrade {scope_text}Detected!",
            "",
            f"Contract: https://etherscan.io/address/{proxy_address}",
            f"New Implementation: https://etherscan.io/address/{new_implementation}",
            f"Transaction: https://etherscan.io/tx/{tx_hash}",
            "",
        ]
        return "\n".join(message)

    def format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results into a readable message

        Args:
            analysis: The analysis results to format

        Returns:
            Formatted message string
        """
        risk_emojis = {"low": "🟢", "medium": "🟡", "high": "🔴", "unknown": "⚪"}

        # Extract and format the summary
        summary = analysis.get("summary", "No summary available")
        if isinstance(summary, dict):
            summary = summary.get("summary", "No summary available")
        elif isinstance(summary, str):
            try:
                # Try to parse if it's a JSON string
                summary_data = json.loads(summary)
                if isinstance(summary_data, dict):
                    summary = summary_data.get("summary", summary)
            except json.JSONDecodeError:
                # If it's not JSON, use as is
                pass

        message = [
            "🔍 Implementation Analysis",
            "",
            f"Risk Level: {risk_emojis.get(analysis.get('risk_level', 'unknown'), '⚪')} {analysis.get('risk_level', 'unknown').upper()}",
            "",
            "📝 Summary:",
            summary,
            "",
        ]

        # Extract and format security concerns
        security_concerns = analysis.get("security_concerns", [])
        if isinstance(security_concerns, dict):
            security_concerns = security_concerns.get("security_concerns", [])
        elif isinstance(security_concerns, str):
            try:
                # Try to parse if it's a JSON string
                concerns_data = json.loads(security_concerns)
                if isinstance(concerns_data, (list, dict)):
                    security_concerns = (
                        concerns_data if isinstance(concerns_data, list) else concerns_data.get("security_concerns", [])
                    )
            except json.JSONDecodeError:
                security_concerns = [security_concerns]

        if security_concerns:
            message.extend(["⚠️ Security Concerns:", *[f"• {concern}" for concern in security_concerns], ""])

            # Add recommendation footer if there are security concerns
            message.extend(
                ["🚨 Recommendation:", "Please review the security concerns carefully before proceeding with the upgrade.", ""]
            )

        return "\n".join(message)


# Function to initialize the agent
def initialize():
    """Initialize the agent"""
    return ProxyImplementationUpgradeAgent()
