"""
ReAct Agent —— 基于 LangGraph StateGraph 手动构建（白盒架构）

架构（本次底座搭建的核心）:
  create_agent(model, prompt, tools)   ← 旧：一行黑盒
              ↓ 拆为 ↓
  StateGraph（手动构建，每个节点职责单一）
    ├── ① agent       LLM 决策：绑定工具，判断是否需要检索
    ├── ② retrieve    纯向量检索（不调 LLM）
    ├── ③ summarize   LLM 基于检索结果生成结构化回答
    └── ④ format      提取页码定位 + 流式输出

控制流:
  START → agent → [有 tool_call?]
                     ├── 是 → retrieve → summarize → format → END
                     └── 否 → summarize → format → END

对比旧版变化:
  - 旧: create_agent() 封装了 ReAct 循环、工具执行、消息管理
  - 新: 每个步骤都由手动编写的节点函数控制，可插拔、可单独测试
  - streamlit_app.py 的调用方式不变（execute_stream 接口保持兼容）
"""

# 系统模块
from typing import TypedDict, Annotated

# 第三方库
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
)

# 项目模块
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from utils.logger_handler import logger

# 导入工具函数（只用其 _get_rag 和 _llm_summarize）
from tools.agent_tools import (
    ds_knowledge_search,
    ds_concept_compare,
    ds_chapter_summary,
    _get_rag,
    _llm_summarize,
)

# ==================== State 定义 ====================

class AgentState(TypedDict):
    """
    AgentState —— StateGraph 中所有节点共享的数据结构。

    messages          — LangGraph add_messages 自动管理追加，不覆盖
                        贯穿整个图的生命周期，用于记录对话历史
    user_query        — 本轮用户输入，agent / summarize 节点读取
    task_type         — agent 选中的工具类型，retrieve 写入，
                        summarize 据此选择 prompt 模板
                        可选值: "search" / "compare" / "summary" / ""
    tool_name         — agent 调用的完整工具名，retrieve 写入
                        用于流式输出的指示文本，如 "ds_knowledge_search"
    retrieved_context — retrieve 节点存入的格式化文档（含页码标记）
                        summarize + format 节点读取
    final_answer      — summarize 节点生成的最终回答文本
                        format 节点读取后拼装输出
    page_locations    — format 节点提取的纯页码定位
                        UI 层通过 ReactAgent.page_locations 获取
    """
    messages: Annotated[list, add_messages]
    user_query: str
    task_type: str
    tool_name: str
    retrieved_context: str
    final_answer: str
    page_locations: str


# ==================== 节点函数 ====================

def agent_node(state: AgentState) -> dict:
    """
    ① agent —— LLM 决策节点。

    职责:
      - 将 3 个工具绑定到 LLM
      - 读取对话历史（messages），由 LLM 判断是否需要检索
      - 不实际执行工具，只输出决策结果

    输入: state["messages"]（含 SystemMessage + 历史 + 当前 HumanMessage）
    输出: AIMessage（可能包含 tool_calls，也可能直接回答）
    """
    logger.info("[节点① agent] LLM 开始决策")

    # 绑定工具：LLM 知道有 3 个工具可用，但由我们手动执行
    tools = [ds_knowledge_search, ds_concept_compare, ds_chapter_summary]
    llm_with_tools = chat_model.bind_tools(tools)

    # 调用 LLM：输入对话历史，输出决策结果
    response = llm_with_tools.invoke(state["messages"])

    # 记录工具调用情况
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_names = [tc.get("name", "?") for tc in response.tool_calls]
        logger.info(f"[节点① agent] 决定调用工具: {', '.join(tool_names)}")
    else:
        preview = (response.content or "")[:50]
        logger.info(f"[节点① agent] 决定直接回答 | 预览: {preview}...")

    return {"messages": [response]}


def retrieve_node(state: AgentState) -> dict:
    """
    ② retrieve —— 纯检索节点（不调 LLM）。

    职责:
      - 从 agent 输出的 tool_call 中提取查询参数
      - 调用 DSRagService.search(mode="full") 做向量检索
      - 根据工具名确定 task_type（影响后续 summarize 的 prompt 选择）

    输入: state["messages"]（最后一条是 agent 的 tool_calls）
    输出: retrieved_context（格式化文本）+ task_type
    """
    # 第一步：从最后一条 AI 消息中提取 tool_call 参数
    messages = state["messages"]
    last_ai_msg = None
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                last_ai_msg = msg
                break

    if last_ai_msg is None or not last_ai_msg.tool_calls:
        logger.warning("[节点② retrieve] 未找到 tool_calls，跳过检索")
        return {
            "retrieved_context": "",
            "task_type": "",
            "tool_name": "",
        }

    # 提取工具名和参数
    tool_call = last_ai_msg.tool_calls[0]
    tool_name = tool_call.get("name", "")
    tool_args = tool_call.get("args", {})

    # 不同工具的参数名不一样：query 或 chapter_name
    search_query = tool_args.get("query") or tool_args.get("chapter_name") or ""

    logger.info(f"[节点② retrieve] 工具: {tool_name} | 查询: {search_query[:50]}...")

    # 第二步：根据工具名确定 task_type
    if "compare" in tool_name:
        task_type = "compare"
    elif "summary" in tool_name or "chapter" in tool_name:
        task_type = "summary"
    else:
        task_type = "search"

    # 第三步：执行向量检索（纯 Python，不调 LLM）
    try:
        rag = _get_rag()
        context = rag.search(search_query, mode="full")

        if not context or "未在" in context:
            logger.warning(f"[节点② retrieve] 未检索到相关内容")
            return {
                "retrieved_context": "",
                "task_type": task_type,
                "tool_name": tool_name,
            }

        logger.info(f"[节点② retrieve] 检索成功 | 结果长度: {len(context)}")
        return {
            "retrieved_context": context,
            "task_type": task_type,
            "tool_name": tool_name,
        }

    except Exception as e:
        logger.error(f"[节点② retrieve] 检索失败 | 错误: {str(e)}")
        return {
            "retrieved_context": "",
            "task_type": task_type,
            "tool_name": tool_name,
        }


def summarize_node(state: AgentState) -> dict:
    """
    ③ summarize —— LLM 总结节点。

    职责:
      - 有检索结果时：调用 _llm_summarize，按 task_type 选模板生成结构化回答
      - 无检索结果时：agent 已经直接回答了，透传其内容

    输入: state["user_query"] + state["retrieved_context"] + state["task_type"]
    输出: final_answer（最终回答文本）
    """
    retrieved_context = state.get("retrieved_context", "")
    task_type = state.get("task_type", "")
    user_query = state.get("user_query", "")

    # 分支 1: 有检索结果 → 用模板生成回答
    if retrieved_context and task_type:
        logger.info(f"[节点③ summarize] 基于检索结果生成回答 | 模板: {task_type}")

        try:
            answer = _llm_summarize(user_query, retrieved_context, task_type)
            logger.info(f"[节点③ summarize] 回答生成完成 | 长度: {len(answer)}")
            return {
                "final_answer": answer,
                "messages": [AIMessage(content=answer)],
            }
        except Exception as e:
            logger.error(f"[节点③ summarize] 生成失败 | 错误: {str(e)}")
            return {
                "final_answer": f"抱歉，回答生成失败：{str(e)}",
                "messages": [AIMessage(content=f"抱歉，回答生成失败：{str(e)}")],
            }

    # 分支 2: 无检索结果 → agent 已直接回答，取最后一条 AI 消息
    messages = state["messages"]
    direct_answer = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            if hasattr(msg, "content") and msg.content:
                # 排除仅包含 tool_calls 的消息（其 content 通常为空）
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    direct_answer = msg.content
                    break

    if not direct_answer:
        direct_answer = "抱歉，我暂时无法回答这个问题，请尝试调整提问方式。"

    logger.info(f"[节点③ summarize] 直接回答路径 | 长度: {len(direct_answer)}")
    return {
        "final_answer": direct_answer,
    }


def format_node(state: AgentState) -> dict:
    """
    ④ format —— 格式化节点（不调 LLM）。

    职责:
      - 从 retrieved_context 中提取页码定位（复用 extract_location_only）
      - 不再额外调用 RAG 搜索，直接从已有数据提取

    输入: state["retrieved_context"]
    输出: page_locations（纯页码定位文本，供 UI 展示在 expander 中）
    """
    retrieved_context = state.get("retrieved_context", "")

    if not retrieved_context:
        logger.info("[节点④ format] 无检索结果，跳过页码提取")
        return {"page_locations": ""}

    try:
        # 复用 DSRagService 的 extract_location_only 方法
        # 从格式化文档中提取页码行，无需重新检索
        rag = _get_rag()
        locations = rag.extract_location_only(retrieved_context)

        if locations:
            logger.info(f"[节点④ format] 提取页码定位 | {len(locations.splitlines())} 条")
        else:
            logger.info("[节点④ format] 未提取到页码定位")

        return {"page_locations": locations}

    except Exception as e:
        logger.error(f"[节点④ format] 页码提取失败 | 错误: {str(e)}")
        return {"page_locations": ""}


# ==================== 路由函数 ====================

def route_after_agent(state: AgentState) -> str:
    """
    agent 节点后的条件路由。

    检查 agent 输出的最后一条消息是否包含 tool_calls：
      - 有 → "retrieve"（需要先去检索）
      - 无 → "summarize"（直接进入回答）

    这是 LangGraph 的 conditional_edge，等同于流程图的判断菱形。
    """
    messages = state["messages"]

    if not messages:
        return "summarize"

    last_msg = messages[-1]

    # 检查是否包含 tool_calls
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        logger.info("[路由] agent → retrieve（检测到工具调用）")
        return "retrieve"

    logger.info("[路由] agent → summarize（无需检索）")
    return "summarize"


# ==================== 图构建 ====================

def build_graph():
    """
    构建 StateGraph，将 4 个节点按控制流连接。

    图结构:
        START
          │
          ▼
        agent ──(有 tool_call?)──→ retrieve ──→ summarize ──→ format ──→ END
          │
          └──────(无 tool_call)──→ summarize ───────────────────┘

    每个节点返回的 dict 会被 LangGraph 合并到 State 中。
    """
    # 创建图，指定 State 类型
    graph = StateGraph(AgentState)

    # 注册 4 个节点
    graph.add_node("agent", agent_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("format", format_node)

    # 连接边
    graph.add_edge(START, "agent")                        # 起点 → agent
    graph.add_conditional_edges(                          # agent → ?
        "agent",
        route_after_agent,
        {
            "retrieve": "retrieve",
            "summarize": "summarize",
        },
    )
    graph.add_edge("retrieve", "summarize")                # retrieve → summarize
    graph.add_edge("summarize", "format")                  # summarize → format
    graph.add_edge("format", END)                          # format → 终点

    # 编译图（将节点编译为可执行的计算图）
    compiled_graph = graph.compile()

    logger.info("[图构建] StateGraph 编译完成")
    return compiled_graph


# ==================== Agent 封装类 ====================

class ReactAgent:
    """
    ReactAgent —— 对上层暴露的统一入口。

    execute_stream() 的接口保持不变，streamlit_app.py 无需大改。
    内部从 create_agent 黑盒切换为手动 StateGraph。
    """

    def __init__(self):
        # 构建手动 StateGraph（替代旧的 create_agent）
        self.graph = build_graph()

        # 保持与旧版兼容的属性
        self._has_tool_call = False   # 本轮是否调用了工具（streamlit 用来决定是否展示页码）
        self.page_locations = ""      # format 节点提取的页码定位（streamlit 直接读取）

    def execute_stream(self, query: str, history: list = None):
        """
        Agent 流式执行 —— 接口与旧版保持兼容。

        流程:
          1. 构建初始 State（SystemMessage + 历史 + 当前问题）
          2. 通过 StateGraph 流式执行 4 个节点
          3. 逐节点 yield chunk（格式与旧版一致）

        Args:
            query:   当前用户问题
            history: 历史消息列表（可选）
                     格式为 [{"role": "user"/"assistant", "content": "..."}]

        Yields:
            str: UI 层逐段展示的文本块
                 "🔧 ..." — 工具调用指示
                 "✅ ..." — 工具完成指示
                 "..."     — LLM 回答正文
        """
        logger.info(f"[Agent执行] 开始处理请求 | 查询: {query[:100]}...")
        logger.info(f"[Agent执行] 历史消息轮数: {len(history) // 2 if history else 0}")

        # 重置状态
        self._has_tool_call = False
        self.page_locations = ""

        # ──── 构建初始消息列表 ────
        messages = []

        # 系统提示词作为第一条消息
        system_prompt = load_system_prompts()
        messages.append(SystemMessage(content=system_prompt))

        # 历史消息：从 dict 格式转为 LangChain 消息对象
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 当前用户问题
        messages.append(HumanMessage(content=query))

        # ──── 构建初始 State ────
        initial_state = {
            "messages": messages,
            "user_query": query,
            "task_type": "",
            "tool_name": "",
            "retrieved_context": "",
            "final_answer": "",
            "page_locations": "",
        }

        # ──── 流式执行 StateGraph ────
        try:
            for update in self.graph.stream(initial_state, stream_mode="updates"):
                # update 格式: {node_name: node_output_dict}
                for node_name, node_output in update.items():

                    if node_name == "agent":
                        # agent 节点输出：检查是否包含工具调用
                        msgs = node_output.get("messages", [])
                        if msgs:
                            last_msg = msgs[-1]
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                tool_names = [
                                    tc.get("name", "unknown")
                                    for tc in last_msg.tool_calls
                                ]
                                logger.info(f"[Agent执行] 调用工具: {', '.join(tool_names)}")
                                self._has_tool_call = True
                                yield f"\n🔧  {', '.join(tool_names)} 正在被调用  \n"

                    elif node_name == "retrieve":
                        # retrieve 节点输出：记录完成
                        tool_name = node_output.get("tool_name", "")
                        if tool_name:
                            logger.info(f"[Agent执行] 工具完成: {tool_name}")
                            yield f"✅ {tool_name} 执行完成  \n"

                    elif node_name == "summarize":
                        # summarize 节点输出：yield 最终回答
                        answer = node_output.get("final_answer", "")
                        if answer:
                            logger.info(f"[Agent执行] 生成回答 | 长度: {len(answer)}")
                            yield answer

                    elif node_name == "format":
                        # format 节点输出：提取页码定位（不 yield，存入实例属性）
                        locations = node_output.get("page_locations", "")
                        if locations:
                            self.page_locations = locations
                            logger.info(f"[Agent执行] 页码定位已提取 | 条数: {len(locations.splitlines())}")

            logger.info("[Agent执行] 请求完成")

        except Exception as e:
            logger.error(f"[Agent执行] 请求失败 | 错误: {str(e)}")
            raise
