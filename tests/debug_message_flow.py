"""Debug script to understand message flow."""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

# Simulate the message flow
messages = []

# Step 1: Initial state
messages.append(SystemMessage(content="System prompt"))
messages.append(HumanMessage(content="User input"))

print("=" * 60)
print("Step 1: Initial messages")
for i, msg in enumerate(messages):
    print(f"{i}: {type(msg).__name__}: {msg.content[:50]}")

# Step 2: Agent responds with tool calls
ai_msg = AIMessage(
    content="I'll call a tool",
    tool_calls=[{"name": "some_tool", "args": {}, "id": "call_1"}]
)
messages.append(ai_msg)

print("\nStep 2: After agent decision")
for i, msg in enumerate(messages):
    tc = " [HAS TOOL_CALLS]" if isinstance(msg, AIMessage) and msg.tool_calls else ""
    print(f"{i}: {type(msg).__name__}{tc}")

# Step 3: Tool executes and returns
tool_msg = ToolMessage(content="Tool result", tool_call_id="call_1")
messages.append(tool_msg)

print("\nStep 3: After tool execution")
for i, msg in enumerate(messages):
    tc = " [HAS TOOL_CALLS]" if isinstance(msg, AIMessage) and msg.tool_calls else ""
    print(f"{i}: {type(msg).__name__}{tc}")

# Step 4: Agent is called again - this is where we add context
# PROBLEM: If we just append HumanMessage, the sequence is valid
messages.append(HumanMessage(content="Context update"))

print("\nStep 4: After adding context (VALID)")
for i, msg in enumerate(messages):
    tc = " [HAS TOOL_CALLS]" if isinstance(msg, AIMessage) and msg.tool_calls else ""
    print(f"{i}: {type(msg).__name__}{tc}")

print("\n" + "=" * 60)
print("✅ This sequence is VALID")
print("=" * 60)

# Now simulate the INVALID case
print("\n" + "=" * 60)
print("INVALID Case: Adding HumanMessage BEFORE ToolMessage")
print("=" * 60)

messages_invalid = []
messages_invalid.append(SystemMessage(content="System prompt"))
messages_invalid.append(HumanMessage(content="User input"))
messages_invalid.append(AIMessage(
    content="I'll call a tool",
    tool_calls=[{"name": "some_tool", "args": {}, "id": "call_1"}]
))
# BUG: Adding HumanMessage here before ToolMessage
messages_invalid.append(HumanMessage(content="Context update"))  # WRONG!

print("\nInvalid sequence:")
for i, msg in enumerate(messages_invalid):
    tc = " [HAS TOOL_CALLS]" if isinstance(msg, AIMessage) and msg.tool_calls else ""
    print(f"{i}: {type(msg).__name__}{tc}")

print("\n❌ This will cause: 'tool_calls' must be followed by tool messages")
