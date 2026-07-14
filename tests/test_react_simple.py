"""Simple test to verify ReAct architecture is working."""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("测试 ReAct 图结构")
print("=" * 60)

# Test 1: Import modules
try:
    from note_agent.agent.graph_react import build_react_graph
    from note_agent.agent.tools import ALL_TOOLS
    print("✅ 模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

# Test 2: Build graph
try:
    graph = build_react_graph()
    print(f"✅ ReAct 图构建成功")
except Exception as e:
    print(f"❌ ReAct 图构建失败: {e}")
    sys.exit(1)

# Test 3: Check tools
try:
    print(f"✅ 工具数量: {len(ALL_TOOLS)}")
    print("   工具列表:")
    for tool in ALL_TOOLS:
        print(f"   - {tool.name}")
except Exception as e:
    print(f"❌ 工具检查失败: {e}")
    sys.exit(1)

# Test 4: Check tool signatures
try:
    from note_agent.agent.tools import infer_note_structure
    import inspect
    sig = inspect.signature(infer_note_structure.func)
    print(f"✅ infer_note_structure 参数: {list(sig.parameters.keys())}")
except Exception as e:
    print(f"❌ 工具签名检查失败: {e}")
    sys.exit(1)

print("=" * 60)
print("✅ ReAct 架构基础验证通过")
print("=" * 60)
