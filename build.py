"""Build script for creating the standalone .exe with PyInstaller."""

import subprocess
import sys


def main():
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "VoxtralTranscriber",
        "--add-data", "src;src",
        "main.py",
    ]

    print("Running PyInstaller...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\nBuild complete! Executable is in the dist/ folder.")


if __name__ == "__main__":
    main()
