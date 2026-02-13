"""Application versioning with auto-increment support.

Version format: MAJOR.MINOR.BUILD
- MAJOR: Manual increment for major releases
- MINOR: Manual increment for feature releases  
- BUILD: Auto-incremented from git commit count
"""

import os
import subprocess
from pathlib import Path

# Base version (manual)
MAJOR = 1
MINOR = 0

# Fallback build number (updated manually for Docker builds without git)
FALLBACK_BUILD = 13


def get_build_number() -> int:
    """Get build number from git commit count or fallback."""
    # First try: environment variable (for Docker builds)
    env_build = os.environ.get('APP_BUILD_NUMBER')
    if env_build:
        try:
            return int(env_build)
        except ValueError:
            pass
    
    # Second try: build number file (for Docker builds)
    build_file = Path(__file__).resolve().parent.parent / ".build_number"
    if build_file.exists():
        try:
            return int(build_file.read_text().strip())
        except (ValueError, IOError):
            pass
    
    # Third try: git commit count
    try:
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
    
    # Final fallback
    return FALLBACK_BUILD


def get_short_hash() -> str:
    """Get short git hash for dev builds."""
    # First try: environment variable
    env_hash = os.environ.get('APP_COMMIT_HASH')
    if env_hash:
        return env_hash
    
    # Second try: commit hash file (for Docker builds)
    hash_file = Path(__file__).resolve().parent.parent / ".commit_hash"
    if hash_file.exists():
        try:
            return hash_file.read_text().strip()
        except (ValueError, IOError):
            pass
    
    # Third try: git
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
    return "docker"


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
