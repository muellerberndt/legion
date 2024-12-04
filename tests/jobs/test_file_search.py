import pytest
from src.jobs.file_search import FileSearchJob
from src.models.base import Asset, AssetType
from src.jobs.base import JobResult, JobStatus
import os
import tempfile
from unittest.mock import MagicMock
from contextlib import contextmanager
from src.util.logging import Logger, LogConfig
import logging

# Configure logging to show during tests
logging.basicConfig(level=logging.INFO)
LogConfig.set_verbose(True)
LogConfig.set_db_logging(False)  # Disable DB logging during tests

logger = Logger("FileSearchTest")

@contextmanager
def create_test_files():
    """Create temporary test files with content"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        files = {
            "test1.sol": "contract Test1 { function hello() public { } }",
            "test2.sol": "contract Test2 { function world() public { } }",
            "test3.txt": "This is a non-solidity file"
        }
        
        paths = {}
        for filename, content in files.items():
            path = os.path.join(tmpdir, filename)
            with open(path, 'w') as f:
                f.write(content)
            paths[filename] = path
            
        logger.info(f"Created test files in {tmpdir}")
        for filename, path in paths.items():
            logger.info(f"File {filename} at {path}")
            with open(path, 'r') as f:
                logger.info(f"Content: {f.read()}")
                
        yield paths

@pytest.fixture
def sample_files():
    with create_test_files() as paths:
        yield paths

@pytest.fixture
def sample_assets(sample_files):
    """Create sample asset objects"""
    assets = []
    for filename, path in sample_files.items():
        asset = Asset(
            id=f"test_{filename}",  # Using filename as ID
            asset_type=AssetType.GITHUB_FILE if filename.endswith(".sol") else "document",
            source_url=f"https://example.com/{filename}",
            local_path=path,
            extra_data={}
        )
        assets.append(asset)
        logger.info(f"Created asset: id={asset.id}, type={asset.asset_type}, path={asset.local_path}")
    return assets

class MockSession:
    def __init__(self, assets):
        self.assets = assets
        
    def execute(self, stmt):
        logger.info(f"Mock executing query: {stmt}")
        return MockQueryResult(self.assets)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class MockQueryResult:
    def __init__(self, assets):
        self.assets = assets
        
    def scalars(self):
        return self
        
    def all(self):
        logger.info(f"Mock query returning {len(self.assets)} assets")
        return self.assets

@pytest.fixture
def mock_db_session(monkeypatch, sample_assets):
    """Create a mock database session"""
    def get_mock_session(self):
        logger.info("Mock session requested")
        return MockSession(sample_assets)
    
    # Mock get_session to return our mock session
    monkeypatch.setattr('src.jobs.file_search.DBSessionMixin.get_session', get_mock_session)

@pytest.mark.asyncio
async def test_file_search_job(sample_files, sample_assets, mock_db_session):
    # Create and run job
    job = FileSearchJob(regex_pattern="function.*public")
    logger.info(f"Created job with pattern: {job.regex_pattern}")
    
    await job.start()
    logger.info(f"Job completed with status: {job.status}")
    
    # Verify job status
    assert job.status == JobStatus.COMPLETED
    assert job.result.success is True
    
    # Get results
    results = job.result.data["results"]
    logger.info(f"Got {len(results)} results")
    if len(results) > 0:
        for result in results:
            logger.info(f"Result: {result}")
    
    # Verify results
    assert len(results) == 2  # Should find matches in both .sol files
    
    # Check first result
    assert results[0]["asset"]["id"].endswith(".sol")
    assert len(results[0]["matches"]) == 1
    assert "function" in results[0]["matches"][0]["match"]
    
    # Check second result
    assert results[1]["asset"]["id"].endswith(".sol")
    assert len(results[1]["matches"]) == 1
    assert "function" in results[1]["matches"][0]["match"]
    
@pytest.mark.asyncio
async def test_file_search_job_no_matches(sample_files, sample_assets, mock_db_session):
    # Create and run job with pattern that won't match
    job = FileSearchJob(regex_pattern="nonexistent_pattern")
    await job.start()
    
    # Verify job status
    assert job.status == JobStatus.COMPLETED
    assert job.result.success is True
    
    # Get results
    results = job.result.data["results"]
    
    # Verify no results found
    assert len(results) == 0