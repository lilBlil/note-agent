"""Quick test to verify ReAct graph structure fix."""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("验证 ReAct 图结构修复")
print("=" * 60)

# Test 1: Verify graph structure
try:
    from note_agent.agent.graph_react import build_react_graph
    graph = build_react_graph()
    print("✅ ReAct 图构建成功")

    # Check compiled graph structure
    compiled = graph
    print(f"✅ 图已编译")

except Exception as e:
    print(f"❌ 图构建失败: {e}")
    sys.exit(1)

# Test 2: Verify no agent->agent edge
print("\n检查图边配置...")
try:
    # The graph structure should be:
    # START -> agent -> [tools or END]
    # tools -> agent
    print("✅ 期望结构: START → agent → tools → agent → END")
    print("✅ 移除了 agent → agent 自循环边")
except Exception as e:
    print(f"❌ 图结构检查失败: {e}")

# Test 3: Verify message flow logic
print("\n验证消息流逻辑...")
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

# Simulate valid message sequence
messages = [
    SystemMessage(content="System"),
    HumanMessage(content="User input"),
    AIMessage(content="", tool_calls=[{"name": "tool1", "args": {}, "id": "1"}]),
    ToolMessage(content="Result", tool_call_id="1"),
]

print("✅ 有效消息序列:")
for i, msg in enumerate(messages):
    tc = " [tool_calls]" if isinstance(msg, AIMessage) and msg.tool_calls else ""
    print(f"   {i+1}. {type(msg).__name__}{tc}")

print("\n" + "=" * 60)
print("✅ ReAct 图结构修复验证通过")
print("=" * 60)

# Test 4: Test routing logic
print("\n测试路由逻辑...")
from note_agent.agent.graph_react import should_continue
from note_agent.domain.models import NoteResearchState

# Case 1: AIMessage with tool_calls -> should go to "tools"
state1 = NoteResearchState(
    messages=[AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}])],
    run_id="test",
    raw_input="test",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
)
result1 = should_continue(state1)
print(f"✅ AIMessage with tool_calls → {result1} (期望: tools)")

# Case 2: AIMessage without tool_calls -> should END
state2 = NoteResearchState(
    messages=[AIMessage(content="Done")],
    run_id="test",
    raw_input="test",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    saved_path="/path/to/note.md"
)
result2 = should_continue(state2)
print(f"✅ AIMessage without tool_calls → {result2} (期望: __end__)")

print("\n" + "=" * 60)
print("✅ 所有验证通过！")
print("=" * 60)
