#!/bin/bash
# G3DT Demo - Start isolated SiteBoon UI
# This starts the UI showing only G3DT folders

cd "$(dirname "$0")"

# Load environment
export $(cat .env | xargs)

echo "Starting G3DT Demo UI..."
echo "  Port: $PORT"
echo "  Workspace: $WORKSPACES_ROOT"
echo ""
echo "Open http://localhost:$PORT in your browser"
echo ""

# Start the UI
npx @siteboon/claude-code-ui --port $PORT
