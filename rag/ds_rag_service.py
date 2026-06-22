# 系统模块
import os
import re
from typing import List, Optional
# 第三方库
from langchain_core.documents import Document
# Agent 项目模块
from utils.config_handler import chroma_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger
from model.factory import embedding_model
# RAG 核心模块
from rag.KnowledgeBaseService import KnowledgeBaseService
from rag.vector_store import VectorStoreService


class DSRagService:
    def __init__(self, data_path: Optional[str] = None) -> None:
        logger.info("=" * 60)
        logger.info("开始初始化 DSRagService...")

        try:
            self.k_default_k:int = chroma_conf.get("k", 3)
            self.k_data_path:str = chroma_conf.get("data_path", "./data")
            logger.info(f"配置读取成功 | k={self.k_default_k}, data_path={self.k_data_path}")

        except Exception as e:
            logger.error(f"读取配置失败：{str(e)}")
            raise RuntimeError("DSRagService 初始化失败：配置加载异常") from e

        try:
            self.kb_service: KnowledgeBaseService = KnowledgeBaseService()
            logger.info("KnowledgeBaseService 初始化成功")

            self.vector_service: VectorStoreService = VectorStoreService(kb_service=self.kb_service)
            logger.info("VectorStoreService 绑定向量库成功")

        except Exception as e:
            logger.error(f"服务初始化失败：{str(e)}")
            raise RuntimeError("DSRagService 服务初始化异常") from e

        """
        if data_path is None:
            data_path = get_abs_path(self.k_data_path)

        logger.info(f"自动加载知识库目录：{data_path}")
        self.pdf_upload_folder_with_md5(data_path)

        logger.info("DSRagService 初始化完成 ✅")
        """
        logger.info("✅ 直接使用已上传的向量库，跳过PDF加载")
        logger.info("=" * 60)


    def pdf_upload_folder_with_md5(self, folder_path: str) -> None:
        """
        递归扫描文件夹（含嵌套子目录），上传所有 PDF 到向量库。
        用子目录路径作为文件名前缀，避免同名文件冲突。
        """
        try:
            abs_folder = get_abs_path(folder_path)
            pdf_count = 0

            for root, dirs, files in os.walk(abs_folder):
                for file_name in files:
                    if not file_name.lower().endswith(".pdf"):
                        continue

                    file_path = os.path.join(root, file_name)
                    if not os.path.isfile(file_path):
                        continue

                    # 用相对于 data/ 的子路径作为显示名，保留目录结构信息
                    rel_path = os.path.relpath(file_path, abs_folder)

                    pdf_count += 1
                    logger.info(f"正在处理 PDF：{rel_path}")
                    result = self.kb_service.upload_entire_pdf(file_path, rel_path)
                    logger.info(f"处理完成：{rel_path} | 结果：{result}")

            logger.info(f"本次共加载 {pdf_count} 个PDF文件（含子文件夹）")

        except Exception as e:
            logger.error(f"批量加载PDF失败：{str(e)}")


    def format_docs(self, docs: List[Document]) -> str:
        """
        获取带页码、来源的格式化文档，并拼接成最终返回字符串

        KnowledgeBaseService中的定义：
            page.metadata["source"] = file_name
            page.metadata["page_num"] = page_num
        """
        if not docs:
            logger.warning("无文档可格式化")
            return "未找到相关资料"

        formatted_list = []
        idx = 1

        for doc in docs:
            source = doc.metadata.get("source", "未知文件")
            page = doc.metadata.get("page_num") or doc.metadata.get("page") or 1
            page = max(int(page), 1)
            content = doc.page_content.strip()
            item = f"【参考资料{idx} | {source} 第{page}页】\n{content} "
            formatted_list.append(item)
            idx += 1
        return "\n\n".join(formatted_list)


    def extract_location_only(self, formatted_text: str) -> str:
        """
        只提取定位，去掉正文内容，仅返回页码。
        正则是为了匹配上方formatted_docs自定义的定位格式
        """
        if not formatted_text:
            return ""
        pattern = r'【参考资料\d+ \| [^】]+?第\d+页】'

        location_lines = re.findall(pattern, formatted_text)
        if location_lines:
            return "\n".join(location_lines)
        else:
            return ""


    def search(self, query: str, k: Optional[int] = None, mode: str = "full") -> str:
        """
            mode是自定义参数，有full和location_only两种模式
        """
        logger.info(f"[RAG检索] 查询: {query[:50]}... | k: {k or self.k_default_k} | 模式: {mode}")

        try:
            k = k or self.k_default_k
            retriever = self.vector_service.get_retriever(search_kwargs={"k": k})
            docs = retriever.invoke(query)

            logger.info(f"[RAG检索] 检索完成 | 命中文档数: {len(docs)}")

            if not docs:
                logger.warning(f"[RAG检索] 未找到相关文档")
                return "未在王道408数据结构知识库中找到相关内容"

            full_formatted = self.format_docs(docs)

            if mode == "location_only":
                result = self.extract_location_only(full_formatted)
                logger.info(f"[RAG检索] 提取定位信息 | 定位数: {len(result.splitlines()) if result else 0}")
            else:
                result = full_formatted

            logger.info(f"[RAG检索] 处理完成")

            return result

        except Exception as e:
            logger.error(f"[RAG检索] 检索失败 | 错误: {str(e)}")
            return f"检索服务暂时不可用：{str(e)}"


# ===================== 单例模式 =====================
_rag_service_instance: Optional[DSRagService] = None

def get_rag_service() -> DSRagService:
    """
    获取唯一的DSRagService，避免重复创建
    """
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = DSRagService()
    return _rag_service_instance