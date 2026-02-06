# AGENTS.md - Agentic Coding Guidelines

## Project Overview

Stock market returns analysis dashboard using Python, Dash, Pandas, and Polars.

## Activating the environment

```bash
source .venv/Scripts/activate
```

## Build/Run Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run the dashboard
python returns_dashboard.py

# Run with hot reload (development)
python returns_dashboard.py --reload
```

## Lint/Format Commands

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Type checking (if mypy is added)
# mypy .
```

## Testing Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_calcs.py

# Run single test
pytest tests/test_calcs.py::test_calculate_returns

# Run with coverage
pytest --cov=funcs --cov-report=html
```

## Code Style Guidelines

### Imports

- **Standard library**: Group first (e.g., `import json`, `from datetime import date`)
- **Third-party**: Group second (e.g., `import pandas as pd`, `import polars as pl`)
- **Local modules**: Group last (e.g., `from funcs.loaders import ...`)
- Use `from json import JSONDecodeError` for specific exceptions
- Sort within groups alphabetically

### Type Hints

- Use type hints for function parameters and return types
- Use `|` syntax for unions (e.g., `str | None`)
- Use `list[str]`, `dict[str, int]` instead of `typing.List`, `typing.Dict`
- Use `-> pd.DataFrame`, `-> pl.DataFrame` for dataframe returns
- Use `-> pd.Series` for series returns

### Naming Conventions

- **Functions**: `snake_case` (e.g., `load_fed_funds_rate`)
- **Variables**: `snake_case` (e.g., `fed_funds_rate`)
- **Constants**: `UPPER_CASE` (e.g., `MAX_RETRY_ATTEMPTS`)
- **Modules**: `snake_case` (e.g., `calcs_numpy.py`)
- **Classes**: `PascalCase` (if any)

### Function Structure

- Keep functions focused and single-purpose
- Use descriptive names (e.g., `calculate_dca_portfolio_value_with_fees_and_interest_vector`)
- Place `*` in parameters to force keyword arguments for optional params
- Example: `def func(required_arg, *, optional_arg=default)`

### Error Handling

- Use specific exceptions (e.g., `ValueError`)
- Use try/except for API calls
- Log errors with `print()` for now (consider adding logging later)

### DataFrame Operations

- **Pandas**: Use method chaining with `assign()`, `pipe()`
- **Polars**: Use expression API with `with_columns()`, `select()`
- Prefer Polars for new code (faster, more memory efficient)
- Keep pandas code in `loaders.py`, polars in `loaders_pl.py`

### String Formatting

- Use f-strings for formatting (e.g., `f"data/{filename}.csv"`)
- Use double quotes for strings consistently

### Comments

- Use docstrings for module and function documentation
- Use inline comments sparingly, only for complex logic
- Link to sources in comments when using formulas from external sources

### Environment Variables

- Access via `os.environ["VAR_NAME"]`
- Check existence before use: `"API_KEY" in os.environ`
- Store API keys in `.env` file (never commit secrets)

### Async Code

- Use `async def` for I/O operations (API calls)
- Use `asyncio.run()` for sync wrappers
- Use `async with httpx.AsyncClient()` for HTTP clients

### File Operations

- Use context managers (`with open(...)`) for file I/O
- Prefer Polars `read_csv`/`write_csv` over pandas for new code
- Use `use_pyarrow=True` for Polars CSV reading when available

## Project Structure

```
.
├── funcs/
│   ├── loaders.py        # Pandas-based data loaders
│   ├── loaders_pl.py     # Polars-based data loaders
│   ├── calcs.py          # Pandas-based calculations
│   └── calcs_numpy.py    # NumPy-based calculations
├── data/                 # Data files (CSV, Excel)
├── assets/               # Static assets (CSS, JS)
├── returns_dashboard.py  # Main Dash application
├── layout.py             # Dash layout components
└── pyproject.toml        # Project configuration
```

## Dependencies

Key packages:

- `dash` / `dash-bootstrap-components` - Web dashboard
- `pandas` / `polars` - Data manipulation
- `numpy` / `scipy` - Numerical computing
- `httpx` - HTTP client
- `plotly` - Visualization

## Notes

- Python version: 3.13.12 (strict)
- Package manager: `uv`
- Formatter/Linter: `ruff`
- No tests currently exist - add them to a `tests/` directory
- Dashboard runs on localhost:8050 by default
