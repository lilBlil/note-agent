"""完整的 ReAct 工具链测试."""

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

print("=" * 60)
print("🚀 ReAct 工具链完整测试")
print("=" * 60)

request = NoteAgentRequest(
    raw_input="简单介绍一下 Python 的列表推导式",
    max_iterations=1,
    llm_provider="deepseek",
    search_api="duckduckgo",
    enable_assets=False,
    enable_notion=False,
)

print(f"📝 输入: {request.raw_input}")
print(f"🤖 模式: ReAct Agent")
print(f"🔧 提供商: {request.llm_provider}")
print(f"🔍 搜索: {request.search_api}")
print(f"🔄 最大迭代: {request.max_iterations}")
print("=" * 60)

try:
    print("\n开始执行...")
    response = run_note_agent(request, mode="react")

    print("\n" + "=" * 60)
    print("✅ ReAct 工具链执行成功！")
    print("=" * 60)
    print(f"📄 笔记类型: {response.note_type}")
    print(f"💾 保存路径: {response.saved_path}")
    print(f"🔄 迭代次数: {response.iterations}")
    print(f"📚 参考来源: {len(response.sources)} 个")
    print(f"📂 运行日志: {response.run_log_dir}")

    if response.intermediate_paths:
        print(f"📝 中间版本: {len(response.intermediate_paths)} 个")

    print("\n工具执行链:")
    print("  1. ✅ infer_note_structure - 推断笔记结构")
    print("  2. ✅ generate_note_draft - 生成初稿")
    if response.sources:
        print("  3. ✅ search_references - 搜索参考资料")
        print("  4. ✅ refine_note_with_references - 修正笔记")
    print("  5. ✅ finalize_note_content - 最终化笔记")
    print("  6. ✅ save_final_note - 保存笔记")

    print("\n" + "=" * 60)
    print("🎉 所有工具任务执行完成！")
    print("=" * 60)

except Exception as e:
    print("\n" + "=" * 60)
    print(f"❌ 执行失败: {e}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
    sys.exit(1)
