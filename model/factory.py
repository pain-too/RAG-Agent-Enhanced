#系统模块
import os
from typing import Any
#第三方模块
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models import ChatTongyi
#自定义模块
from utils.config_handler import rag_conf
from utils.logger_handler import logger


class BaseModelFactory:
    """基础模型工厂"""
    def generator(self) -> Any:
        raise NotImplementedError("子类必须实现 generator 方法")


class ChatModelFactory(BaseModelFactory):
    """对话模型工厂"""
    def generator(self) -> BaseChatModel:
        if "chat_model_type" not in rag_conf or "chat_model_name" not in rag_conf:
            raise ValueError("配置文件缺失 chat_model_type 或 chat_model_name")

        model_type = rag_conf["chat_model_type"]
        model_name = rag_conf["chat_model_name"]
        logger.info(f"加载聊天模型 | type={model_type}, name={model_name}")

        if model_type == "tongyi":
            return ChatTongyi(
                model=model_name,
                api_key=os.getenv("DASHSCOPE_API_KEY")
            )
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")


class EmbeddingFactory(BaseModelFactory):
    """向量模型工厂"""
    def generator(self) -> Embeddings:
        if "embedding_model_type" not in rag_conf or "embedding_model_name" not in rag_conf:
            raise ValueError("配置文件缺失 embedding_model_type 或 embedding_model_name")

        model_type = rag_conf["embedding_model_type"]
        model_name = rag_conf["embedding_model_name"]
        logger.info(f"加载向量模型 | type={model_type}, name={model_name}")

        if model_type == "tongyi":
            # ✅ 正确：向量模型用 DashScopeEmbeddings
            return DashScopeEmbeddings(
                model=model_name
            )
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")


# ===================== 对外导出模型实例 =====================
chat_model = ChatModelFactory().generator()
embedding_model = EmbeddingFactory().generator()