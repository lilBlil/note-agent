"""Quick test script for ReAct mode."""

from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner_unified import run_note_agent

# Simple test case
request = NoteAgentRequest(
    raw_input="介绍一下 Python 的装饰器（decorator）",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    enable_assets=False,
    enable_notion=False,
)

print("=" * 60)
print("测试 ReAct 模式")
print("=" * 60)

try:
    response = run_note_agent(request, mode="react")
    print("\n✅ ReAct 模式运行成功!")
    print(f"保存路径: {response.saved_path}")
    print(f"笔记类型: {response.note_type}")
    print(f"迭代次数: {response.iterations}")
    print(f"参考来源数: {len(response.sources)}")
except Exception as e:
    print(f"\n❌ ReAct 模式运行失败: {e}")
    import traceback
    traceback.print_exc()
