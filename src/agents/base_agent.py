from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from src.agents.llm_base import LLMBase
import time
import uuid


@dataclass
class AgentResult:
    """Result of an agent operation"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_user_input: bool = False
    user_prompt: Optional[str] = None


@dataclass
class ExecutionStep:
    """Record of a single execution step"""

    step_number: int
    action: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning: str
    next_action: str
    timestamp: float = time.time()


class BaseAgent(LLMBase, ABC):
    """Base class for autonomous agents that perform specific tasks"""

    def __init__(self, custom_prompt: Optional[str] = None, command_names: Optional[List[str]] = None):
        super().__init__(custom_prompt=custom_prompt, command_names=command_names)

        # Initialize execution state
        self.max_steps = 10
        self.timeout = 300
        self.step_count = 0
        self.start_time: Optional[float] = None
        self.state: Dict[str, Any] = {}
        self.execution_id: Optional[str] = None
        self.execution_steps: List[ExecutionStep] = []

    async def execute_task(self, task: Dict[str, Any], trigger: str = None) -> AgentResult:
        """Execute a task with safety limits and state tracking"""
        self.start_time = time.time()
        self.step_count = 0
        self.state = {"task": task, "status": "started"}
        self.execution_id = str(uuid.uuid4())
        self.execution_steps = []

        try:
            while self.step_count < self.max_steps:
                # Check timeout
                if time.time() - self.start_time > self.timeout:
                    self.state["status"] = "failed"
                    self.state["error"] = f"Task timed out after {self.timeout} seconds"
                    return AgentResult(success=False, error=f"Task timed out after {self.timeout} seconds")

                # Execute next step
                self.step_count += 1
                step_result = await self.execute_step()

                # Handle step result
                if not step_result.success:
                    self.state["status"] = "failed"
                    self.state["error"] = step_result.error
                    return step_result

                if step_result.requires_user_input:
                    self.state["status"] = "waiting_for_input"
                    return step_result

                if self.is_task_complete():
                    result = AgentResult(
                        success=True, data={"result": self.state.get("result"), "steps_taken": self.step_count}
                    )
                    self.state["status"] = "completed"
                    return result

            # Max steps reached
            self.state["status"] = "failed"
            self.state["error"] = f"Task exceeded maximum steps ({self.max_steps})"
            return AgentResult(success=False, error=f"Task exceeded maximum steps ({self.max_steps})")

        except Exception as e:
            self.logger.error(f"Error in task execution: {str(e)}")
            self.state["status"] = "failed"
            self.state["error"] = str(e)
            return AgentResult(success=False, error=str(e))

    def record_step(self, action: str, input_data: Dict, output_data: Dict, reasoning: str, next_action: str) -> None:
        """Record a step in memory"""
        step = ExecutionStep(
            step_number=self.step_count,
            action=action,
            input_data=input_data,
            output_data=output_data,
            reasoning=reasoning,
            next_action=next_action,
        )
        self.execution_steps.append(step)

    @abstractmethod
    async def execute_step(self) -> AgentResult:
        """Execute a single step of the task"""

    @abstractmethod
    def is_task_complete(self) -> bool:
        """Check if the task is complete"""

    @abstractmethod
    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution"""
        return {
            "execution_id": self.execution_id,
            "status": self.state.get("status"),
            "steps_taken": self.step_count,
            "error": self.state.get("error"),
            "result": self.state.get("result"),
            "steps": [
                {
                    "step_number": step.step_number,
                    "action": step.action,
                    "reasoning": step.reasoning,
                    "next_action": step.next_action,
                    "timestamp": step.timestamp,
                }
                for step in self.execution_steps
            ],
        }
