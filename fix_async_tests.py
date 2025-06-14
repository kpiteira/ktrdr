#!/usr/bin/env python3
"""
Script to systematically fix async/await issues in API service tests.
"""

import re
from pathlib import Path


def fix_async_test_file(file_path: Path):
    """Fix async/await issues in a test file."""
    content = file_path.read_text()
    
    # Methods that are async in DataService
    async_methods = [
        'load_data', 'get_available_symbols', 'get_available_timeframes', 
        'get_data_range', 'health_check'
    ]
    
    changes_made = []
    
    # Fix function definitions to be async
    for method in async_methods:
        # Pattern: def test_something_with_method_name(
        pattern = rf'(def test_[^(]*{method}[^(]*\([^)]*\):)'
        matches = re.findall(pattern, content)
        for match in matches:
            # Add @pytest.mark.asyncio decorator if not present
            if f'@pytest.mark.asyncio\n{match.replace("def", "async def")}' not in content:
                # Find the test function and add async
                new_match = match.replace('def ', 'async def ')
                content = content.replace(match, new_match)
                
                # Add @pytest.mark.asyncio decorator before the function
                if '@pytest.mark.asyncio' not in content[:content.find(new_match)]:
                    content = content.replace(new_match, f'@pytest.mark.asyncio\n    {new_match}')
                
                changes_made.append(f"Made {match} async")
    
    # Fix method calls to be awaited
    for method in async_methods:
        # Pattern: service.method_name( or result = service.method_name(
        pattern = rf'(\w+\.{method}\([^)]*\))'
        
        def add_await(match):
            call = match.group(1)
            if not call.startswith('await '):
                return f'await {call}'
            return call
        
        new_content = re.sub(pattern, add_await, content)
        if new_content != content:
            changes_made.append(f"Added await to {method} calls")
            content = new_content
    
    # Write back if changes were made
    if changes_made:
        file_path.write_text(content)
        print(f"Fixed {file_path}: {', '.join(changes_made)}")
        return True
    return False


def main():
    """Fix async issues in test files."""
    test_files = [
        Path("tests/api/test_data_service.py"),
    ]
    
    for file_path in test_files:
        if file_path.exists():
            fix_async_test_file(file_path)
        else:
            print(f"File not found: {file_path}")


if __name__ == "__main__":
    main()