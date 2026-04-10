# Agent Instructions

## Python Environment

Before running any commands, ensure the virtual environment is activated:

**Windows:**

```powershell
.venv/Scripts/Activate.ps1
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

## Linting and Foramtting

After editing any Python file, run ruff check and ruff format:

```bash
ruff check --fix && ruff format
```
