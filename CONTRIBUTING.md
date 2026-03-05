# Contributing to Clearence

Thank you for your interest in contributing to Clearence! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

- Use the [GitLab issue tracker](https://gitlab.com/YOUR_ORG/clearence/-/issues) to report bugs
- Include a clear description of the problem, steps to reproduce, and your environment (OS, Python version)
- If applicable, include relevant log output or error messages

### Suggesting Features

- Open an issue with the `enhancement` label
- Describe the use case and proposed solution
- Discuss before implementing large changes

### Security Vulnerabilities

Please report security vulnerabilities privately. See [SECURITY.md](SECURITY.md) for details.

### Pull Requests

1. **Fork and clone** the repository
2. **Create a branch** from `main` (e.g., `feature/add-xyz` or `fix/issue-123`)
3. **Make your changes** following the project's style:
   - Run `make format` before committing
   - Run `make lint` and `make test` to ensure quality
4. **Commit** with clear, descriptive messages
5. **Push** to your fork and open a Merge Request
6. **Address review feedback** promptly

### Development Setup

```bash
git clone https://gitlab.com/YOUR_ORG/clearence.git
cd clearence
pip install -e ".[dev]"
make test   # Verify tests pass
```

### Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Run `make lint` and `make format` before submitting
- Follow existing patterns in the codebase

### Testing

- Add or update tests for new functionality
- Ensure `make test` passes before submitting
- Use pytest; async tests use `pytest-asyncio`

## License

By contributing, you agree that your contributions will be licensed under the same [MIT License](LICENSE) that covers this project.
