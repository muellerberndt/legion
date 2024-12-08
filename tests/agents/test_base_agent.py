import pytest
from src.agents.base_agent import BaseAgent, AgentResult
from typing import Dict, Any


class MockAgent(BaseAgent):
    """Mock implementation of BaseAgent for testing"""

    async def execute_step(self) -> AgentResult:
        self.state["result"] = {"test": "success"}  # Set a result to mark task as complete
        return AgentResult(success=True)

    def is_task_complete(self) -> bool:
        return "result" in self.state

    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "test"}


@pytest.fixture
def agent():
    """Create a test agent"""
    return MockAgent(custom_prompt="Test prompt", command_names=["test_command"])


def test_base_agent_init(agent):
    """Test agent initialization"""
    assert agent.max_steps == 10
    assert agent.timeout == 300
    assert agent.step_count == 0
    assert agent.start_time is None
    assert isinstance(agent.state, dict)
    assert agent.execution_id is None
    assert isinstance(agent.execution_steps, list)


@pytest.mark.asyncio
async def test_base_agent_execute_task(agent):
    """Test task execution"""
    # Setup
    task = {"type": "test", "data": "test_data"}

    # Execute
    result = await agent.execute_task(task)

    # Verify
    assert result.success is True
    assert agent.state["status"] == "completed"  # Now it should be completed
    assert agent.step_count == 1
    assert "result" in agent.state  # Verify result was set
    assert agent.state["result"] == {"test": "success"}


@pytest.mark.asyncio
async def test_base_agent_record_step(agent):
    """Test step recording"""
    # Setup
    agent.step_count = 1

    # Execute
    agent.record_step(
        action="test",
        input_data={"test": "input"},
        output_data={"test": "output"},
        reasoning="test reasoning",
        next_action="complete",
    )

    # Verify
    assert len(agent.execution_steps) == 1
    step = agent.execution_steps[0]
    assert step.step_number == 1
    assert step.action == "test"
    assert step.reasoning == "test reasoning"
    assert step.next_action == "complete"


@pytest.mark.asyncio
async def test_base_agent_execution_summary(agent):
    """Test execution summary"""
    # Setup
    agent.execution_id = "test-id"
    agent.state = {"status": "completed", "result": {"test": "result"}}
    agent.step_count = 1
    agent.record_step(
        action="test",
        input_data={"test": "input"},
        output_data={"test": "output"},
        reasoning="test reasoning",
        next_action="complete",
    )

    # Execute
    summary = agent.get_execution_summary()

    # Verify
    assert summary["execution_id"] == "test-id"
    assert summary["status"] == "completed"
    assert summary["steps_taken"] == 1
    assert len(summary["steps"]) == 1
    assert summary["steps"][0]["action"] == "test"
