"""
RAGAS 评估脚本 —— 王道408数据结构知识库问答系统

使用方法：
    cd 项目根目录
    python3 eval/run_eval.py                  # 默认跑全部
    python3 eval/run_eval.py --limit 5        # 只跑前 5 条

评估指标（RAGAS 0.4+）：
    - faithfulness             忠实度：回答是否忠于检索到的上下文（不幻觉）
    - answer_relevancy         回答相关性：回答是否与问题相关
    - nv_context_relevance     上下文相关性：检索结果与问题的相关度（不需要 ground_truth）
    - context_recall           上下文召回：ground_truth 中的信息是否被检索到

输出：
    - 控制台打印各指标得分
    - 结果保存到 eval/results/ 目录（CSV + JSON）

前置条件：
    - .env 中已配置 DASHSCOPE_API_KEY
    - 向量库已初始化（chroma_db 目录存在）
"""


import sys
import json
import re
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ===================== 加载环境变量 =====================
import os
os.environ.setdefault("PYTHONHASHSEED", "0")
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ===================== RAGAS 核心导入（适配 0.4+ 版本） =====================
from datasets import Dataset
from ragas import evaluate
# 第一次修改：0.4+ 版本中，evaluate() 要求 Metric 子类实例
# collections 下的 BaseMetric 不是 Metric 子类，需要从内部模块导入
from ragas.metrics._faithfulness import Faithfulness
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.metrics._nv_metrics import ContextRelevance
from ragas.metrics import ContextRecall
# 第一次修改：使用 LangChain 包装器（llm_factory + instructor 与 DashScope 不兼容，会 404）
from ragas.llms.base import LangchainLLMWrapper
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings

# ===================== 项目模块导入 =====================
from rag.ds_rag_service import DSRagService
from utils.logger_handler import logger


def create_eval_llm():
    """
    第一次修改：创建 RAGAS 评估用的 LLM 实例
    使用 LangChain 的 ChatTongyi 包装为 RAGAS 兼容格式
    注：llm_factory + instructor 库与 DashScope 不兼容（返回 404），
    因此改用 LangchainLLMWrapper 包装已有的 ChatTongyi
    """
    # 使用 qwen-plus 作为评估 LLM（性价比高，速度适中）
    chat = ChatTongyi(model="qwen-plus")
    eval_llm = LangchainLLMWrapper(langchain_llm=chat)
    return eval_llm


def create_eval_embeddings():
    """
    第一次修改：创建 RAGAS 评估用的 Embeddings 实例
    AnswerRelevancy 指标需要 embeddings 来计算回答相关性
    使用 LangChain 的 DashScopeEmbeddings 包装为 RAGAS 兼容格式
    """
    emb = DashScopeEmbeddings(model="text-embedding-v3")
    eval_embeddings = LangchainEmbeddingsWrapper(embeddings=emb)
    return eval_embeddings


def create_eval_metrics(eval_llm, eval_embeddings):
    """
    第一次修改：创建 RAGAS 评估指标实例
    RAGAS 0.4+ 要求使用 Metric 子类的实例化对象
    AnswerRelevancy 还需要传入 embeddings 参数
    """
    metrics = [
        Faithfulness(llm=eval_llm),
        # AnswerRelevancy 需要 embeddings 来计算回答与问题的语义相关性
        AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings),
        # NV ContextRelevance：检索上下文与问题的相关度（不需要 ground_truth）
        ContextRelevance(llm=eval_llm),
        # ContextRecall：ground_truth 中的信息是否被检索到
        ContextRecall(llm=eval_llm),
    ]
    return metrics


def load_test_dataset(dataset_path: str = None) -> list:
    """
    加载测试数据集
    数据集格式：[{question, ground_truth, chapter}, ...]
    """
    if dataset_path is None:
        dataset_path = str(PROJECT_ROOT / "eval" / "test_dataset.json")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"加载测试数据集：{len(data)} 条")
    return data


def run_rag_pipeline(rag_service: DSRagService, questions: list) -> dict:
    """
    运行 RAG 管道，收集每个问题的回答和检索到的上下文

    返回格式（供 RAGAS 使用）：
        {
            "question":      [str, ...],       # 原始问题
            "answer":        [str, ...],       # LLM 生成的回答
            "contexts":      [[str, ...], ...], # 检索到的上下文（每个问题是多个段落的列表）
            "ground_truth":  [str, ...],       # 标准答案
        }
    """
    results = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for i, item in enumerate(questions):
        question = item["question"]
        ground_truth = item["ground_truth"]

        logger.info(f"[{i+1}/{len(questions)}] 处理问题：{question[:50]}...")
        start_time = time.time()

        try:
            # 1. 获取检索上下文（mode="full" 返回带定位的格式化文本）
            full_result = rag_service.search(question, mode="full")

            # 2. 提取纯文本上下文（去掉定位标签，只保留正文内容）
            #    格式：【参考资料1 | xxx.pdf 第3页】\n正文内容
            contexts = extract_contexts(full_result)

            # 3. 获取 LLM 回答：调用 ds_knowledge_search 工具
            #    工具内部会调 LLM 基于 context 总结，返回精炼回答
            from tools.agent_tools import ds_knowledge_search
            answer = ds_knowledge_search.invoke({"query": question})

            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[{i+1}/{len(questions)}] 完成 | 耗时: {elapsed:.0f}ms | 上下文段数: {len(contexts)} | 回答长度: {len(answer)}")

        except Exception as e:
            logger.error(f"[{i+1}/{len(questions)}] 处理失败：{str(e)}")
            contexts = []
            answer = f"处理失败：{str(e)}"

        results["question"].append(question)
        results["answer"].append(answer)
        results["contexts"].append(contexts)
        results["ground_truth"].append(ground_truth)

    return results


def extract_contexts(formatted_text: str) -> list:
    """
    从格式化的检索结果中提取纯文本上下文列表
    输入格式：【参考资料1 | xxx.pdf 第3页】\n正文内容
    输出：["正文内容1", "正文内容2", ...]
    """
    if not formatted_text or formatted_text.startswith("未在"):
        return []

    # 按 【参考资料X | ...】 分割，提取每段的正文
    pattern = r'【参考资料\d+ \| [^】]+?第\d+页】\n'
    parts = re.split(pattern, formatted_text)

    # 过滤空字符串，去除首尾空白
    contexts = [p.strip() for p in parts if p.strip()]
    return contexts


def run_evaluation(rag_service: DSRagService, dataset_path: str = None, limit: int = None):
    """
    运行完整的 RAGAS 评估流程
    """
    logger.info("=" * 60)
    logger.info("开始 RAGAS 评估...")
    logger.info("=" * 60)

    # ===================== 1. 加载测试数据 =====================
    test_data = load_test_dataset(dataset_path)
    if limit is not None and limit > 0:
        test_data = test_data[:limit]
        logger.info(f"按 --limit={limit} 截断，实际跑 {len(test_data)} 条")
    logger.info(f"测试数据加载完成，共 {len(test_data)} 条")

    # ===================== 2. 运行 RAG 管道 =====================
    logger.info("开始运行 RAG 管道，收集回答和上下文...")
    pipeline_results = run_rag_pipeline(rag_service, test_data)

    # ===================== 3. 构建 RAGAS 评估数据集 =====================
    eval_dataset = Dataset.from_dict(pipeline_results)
    logger.info(f"评估数据集构建完成，共 {len(eval_dataset)} 条")

    # ===================== 4. 创建评估 LLM 和指标 =====================
    logger.info("初始化评估 LLM（通义千问 qwen-plus）...")
    eval_llm = create_eval_llm()
    eval_embeddings = create_eval_embeddings()
    metrics = create_eval_metrics(eval_llm, eval_embeddings)
    logger.info(f"评估指标：{[type(m).__name__ for m in metrics]}")

    # ===================== 5. 运行 RAGAS 评估 =====================
    logger.info("开始 RAGAS 指标计算（此过程需要调用 LLM，请耐心等待）...")

    try:
        result = evaluate(
            dataset=eval_dataset,
            metrics=metrics,
        )

        # ===================== 6. 输出结果 =====================
        logger.info("=" * 60)
        logger.info("RAGAS 评估结果：")
        logger.info("=" * 60)

        # 第一次修改：RAGAS 0.4+ 的 EvaluationResult 不是 dict
        # 用 _repr_dict 访问平均分
        for metric_name, score in result._repr_dict.items():
            logger.info(f"  {metric_name}: {score:.4f}")

        # ===================== 7. 保存结果 =====================
        save_results(result, pipeline_results)
        return result

    except Exception as e:
        logger.error(f"RAGAS 评估失败：{str(e)}")
        raise


def save_results(result, pipeline_results: dict):
    """
    保存评估结果到文件
    """
    results_dir = PROJECT_ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存指标摘要
    summary_path = results_dir / f"eval_{timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            # 第一次修改：使用 _repr_dict 获取平均分
            "metrics": {k: float(v) for k, v in result._repr_dict.items()},
            "num_samples": len(pipeline_results["question"]),
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"评估摘要已保存：{summary_path}")

    # 保存详细结果（每条数据的回答和上下文）
    detail_path = results_dir / f"eval_{timestamp}_detail.json"
    with open(detail_path, "w", encoding="utf-8") as f:
        detail = []
        for i in range(len(pipeline_results["question"])):
            detail.append({
                "question": pipeline_results["question"][i],
                "ground_truth": pipeline_results["ground_truth"][i],
                "answer": pipeline_results["answer"][i][:500],  # 截断过长的回答
                "num_contexts": len(pipeline_results["contexts"][i]),
            })
        json.dump(detail, f, ensure_ascii=False, indent=2)
    logger.info(f"详细结果已保存：{detail_path}")

    # 保存 RAGAS 原始结果为 CSV
    try:
        result_df = result.to_pandas()
        csv_path = results_dir / f"eval_{timestamp}.csv"
        result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"CSV 结果已保存：{csv_path}")
    except Exception as e:
        logger.warning(f"CSV 保存失败（不影响评估结果）：{str(e)}")


# ===================== 主入口 =====================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAGAS 评估 —— 王道408数据结构知识库")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条样本（默认跑全部）")
    parser.add_argument("--dataset", type=str, default=None, help="测试数据集路径（默认 eval/test_dataset.json）")
    args = parser.parse_args()

    # 初始化 RAG 服务
    logger.info("初始化 RAG 服务...")
    rag_service = DSRagService(data_path=None)

    # 运行评估
    result = run_evaluation(rag_service, dataset_path=args.dataset, limit=args.limit)

    print("\n" + "=" * 60)
    print("RAGAS 评估完成！核心指标：")
    print("=" * 60)
    # 第一次修改：使用 _repr_dict 访问平均分
    for metric_name, score in result._repr_dict.items():
        print(f"  {metric_name}: {score:.4f}")
    print("=" * 60)
