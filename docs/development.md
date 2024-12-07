# Development Guide

## Code Style

This project uses Black for code formatting and flake8 for linting. To check your code:

```bash
# Install tools
pip install black flake8 autoflake

# Remove unused imports
autoflake --in-place --remove-all-unused-imports --recursive .

# Check formatting (add --diff to see changes)
black --check .

# Format code
black .

# Run linter (will catch trailing whitespaces)
flake8 .
```

You can also run the tools on specific directories:

```bash
autoflake --in-place --remove-all-unused-imports --recursive src/ tests/
black src/ tests/
flake8 src/ tests/
```

The recommended order is:
1. Run autoflake to remove unused imports
2. Run black to format the code
3. Run flake8 to check for remaining issues

### Handling Trailing Whitespaces

Flake8 will report trailing whitespaces with these warnings:
- W291: trailing whitespace
- W293: blank line contains whitespace

To automatically remove trailing whitespaces, you can use the `strip-trailing-whitespace` command in VS Code or run this command:

```bash
# Find files with trailing whitespaces
find . -type f -name "*.py" -exec grep -l "[[:space:]]$" {} \;

# Remove trailing whitespaces (macOS/Linux)
find . -type f -name "*.py" -exec sed -i '' -e 's/[[:space:]]*$//' {} \;

# Remove trailing whitespaces (Linux only)
find . -type f -name "*.py" -exec sed -i 's/[[:space:]]*$//' {} \;
```

## Running Tests

To run the test suite:

```bash
pytest tests/ -v
```

For test coverage information:

```bash
pytest tests/ -v --cov=src
```

## GitHub Actions

The repository is configured with GitHub Actions that automatically run linting and tests on every push and pull request. The workflow configuration can be found in `.github/workflows/tests.yml`.

To ensure your PR can be merged:
1. Make sure all tests pass locally
2. Run the linter and fix any issues
3. Format your code with Black 