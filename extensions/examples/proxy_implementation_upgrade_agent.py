from src.agents.base_agent import BaseAgent
from src.util.logging import Logger
from typing import Dict, Any, List
import json

__all__ = ['ProxyImplementationUpgradeAgent']

class ProxyImplementationUpgradeAgent(BaseAgent):
    """Agent for analyzing proxy implementation upgrades"""
    
    def __init__(self):
        super().__init__()
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
3. Notable changes or additions that could affect security

Source code:
{source_code}

Please format your response as JSON with the following structure:
{{
    "summary": "Brief description of main functionality",
    "security_concerns": ["List of potential security issues"],
    "notable_changes": ["List of notable changes"],
    "risk_level": "low|medium|high"
}}"""

        self.logger.info("Sending prompt to OpenAI")
        # Get analysis from OpenAI
        response = await self.chat_with_ai(prompt)
        self.logger.info("Received response from OpenAI", extra_data={"response": response})
        
        try:
            # Parse response as JSON
            analysis = json.loads(response)
            self.logger.info("Successfully parsed response as JSON", extra_data={"analysis": analysis})
            return analysis
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            # Return basic analysis if JSON parsing fails
            basic_analysis = {
                "summary": response[:500],  # First 500 chars as summary
                "security_concerns": [],
                "notable_changes": [],
                "risk_level": "unknown"
            }
            self.logger.info("Returning basic analysis", extra_data={"analysis": basic_analysis})
            return basic_analysis
            
    def format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results into a readable message
        
        Args:
            analysis: The analysis results to format
            
        Returns:
            Formatted message string
        """
        risk_emojis = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴",
            "unknown": "⚪"
        }
        
        message = [
            "Implementation Analysis:",
            "",
            f"Risk Level: {risk_emojis.get(analysis.get('risk_level', 'unknown'), '⚪')} {analysis.get('risk_level', 'unknown').upper()}",
            "",
            "Summary:",
            analysis.get('summary', 'No summary available'),
            ""
        ]
        
        if analysis.get('security_concerns'):
            message.extend([
                "Security Concerns:",
                *[f"• {concern}" for concern in analysis['security_concerns']],
                ""
            ])
            
        if analysis.get('notable_changes'):
            message.extend([
                "Notable Changes:",
                *[f"• {change}" for change in analysis['notable_changes']],
                ""
            ])
            
        return "\n".join(message)

# Function to initialize the agent
def initialize():
    """Initialize the agent"""
    return ProxyImplementationUpgradeAgent() 