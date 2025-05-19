import pytest

# This helps properly configure pytest-asyncio
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )