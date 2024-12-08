from src.agents.base_agent import BaseAgent
from src.util.logging import Logger
from typing import Dict, Any, Tuple


class ProxyImplementationUpgradeAgent(BaseAgent):
    """Agent for analyzing proxy implementation upgrades"""

    def __init__(self):
        # Add specialized prompt for analyzing proxy upgrades
        custom_prompt = """You are specialized in analyzing proxy implementation upgrades.

Your responsibilities:
1. Analyze new implementation code for changes
2. Identify potential security implications
3. Compare with previous implementations
4. Generate clear summaries for security researchers

You should focus on:
- Storage layout changes
- Function selector changes
- Access control modifications
- State variable modifications
- Critical functionality changes"""

        # Specify commands this agent can use
        command_names = []

        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        self.logger = Logger("ProxyImplementationUpgradeAgent")
        self._source_code = None
        self._analysis = None

    async def plan_next_step(self) -> Tuple[str, Dict[str, Any]]:
        """Plan the next step in the analysis process.

        Returns:
            Tuple of command name and parameters
        """
        if not self._source_code:
            return "wait", {"message": "No source code provided for analysis"}
        if not self._analysis:
            self._analysis = await self.analyze_implementation(self._source_code)
            return "complete", {"analysis": self._analysis}
        return "complete", {"analysis": self._analysis}

    async def execute_step(self, command_name: str, parameters: Dict[str, Any]) -> bool:
        """Execute a step in the analysis process.

        Args:
            command_name: The name of the command to execute
            parameters: The parameters for the command

        Returns:
            Whether the step was executed successfully
        """
        if command_name == "wait":
            return True
        if command_name == "complete":
            return True
        return False

    def is_task_complete(self) -> bool:
        """Check if the analysis task is complete.

        Returns:
            Whether the task is complete
        """
        return self._analysis is not None

    async def analyze_implementation(self, source_code: str) -> Dict[str, Any]:
        """Analyze implementation source code

        Args:
            source_code: The verified source code to analyze

        Returns:
            Dictionary containing analysis results
        """
        self._source_code = source_code
        self.logger.info("Starting implementation analysis")

        prompt = f"""Please analyze this smart contract implementation code and provide:
1. A brief summary of the main functionality
2. Any potential security concerns or critical bugs
3. Storage layout analysis
4. Function selector changes

Source code:
{source_code}

Please format your response in plain text with clear sections:

SUMMARY:
(Write a brief description of the main functionality)

SECURITY CONCERNS:
- First concern
- Second concern
(etc.)

STORAGE ANALYSIS:
(Describe any storage layout changes)

FUNCTION CHANGES:
(List significant function modifications)

RISK LEVEL: (low|medium|high)"""

        self.logger.info("Sending prompt to OpenAI")
        response = await self.chat_completion([{"role": "user", "content": prompt}])
        self.logger.info("Received response from OpenAI", extra_data={"response": response})

        # Parse the response into sections
        sections = response.split("\n\n")
        analysis = {
            "summary": "",
            "security_concerns": [],
            "storage_analysis": "",
            "function_changes": "",
            "risk_level": "unknown",
        }

        for section in sections:
            if section.startswith("SUMMARY:"):
                analysis["summary"] = section.replace("SUMMARY:", "").strip()
            elif section.startswith("SECURITY CONCERNS:"):
                concerns = section.replace("SECURITY CONCERNS:", "").strip().split("\n")
                analysis["security_concerns"] = [c.strip("- ").strip() for c in concerns if c.strip("- ").strip()]
            elif section.startswith("STORAGE ANALYSIS:"):
                analysis["storage_analysis"] = section.replace("STORAGE ANALYSIS:", "").strip()
            elif section.startswith("FUNCTION CHANGES:"):
                analysis["function_changes"] = section.replace("FUNCTION CHANGES:", "").strip()
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

        message = [
            "🔍 Implementation Analysis",
            "",
            f"Risk Level: {risk_emojis.get(analysis.get('risk_level', 'unknown'), '⚪')} {analysis.get('risk_level', 'unknown').upper()}",
            "",
            "📝 Summary:",
            analysis.get("summary", "No summary available"),
            "",
        ]

        security_concerns = analysis.get("security_concerns", [])
        if security_concerns:
            message.extend(["⚠️ Security Concerns:", *[f"• {concern}" for concern in security_concerns], ""])

        storage_analysis = analysis.get("storage_analysis")
        if storage_analysis:
            message.extend(["📦 Storage Analysis:", storage_analysis, ""])

        function_changes = analysis.get("function_changes")
        if function_changes:
            message.extend(["🔧 Function Changes:", function_changes, ""])

        if security_concerns:
            message.extend(
                ["🚨 Recommendation:", "Please review the security concerns carefully before proceeding with the upgrade.", ""]
            )

        return "\n".join(message)


# Function to initialize the agent
def initialize():
    """Initialize the agent"""
    return ProxyImplementationUpgradeAgent()
