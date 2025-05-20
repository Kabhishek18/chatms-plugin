#!/bin/bash

# Compatible test runner for ChatMS Plugin
echo "ChatMS Plugin - Compatible Test Runner"
echo "======================================"

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Install required test dependencies
echo "Installing/updating dependencies..."
python -m pip install --upgrade pytest pytest-asyncio python-magic Pillow python-jose bcrypt cryptography pydantic fastapi uvicorn motor aioredis aiofiles

# Create temporary directories for tests
echo "Setting up test environment..."
mkdir -p /tmp/chatms_test_storage
mkdir -p logs

# Function to run a specific test file
run_test_file() {
    local test_file=$1
    local test_name=$2
    
    echo ""
    echo "Running $test_name..."
    echo "$(printf '=%.0s' {1..50})"
    
    # Try different pytest configurations based on what's available
    if python -c "import pytest_asyncio" 2>/dev/null; then
        echo "Using pytest-asyncio..."
        python -m pytest "$test_file" -v --tb=short -p no:warnings 2>&1 | tee "logs/${test_name}_results.log"
    else
        echo "Running without pytest-asyncio plugin..."
        python -m pytest "$test_file" -v --tb=short --disable-warnings 2>&1 | tee "logs/${test_name}_results.log"
    fi
    
    local exit_code=${PIPESTATUS[0]}
    if [ $exit_code -eq 0 ]; then
        echo "✅ $test_name: PASSED"
    else
        echo "❌ $test_name: FAILED (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Initialize test results
passed_tests=0
failed_tests=0
total_tests=0

# Test files to run (in order of complexity)
declare -a test_files=(
    "tests/test_security.py:Security Tests"
    "tests/test_storage.py:Storage Tests" 
    "tests/test_websocket.py:WebSocket Tests"
    "tests/test_database.py:Database Tests"
    "tests/test_chat_system.py:Chat System Tests"
)

# Check pytest-asyncio configuration
echo "Checking pytest configuration..."
if python -c "import pytest_asyncio; print('pytest-asyncio version:', pytest_asyncio.__version__)" 2>/dev/null; then
    echo "✅ pytest-asyncio is available"
else
    echo "⚠️  pytest-asyncio not found, installing..."
    python -m pip install pytest-asyncio
fi

# Run individual test files
for test_info in "${test_files[@]}"; do
    IFS=':' read -r test_file test_name <<< "$test_info"
    
    if [ -f "$test_file" ]; then
        total_tests=$((total_tests + 1))
        if run_test_file "$test_file" "$test_name"; then
            passed_tests=$((passed_tests + 1))
        else
            failed_tests=$((failed_tests + 1))
        fi
    else
        echo "⚠️  Test file not found: $test_file"
    fi
done

echo ""
echo "Individual Test Summary"
echo "======================"
echo "Total test files: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"

# Run all tests together with compatible options
echo ""
echo "Running All Tests Together..."
echo "============================="

# Try different configurations
if python -c "import pytest_asyncio" 2>/dev/null; then
    echo "Running with pytest-asyncio..."
    python -m pytest tests/ -v --tb=short -p no:warnings 2>&1 | tee "logs/all_tests_results.log"
else
    echo "Running basic pytest..."
    python -m pytest tests/ -v --tb=short 2>&1 | tee "logs/all_tests_results.log"
fi

all_tests_exit_code=${PIPESTATUS[0]}

echo ""
echo "Final Test Summary"
echo "=================="
if [ $all_tests_exit_code -eq 0 ]; then
    echo "✅ ALL TESTS PASSED!"
else
    echo "❌ Some tests failed. Check the logs for details."
    echo ""
    echo "Common issues and solutions:"
    echo "1. Missing dependencies - run: pip install -r requirements.txt"
    echo "2. pytest-asyncio configuration - check pyproject.toml"
    echo "3. Import errors - ensure PYTHONPATH is set correctly"
fi

echo ""
echo "Log files created in logs/ directory:"
echo "- Individual test logs: logs/*_results.log"
echo "- Combined test log: logs/all_tests_results.log"

# Check test dependencies
echo ""
echo "Dependency Check:"
python -c "
try:
    import pytest
    print('✅ pytest:', pytest.__version__)
except ImportError:
    print('❌ pytest not found')

try:
    import pytest_asyncio
    print('✅ pytest-asyncio:', pytest_asyncio.__version__)
except ImportError:
    print('❌ pytest-asyncio not found')

try:
    import chatms_plugin
    print('✅ chatms_plugin module found')
except ImportError:
    print('❌ chatms_plugin module not found')
"

# Cleanup
echo ""
echo "Cleaning up..."
rm -rf /tmp/chatms_test_storage

echo "Test execution completed!"
exit $all_tests_exit_code