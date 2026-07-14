"""执行 ReAct 工具任务 - 生成关于 LangGraph 的笔记."""

import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

# 检查 API Key
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key or api_key.startswith("your_"):
    print("❌ 请先配置 DEEPSEEK_API_KEY")
    sys.exit(1)

from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner_unified import stream_note_agent_events

print("=" * 80)
print("🚀 ReAct Agent 工具任务执行")
print("=" * 80)

request = NoteAgentRequest(
    raw_input="什么是 LangGraph？它的核心概念和使用场景是什么？",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    enable_assets=False,
    enable_notion=False,
)

print(f"\n📝 任务输入: {request.raw_input}")
print(f"🤖 Agent 模式: ReAct (自主决策工具调用)")
print(f"🔧 LLM: {request.llm_provider}")
print(f"🔍 搜索: {request.search_api}")
print(f"🔄 最大迭代: {request.max_iterations}")
print("\n" + "=" * 80)
print("开始执行工具链...\n")

tool_calls = []
current_step = ""

try:
    for event in stream_note_agent_events(request, mode="react"):
        event_type = event.get("type")

        if event_type == "info":
            text = event.get("text", "")
            # 记录工具调用
            if "正在" in text or "开始" in text:
                tool_calls.append(text)
                print(f"🔧 {text}")
            elif "✅" in text:
                print(f"   {text}")

        elif event_type == "node_start":
            node_name = event.get("node_name", "")
            step_label = event.get("step_label", "")
            current_step = step_label
            if node_name == "agent":
                print(f"\n🧠 Agent 决策中...")
            elif node_name == "tools":
                print(f"⚙️  执行工具...")

        elif event_type == "warning":
            print(f"⚠️  {event.get('text', '')}")

        elif event_type == "error":
            print(f"❌ 错误: {event.get('message', '')}")
            if event.get("fatal"):
                break

        elif event_type == "done":
            state = event.get("state", {})
            usage = event.get("usage", {})

            print("\n" + "=" * 80)
            print("✅ 工具链执行完成！")
            print("=" * 80)

            print(f"\n📊 执行结果:")
            print(f"  📄 笔记类型: {state.get('note_type', 'N/A')}")
            print(f"  💾 保存路径: {state.get('saved_path', 'N/A')}")
            print(f"  🔄 迭代次数: {state.get('iteration_count', 0)}")
            print(f"  📚 参考来源: {len(state.get('sources', []))} 个")
            print(f"  📝 中间版本: {len(state.get('intermediate_paths', []))} 个")

            if usage.get('total_tokens'):
                print(f"\n💰 Token 使用:")
                print(f"  输入: {usage.get('total_input_tokens', 0):,}")
                print(f"  输出: {usage.get('total_output_tokens', 0):,}")
                print(f"  总计: {usage.get('total_tokens', 0):,}")

            print(f"\n📂 运行日志: {event.get('run_log_dir', 'N/A')}")

            print("\n🔧 工具调用统计:")
            for i, call in enumerate(tool_calls, 1):
                print(f"  {i}. {call}")

            print("\n" + "=" * 80)
            print("🎉 任务成功完成！")
            print("=" * 80)
            break

except KeyboardInterrupt:
    print("\n\n⏹️  用户中断执行")
    sys.exit(1)
except Exception as e:
    print(f"\n\n❌ 执行失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
