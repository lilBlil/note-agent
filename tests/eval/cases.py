"""
Comprehensive eval cases covering diverse scenarios.

Each case documents:
- name: unique identifier (used in snapshot filenames)
- input: the raw user input
- expected_note_type: expected classification (soft check — LLM may vary)
- dimensions: which quality dimensions this case exercises
- needs_assets: whether the output should have asset planning
- edge_case_of: what edge case this represents (if any)
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Case dimension tags for filtering
# ---------------------------------------------------------------------------
class Dim:
    THEORY = "theory"           # Theoretical/conceptual content
    CODE = "code"               # Code-heavy content
    MATH = "math"               # Math/formula-heavy content
    ARCHITECTURE = "architecture"  # System/software architecture
    COMPARISON = "comparison"   # Multi-option comparison
    ENGLISH = "english"         # English input
    MIXED_LANG = "mixed_lang"   # Chinese + English mixed
    SHORT = "short"             # Very brief input
    LONG = "long"               # Lengthy/multi-paragraph input
    VAGUE = "vague"             # Underspecified/fuzzy input
    URL = "url"                 # URL-based input
    TUTORIAL = "tutorial"       # Tutorial/guide style
    SURVEY = "survey"           # Literature survey


# ---------------------------------------------------------------------------
# Case definitions
# ---------------------------------------------------------------------------

EVAL_CASES: list[dict[str, Any]] = [
    # === 学习笔记 ===
    {
        "id": "case_01_quantum",
        "name": "量子计算基础概念",
        "input": "量子计算基础：解释量子比特（qubit）与经典比特的区别、量子门操作、"
                 "量子纠缠和量子叠加原理，以及Shor算法和Grover算法的基本思路和应用前景。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.THEORY, Dim.MATH],
        "needs_assets": True,      # should plan formula assets
        "min_sections": 4,
        "key_terms": ["qubit", "量子比特", "Shor", "Grover", "纠缠", "叠加"],
    },
    {
        "id": "case_02_python_decorator",
        "name": "Python装饰器详解",
        "input": "Python装饰器详解：从一等公民函数对象、闭包机制、简单装饰器到带参数的装饰器、"
                 "类装饰器、functools.wraps的使用。每个阶段都要有完整的代码示例说明输出结果。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.CODE, Dim.TUTORIAL],
        "needs_assets": True,      # should plan code examples
        "min_sections": 4,
        "key_terms": ["装饰器", "闭包", "functools", "wraps", "@", "语法糖"],
    },
    {
        "id": "case_03_cap_theorem",
        "name": "CAP定理深入理解",
        "input": "深入理解分布式系统中的CAP定理。请解释一致性（Consistency）、可用性（Availability）、"
                 "分区容错性（Partition Tolerance）的严格定义，为什么三者不可兼得，"
                 "分别给出CP系统和AP系统的实际产品案例，讨论PACELC扩展。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.THEORY, Dim.COMPARISON],
        "needs_assets": False,     # pure text concept
        "min_sections": 4,
        "key_terms": ["CAP", "一致性", "可用性", "分区容错", "PACELC", "CP", "AP"],
    },
    {
        "id": "case_04_closure",
        "name": "单一概念：闭包",
        "input": "什么是闭包（Closure）？请用JavaScript举例说明闭包的实际用途。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.CODE, Dim.SHORT],
        "needs_assets": True,      # should have code examples
        "min_sections": 2,
        "key_terms": ["闭包", "closure", "JavaScript", "作用域"],
    },
    {
        "id": "case_05_k8s_service_mesh",
        "name": "Kubernetes Service Mesh选型",
        "input": "在Kubernetes集群中实现Service Mesh服务网格：详细对比Istio、"
                 "Linkerd和Consul Connect三种方案的架构设计、sidecar模式实现、"
                 "性能基准测试数据、资源开销、安全特性和生产环境适用场景。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.COMPARISON, Dim.ARCHITECTURE, Dim.MIXED_LANG],
        "needs_assets": True,      # needs comparison table/chart and architecture diagram
        "min_sections": 4,
        "key_terms": ["Service Mesh", "Istio", "Linkerd", "Consul", "sidecar", "Kubernetes"],
    },

    # === 论文阅读笔记 ===
    {
        "id": "case_06_transformer",
        "name": "Transformer论文阅读",
        "input": "详细阅读并分析论文《Attention Is All You Need》(Vaswani et al., 2017)。"
                 "总结以下内容：1) Self-Attention机制的数学定义和直觉解释 "
                 "2) Multi-Head Attention的设计动机 3) Positional Encoding的几种方案对比 "
                 "4)  encoder-decoder整体架构 5) 相比RNN/LSTM的优势 6) 后续影响力分析。",
        "expected_note_type": "论文阅读笔记",
        "dimensions": [Dim.THEORY, Dim.MATH, Dim.ARCHITECTURE, Dim.MIXED_LANG],
        "needs_assets": True,      # needs formula + architecture diagram
        "min_sections": 5,
        "key_terms": ["Attention", "Transformer", "Self-Attention", "Multi-Head", "Positional Encoding"],
    },
    {
        "id": "case_07_rag_paper",
        "name": "RAG最新论文综述",
        "input": "阅读并综述以下RAG领域的论文：Self-RAG (Asai et al., 2024)、"
                 "Corrective RAG (Yan et al., 2024)、RAFT (Zhang et al., 2024)、"
                 "以及GraphRAG (Microsoft, 2024)。对比它们在检索策略、生成质量、"
                 "推理能力和计算开销方面的异同。",
        "expected_note_type": "论文阅读笔记",
        "dimensions": [Dim.SURVEY, Dim.COMPARISON, Dim.MIXED_LANG],
        "needs_assets": True,      # comparison table
        "min_sections": 4,
        "key_terms": ["RAG", "Self-RAG", "Corrective RAG", "RAFT", "GraphRAG", "检索"],
    },

    # === GitHub项目分析 ===
    {
        "id": "case_08_fastapi",
        "name": "FastAPI项目架构分析",
        "input": "深入分析GitHub开源项目 https://github.com/tiangolo/fastapi 的架构设计。"
                 "关注：1) 基于Starlette的异步框架设计 2) 依赖注入（Dependency Injection）系统的实现 "
                 "3) 基于Pydantic的自动数据验证和序列化 4) OpenAPI/Swagger文档自动生成机制 "
                 "5) 路由注册和中间件系统的设计模式 6) 性能优化策略。",
        "expected_note_type": "GitHub项目分析笔记",
        "dimensions": [Dim.CODE, Dim.ARCHITECTURE, Dim.URL, Dim.MIXED_LANG],
        "needs_assets": True,      # needs architecture diagram + code examples
        "min_sections": 5,
        "key_terms": ["FastAPI", "Starlette", "依赖注入", "Pydantic", "OpenAPI", "异步"],
    },
    {
        "id": "case_09_redo",
        "name": "仅URL输入：Redo构建工具",
        "input": "https://github.com/apenwarr/redo",
        "expected_note_type": "GitHub项目分析笔记",
        "dimensions": [Dim.URL, Dim.SHORT],
        "needs_assets": False,
        "min_sections": 3,
        "key_terms": ["redo", "build", "apenwarr"],
        "edge_case": "仅URL输入，无其他描述",
    },

    # === 面试准备笔记 ===
    {
        "id": "case_10_url_shortener",
        "name": "系统设计：短链接服务",
        "input": "系统设计面试题：设计一个类似TinyURL的短链接服务。需求：1) 支持每天1亿次写入、"
                 "10亿次读取 2) 短链接长度不超过7个字符 3) 支持自定义短链接 4) 链接可设置过期时间 "
                 "5) 提供点击统计分析。请从数据模型、API设计、短链生成算法、存储方案、"
                 "缓存策略和扩展性方案等角度给出完整设计。",
        "expected_note_type": "面试准备笔记",
        "dimensions": [Dim.ARCHITECTURE, Dim.THEORY],
        "needs_assets": True,      # needs system architecture diagram
        "min_sections": 5,
        "key_terms": ["短链接", "TinyURL", "哈希", "base62", "分库分表", "缓存"],
    },
    {
        "id": "case_11_go_interview",
        "name": "Golang面试核心知识点",
        "input": "准备Golang后端开发面试，覆盖以下核心主题：goroutine调度模型(GMP)、"
                 "channel的底层实现和happens-before语义、GC机制(三色标记+混合写屏障)、"
                 "slice扩容策略、map并发安全问题、interface底层结构(eface/iface)、"
                 "以及Go内存模型。每个主题给出面试常问的深度问题。",
        "expected_note_type": "面试准备笔记",
        "dimensions": [Dim.CODE, Dim.THEORY, Dim.MIXED_LANG],
        "needs_assets": True,      # needs code examples
        "min_sections": 6,
        "key_terms": ["goroutine", "GMP", "channel", "GC", "slice", "map", "interface"],
    },

    # === 技术方案笔记 ===
    {
        "id": "case_12_microservice_vs_monolith",
        "name": "微服务 vs 单体架构技术选型",
        "input": "技术方案：为一个中型电商平台（日活50万，开发团队30人）选择架构方案。"
                 "从以下维度详细对比微服务架构和单体架构：开发效率（包括本地开发环境搭建、"
                 "CI/CD复杂度）、部署与运维（容器化、服务发现、配置管理、日志聚合）、"
                 "性能与可靠性（网络开销、故障隔离、弹性伸缩）、团队组织（康威定律、"
                 "团队自治性）、数据管理（分布式事务、数据一致性）。给出推荐方案和迁移路径。",
        "expected_note_type": "技术方案笔记",
        "dimensions": [Dim.COMPARISON, Dim.ARCHITECTURE, Dim.LONG],
        "needs_assets": True,      # needs comparison charts
        "min_sections": 5,
        "key_terms": ["微服务", "单体架构", "康威定律", "分布式事务", "CI/CD", "容器化"],
    },
    {
        "id": "case_13_mysql_deadlock",
        "name": "MySQL死锁排查方案",
        "input": "MySQL InnoDB死锁问题排查与解决方案。内容包括：1) 死锁产生的四个必要条件及"
                 "InnoDB中对应的实现机制 2) 如何通过 SHOW ENGINE INNODB STATUS 解读死锁日志 "
                 "3) INFORMATION_SCHEMA.INNODB_TRX/LOCKS/LOCK_WAITS 三张表的联合分析 "
                 "4) 常见的死锁场景（并发insert gap lock、唯一键冲突、外键级联更新）"
                 "5) 预防和解决方案：调整事务顺序、降级隔离级别、重试机制、乐观锁替代方案。",
        "expected_note_type": "技术方案笔记",
        "dimensions": [Dim.CODE, Dim.TUTORIAL],
        "needs_assets": True,      # needs code examples
        "min_sections": 5,
        "key_terms": ["InnoDB", "死锁", "gap lock", "INNODB_TRX", "隔离级别", "乐观锁"],
    },

    # === 研究综述笔记 ===
    {
        "id": "case_14_llm_hallucination",
        "name": "LLM幻觉问题研究综述",
        "input": "大语言模型(LLM)幻觉问题研究综述。系统梳理以下方面："
                 "1) 幻觉的分类（事实性幻觉 vs 忠实性幻觉；内在幻觉 vs 外在幻觉）"
                 "2) 产生原因（训练数据噪声、曝光偏差、解码策略、知识边界模糊、"
                 "对齐税/ sycophancy）3) 检测方法（基于不确定性估计、基于检索验证、"
                 "基于自一致性、基于LLM-as-judge）4) 缓解策略（RAG、知识编辑、"
                 "推理时验证、训练数据优化）5) 评估基准（TruthfulQA、HaluEval、"
                 "FActScore等）。覆盖2023-2025年的主要研究进展。",
        "expected_note_type": "研究综述笔记",
        "dimensions": [Dim.SURVEY, Dim.THEORY, Dim.LONG],
        "needs_assets": True,      # needs taxonomy diagram + comparison table
        "min_sections": 5,
        "key_terms": ["幻觉", "hallucination", "RAG", "TruthfulQA", "sycophancy", "事实性"],
    },
    {
        "id": "case_15_rag_survey",
        "name": "RAG技术综述",
        "input": "检索增强生成(Retrieval-Augmented Generation)技术综述。覆盖：1) Naive RAG的基本流程"
                 "(索引、检索、增强、生成)和局限性 2) Advanced RAG范式：预检索优化(滑窗、"
                 "元数据过滤)、检索后处理(重排序、压缩) 3) Modular RAG架构：搜索适配器、"
                 "记忆模块、路由分发 4) 评估方法：检索质量(Recall/Precision/NDCG)"
                 "和生成质量(Faithfulness/Relevance/Correctness) 5) 生产实践：延迟优化、"
                 "成本控制、多模态扩展。重点分析2024-2025年的最新进展。",
        "expected_note_type": "研究综述笔记",
        "dimensions": [Dim.SURVEY, Dim.THEORY, Dim.LONG, Dim.MIXED_LANG],
        "needs_assets": True,
        "min_sections": 5,
        "key_terms": ["RAG", "检索增强生成", "索引", "重排序", "Faithfulness", "多模态"],
    },

    # === 纯英文 ===
    {
        "id": "case_16_rust_ownership",
        "name": "Rust所有权系统",
        "input": "A comprehensive explanation of Rust's ownership system. Cover: "
                 "1) The three ownership rules 2) Move semantics vs Copy types "
                 "3) References and Borrowing (mutable vs immutable, borrowing rules) "
                 "4) Lifetimes: elision rules, explicit lifetime annotations, "
                 "and common lifetime patterns (struct lifetimes, 'static) "
                 "5) How ownership enables memory safety without garbage collection "
                 "6) Practical patterns: Rc/Arc, RefCell/Mutex for interior mutability. "
                 "Include code examples for each concept.",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.CODE, Dim.THEORY, Dim.ENGLISH],
        "needs_assets": True,      # needs code examples
        "min_sections": 5,
        "key_terms": ["ownership", "borrowing", "lifetimes", "Rc", "Arc", "RefCell", "Mutex"],
    },
    {
        "id": "case_17_backpropagation_en",
        "name": "反向传播算法数学推导（英文）",
        "input": "Derive the backpropagation algorithm for training multi-layer neural networks "
                 "from first principles. Start with gradient descent, derive the chain rule "
                 "for a simple 2-layer network, then generalize to L layers. Include the "
                 "derivatives for common activation functions (sigmoid, tanh, ReLU, softmax) "
                 "and common loss functions (MSE, cross-entropy). Explain the vanishing "
                 "gradient problem mathematically. Provide numpy-style pseudocode for the "
                 "forward and backward passes.",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.MATH, Dim.CODE, Dim.ENGLISH],
        "needs_assets": True,      # needs formula + code
        "min_sections": 4,
        "key_terms": ["backpropagation", "gradient descent", "chain rule", "softmax", "ReLU"],
    },

    # === 边缘用例 ===
    {
        "id": "case_18_vague_ai",
        "name": "模糊输入：想了解AI",
        "input": "想了解一下AI",
        "expected_note_type": None,   # open-ended, any type is acceptable
        "dimensions": [Dim.VAGUE, Dim.SHORT],
        "needs_assets": False,
        "min_sections": 2,
        "key_terms": ["AI", "人工智能"],
        "edge_case": "极度模糊的输入，测试agent如何处理欠指定",
    },
    {
        "id": "case_19_technical_debt",
        "name": "纯文字概念：技术债务",
        "input": "什么是技术债务（Technical Debt）？请分类说明各种类型的技术债务"
                 "（代码债务、设计债务、架构债务、文档债务、测试债务），"
                 "并讨论每种类型产生的原因、识别方法和偿还策略。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.THEORY, Dim.TUTORIAL],
        "needs_assets": False,     # pure text, no assets needed
        "min_sections": 3,
        "key_terms": ["技术债务", "Technical Debt", "重构", "偿还"],
    },
    {
        "id": "case_20_docker_tutorial",
        "name": "Docker从入门到实践",
        "input": "Docker从入门到实践完整教程：1) Docker核心概念（Image/Layer/Container/Registry）"
                 "2) Dockerfile编写最佳实践（多阶段构建、层缓存优化、安全加固）"
                 "3) docker run/exec/build/compose 常用命令详解 4) Docker Compose多容器编排"
                 "5) 数据卷和网络管理 6) Docker Compose vs Kubernetes 适用场景对比。"
                 "所有概念都配有可运行的示例，适合初学者从零开始学习。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.TUTORIAL, Dim.CODE, Dim.COMPARISON],
        "needs_assets": True,      # needs code examples + comparison
        "min_sections": 5,
        "key_terms": ["Docker", "Dockerfile", "Compose", "Image", "Container", "多阶段构建"],
    },
    {
        "id": "case_21_react_vs_vue",
        "name": "React vs Vue技术选型",
        "input": "React vs Vue.js 技术选型全面对比。从以下维度分析：1) 学习曲线（JSX vs 模板语法、"
                 "响应式原理）2) 生态系统丰富度（路由、状态管理、UI库）3) 性能表现"
                 "（Virtual DOM实现差异、编译时优化）4) TypeScript支持体验 5) 社区活跃度和"
                 "企业采用率 6) 适合的团队类型和项目规模。给出明确的选型建议。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.COMPARISON, Dim.CODE],
        "needs_assets": True,      # comparison table
        "min_sections": 5,
        "key_terms": ["React", "Vue", "JSX", "Virtual DOM", "TypeScript", "响应式"],
    },
    {
        "id": "case_22_chinese_only",
        "name": "纯中文输入：古文观止",
        "input": "请帮我系统整理《古文观止》中唐宋八大家的散文特点、代表作品和文学价值。"
                 "分别介绍韩愈、柳宗元、欧阳修、苏洵、苏轼、苏辙、王安石、曾巩的文章风格，"
                 "并选取每人最有代表性的1-2篇作品进行简要赏析。",
        "expected_note_type": "学习笔记",
        "dimensions": [Dim.THEORY, Dim.LONG],
        "needs_assets": False,     # literary analysis, no technical assets
        "min_sections": 5,
        "key_terms": ["古文观止", "唐宋八大家", "韩愈", "欧阳修", "苏轼", "散文"],
        "edge_case": "纯中文人文类输入，无技术内容，验证agent在非技术主题上的表现",
    },
]

# Helper to get cases filtered by dimension
def cases_by_dim(dimension: str) -> list[dict]:
    return [c for c in EVAL_CASES if dimension in c["dimensions"]]

# Helper to get edge cases only
def edge_cases() -> list[dict]:
    return [c for c in EVAL_CASES if "edge_case" in c]

# Helper to get cases by note type
def cases_by_type(note_type: str) -> list[dict]:
    return [c for c in EVAL_CASES if c.get("expected_note_type") == note_type]
