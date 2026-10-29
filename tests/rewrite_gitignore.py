#!/usr/bin/env python3
import os

gitignore_path = r"e:\proIT\.gitignore"

content = """# Python/Django
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg
*.egg-info/
dist/
build/
*.egg-info/
.coverage
htmlcov/
.mypy_cache/
.tox/

# Virtual environment (singular choice)
.venv/
venv/
env/
ENV/

# Environment variables
.env
*.env

# Database
*.db
*.sqlite3

# VS Code
.vscode/

# But keep these if they exist:
# settings.json, launch.json (they're small and useful)

# Logs
*.log
logs/

# Media/files (Django user-uploaded files)
media/

# OS
.DS_Store
Thumbs.db
"""

with open(gitignore_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Successfully rewritten {gitignore_path}")