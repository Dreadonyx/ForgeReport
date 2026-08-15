from setuptools import find_packages, setup


with open("README.md", "r", encoding="utf-8") as handle:
    long_description = handle.read()


setup(
    name="forgereport",
    version="0.1.0",
    description="Raw input. Professional output.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ForgeReport",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "python-docx>=0.8.11",
        "weasyprint>=60.0",
        "requests>=2.31",
        "pyyaml>=6.0",
        "python-slugify>=8.0",
        "python-dotenv>=1.0",
    ],
    entry_points={
        "console_scripts": [
            "forgereport=forgereport.cli:main",
        ],
    },
    python_requires=">=3.10",
)
