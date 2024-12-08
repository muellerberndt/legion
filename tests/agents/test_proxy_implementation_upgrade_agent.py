import pytest
from unittest.mock import patch
from extensions.examples.proxy_implementation_upgrade_agent import ProxyImplementationUpgradeAgent


@pytest.fixture
def agent():
    return ProxyImplementationUpgradeAgent()


@pytest.fixture
def mock_response():
    return """SUMMARY:
Added new admin functions and modified access control

SECURITY CONCERNS:
- New admin role has unrestricted access
- Missing timelock on critical functions

STORAGE ANALYSIS:
Added new admin mapping at slot 5

FUNCTION CHANGES:
- Added setAdmin function
- Modified pause mechanism

RISK LEVEL: high"""


@pytest.mark.asyncio
async def test_analyze_implementation(agent, mock_response):
    with patch.object(agent, "chat_completion", return_value=mock_response):
        result = await agent.analyze_implementation("contract Test {}")

        assert result["summary"] == "Added new admin functions and modified access control"
        assert len(result["security_concerns"]) == 2
        assert result["security_concerns"][0] == "New admin role has unrestricted access"
        assert result["storage_analysis"] == "Added new admin mapping at slot 5"
        assert result["function_changes"] == "- Added setAdmin function\n- Modified pause mechanism"
        assert result["risk_level"] == "high"


def test_format_message(agent):
    message = agent.format_message(proxy_address="0x123", new_implementation="0x456", tx_hash="0x789", in_scope=True)

    assert "In Bounty Scope" in message
    assert "0x123" in message
    assert "0x456" in message
    assert "0x789" in message


def test_format_message_not_in_scope(agent):
    message = agent.format_message(proxy_address="0x123", new_implementation="0x456", tx_hash="0x789", in_scope=False)

    assert "In Bounty Scope" not in message
    assert "0x123" in message
    assert "0x456" in message
    assert "0x789" in message


def test_format_analysis(agent):
    analysis = {
        "summary": "Test summary",
        "security_concerns": ["Risk 1", "Risk 2"],
        "storage_analysis": "Storage changed",
        "function_changes": "Functions modified",
        "risk_level": "high",
    }

    message = agent.format_analysis(analysis)

    assert "Test summary" in message
    assert "Risk 1" in message
    assert "Risk 2" in message
    assert "Storage changed" in message
    assert "Functions modified" in message
    assert "🔴 HIGH" in message
    assert "Recommendation" in message


def test_format_analysis_no_concerns(agent):
    analysis = {
        "summary": "Test summary",
        "security_concerns": [],
        "storage_analysis": "Storage changed",
        "function_changes": "Functions modified",
        "risk_level": "low",
    }

    message = agent.format_analysis(analysis)

    assert "Test summary" in message
    assert "Security Concerns" not in message
    assert "Storage changed" in message
    assert "Functions modified" in message
    assert "🟢 LOW" in message
    assert "Recommendation" not in message
