"""Improved ReAct mode test script with better error handling."""

import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner_unified import run_note_agent

# Check API key
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key or api_key.startswith("your_"):
    print("=" * 60)
    print("❌ API Key 配置错误")
    print("=" * 60)
    print("请在 .env 文件中配置 DEEPSEEK_API_KEY")
    print("或者将测试脚本中的 llm_provider 改为其他已配置的提供商")
    sys.exit(1)

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
print(f"输入: {request.raw_input}")
print(f"提供商: {request.llm_provider}")
print(f"最大迭代: {request.max_iterations}")
print("=" * 60)

try:
    response = run_note_agent(request, mode="react")
    print("\n✅ ReAct 模式运行成功!")
    print("=" * 60)
    print(f"保存路径: {response.saved_path}")
    print(f"笔记类型: {response.note_type}")
    print(f"迭代次数: {response.iterations}")
    print(f"参考来源数: {len(response.sources)}")
    print(f"运行日志: {response.run_log_dir}")
    print("=" * 60)
except Exception as e:
    print(f"\n❌ ReAct 模式运行失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
