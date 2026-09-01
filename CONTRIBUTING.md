# Contributing to ollama-catalog

First off, thank you for considering a contribution to ollama-catalog! It's people
like you that make this project such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out
that you don't need to create one. When you are creating a bug report, please
include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed after following the steps**
- **Explain which behavior you expected to see instead and why**
- **Include screenshots and animated GIFs if possible**
- **Include your environment** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement
suggestion, please include:

- **A clear and descriptive title**
- **A detailed description of the suggested enhancement**
- **Specific use cases and examples**
- **Why this enhancement would be useful**

### Pull Requests

- Fill in the required template
- Follow the Python styleguide
- Include appropriate test cases
- Update documentation as needed
- End all files with a newline

## Development Setup

1. **Fork and clone** the repository
   ```bash
   git clone https://github.com/YOUR-USERNAME/ollama-catalog.git
   cd ollama-catalog
   ```

2. **Install development dependencies**
   ```bash
   uv pip install -e '.[dev]'
   ```

3. **Run tests**
   ```bash
   uv run pytest tests/ -v
   ```

4. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Styleguide

### Python Code
- Follow [PEP 8](https://pep8.org/)
- Use meaningful variable and function names
- Add docstrings for public functions
- Keep functions focused and single-purpose

### Commit Messages
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

### Pull Request Titles
- Prefix with scope: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
- Describe what is being changed
- Example: `feat(discovery): improve pagination handling`

## Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Maintain or improve code coverage

## Recognition

Contributors will be recognized in:
- Pull request discussion threads
- Release notes (for substantial contributions)
- GitHub repository Contributors page

## Questions?

Feel free to open a discussion or an issue with the `question` label.

Thank you for contributing! 🎉
