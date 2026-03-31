"""Backward-compatible entry point.

Prefer: ``dynamodb-mcp-server`` CLI or ``python -m dynamodb_mcp_server``.
"""

from dynamodb_mcp_server.__main__ import main

if __name__ == "__main__":
    main()
