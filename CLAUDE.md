# CLAUDE.md - 项目指令文件

## 开发者背景与目标

- **身份**: 西北农林科技大学，信息与计算科学专业，大二在读
- **研究兴趣**: AI Agent 安全、大模型安全（Prompt Injection、Jailbreak、数据投毒、模型鲁棒性等）
- **考研目标**: 西安电子科技大学，网络空间安全专硕
- **短期计划**:
  - 暑假前往西安电子科技大学 / 西安交通大学 / 西北工业大学 / 西安邮电大学 的导师组实习
  - 两周内联系导师，需要准备项目展示材料和技术储备
- **当前阶段**:
  - 深入理解并完善本 RAG Agent 项目（作为基础技术展示）
  - 使用 Claude Code 开发 AI 安全方向的新代码，不再手敲复现
  - 积累可写入简历/联系导师邮件的安全相关项目
- **已收到的反馈**:
  - **西电导师团队**: 项目偏 demo、偏 toy，建议加入 workflow、harness，增进对技术细节的理解
  - **创业公司负责人**: 建议学习 LangGraph、自动化理论、深度学习、TypeScript
- **现实约束**: 时间紧张，不可能全部学完。当前策略是优先做**易上手的网络安全相关技术**来升级项目，让它脱离 toy 感，两周内能拿得出手联系导师
- **学习背景**: 无实际工程团队开发经验，零基础自学 Agent、RAG、大模型安全。依赖 AI 编程工具辅助学习和开发。此前 Python 学习方式为跟课 + 手敲复现，从未接触过 vibe coding 工具。从现在起改用 vibe coding 方式开发：AI 生成代码后，只看基本结构和搞懂干什么，不再逐行手敲复现，因为联系导师的时间窗口很紧。

### 协助原则

- 解释技术概念时兼顾深度与可理解性，帮助建立扎实的理论基础
- 写代码时注重工程质量（结构清晰、有注释、可扩展），便于作为项目展示
- 涉及安全方向时，主动关联 AI 安全的前沿论文、攻击手法、防御方案
- 帮助准备联系导师的材料（邮件、简历项目描述、技术总结）
- **优先级判断**: 时间紧迫，建议方案时优先选择见效快、能在短期内落地的方向，避免推荐需要长期学习才能产出的技术栈。不过为了拓宽知识面，相关复杂技术需要简单罗列与介绍。

### 工程规范要求

由于开发者缺乏实际团队协作经验，在给出方案和写代码时必须遵守以下原则：

1. **动手前先对齐**：写代码之前，先确认思路是否足够工程化。如果开发者提出的想法存在更规范的做法，主动指出并解释为什么业界/团队实践中那样做更好。
2. **参考业界实践**：解释架构设计、模块拆分、命名规范、错误处理等时，引用互联网公司或实际工程团队的常见做法（如 LangChain/LangGraph 的官方最佳实践、常见 RAG 系统的生产级架构模式、业界安全基准等），让开发者了解「真正团队里是怎么做的」。
3. **不只是能跑，要能讲**：代码除了能正确运行，结构要清晰到可以对着导师一行行解释。每个模块的职责、为什么这样拆分、这样做防住了什么风险，都能说清楚。
4. **杜绝 toy 感**：避免硬编码、全局变量滥用、错误处理缺失、配置散落等学生项目常见问题。每次改动后自觉检查：这段代码放到生产环境还缺什么。

---

## 项目概述

王道408数据结构智能答疑助手 —— 基于 ReAct Agent 架构的 RAG 知识库问答系统。
- **前端**: Streamlit
- **Agent 框架**: LangGraph + LangChain
- **LLM**: 阿里通义千问 (DashScope API)
- **向量数据库**: ChromaDB
- **知识库来源**: 王道408数据结构 PDF

## 项目结构

```
├── streamlit_app.py          # 入口，Streamlit Web UI
├── react_agent.py            # ReAct Agent（LangGraph 构建）
├── model/factory.py          # 模型工厂（ChatTongyi + DashScopeEmbeddings）
├── config/                   # YAML 配置
│   ├── rag.yml               # 模型类型/名称
│   ├── chroma.yml            # ChromaDB 配置
│   ├── prompts.yml           # Prompt 路径
│   └── agent.yml             # Agent 工具列表
├── rag/                      # RAG 核心
│   ├── ds_rag_service.py     # RAG 服务（检索、定位、格式化）
│   ├── vector_store.py       # ChromaDB 封装
│   ├── KnowledgeBaseService.py # PDF 入库
│   └── file_history_store.py # 文件持久化聊天历史
├── tools/agent_tools.py      # LangChain 工具（检索/对比/总结）
├── prompts/main_prompt.txt   # 系统提示词
├── utils/                    # 工具模块（配置加载、日志、路径）
└── eval/run_eval.py          # RAGAS 评估
```

## 环境

- **Python**: 3.14 (python.org framework installer)
- **macOS** 开发环境
- API Key 通过环境变量 `DASHSCOPE_API_KEY` 或 Streamlit secrets 配置
- 无 `.env` 文件（eval 脚本除外）

## 常用命令

```bash
# 启动应用
streamlit run streamlit_app.py

# 知识库入库（首次或更新时，递归扫描 data/ 下所有子文件夹）
python -c "from rag.KnowledgeBaseService import ingest; ingest()"

# 运行评估
python eval/run_eval.py
```

## 已知问题

- macOS python.org 安装可能遇到 SSL 证书验证失败（`unable to get local issuer certificate`）
  - 解决: 运行 `/Applications/Python 3.14/Install Certificates.command`
  - 或设置环境变量: `export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")`
- 本地代理（ClashX 等）未运行时会导致连接失败，`streamlit_app.py` 已做代理环境变量清除

---

## 项目升级总体编排

> 以下为项目升级的顶层规划，目标是两周内让项目脱离 toy 感，能拿得出手联系导师。

### 总路线图

```
                        ┌──────────────────────┐
                        │  ① LangGraph 黑盒拆分  │ ← 当前第一步，两个版本共同的前置工程
                        │  手动 StateGraph       │
                        │  控制流/数据流分离      │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
    ┌─────────┴─────────┐                   ┌───────────┴──────────┐
    │ ②a 安全版 Agent    │                   │ ②b 纯 Agent 版        │
    └─────────┬──────────┘                   └───────────┬──────────┘
              │                                         │
              └──────────────────┬──────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │ ③ 研究目标导师论文        │
                    │ · 结合项目形成自己的思考   │
                    │ · 带着问题联系导师         │
                    └─────────────────────────┘
```

- **① 是必经之路**：不管是安全版还是纯 Agent 版，都需要先把当前 `create_agent` 黑盒拆成手动 StateGraph，获得对每个节点的完全控制权。这一步不涉及新功能，是纯粹的架构重构。
- **②a 与 ②b 是并行分支**：两个版本共享同一个 LangGraph 骨架，在骨架上挂不同的节点。安全版侧重防御，纯 Agent 版侧重检索质量与工程化。
- **③ 是连接导师的关键**：项目升级完成后，阅读目标导师近年的论文（尤其是 AI 安全方向），结合自己在项目中踩过的坑和思考，带着有深度的问题去联系导师，而不是空手说「我对你的方向感兴趣」。

### 一、安全防护体系

> 对应西电导师「AI Agent 安全」方向，是展示核心竞争力的关键模块。

- **Prompt Injection 防御**
  - 输入清洗 + 指令隔离（具体方案待定）
  - 在 input_guard 节点加入 Query Rewriting
- **越狱攻击（Jailbreak）防护**
  - System Prompt 加固：在 prompt 中显式声明角色边界与拒绝规则
  - 意图识别：在 Agent 执行前增加一层轻量级意图分类器
- **内容安全**
  - 输出过滤：对 LLM 输出做敏感词/违规内容检测
  - 输入审计日志：记录所有用户输入，便于事后审查

### 二、Agent 架构升级

> 当前 ReAct Agent 过于简单，需要加入 workflow 和 harness等等（技术选型还不确定，也有可能加入其他技术）

- **Workflow 升级：从「黑盒」到「白盒」**
  - 当前架构（黑盒）：`create_agent(model, prompt, tools)` — 一个函数封装了所有逻辑，内部不可见、不可控
  - 目标架构（白盒）：用 LangGraph StateGraph 显式拆分为多个结点，每个节点职责单一、可单独测试、可插拔，下面是一个初步的构想（不一定非要这样做）

  **StateGraph 节点拆分（白盒）：**

  ```
  create_agent(model, prompt, tools)  ──拆成──→  StateGraph
                                                     ├── ① input_guard    安全门（新增）
                                                     ├── ② agent          LLM决策+回答
                                                     ├── ③ retrieve       纯检索+计数（从agent中拆分）
                                                     ├── ④ summarize      LLM总结（从agent中拆分）
                                                     ├── ⑤ output_guard  输出审查（新增）
                                                     └── ⑥ format        页码定位+流式输出（原execute_stream后半段）
  ```

  - ① **input_guard（安全门）**：安全检查 + Query Rewriting（具体技术待定），不通过的直接拒绝
  - ② **agent（LLM 决策+回答）**：纯粹的 LLM 调用，决定是否检索、如何回答，不混杂检索逻辑
  - ③ **retrieve（纯检索）**：只做向量检索 + 结果计数，不含 LLM 调用，职责单一
  - ④ **summarize（LLM 总结）**：将检索结果 + 用户问题交给 LLM 生成总结回答
  - ⑤ **output_guard（输出审查）**：对最终输出做安全检查（敏感信息泄露、越狱成功判定），不安全的输出打码或拦截
  - ⑥ **format（格式化输出）**：页码定位 + 流式输出，原 `execute_stream` 的后半段逻辑




### 三、RAG 检索增强

> 当前 RAG 仅为简单的向量检索，检索质量直接影响回答准确性。

- **混合检索**
  - BM25 稀疏检索（关键词匹配）+ 向量稠密检索（语义匹配）
  - 两种结果做融合排序（如 RRF: Reciprocal Rank Fusion）
- **重排序（Re-ranking）**
  - 初检 → Cross-encoder 重排序 → Top-K 送入 LLM
  - 可选模型：bge-reranker、Cohere Rerank API
- **查询重写（Query Rewriting）**
  - 在 input_guard 节点中实现，具体技术待定
- **文档分块优化**
  - 当前：固定大小分块 → 升级为语义分块（按段落/小节边界）
  - 父子文档（Parent-Child）：检索小块，返回大块上下文

### 四、工程化建设

> 让项目具备生产级代码的基本特征，写进简历时有说服力。

- **配置管理**
  - 已有 YAML 统一配置 → 补充环境变量管理 + 配置校验
  - 区分 dev / prod 环境配置
- **日志与链路追踪**
  - 结构化日志（JSON 格式），含 trace_id 串联一次完整请求
  - 接入 LangSmith / LangFuse 做 LLM 调用链可观测
- **错误处理与降级**
  - LLM API 不可用时的兜底策略（缓存回复 / 友好降级提示）
  - 分级错误码：可重试错误 vs 不可重试错误
- **评估体系**
  - RAGAS 自动化评估（已有基础脚本 eval/run_eval.py）
  - 建立评估数据集 → 每次改动后跑回归评估 → 对比报告
- **测试框架**
  - pytest 单元测试（工具函数、RAG 检索、配置加载等）
  - API Mock：DashScope API 的 mock 层，支持离线测试

### 优先级排序（两周冲刺）

| 优先级 | 模块 | 理由 |
|--------|------|------|
| P0 | 安全防护体系 | 西电导师的核心研究方向，差异化竞争力 |
| P0 | Agent 架构升级（Workflow） | 「加入 workflow」 |
| P1 | RAG 检索增强（混合检索+重排序） | 提升回答质量，展示时效果明显 |
| P1 | 工程化（日志+错误处理+配置） | 消除 toy 感，简历加分 |
| P2 | 多 Agent 协作 | 加分项，但两周内可能时间不够 |
| P2 | 评估体系+测试 | 长期有价值，但展示时看不到 |

## 代码风格

- 注释使用中文
- 模块导入分组: 系统模块 → 第三方模块 → 自定义模块
- 配置通过 `utils/config_handler.py` 统一加载 YAML
- 日志通过 `utils/logger_handler.py` 统一配置
- 模型生成的代码要和原有代码保持一致风格