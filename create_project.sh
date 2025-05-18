#!/bin/bash

# Root directory
PROJECT_ROOT="$(pwd)"

# List of files and directories to create
FILES_AND_DIRS=(
  "$PROJECT_ROOT/pyproject.toml"
  "$PROJECT_ROOT/setup.py"
  "$PROJECT_ROOT/README.md"
  "$PROJECT_ROOT/LICENSE"
  "$PROJECT_ROOT/.env.example"

  "$PROJECT_ROOT/chatms-plugin/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/config.py"
  "$PROJECT_ROOT/chatms-plugin/exceptions.py"

  "$PROJECT_ROOT/chatms-plugin/core/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/core/chat_system.py"
  "$PROJECT_ROOT/chatms-plugin/core/connection.py"
  "$PROJECT_ROOT/chatms-plugin/core/security.py"
  "$PROJECT_ROOT/chatms-plugin/core/analytics.py"

  "$PROJECT_ROOT/chatms-plugin/models/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/models/base.py"
  "$PROJECT_ROOT/chatms-plugin/models/user.py"
  "$PROJECT_ROOT/chatms-plugin/models/chat.py"
  "$PROJECT_ROOT/chatms-plugin/models/message.py"

  "$PROJECT_ROOT/chatms-plugin/database/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/database/base.py"
  "$PROJECT_ROOT/chatms-plugin/database/postgresql.py"
  "$PROJECT_ROOT/chatms-plugin/database/mongodb.py"

  "$PROJECT_ROOT/chatms-plugin/storage/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/storage/base.py"
  "$PROJECT_ROOT/chatms-plugin/storage/local.py"
  "$PROJECT_ROOT/chatms-plugin/storage/s3.py"
  "$PROJECT_ROOT/chatms-plugin/storage/gcp.py"
  "$PROJECT_ROOT/chatms-plugin/storage/azure.py"

  "$PROJECT_ROOT/chatms-plugin/notifications/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/notifications/base.py"
  "$PROJECT_ROOT/chatms-plugin/notifications/fcm.py"
  "$PROJECT_ROOT/chatms-plugin/notifications/apns.py"
  "$PROJECT_ROOT/chatms-plugin/notifications/email.py"

  "$PROJECT_ROOT/chatms-plugin/api/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/api/rest.py"
  "$PROJECT_ROOT/chatms-plugin/api/websocket.py"
  "$PROJECT_ROOT/chatms-plugin/api/middlewares.py"

  "$PROJECT_ROOT/chatms-plugin/utils/__init__.py"
  "$PROJECT_ROOT/chatms-plugin/utils/encryption.py"
  "$PROJECT_ROOT/chatms-plugin/utils/validation.py"
  "$PROJECT_ROOT/chatms-plugin/utils/file_processing.py"
  "$PROJECT_ROOT/chatms-plugin/utils/rate_limiting.py"

  "$PROJECT_ROOT/examples/simple_server.py"
  "$PROJECT_ROOT/examples/chat_client.py"
  "$PROJECT_ROOT/examples/config_examples/local_dev.py"
  "$PROJECT_ROOT/examples/config_examples/production.py"

  "$PROJECT_ROOT/tests/__init__.py"
  "$PROJECT_ROOT/tests/conftest.py"
  "$PROJECT_ROOT/tests/test_chat_system.py"
  "$PROJECT_ROOT/tests/test_database.py"
  "$PROJECT_ROOT/tests/test_storage.py"
  "$PROJECT_ROOT/tests/test_websocket.py"
  "$PROJECT_ROOT/tests/test_security.py"
)

# Create directories and files
for path in "${FILES_AND_DIRS[@]}"; do
  dir=$(dirname "$path")
  mkdir -p "$dir"
  touch "$path"
done

echo "✅ Project structure created successfully!"
