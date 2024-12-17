import pytest
from src.util.command_parser import CommandParser
from src.actions.base import ActionSpec, ActionArgument


def test_parse_arguments_with_quotes():
    """Test parsing arguments with quotes"""
    parser = CommandParser()

    # Test quoted JSON with equals signs
    json_query = '\'{"from": "projects", "where": [{"field": "project_source", "op": "=", "value": "immunefi"}]}\''
    args = parser.parse_arguments(json_query)
    assert len(args) == 1
    assert args[0] == '{"from": "projects", "where": [{"field": "project_source", "op": "=", "value": "immunefi"}]}'

    # Test mixed quoted and unquoted equals signs
    args = parser.parse_arguments('param1=value1 param2="value=2"')
    assert isinstance(args, dict)
    assert args["param1"] == "value1"
    assert args["param2"] == "value=2"

    # Test multiple equals signs in quotes
    args = parser.parse_arguments("param1='value=with=equals'")
    assert isinstance(args, dict)
    assert args["param1"] == "value=with=equals"


def test_parse_command():
    """Test parsing command and arguments"""
    parser = CommandParser()

    # Test basic command
    cmd, args = parser.parse_command("/test arg1 arg2")
    assert cmd == "test"
    assert args == "arg1 arg2"

    # Test command with quoted arguments
    cmd, args = parser.parse_command('/test "arg 1" arg2')
    assert cmd == "test"
    assert args == '"arg 1" arg2'

    # Test command with no arguments
    cmd, args = parser.parse_command("/test")
    assert cmd == "test"
    assert args == ""


def test_validate_arguments():
    """Test argument validation"""
    parser = CommandParser()

    # Create test spec
    spec = ActionSpec(
        name="test",
        description="Test command",
        help_text="Test help",
        agent_hint="Test hint",
        arguments=[
            ActionArgument(name="required", description="Required param", required=True),
            ActionArgument(name="optional", description="Optional param", required=False),
        ],
    )

    # Test valid arguments
    assert parser.validate_arguments({"required": "value"}, spec) is True
    assert parser.validate_arguments({"required": "value", "optional": "value"}, spec) is True

    # Test missing required argument
    with pytest.raises(ValueError, match="Missing required parameters"):
        parser.validate_arguments({"optional": "value"}, spec)

    # Test unknown argument
    with pytest.raises(ValueError, match="Unknown parameters"):
        parser.validate_arguments({"required": "value", "unknown": "value"}, spec)
