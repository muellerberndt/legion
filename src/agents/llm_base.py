from abc import ABC
from typing import Dict, Any, List, Optional
from src.util.logging import Logger
from src.config.config import Config
from openai import AsyncOpenAI
from dataclasses import dataclass


@dataclass
class AgentCommand:
    """Command that can be executed by an agent"""

    name: str
    description: str
    help_text: str
    agent_hint: str
    required_params: List[str]
    optional_params: List[str]


class LLMBase(ABC):
    """Base class for LLM-powered components with shared functionality"""

    def __init__(self, custom_prompt: Optional[str] = None, command_names: Optional[List[str]] = None):
        self.logger = Logger(self.__class__.__name__)
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.get("llm.openai.key"))

        # Initialize action registry and wait for it to be ready
        from src.actions.registry import ActionRegistry

        self.action_registry = ActionRegistry()
        self.action_registry.initialize()  # Explicitly call initialize

        # Log available actions before getting commands
        actions = self.action_registry.get_actions()
        self.logger.info("Available actions in registry:", extra_data={"actions": list(actions.keys())})

        # Get available commands - if None, get all commands (for Chatbot)
        self.commands = self._get_available_commands(command_names)

        # Build complete system prompt
        self.system_prompt = self._build_system_prompt(custom_prompt)

        # Log the complete system prompt
        self.logger.info(
            "Initialized LLM component with system prompt:",
            extra_data={
                "prompt": self.system_prompt,
                "command_count": len(self.commands),
                "commands": list(self.commands.keys()),
            },
        )

    def _get_available_commands(self, command_names: Optional[List[str]] = None) -> Dict[str, AgentCommand]:
        """Get the commands available to this component"""
        commands = {}

        # Get all registered actions
        actions = self.action_registry.get_actions()
        self.logger.info("Found registered actions:", extra_data={"available_actions": list(actions.keys())})

        # If command_names is None, include ALL commands (for Chatbot)
        if command_names is None:
            command_names = list(actions.keys())
            self.logger.info("Including all commands (Chatbot mode)")
        elif not command_names:
            self.logger.info("No commands specified")
            return commands

        self.logger.info("Filtering actions by command names:", extra_data={"requested_commands": command_names})

        # Convert actions to commands
        for name, (_, spec) in actions.items():
            if name in command_names:
                if not spec:
                    self.logger.warning(f"Action {name} has no spec, skipping")
                    continue

                commands[name] = AgentCommand(
                    name=name,
                    description=spec.description,
                    help_text=spec.help_text or "",
                    agent_hint=spec.agent_hint or "",
                    required_params=[arg.name for arg in spec.arguments or [] if arg.required],
                    optional_params=[arg.name for arg in spec.arguments or [] if not arg.required],
                )

        self.logger.info("Initialized commands:", extra_data={"available_commands": list(commands.keys())})
        return commands

    def _build_system_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Build the complete system prompt including available commands"""
        base_prompt = custom_prompt or "You are an AI assistant."

        # Add command descriptions
        command_descriptions = []
        for name, cmd in self.commands.items():
            # Build parameter string
            params = []
            if cmd.required_params:
                params.extend([f"<{p}>" for p in cmd.required_params])
            if cmd.optional_params:
                params.extend([f"[{p}]" for p in cmd.optional_params])

            param_str = " ".join(params)

            # Build command description with help text and agent hint
            command_desc = [f"/{name} {param_str}", cmd.description]

            if cmd.help_text:
                command_desc.append(f"Help: {cmd.help_text}")
            if cmd.agent_hint:
                command_desc.append(f"Usage hint: {cmd.agent_hint}")

            command_descriptions.append("\n".join(command_desc))

        if command_descriptions:
            base_prompt += "\n\nAvailable commands:\n\n" + "\n\n".join(command_descriptions)

        return base_prompt

    async def execute_command(self, command: str, **kwargs) -> Any:
        """Execute a registered command"""
        if command not in self.commands:
            raise ValueError(f"Unknown command: {command}")

        # Get the command spec
        cmd = self.commands[command]

        # Validate required parameters
        missing_params = [p for p in cmd.required_params if p not in kwargs]
        if missing_params:
            raise ValueError(f"Missing required parameters for {command}: {', '.join(missing_params)}")

        # Execute the command through action registry
        action = self.action_registry.get_action(command)
        if not action:
            raise ValueError(f"Action not found for command: {command}")

        handler, _ = action
        return await handler(**kwargs)

    async def chat_completion(self, messages: List[Dict[str, str]], model: str = None) -> str:
        """Get completion from LLM"""
        try:
            # Get OpenAI config
            llm_config = self.config.get("llm", {}).get("openai", {})
            api_key = llm_config.get("key")
            if not api_key:
                raise ValueError("OpenAI API key not configured")

            model = model or llm_config.get("model", "gpt-4")

            client = AsyncOpenAI(api_key=api_key)

            self.logger.info("Sending chat completion request", extra_data={"messages": messages})
            response = await client.chat.completions.create(model=model, messages=messages, temperature=0.7)

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"Error in chat completion: {str(e)}")
            raise
