from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.config.config import Config
from src.util.logging import Logger
from dataclasses import dataclass
from src.actions.registry import ActionRegistry

@dataclass
class AgentCommand:
    """Represents a command that an agent can use"""
    name: str
    description: str
    required_params: List[str]
    optional_params: List[str]

class BaseAgent(ABC):
    """Base class for all agents in the system
    
    This provides:
    1. Standard system prompt with R4dar context
    2. Command management and execution
    3. OpenAI client setup and configuration
    4. Common utility methods
    """
    
    # Default system prompt giving context about R4dar
    DEFAULT_SYSTEM_PROMPT = """You are an AI agent working within R4dar, a security analysis platform for web3 projects.

Key Context:
- R4dar monitors bug bounty programs, smart contracts, and project updates
- The platform indexes data from sources like Immunefi, GitHub, and blockchain explorers
- Assets can be smart contracts, repositories, or specific files
- Projects can have multiple associated assets
- The goal is to help security researchers find potential vulnerabilities

Your role is to assist in analyzing and processing this data to identify security-relevant information.
Always maintain a security-focused perspective in your analysis."""

    def __init__(self, custom_prompt: Optional[str] = None, command_names: Optional[List[str]] = None):
        self.logger = Logger(self.__class__.__name__)
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)
        
        # Initialize action registry and wait for it to be ready
        self.action_registry = ActionRegistry()
        self.action_registry.initialize()  # Explicitly call initialize
        
        # Log available actions before getting commands
        actions = self.action_registry.get_actions()
        self.logger.info("Available actions in registry:", extra_data={
            "actions": list(actions.keys())
        })
        
        # Get available commands
        self.commands = self._get_available_commands(command_names)
        
        # Build complete system prompt
        self.system_prompt = self._build_system_prompt(custom_prompt)
        
        # Log the complete system prompt
        self.logger.info("Initialized agent with system prompt:", extra_data={
            "prompt": self.system_prompt,
            "command_count": len(self.commands),
            "commands": list(self.commands.keys())
        })
            
    def _get_available_commands(self, command_names: Optional[List[str]] = None) -> Dict[str, AgentCommand]:
        """Get the commands available to this agent
        
        Args:
            command_names: Optional list of command names to include. If None, all commands are included.
            
        Returns:
            Dict mapping command names to AgentCommand objects
        """
        commands = {}
        
        # Get all registered actions
        actions = self.action_registry.get_actions()
        self.logger.info("Found registered actions:", extra_data={
            "available_actions": list(actions.keys())
        })
        
        # If command_names is None or empty, include all commands
        if not command_names:
            command_names = list(actions.keys())
            self.logger.info("Using all available commands")
        else:
            self.logger.info("Filtering actions by command names:", extra_data={
                "requested_commands": command_names
            })
            
        # Convert actions to commands
        for name, (_, spec) in actions.items():
            if name in command_names:
                if not spec:
                    self.logger.warning(f"Action {name} has no spec, skipping")
                    continue
                    
                commands[name] = AgentCommand(
                    name=name,
                    description=spec.description,
                    required_params=[arg.name for arg in spec.arguments or [] if arg.required],
                    optional_params=[arg.name for arg in spec.arguments or [] if not arg.required]
                )
                
        self.logger.info("Initialized commands for agent:", extra_data={
            "available_commands": list(commands.keys())
        })
                
        return commands
        
    def _build_system_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Build the complete system prompt including command documentation
        
        Args:
            custom_prompt: Optional custom prompt to add
            
        Returns:
            Complete system prompt
        """
        self.logger.info("Building system prompt", extra_data={
            "has_custom_prompt": custom_prompt is not None,
            "command_count": len(self.commands)
        })
        
        prompt_parts = [self.DEFAULT_SYSTEM_PROMPT]
        
        if custom_prompt:
            self.logger.info("Adding custom prompt")
            prompt_parts.append("\n\n" + custom_prompt)
            
        # Add command documentation
        if self.commands:
            self.logger.info("Adding command documentation")
            prompt_parts.append("\nAvailable Commands:\n")
            
            for name, command in self.commands.items():
                # Get the full action spec
                action = self.action_registry.get_action(name)
                if not action:
                    self.logger.warning(f"Action spec not found for command: {name}")
                    continue
                    
                _, spec = action
                
                # Add command documentation
                prompt_parts.extend([
                    f"\n{name}:",
                    f"Description: {spec.description}",
                    f"When to use: {spec.agent_hint}"
                ])
                
                # Add parameter information
                if spec.arguments:
                    prompt_parts.append("Parameters:")
                    for arg in spec.arguments:
                        required = "(required)" if arg.required else "(optional)"
                        prompt_parts.append(f"  - {arg.name}: {arg.description} {required}")
                        
        final_prompt = "\n".join(prompt_parts)
        self.logger.info("Built system prompt", extra_data={
            "prompt_length": len(final_prompt),
            "section_count": len(prompt_parts)
        })
        return final_prompt
        
    async def execute_command(self, command_name: str, **params) -> Any:
        """Execute a command with given parameters
        
        Args:
            command_name: Name of the command to execute
            **params: Command parameters
            
        Returns:
            Command execution result
            
        Raises:
            ValueError: If command doesn't exist or required params are missing
        """
        if command_name not in self.commands:
            raise ValueError(f"Unknown command: {command_name}")
            
        command = self.commands[command_name]
        
        # Validate required parameters
        missing_params = [p for p in command.required_params if p not in params]
        if missing_params:
            raise ValueError(f"Missing required parameters for {command_name}: {missing_params}")
            
        # Remove any params that aren't defined
        valid_params = command.required_params + command.optional_params
        cleaned_params = {k: v for k, v in params.items() if k in valid_params}
        
        # Get and execute the action
        action = self.action_registry.get_action(command_name)
        if not action:
            raise ValueError(f"Action not found for command: {command_name}")
            
        handler, _ = action
        return await handler(cleaned_params)
            
    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Get a chat completion from OpenAI
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Temperature for response generation
            
        Returns:
            Generated response text
        """
        try:
            # Always include system prompt as first message
            full_messages = [
                {"role": "system", "content": self.system_prompt}
            ] + messages
            
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=full_messages,
                temperature=temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Failed to get chat completion: {str(e)}")
            raise
            
    def format_command_help(self) -> str:
        """Format help text for available commands
        
        Returns:
            Formatted help text listing all commands and their parameters
        """
        lines = ["Available Commands:"]
        for name, cmd in self.commands.items():
            lines.append(f"\n{name}:")
            lines.append(f"  Description: {cmd.description}")
            if cmd.required_params:
                lines.append("  Required parameters:")
                for param in cmd.required_params:
                    lines.append(f"    - {param}")
            if cmd.optional_params:
                lines.append("  Optional parameters:")
                for param in cmd.optional_params:
                    lines.append(f"    - {param}")
        return "\n".join(lines) 