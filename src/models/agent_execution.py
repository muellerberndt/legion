from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.backend.database import Base


class AgentExecution(Base):
    """Model for storing agent execution data"""

    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True)
    agent_type = Column(String, nullable=False)  # Type of agent (e.g., "github_event", "contract_analyzer")
    status = Column(String, nullable=False)  # started, running, completed, failed
    trigger = Column(String)  # What triggered this execution
    input_data = Column(JSON)  # Input data/parameters
    result = Column(JSON)  # Final result/report
    error = Column(String)  # Error message if failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    steps_taken = Column(Integer, default=0)

    # One-to-many relationship with execution steps
    steps = relationship("AgentExecutionStep", back_populates="execution", cascade="all, delete-orphan")


class AgentExecutionStep(Base):
    """Model for storing individual steps in an agent execution"""

    __tablename__ = "agent_execution_steps"

    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    action = Column(String, nullable=False)  # The action/tool used
    input_data = Column(JSON)  # Input to the action
    output_data = Column(JSON)  # Output from the action
    reasoning = Column(String)  # Agent's reasoning for this step
    next_action = Column(String)  # Agent's planned next action
    created_at = Column(DateTime, default=datetime.utcnow)

    # Many-to-one relationship with execution
    execution = relationship("AgentExecution", back_populates="steps")
