"""Models for agent-related functionality"""

from dataclasses import dataclass
from typing import List


@dataclass
class AgentCommand:
    """Command that can be executed by an agent"""

    name: str
    description: str
    help_text: str
    agent_hint: str
    required_params: List[str]
    optional_params: List[str]
    positional_params: List[str]  # List of parameter names that should be passed positionally
