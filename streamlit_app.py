import streamlit as st
import os
import sys
import uuid
from pathlib import Path

# 强制清除代理环境变量，避免代理服务不可用导致请求失败
proxy_vars = ['http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
for var in proxy_vars:
    os.environ.pop(var, None)

# 解决云端找不到 rag 模块
sys.path.append(str(Path(__file__).parent))

# ==================== API KEY 兼容本地 & 云端 ====================
# DeepSeek API Key（用于聊天模型）
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
# 窗口记忆：只保留最近 N 轮对话（每轮 = user + assistant）
if "max_history_rounds" not in st.session_state:
    st.session_state.max_history_rounds = 5  # 默认保留最近5轮

# 会话ID：用于持久化存储
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ==================== 你原版的说明表格（完全保留） ====================
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
    
    # 尝试从文件加载历史消息
    try:
        from rag.file_history_store import get_history
        from langchain_core.messages import HumanMessage, AIMessage
        
        chat_history = get_history(st.session_state.session_id)
        langchain_messages = chat_history.messages
        
        # 转换为前端格式
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

# ==================== 历史聊天（含定位展示） ====================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("location"):
            with st.expander("📍 参考资料定位", expanded=False):
                st.markdown(f"```\n{msg['location']}\n```")

# ==================== 用户输入 ====================
prompt = st.chat_input("请输入你的问题...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ==================== AI 回答（支持多轮对话） ====================
    with st.chat_message("assistant"):
        with st.spinner("🤖 Agent 正在思考..."):
            full_answer = ""
            placeholder = st.empty()
            
            # 构建历史消息（窗口记忆：只传最近 N 轮）
            history = st.session_state.messages[:-1][-2*st.session_state.max_history_rounds:]
            
            # 调用 Agent，传入历史消息
            for chunk in st.session_state.agent.execute_stream(prompt, history=history):
                full_answer += chunk
                placeholder.markdown(full_answer, unsafe_allow_html=True)

            # 页码定位：直接从 agent 读取（format 节点已从检索结果中提取，无需重复搜索）
            location_info = st.session_state.agent.page_locations

            if location_info:
                with st.expander("📍 参考资料定位", expanded=True):
                    st.markdown(f"```\n{location_info}\n```")
            elif st.session_state.agent._has_tool_call:
                st.caption("📍 未检索到相关参考资料定位")

    # ==================== 保存历史（含定位） ====================
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "location": location_info
    })
    
    # ==================== 持久化到文件 ====================
    try:
        from rag.file_history_store import get_history
        from langchain_core.messages import HumanMessage, AIMessage
        
        chat_history = get_history(st.session_state.session_id)
        # 保存用户消息
        chat_history.add_messages([HumanMessage(content=prompt)])
        # 保存 AI 回答
        chat_history.add_messages([AIMessage(content=full_answer)])
    except Exception as e:
        st.warning(f"⚠️ 保存历史记录失败: {str(e)}")