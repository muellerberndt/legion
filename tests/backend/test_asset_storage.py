import pytest
import os
from src.backend.asset_storage import AssetStorage


@pytest.fixture
def base_dir(tmp_path):
    """Create a temporary base directory for testing"""
    return str(tmp_path / "assets")


def test_get_asset_path_github(base_dir):
    """Test path generation for GitHub URLs"""
    url = "https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/ERC20.sol"
    target_dir, relative_path = AssetStorage.get_asset_path(base_dir, url)

    expected_path = os.path.join(
        base_dir,
        "github.com",
        "OpenZeppelin",
        "openzeppelin-contracts",
        "blob",
        "master",
        "contracts",
        "token",
        "ERC20",
        "ERC20.sol",
    )
    expected_relative = os.path.join(
        "github.com", "OpenZeppelin", "openzeppelin-contracts", "blob", "master", "contracts", "token", "ERC20", "ERC20.sol"
    )

    assert target_dir == expected_path
    assert relative_path == expected_relative


def test_get_asset_path_etherscan(base_dir):
    """Test path generation for Etherscan URLs"""
    url = "https://etherscan.io/address/0x1234567890123456789012345678901234567890"
    target_dir, relative_path = AssetStorage.get_asset_path(base_dir, url)

    expected_path = os.path.join(base_dir, "etherscan.io", "address", "0x1234567890123456789012345678901234567890")
    expected_relative = os.path.join("etherscan.io", "address", "0x1234567890123456789012345678901234567890")

    assert target_dir == expected_path
    assert relative_path == expected_relative


def test_get_asset_path_with_query_params(base_dir):
    """Test path generation with query parameters"""
    url = "https://github.com/org/repo/blob/main/file.sol?ref=v1.0"
    target_dir, relative_path = AssetStorage.get_asset_path(base_dir, url)

    expected_path = os.path.join(base_dir, "github.com", "org", "repo", "blob", "main", "file.sol")
    expected_relative = os.path.join("github.com", "org", "repo", "blob", "main", "file.sol")

    assert target_dir == expected_path
    assert relative_path == expected_relative


def test_get_asset_path_directory_traversal(base_dir):
    """Test protection against directory traversal attempts"""
    url = "https://evil.com/../../../etc/passwd"

    with pytest.raises(ValueError) as exc_info:
        AssetStorage.get_asset_path(base_dir, url)
    assert "not under base directory" in str(exc_info.value)


def test_get_asset_path_empty_components(base_dir):
    """Test handling of URLs with empty path components"""
    url = "https://example.com///path//to//file"
    target_dir, relative_path = AssetStorage.get_asset_path(base_dir, url)

    expected_path = os.path.join(base_dir, "example.com", "path", "to", "file")
    expected_relative = os.path.join("example.com", "path", "to", "file")

    assert target_dir == expected_path
    assert relative_path == expected_relative


def test_get_asset_path_absolute_path(base_dir):
    """Test handling of URLs with absolute paths"""
    url = "https://example.com/absolute/path"
    target_dir, relative_path = AssetStorage.get_asset_path(base_dir, url)

    expected_path = os.path.join(base_dir, "example.com", "absolute", "path")
    expected_relative = os.path.join("example.com", "absolute", "path")

    assert target_dir == expected_path
    assert relative_path == expected_relative
