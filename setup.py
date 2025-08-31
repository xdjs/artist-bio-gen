#!/usr/bin/env python3
"""
Setup script for Artist Bio Generator package.
"""

from setuptools import setup, find_packages

# Read version from package
version = {}
with open("artist_bio_gen/__init__.py") as f:
    exec(f.read(), version)

# Read requirements
with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="artist-bio-gen",
    version=version["__version__"],
    author=version["__author__"],
    description=version["__description__"],
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "artist-bio-gen=artist_bio_gen.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: General",
    ],
    keywords="openai api biography generation database postgresql",
    project_urls={
        "Source": "https://github.com/your-org/artist-bio-gen",
        "Bug Reports": "https://github.com/your-org/artist-bio-gen/issues",
    },
)