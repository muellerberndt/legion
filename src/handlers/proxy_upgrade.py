from typing import List, Dict, Any
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.util.logging import Logger
from src.services.telegram import TelegramService
from src.ai.llm import chat_completion

# Security analysis prompt template
UPGRADE_ANALYSIS_PROMPT = """You are a security researcher analyzing smart contract upgrades. For each analysis:

1. Provide a single paragraph summarizing the implementation changes and their potential security relevance
2. On a new line, add "Security Impact: Yes" or "Security Impact: No"

Focus on:
- State variable changes
- Access control modifications
- New functionality that could impact existing state
- Changes to core business logic
- Potential vulnerabilities introduced

Be concise and direct in your analysis."""


class ProxyUpgradeHandler(Handler):
    """Handler for proxy contract implementation upgrades"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("ProxyUpgradeHandler")
        self.telegram = TelegramService.get_instance()

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.CONTRACT_UPGRADED]

    async def analyze_upgrade(self, old_code: str, new_code: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze implementation upgrade for security implications"""
        upgrade_content = f"""
Old Implementation:
{old_code}

New Implementation:
{new_code}

Upgrade Event:
Block Number: {event.get('blockNumber')}
Timestamp: {event.get('timestamp')}
"""
        prompt = (
            "Analyze this implementation upgrade and provide a single paragraph summary "
            "of the changes and potential security impact. Always end with "
            "'Security Impact: Yes' or 'Security Impact: No':"
        )

        response = await chat_completion(
            [
                {"role": "system", "content": UPGRADE_ANALYSIS_PROMPT},
                {"role": "user", "content": f"{prompt}\n{upgrade_content}"},
            ]
        )

        return self.process_analysis(response)

    def process_analysis(self, response: str) -> Dict[str, Any]:
        """Process the LLM response and extract analysis and security impact"""
        try:
            # Split on newline to separate analysis from security impact
            parts = response.strip().split("\n")

            if len(parts) > 0:
                if len(parts) > 1:
                    analysis = "\n".join(parts[:-1]).strip()
                    has_security_impact = "Security Impact: Yes" in parts[-1]
                else:
                    text = parts[0]
                    has_security_impact = "Security Impact: Yes" in text
                    analysis = text.replace("Security Impact: Yes", "").replace("Security Impact: No", "").strip()

                if not analysis:
                    analysis = "No analysis provided"

                return {"has_security_impact": has_security_impact, "analysis": analysis}

            return {"has_security_impact": False, "analysis": "Error processing analysis: Empty response"}

        except Exception as e:
            return {"has_security_impact": False, "analysis": f"Error processing analysis: {str(e)}"}

    async def handle(self) -> HandlerResult:
        """Handle proxy upgrade events"""
        try:
            if not self.context:
                self.logger.error("No context provided")
                return HandlerResult(success=False, data={"error": "No context provided"})

            proxy = self.context.get("proxy")
            old_impl = self.context.get("old_implementation")
            new_impl = self.context.get("new_implementation")
            event = self.context.get("event")

            if not all([proxy, new_impl, event]):
                self.logger.error("Missing required context data")
                return HandlerResult(success=False, data={"error": "Missing required context data"})

            # Get implementation code
            old_code = old_impl.get_code() if old_impl else "No previous implementation"
            new_code = new_impl.get_code()
            if not new_code:
                self.logger.error("Could not retrieve new implementation code")
                return HandlerResult(success=False, data={"error": "Could not retrieve new implementation code"})

            # Analyze the upgrade
            analysis_result = await self.analyze_upgrade(old_code, new_code, event)
            if not analysis_result.get("has_security_impact", False):
                return HandlerResult(success=True, data={"message": "No security impact detected"})

            # Build notification message
            message_lines = [
                "🔄 Security-Relevant Proxy Upgrade Detected\n",
                f"Proxy: {proxy.identifier}",
                f"New Implementation: {new_impl.identifier}\n",
                analysis_result.get("analysis", "No analysis available"),
                f"\nBlock: {event.get('blockNumber')}",
            ]

            if proxy.project:
                message_lines.extend([f"\n📁 Project: {proxy.project.name}", f"Type: {proxy.project.project_type}"])

            # Send notification
            await self.telegram.send_message("\n".join(message_lines))

            return HandlerResult(
                success=True,
                data={
                    "proxy": proxy.identifier,
                    "new_implementation": new_impl.identifier,
                    "analysis": analysis_result.get("analysis"),
                    "has_security_impact": analysis_result.get("has_security_impact"),
                },
            )

        except Exception as e:
            self.logger.error(f"Error handling proxy upgrade: {str(e)}")
            return HandlerResult(success=False, data={"error": str(e)})
