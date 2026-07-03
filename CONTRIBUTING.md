# Contributing to Antigravity-K

We love your input! We want to make contributing to Antigravity-K as easy and transparent as possible.

## Development Process

1. **Fork the repo** and create your branch from `main`
2. **Set up your environment**:
   ```bash
   make venv
   source .venv/bin/activate
   make install
   make pre-commit
   ```
3. **Make your changes** following our coding conventions
4. **Run checks locally**:
   ```bash
   make check        # lint + format check + typecheck
   make test-quick   # fast tests
   ```
5. **Submit a Pull Request**

## Code Quality Standards

### Python

- **Style**: Follow PEP 8 via Ruff (line length: 120)
- **Types**: Use type hints for all public functions and methods
- **Docstrings**: Google-style docstrings for all public APIs
- **Imports**: Group standard library, third-party, first-party (use `isort`)

### Type Hints

All new code must include type hints:
```python
def process_items(items: list[str], threshold: float = 0.5) -> dict[str, int]:
    ...
```

### Error Handling

- Use specific exception types (not bare `except:`)
- Log exceptions with `logger.exception()` at the call site
- Never leak sensitive information in error messages
- Use the project's `error_classifier` for API error classification

### Testing

- Write tests for all new functionality
- Use pytest with async support (`pytest-asyncio`)
- Mark slow tests with `@pytest.mark.slow`
- Mark benchmark tests with `@pytest.mark.benchmark`
- Target minimum 30% coverage (increasing over time)

## Pull Request Guidelines

1. **One PR per feature/fix** — keep changes focused
2. **Write meaningful commit messages** following conventional commits:
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation
   - `refactor:` code restructuring
   - `test:` adding tests
   - `chore:` maintenance tasks
3. **Update CHANGELOG.md** for notable changes
4. **All checks must pass** before merge

## Project Structure

```
antigravity-k/
├── src/antigravity_k/     # Main package
│   ├── engine/            # Core engine modules
│   │   ├── memory/        # Memory providers
│   │   ├── code_intel/    # Code intelligence
│   │   └── provider_adapters/  # LLM provider adapters
│   ├── agents/            # Agent implementations
│   ├── api/               # FastAPI server
│   │   └── routes/        # API route handlers
│   ├── security/          # Security modules
│   ├── tools/             # Tool implementations
│   └── knowledge/         # Knowledge management
├── dashboard/             # Web dashboard (Vite + vanilla JS)
├── tests/                 # Test suite
├── scripts/               # Utility scripts
└── docs/                  # Documentation
```

## Getting Help

- Open an issue for bugs or feature requests
- Join our discussions for architecture questions
- Check `AGENTS.md` for AI agent interaction protocols

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
