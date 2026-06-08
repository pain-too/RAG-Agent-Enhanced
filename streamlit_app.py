import streamlit as st
import os
import sys
from pathlib import Path

# 解决云端找不到 rag 模块
sys.path.append(str(Path(__file__).parent))

# ==================== API KEY 兼容本地 & 云端 ====================
try:
    dashscope_key = st.secrets["DASHSCOPE_API_KEY"]
except:
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY")

if not dashscope_key:
    st.error("❌ 未找到 DASHSCOPE_API_KEY")
    st.stop()

os.environ["DASHSCOPE_API_KEY"] = dashscope_key

# ==================== 页面配置 ====================
st.set_page_config(page_title="408答疑助手", page_icon="📚")
st.title("📚 王道408数据结构智能答疑助手")

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


if "messages" not in st.session_state:
    st.session_state.messages = []

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

    # ==================== AI 回答（原版逻辑） ====================
    with st.chat_message("assistant"):
        with st.spinner("🤖 Agent 正在思考..."):
            full_answer = ""
            placeholder = st.empty()

            for chunk in st.session_state.agent.execute_stream(prompt):
                full_answer += chunk
                placeholder.markdown(full_answer, unsafe_allow_html=True)

            # ====================正则提取定位 ====================
            with st.spinner("📍 正在检索参考资料定位..."):
                location_info = st.session_state.rag.search(
                    query=prompt,
                    mode="location_only"
                )

            if location_info and location_info != "未在王道408数据结构知识库中找到相关内容":
                with st.expander("📍 参考资料定位", expanded=True):
                    st.markdown(f"```\n{location_info}\n```")
            else:
                st.caption("📍 未检索到相关参考资料定位")

    # 保存历史（含定位）
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "location": location_info
    })