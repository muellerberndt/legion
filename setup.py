from setuptools import setup, find_packages

setup(
    name="r4dar",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "click",
        "sqlalchemy",
        "aiohttp",
        "pytest",
        "pytest-asyncio",
    ],
    entry_points={
        "console_scripts": [
            "r4dar=src.cli.main:cli",
        ],
    },
)
