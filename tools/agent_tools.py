import time
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from utils.logger_handler import logger, get_request_id
from model.factory import chat_model

_rag_service = None

def _get_rag():
    global _rag_service
    if _rag_service is None:
        from rag.ds_rag_service import get_rag_service
        _rag_service = get_rag_service()
    return _rag_service


def _llm_summarize(query: str, context: str, task_type: str) -> str:
    prompts = {
        "search": """你是王道408数据结构的答疑老师。请基于以下参考资料回答用户问题。
要求：
1. 只保留与问题直接相关的知识点
2. 结构化、简洁、分点阐述
3. 保留关键页码定位（【参考资料X | 文件名 第X页】格式）
4. 如资料不足，明确说明

用户问题：{query}

参考资料：
{context}

回答：""",

        "compare": """你是王道408数据结构的答疑老师。请基于以下参考资料对两个概念进行对比辨析。
要求：
1. 按对比维度组织（定义/结构/复杂度/适用场景/408考点）
2. 突出异同点
3. 保留关键页码定位
4. 如资料不足，明确说明

对比对象：{query}

参考资料：
{context}

对比分析：""",

        "summary": """你是王道408数据结构的答疑老师。请基于以下资料对章节进行归纳总结。
要求：
1. 按知识体系组织（核心概念/必考算法/复杂度/易错点/真题考点）
2. 突出408高频考点
3. 保留关键页码定位
4. 如资料不足，明确说明

章节：{query}

参考资料：
{context}

章节归纳："""
    }
    prompt = prompts[task_type].format(query=query, context=context)
    response = chat_model.invoke([HumanMessage(content=prompt)])
    return response.content


@tool
def ds_knowledge_search(query: str) -> str:
    """
    王道408数据结构 —— 知识点检索工具
    """
    request_id = get_request_id()
    start_time = time.time()

    logger.info(f"[工具调用] ds_knowledge_search | 请求ID: {request_id} | 查询: {query[:50]}...")

    try:
        rag = _get_rag()
        context = rag.search(query, mode="full")

        if not context or "未在" in context:
            elapsed_time = (time.time() - start_time) * 1000
            logger.warning(f"[工具调用] ds_knowledge_search | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 未找到")
            return "未在王道408数据结构资料库检索到相关内容，请换一种提问方式。"

        ans = _llm_summarize(query, context, "search")

        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[工具调用] ds_knowledge_search | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 成功 | 长度: {len(ans)}")
        return ans

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"[工具调用] ds_knowledge_search | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 错误: {str(e)}")
        return f"检索服务暂时不可用：{str(e)}"


@tool
def ds_concept_compare(query: str) -> str:
    """
    王道408数据结构 —— 易混概念对比辨析工具
    """
    request_id = get_request_id()
    start_time = time.time()

    logger.info(f"[工具调用] ds_concept_compare | 请求ID: {request_id} | 查询: {query[:50]}...")

    try:
        rag = _get_rag()
        context = rag.search(query, mode="full")

        if not context or "未在" in context:
            elapsed_time = (time.time() - start_time) * 1000
            logger.warning(f"[工具调用] ds_concept_compare | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 未找到")
            return "未在王道408数据结构资料库检索到相关内容，请换一种提问方式。"

        ans = _llm_summarize(query, context, "compare")

        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[工具调用] ds_concept_compare | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 成功 | 长度: {len(ans)}")
        return ans

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"[工具调用] ds_concept_compare | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 错误: {str(e)}")
        return f"对比服务暂时不可用：{str(e)}"


@tool
def ds_chapter_summary(chapter_name: str) -> str:
    """
    王道408数据结构 —— 章节知识点归纳工具
    """
    request_id = get_request_id()
    start_time = time.time()

    logger.info(f"[工具调用] ds_chapter_summary | 请求ID: {request_id} | 章节: {chapter_name}")

    try:
        rag = _get_rag()
        context = rag.search(chapter_name, mode="full")

        if not context or "未在" in context:
            elapsed_time = (time.time() - start_time) * 1000
            logger.warning(f"[工具调用] ds_chapter_summary | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 未找到")
            return "未在王道408数据结构资料库检索到相关内容，请换一种提问方式。"

        ans = _llm_summarize(chapter_name, context, "summary")

        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[工具调用] ds_chapter_summary | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 结果: 成功 | 长度: {len(ans)}")
        return ans

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"[工具调用] ds_chapter_summary | 请求ID: {request_id} | 耗时: {elapsed_time:.2f}ms | 错误: {str(e)}")
        return f"总结服务暂时不可用：{str(e)}"