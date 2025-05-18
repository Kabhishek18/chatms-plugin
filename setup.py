
from setuptools import setup, find_packages

# The setup script is a bit simpler - we're using pyproject.toml for most configuration
# This is mainly for compatibility with older tools

setup(
    name="chatms-plugin",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "chatms-server=chatms_plugin.examples.simple_server:main",
        ],
    },
)