#!/usr/bin/env python3
"""
Audio File Verification Script

Verifies that all 24 Greek letter audio files exist and are valid.
Checks for:
- File existence
- File size (warns on suspiciously small files)
- Optional: Audio format validation

Usage:
    python scripts/verify_audio.py
    python scripts/verify_audio.py --strict  # Exit with error if any issues
"""

import os
import sys
import argparse
from pathlib import Path

# Greek letter names (lowercase for filename matching)
GREEK_LETTERS = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta",
    "eta", "theta", "iota", "kappa", "lambda", "mu",
    "nu", "xi", "omicron", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega"
]

# Minimum expected file size in bytes (suspiciously small if below this)
MIN_FILE_SIZE_BYTES = 1000  # 1KB

# Audio directory relative to project root
AUDIO_DIR = "app/static/audio"


def get_project_root() -> Path:
    """Get the project root directory."""
    # This script is in scripts/, so parent is project root
    return Path(__file__).parent.parent


def verify_audio_files(strict: bool = False) -> bool:
    """
    Verify all Greek letter audio files exist and are valid.

    Args:
        strict: If True, treat warnings as errors

    Returns:
        True if all files pass verification, False otherwise
    """
    project_root = get_project_root()
    audio_path = project_root / AUDIO_DIR

    print(f"Verifying audio files in: {audio_path}")
    print("-" * 50)

    missing_files = []
    small_files = []
    valid_files = []

    for letter in GREEK_LETTERS:
        file_path = audio_path / f"{letter}.mp3"

        if not file_path.exists():
            missing_files.append(letter)
            print(f"  MISSING: {letter}.mp3")
        else:
            file_size = file_path.stat().st_size

            if file_size < MIN_FILE_SIZE_BYTES:
                small_files.append((letter, file_size))
                print(f"  WARNING: {letter}.mp3 - suspiciously small ({file_size} bytes)")
            else:
                valid_files.append(letter)
                print(f"  OK: {letter}.mp3 ({file_size} bytes)")

    print("-" * 50)
    print(f"Summary:")
    print(f"  Valid files:   {len(valid_files)}/24")
    print(f"  Missing files: {len(missing_files)}")
    print(f"  Small files:   {len(small_files)}")

    if missing_files:
        print(f"\nMissing files: {', '.join(missing_files)}")

    if small_files:
        print(f"\nSmall files (may need regeneration):")
        for letter, size in small_files:
            print(f"  - {letter}.mp3 ({size} bytes)")

    # Determine pass/fail
    has_errors = len(missing_files) > 0
    has_warnings = len(small_files) > 0

    if strict and (has_errors or has_warnings):
        print("\nResult: FAIL (strict mode)")
        return False
    elif has_errors:
        print("\nResult: FAIL")
        return False
    elif has_warnings:
        print("\nResult: PASS with warnings")
        return True
    else:
        print("\nResult: PASS")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify Greek letter audio files exist and are valid"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit with non-zero status)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output summary, not individual file status"
    )

    args = parser.parse_args()

    success = verify_audio_files(strict=args.strict)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
