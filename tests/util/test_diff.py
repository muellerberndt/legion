import pytest
import os
from src.util.diff import compute_file_diff, DiffResult
import aiofiles

@pytest.fixture
async def test_files(tmp_path):
    """Create test files with known content"""
    old_content = """def hello():
    print("Hello")
    print("World")
    # Old comment
    return True"""
    
    new_content = """def hello():
    print("Hello!")
    print("World")
    # New comment
    print("Added line")
    return True"""
    
    old_path = tmp_path / "old.py"
    new_path = tmp_path / "new.py"
    
    async with aiofiles.open(old_path, 'w') as f:
        await f.write(old_content)
    async with aiofiles.open(new_path, 'w') as f:
        await f.write(new_content)
        
    return str(old_path), str(new_path)

@pytest.mark.asyncio
async def test_compute_file_diff(test_files):
    """Test computing diff between two files"""
    old_path, new_path = test_files
    
    diff_result = await compute_file_diff(old_path, new_path)
    assert isinstance(diff_result, DiffResult)
    assert diff_result.has_changes
    
    # Verify modified line
    assert len(diff_result.modified_lines) == 2
    old_line, new_line, old_content, new_content = diff_result.modified_lines[0]
    assert old_content == '    print("Hello")'
    assert new_content == '    print("Hello!")'
    
    # Verify added line
    assert len(diff_result.added_lines) == 1
    line_num, content = diff_result.added_lines[0]
    assert content == '    print("Added line")'
    
    # Test unified diff format
    diff_text = diff_result.to_unified_diff()
    assert '--- ' in diff_text
    assert '+++ ' in diff_text
    assert '-2: ' in diff_text
    assert '+2: ' in diff_text

@pytest.mark.asyncio
async def test_compute_file_diff_no_changes(tmp_path):
    """Test computing diff between identical files"""
    content = "No changes here\n"
    
    path1 = tmp_path / "file1.txt"
    path2 = tmp_path / "file2.txt"
    
    async with aiofiles.open(path1, 'w') as f:
        await f.write(content)
    async with aiofiles.open(path2, 'w') as f:
        await f.write(content)
        
    diff_result = await compute_file_diff(str(path1), str(path2))
    assert isinstance(diff_result, DiffResult)
    assert not diff_result.has_changes
    assert not diff_result.added_lines
    assert not diff_result.removed_lines
    assert not diff_result.modified_lines

@pytest.mark.asyncio
async def test_compute_file_diff_missing_file(tmp_path):
    """Test computing diff with missing file"""
    # Create one file
    path1 = tmp_path / "exists.txt"
    async with aiofiles.open(path1, 'w') as f:
        await f.write("test")
        
    # Try to diff with non-existent file
    path2 = tmp_path / "does_not_exist.txt"
    
    diff_result = await compute_file_diff(str(path1), str(path2))
    assert diff_result is None 