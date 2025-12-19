# Contributing to Lola

**Write your AI skills once, use them everywhere.**

Thank you for your interest in contributing to Lola! This
document provides guidelines for contributing to the project.
Whether you're fixing a bug, adding a feature, or improving
documentation, we appreciate your help in making Lola better.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**: Check your version with `python --version`
- **uv**: Package manager for Python. Install from
  https://astral.sh/uv
- **Git**: Version control system
- **(Optional) AI coding assistant**: Tools like Claude Code,
  Cursor, or GitHub Copilot

## Getting Started

### 1. Fork and Clone

1. Fork the repository by clicking the "Fork" button on
   https://github.com/RedHatProductSecurity/lola
2. Clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/lola.git
cd lola
```

### 2. Install Dependencies

Install all development dependencies using uv:

```bash
uv sync --group dev
```

This creates a virtual environment (`.venv/`) and installs pytest,
ruff, basedpyright, and all project dependencies.

### 3. Install Pre-Commit Hooks (Recommended)

Pre-commit hooks automatically run tests, linting, and type
checking before each commit:

```bash
uv run pre-commit install
```

### 4. Verify Setup

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Then run tests to verify everything works:

```bash
pytest
```

You should see all tests pass. Pre-commit will also run these
checks automatically before each commit.

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b your-feature-name
```

Use descriptive names like `fix-readme-typo` or
`add-validation`.

### 2. Make Your Changes

Edit code, tests, or docs. Keep changes focused on one issue.

### 3. Run Quality Checks

Before committing, ensure everything passes:

```bash
pytest                    # Run tests
ruff check src tests      # Linting
basedpyright src          # Type checking
```

If you changed CLI functionality, test it:

```bash
lola --help
lola mod ls
lola install <module>
```

### 4. Commit Your Changes

We use [Conventional Commits]
(https://www.conventionalcommits.org/):

```bash
git commit -m "docs: fix typo in README"
git commit -m "feat: add module validation"
git commit -m "fix: resolve path handling"
```

## Submitting a Pull Request

### 1. Push to Your Fork

```bash
git push origin your-feature-name
```

### 2. Open the Pull Request

1. Go to https://github.com/RedHatProductSecurity/lola
2. Click "Compare & pull request"
3. Describe what changed and why
4. Link related issues
5. Include AI disclosure if you used AI tools (see below)

### 3. Wait for CI Checks

GitHub Actions will run tests. If they fail, fix the issues and
push again.

### 4. Respond to Feedback

Maintainers may suggest changes. Update your code and push - the
PR updates automatically!

**Note**: For large changes, open an issue first to discuss your
approach.

## AI-Assisted Contributions

We welcome contributions made with AI coding assistants! As an
AI skills package manager, Lola embraces AI-assisted development
while maintaining quality through transparency.

### How to Disclose AI Usage

**Option 1: Git commit signature** (Recommended)

Configure git to add "Assisted-by" to your commits:

```bash
git config user.assistedby "Claude Code"
git config user.assistedby "GitHub Copilot"
```

**Option 2: Commit message**

Mention AI assistance in your commit message:

```bash
git commit -m "feat: add validation

Co-authored-by: Claude Code <ai@anthropic.com>"
```

Or simply:

```bash
git commit -m "feat: add validation (AI-assisted)"
```

### Quality Standards

Whether AI-assisted or not, all contributions must:
- Pass all tests (`pytest`)
- Pass linting (`ruff check src tests`)
- Pass type checking (`basedpyright src`)
- Be reviewed and understood by you

### What Gets Closed

PRs will be closed if they:
- Don't pass quality checks
- Appear to be bulk AI submissions without human review
- Lack tests for new functionality
- Don't respond to feedback

Good AI-assisted contributions are thoughtful, tested, and show
human understanding. We value your work!

## Testing Guidelines

### Running Tests

Make sure you have activated the virtual environment first
(`source .venv/bin/activate`), then:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_cli_mod.py

# Run tests matching a pattern
pytest -k test_add

# Run with coverage report
pytest --cov=src/lola
```

### Writing Tests

When adding new functionality:
- Add tests in `tests/test_*.py` files
- Use pytest fixtures from `tests/conftest.py`
- Test both success and error cases
- Aim for >80% coverage on changed files

### Automated Checks

If you installed pre-commit hooks, they'll automatically run
before each commit:
- ruff (linting and formatting)
- basedpyright (type checking)
- pytest (tests)

You can also run pre-commit manually:

```bash
uv run pre-commit run --all-files
```

## Troubleshooting

### uv Not Installed

Install uv using the official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python Version Too Old

Lola requires Python 3.13+. Check your version:

```bash
python --version
```

If too old, install Python 3.13+ using your system package
manager or [pyenv](https://github.com/pyenv/pyenv).

### Tests Fail on Initial Setup

1. Verify Python version: `python --version`
2. Ensure virtual environment is activated:
   `source .venv/bin/activate`
3. Reinstall dependencies: `uv sync --group dev`

### Git Push Fails (Permission Denied)

Configure SSH keys for GitHub:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh

## Resources

- **[AGENTS.md](AGENTS.md)**: Development commands and
  architecture overview
- **[README.md](README.md)**: Project overview and installation
  instructions
- **[LICENSE](LICENSE)**: GPL-2.0-or-later license
- **[GitHub Contributing Guide]
  (https://opensource.guide/how-to-contribute/)**: General
  open-source contribution guidance

## Questions?

If you have questions about contributing, please open an issue on
GitHub. We're happy to help!
