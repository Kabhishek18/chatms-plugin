#!/bin/bash

# Script to run the fixed ChatMS tests

echo "Running ChatMS Plugin Tests"
echo "============================"

# Install required test dependencies
echo "Installing test dependencies..."
pip install pytest pytest-asyncio python-magic Pillow

# Set PYTHONPATH to include the current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run specific test files with verbose output
echo ""
echo "Running Storage Tests..."
pytest tests/test_storage.py -v

echo ""
echo "Running WebSocket Tests..."
pytest tests/test_websocket.py -v

echo ""
echo "Running Security Tests..."
pytest tests/test_security.py -v

echo ""
echo "Running Database Tests..."
pytest tests/test_database.py -v

echo ""
echo "Running Chat System Tests..."
pytest tests/test_chat_system.py -v

echo ""
echo "Running ALL tests..."
pytest tests/ -v --tb=short

echo ""
echo "Test execution completed!"