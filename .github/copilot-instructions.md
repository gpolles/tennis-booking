# Tennis Book - AI Coding Agent Instructions

## Project Overview

Tennis Book is a Python application for managing and analyzing tennis-related data. The project is in early stages with a basic structure:

- **Entry point**: `tennis-book.py` - single main application file
- **Dependencies**: Listed in `requirements.txt` (currently empty/minimal)
- **Architecture**: Monolithic Python script pattern (no multi-module structure yet)

## Essential Setup

To work in this project, always:

1. Activate the virtual environment:

   ```bash
   source venv/bin/activate  # macOS/Linux
   # or
   python -m venv venv
   source venv/bin/activate  # if first time
   ```

2. Before running or modifying code, ensure dependencies are installed:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the application with:
   ```bash
   python tennis-book.py
   ```

## Code Organization & Patterns

- **Single-file architecture**: Currently all code lives in `tennis-book.py`
- **Entry pattern**: Uses `if __name__ == "__main__":` with a `main()` function
- **Module docstrings**: Files start with `#!/usr/bin/env python3` shebang and module-level docstring

## Development Workflow

- **Testing**: No test framework currently in place - consider pytest for future additions
- **Linting/Formatting**: No configured formatter (black/flake8) - recommend adding if expanding
- **Version control**: Git repository present with main branch

## Dependency Management

The `requirements.txt` file is currently empty. When adding dependencies:

- Update `requirements.txt` with pinned versions
- Test that `pip install -r requirements.txt` works cleanly
- Document new dependencies in README.md if they're user-facing

## When to Ask for Clarification

Tennis Book is a green-field project with minimal existing conventions. When:

- Extending beyond the main() function, clarify whether to create separate modules
- Adding database/file persistence, ask about data storage patterns
- Expanding UI/CLI features, confirm interaction style with the user
