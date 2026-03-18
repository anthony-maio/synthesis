"""
Setup configuration for Synthesis v2
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="synthesis-v2",
    version="2.0.0",
    author="Synthesis Development Team",
    description="Evolution Engine for AI Model Agency - Enable AI models to create, test, share, and evolve their own tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anthony-maio/synthesis-v2",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "click>=8.0.0",
        "tabulate>=0.9.0",
        "docker>=6.0.0",
        "psutil>=5.9.0",
        "aiofiles>=23.0.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "mcp": [
            "mcp>=0.1.0",  # MCP SDK when available
        ],
    },
    entry_points={
        "console_scripts": [
            "synthesis=synthesis_v2.cli:cli",
        ],
    },
)
