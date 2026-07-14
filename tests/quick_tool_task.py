"""快速执行一个 ReAct 工具任务."""

import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

# 检查 API Key
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key or api_key.startswith("your_"):
    print("❌ 请先在 .env 文件中配置 DEEPSEEK_API_KEY")
    sys.exit(1)

from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner_unified import run_note_agent

print("=" * 70)
print("🚀 执行 ReAct 工具任务")
print("=" * 70)

# 创建一个简单的任务
request = NoteAgentRequest(
    raw_input="什么是微服务架构？它的优缺点是什么？",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    enable_assets=False,
    enable_notion=False,
)

print(f"\n📝 任务: {request.raw_input}")
print(f"🤖 模式: ReAct Agent")
print(f"🔧 LLM: {request.llm_provider}")
print("\n" + "=" * 70)
print("开始执行...\n")

try:
    response = run_note_agent(request, mode="react")

    print("\n" + "=" * 70)
    print("✅ 任务执行成功！")
    print("=" * 70)
    print(f"\n📄 笔记类型: {response.note_type}")
    print(f"💾 保存路径: {response.saved_path}")
    print(f"🔄 迭代次数: {response.iterations}")
    print(f"📚 参考来源: {len(response.sources)} 个")
    print(f"📝 中间版本: {len(response.intermediate_paths)} 个")

    print("\n" + "=" * 70)
    print("🎉 ReAct 工具任务完成！")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 执行失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
