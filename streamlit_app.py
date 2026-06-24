import streamlit as st
import os
import sys
import uuid
from pathlib import Path

# ==================== Streamlit Cloud SQLite3 兼容 ====================
# ChromaDB 需要 SQLite 3.35+，云端默认版本太低
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# 强制清除代理环境变量，避免代理服务不可用导致请求失败
proxy_vars = ['http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
for var in proxy_vars:
    os.environ.pop(var, None)

# 解决云端找不到 rag 模块
sys.path.append(str(Path(__file__).parent))

# ==================== API KEY 兼容本地 & 云端 ====================
try:
    deepseek_key = st.secrets["DEEPSEEK_API_KEY"]
except:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

if not deepseek_key:
    st.error("❌ 未找到 DEEPSEEK_API_KEY，请在环境变量或 .streamlit/secrets.toml 中设置")
    st.stop()

os.environ["DEEPSEEK_API_KEY"] = deepseek_key

# 日志：确认模型配置
from utils.config_handler import rag_conf
st.caption(f"🤖 聊天模型: {rag_conf.get('chat_model_type', '?')}/{rag_conf.get('chat_model_name', '?')} | 📐 嵌入模型: {rag_conf.get('embedding_model_type', '?')}/{rag_conf.get('embedding_model_name', '?')}")

# ==================== 页面配置 ====================
st.set_page_config(page_title="408答疑助手", page_icon="📚")
st.title("📚 王道408数据结构智能答疑助手")

# ==================== 会话记忆配置 ====================
if "max_history_rounds" not in st.session_state:
    st.session_state.max_history_rounds = 5

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ==================== 功能说明 ====================
st.markdown("""
### 程序简要说明
本系统为 **王道408数据结构知识库问答系统**，基于 ReAct Agent 架构，集成检索、推理、对比、总结能力。

### 可用工具
| 工具 | 功能  | 提问示例 |
|------|------|------------|
| 知识检索ds_knowledge_search | 从PDF知识库查找相关内容 | 1、简述栈的基本定义与特点  <br> 2、红黑树是什么 |
| 概念对比ds_concept_compare | 对比两个易混淆概念 | 1、对比顺序表与链表优缺点  <br> 2、对比三种处理最短路径问题的方法 |
| 章节总结ds_chapter_summary | 输出指定章节核心考点 | 1、总结树结构高频考试知识点  <br> 2、总结处理冲突的方法 |

> 🤖 Agent 会自动判断需要调用哪个工具，无需手动指定
> 📍 回答后会自动展示参考资料的文件及页码定位
""", unsafe_allow_html=True)


# ==================== 初始化消息（支持持久化） ====================
if "messages" not in st.session_state:
    st.session_state.messages = []

    try:
        from rag.file_history_store import get_history
        from langchain_core.messages import HumanMessage, AIMessage

        chat_history = get_history(st.session_state.session_id)
        langchain_messages = chat_history.messages

        for msg in langchain_messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            st.session_state.messages.append({
                "role": role,
                "content": msg.content,
                "location": ""
            })

        if st.session_state.messages:
            st.info(f"📂 已加载历史对话（共 {len(st.session_state.messages)} 条消息）")
    except Exception as e:
        st.warning(f"未找到历史记录或加载失败: {str(e)}")

if "rag" not in st.session_state:
    with st.spinner("正在加载知识库..."):
        from rag.ds_rag_service import DSRagService
        st.session_state.rag = DSRagService(data_path=None)

if "agent" not in st.session_state:
    from react_agent import ReactAgent
    st.session_state.agent = ReactAgent()

st.success("✅ 知识库加载成功 | Agent 准备就绪")

# ==================== 安全门初始化 ====================
from guard import input_guard, GuardResult

# ==================== 历史聊天展示 ====================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("location"):
            with st.expander("📍 参考资料定位", expanded=False):
                st.markdown(f"```\n{msg['location']}\n```")

# ==================== 用户输入 ====================
prompt = st.chat_input("请输入你的问题...")

if prompt:
    # ──── 第零步：安全门检查 ────
    guard_result = input_guard(prompt)

    # ──── 展示用户消息 ────
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ==================== 安全拦截分支 ====================
    if guard_result.verdict != "pass":
        verdict_label = {
            "block_security": "安全拦截",
            "block_scope": "范围拦截",
            "block_invalid": "无效输入",
        }.get(guard_result.verdict, guard_result.verdict)

        severity = guard_result.trace.get("layer2", {}).get("severity", "NONE")
        matched_rules = guard_result.trace.get("layer2", {}).get("matched_rules", [])

        with st.chat_message("assistant"):
            st.error(f"🛡️ {verdict_label}")

            # 攻击分析卡片
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 攻击分析")
                if guard_result.attack_types:
                    st.markdown("**攻击类型:**")
                    for at in guard_result.attack_types:
                        st.markdown(f"- `{at}`")
                else:
                    st.markdown("**攻击类型:** —")

                if matched_rules:
                    st.markdown("**命中规则:**")
                    for r in matched_rules:
                        st.markdown(f"✓ `{r}`")
                else:
                    st.markdown("**命中规则:** —")

            with col2:
                st.markdown("### 处理信息")
                st.markdown(f"**风险等级:** `{severity}`")
                verdict_display = guard_result.verdict.upper().replace("_", " ")
                st.markdown(f"**处理结果:** {verdict_display}")
                st.markdown(f"**原因:** {guard_result.reason}")

            # Trace 面板
            with st.expander("📋 调试信息 (Trace)", expanded=False):
                st.json(guard_result.trace)

            st.info("💡 请提出与数据结构/408考研相关的问题")

        # 保存安全拦截消息
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"🛡️ {verdict_label}\n\n{guard_result.reason}",
            "location": ""
        })

        # 持久化
        try:
            from rag.file_history_store import get_history
            from langchain_core.messages import HumanMessage, AIMessage
            chat_history = get_history(st.session_state.session_id)
            chat_history.add_messages([HumanMessage(content=prompt)])
            chat_history.add_messages([AIMessage(
                content=f"🛡️ [安全拦截] {guard_result.reason}"
            )])
        except Exception:
            pass

        st.stop()

    # ==================== 安全通过分支 ====================
    with st.chat_message("assistant"):
        # 安全通过指示器
        rewrite_trace = guard_result.rewrite_trace
        if rewrite_trace and rewrite_trace.total_modifications > 0:
            st.caption(
                f"🛡️ 安全检测 ✓ 通过 | "
                f"查询优化: {rewrite_trace.total_modifications} 步 "
                f"(rule: {rewrite_trace.method_summary.get('rule', 0)}, "
                f"llm: {rewrite_trace.method_summary.get('llm', 0)})"
            )
        else:
            st.caption("🛡️ 安全检测 ✓ 通过 | 查询无需改写")

        # 改写回溯面板（仅在改写时显示）
        if rewrite_trace and rewrite_trace.total_modifications > 0:
            with st.expander("🔍 查询改写回溯", expanded=False):
                st.markdown("| 步骤 | 方法 | 变换 |")
                st.markdown("|------|------|------|")
                for s in rewrite_trace.steps:
                    if s.method == "none":
                        continue
                    change = f"{s.input[:30]}... → {s.output[:30]}..." if len(s.input) > 30 else f"{s.input} → {s.output}"
                    st.markdown(f"| {s.stage} | `{s.method}` | {change} |")

        # 调用 Agent（传入改写后的查询）
        with st.spinner("🤖 Agent 正在思考..."):
            full_answer = ""
            placeholder = st.empty()

            history = st.session_state.messages[:-1][-2 * st.session_state.max_history_rounds:]

            # 传入改写后的 query 给 Agent
            for chunk in st.session_state.agent.execute_stream(
                guard_result.query, history=history
            ):
                full_answer += chunk
                placeholder.markdown(full_answer, unsafe_allow_html=True)

            location_info = st.session_state.agent.page_locations

            if location_info:
                with st.expander("📍 参考资料定位", expanded=True):
                    st.markdown(f"```\n{location_info}\n```")
            elif st.session_state.agent._has_tool_call:
                st.caption("📍 未检索到相关参考资料定位")

    # ==================== 保存历史 ====================
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "location": location_info
    })

    try:
        from rag.file_history_store import get_history
        from langchain_core.messages import HumanMessage, AIMessage

        chat_history = get_history(st.session_state.session_id)
        chat_history.add_messages([HumanMessage(content=prompt)])
        chat_history.add_messages([AIMessage(content=full_answer)])
    except Exception as e:
        st.warning(f"⚠️ 保存历史记录失败: {str(e)}")
