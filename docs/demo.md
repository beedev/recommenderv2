# MCP AI Commit Demo - Testing automatic provenance tracking

This file demonstrates the improved commit flag system where:

1. AI interactions are logged with `commit_included=False`
2. When a commit is created, all uncommitted interactions are consolidated
3. After successful commit, interactions are marked with `commit_included=True`
4. This prevents duplicate inclusion in future commits

## Test Interaction Details

- **exec_id**: ab3c086b-7075-4a8a-aae2-f0e1e5654ec7
- **Model**: anthropic/claude-sonnet-4-20250514
- **Current Status**: commit_included=False (ready for consolidation)

## Expected Behavior

When this file is committed, the commit message should automatically include:
- AI provenance footer with exec_id
- Prompt and response details
- Model information
- Timestamp data

After commit, the database flag will be updated to `commit_included=True`.