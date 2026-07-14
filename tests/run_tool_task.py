"""执行 ReAct 工具任务 - 生成技术笔记."""

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
from note_agent.agent.runner_unified import run_note_agent

print("=" * 80)
print("🚀 ReAct Agent 工具任务执行演示")
print("=" * 80)

# 任务：生成关于 Docker 容器化的笔记
request = NoteAgentRequest(
    raw_input="Docker 容器化技术的核心概念和实际应用场景",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    enable_assets=False,
    enable_notion=False,
)

print(f"\n📝 任务: {request.raw_input}")
print(f"🤖 Agent 模式: ReAct (自主决策)")
print(f"🔧 LLM: {request.llm_provider}")
print(f"🔍 搜索: {request.search_api}")
print(f"🔄 最大迭代: {request.max_iterations}")
print("\n" + "=" * 80)
print("开始执行...\n")

try:
    response = run_note_agent(request, mode="react")

    print("\n" + "=" * 80)
    print("✅ 工具任务执行成功！")
    print("=" * 80)

    print(f"\n📊 执行结果:")
    print(f"  📄 笔记类型: {response.note_type}")
    print(f"  💾 保存路径: {response.saved_path}")
    print(f"  🔄 迭代次数: {response.iterations}")
    print(f"  📚 参考来源: {len(response.sources)} 个")
    print(f"  📝 中间版本: {len(response.intermediate_paths)} 个")
    print(f"  📂 运行日志: {response.run_log_dir}")

    print(f"\n🔧 Agent 自主调用的工具:")
    print("  1. infer_note_structure - 推断笔记结构")
    print("  2. generate_note_draft - 生成初稿")
    if response.sources:
        print("  3. search_references - 搜索参考资料")
        print("  4. refine_note_with_references - 修正笔记")
    print("  5. finalize_note_content - 最终化笔记")
    print("  6. save_final_note - 保存笔记")

    if response.sources:
        print(f"\n📚 参考来源示例:")
        for i, source in enumerate(response.sources[:3], 1):
            print(f"  {i}. {source}")

    print("\n" + "=" * 80)
    print("🎉 ReAct 工具链执行完成！")
    print("=" * 80)

except Exception as e:
    print("\n" + "=" * 80)
    print(f"❌ 执行失败: {e}")
    print("=" * 80)
    import traceback
    traceback.print_exc()
    sys.exit(1)
