# Claude Code + MCP AI Commit Integration Setup

## Problem
Claude Code prompts and responses are not automatically being logged to the PostgreSQL database because automatic interception is not configured.

## Solution: Manual Logging Function

Since automatic MCP integration requires complex setup, here's a simple function to manually log important Claude Code sessions:

### Quick Log Function

Create this file in your repository: `log-claude-session.py`

```python
#!/usr/bin/env python3
import sys
import asyncio
sys.path.insert(0, "/Users/bharath/mcp-ai-commit/src")

from mcp_ai_commit.interceptor import get_interceptor

async def log_session(prompt_text, response_text, topic="claude_code_session"):
    interceptor = get_interceptor()
    
    context = {
        'repo_path': '/Users/bharath/Desktop/AgenticAI/Recommender',
        'branch_name': 'main',
        'user': 'bharath',
        'session_type': 'claude_code_manual',
        'topic': topic
    }
    
    print(f"📝 Logging Claude Code session: {topic}")
    exec_id = await interceptor.log_prompt(prompt_text, context)
    
    model_info = {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514'
    }
    
    await interceptor.log_response(exec_id, response_text, model_info)
    print(f"✅ Session logged with exec_id: {exec_id}")
    return exec_id

# Example usage
if __name__ == "__main__":
    prompt = input("Enter the prompt: ")
    response = input("Enter the response summary: ")
    topic = input("Enter topic (optional): ") or "general"
    
    exec_id = asyncio.run(log_session(prompt, response, topic))
    print(f"Use 'python show-ai-history.py' to view all logged sessions")
```

### Usage Examples

```bash
# Log current conversation manually
python log-claude-session.py

# Or use directly in Python
python3 -c "
import asyncio
import sys
sys.path.insert(0, '/Users/bharath/mcp-ai-commit/src')
from mcp_ai_commit.interceptor import get_interceptor

async def quick_log():
    interceptor = get_interceptor()
    
    context = {
        'repo_path': '/Users/bharath/Desktop/AgenticAI/Recommender',
        'branch_name': 'main',
        'user': 'bharath',
        'session_type': 'claude_code_fix',
        'topic': 'database_debugging'
    }
    
    prompt = 'User reported that Claude Code prompts were not being logged to PostgreSQL database'
    exec_id = await interceptor.log_prompt(prompt, context)
    
    response = 'Fixed database field mappings, updated CLI history display, and created manual logging scripts'
    model_info = {'provider': 'anthropic', 'model': 'claude-sonnet-4-20250514'}
    await interceptor.log_response(exec_id, response, model_info)
    
    print(f'Logged session: {exec_id}')

asyncio.run(quick_log())
"
```

## Current Status

✅ **Database is working**: PostgreSQL connection and schema are properly configured
✅ **Manual logging works**: Can log prompts/responses programmatically  
✅ **History viewing works**: Scripts available to view logged interactions
❌ **Automatic interception**: Not yet configured for Claude Code sessions

## Recommendation

For now, manually log important Claude Code sessions using the provided scripts. This gives you full control over what gets logged and when.

To view all logged interactions:
```bash
python show-ai-history.py
```