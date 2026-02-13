"""Application versioning with auto-increment support.

Version format: MAJOR.MINOR.BUILD
- MAJOR: Manual increment for major releases
- MINOR: Manual increment for feature releases  
- BUILD: Auto-incremented from git commit count
"""

import subprocess
from pathlib import Path

# Base version (manual)
MAJOR = 1
MINOR = 0


def get_build_number() -> int:
    """Get build number from git commit count."""
    try:
        # Get the number of commits on current branch
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent.parent
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def get_short_hash() -> str:
    """Get short git hash for dev builds."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent.parent
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "dev"


def get_version() -> str:
    """Get full version string."""
    build = get_build_number()
    return f"{MAJOR}.{MINOR}.{build}"


def get_version_with_hash() -> str:
    """Get version with git hash for detailed display."""
    build = get_build_number()
    short_hash = get_short_hash()
    return f"{MAJOR}.{MINOR}.{build}-{short_hash}"


# Export version for easy import
__version__ = get_version()
