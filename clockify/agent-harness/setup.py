from pathlib import Path

from setuptools import find_namespace_packages, setup

ROOT = Path(__file__).parent

setup(
    name="cli-anything-clockify",
    version="0.1.0",
    description="Agent-native Clockify time tracking, projects, teams, and reports",
    long_description=(ROOT / "cli_anything/clockify/README.md").read_text(
        encoding="utf-8"
    ),
    long_description_content_type="text/markdown",
    author="CLI-Anything contributors",
    license="Apache-2.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(
        include=["cli_anything.clockify*"], exclude=["*.tests*"]
    ),
    package_data={"cli_anything.clockify": ["README.md", "skills/SKILL.md"]},
    install_requires=["click>=8.0", "requests>=2.28", "prompt-toolkit>=3.0"],
    extras_require={"dev": ["pytest>=7.0", "responses>=0.23", "build"]},
    entry_points={
        "console_scripts": [
            "cli-anything-clockify=cli_anything.clockify.clockify_cli:main"
        ]
    },
)
