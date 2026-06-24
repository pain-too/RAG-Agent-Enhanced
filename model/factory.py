#系统模块
import os
from typing import Any
#第三方模块
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
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

    @staticmethod
    def _create(model_type: str, model_name: str) -> BaseChatModel:
        """根据类型和名称创建模型实例（供内部复用）。"""
        if model_type == "tongyi":
            return ChatTongyi(
                model=model_name,
                api_key=os.getenv("DASHSCOPE_API_KEY")
            )

        elif model_type == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("未设置 DEEPSEEK_API_KEY 环境变量，无法初始化 DeepSeek 模型")
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
                temperature=0.3,
            )

        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    def generator(self) -> BaseChatModel:
        if "chat_model_type" not in rag_conf or "chat_model_name" not in rag_conf:
            raise ValueError("配置文件缺失 chat_model_type 或 chat_model_name")

        model_type = rag_conf["chat_model_type"]
        model_name = rag_conf["chat_model_name"]
        logger.info(f"加载聊天模型 | type={model_type}, name={model_name}")

        return self._create(model_type, model_name)

    def rewriter_generator(self) -> BaseChatModel:
        """创建改写专用模型（轻量级，独立于主 Agent）。"""
        model_type = rag_conf.get("rewriter_model_type", rag_conf.get("chat_model_type", "deepseek"))
        model_name = rag_conf.get("rewriter_model_name", "deepseek-chat")
        logger.info(f"加载改写模型 | type={model_type}, name={model_name}")

        return self._create(model_type, model_name)


class EmbeddingFactory(BaseModelFactory):
    """向量模型工厂"""
    def generator(self) -> Embeddings:
        if "embedding_model_type" not in rag_conf or "embedding_model_name" not in rag_conf:
            raise ValueError("配置文件缺失 embedding_model_type 或 embedding_model_name")

        model_type = rag_conf["embedding_model_type"]
        model_name = rag_conf["embedding_model_name"]
        logger.info(f"加载向量模型 | type={model_type}, name={model_name}")

        if model_type == "tongyi":
            return DashScopeEmbeddings(model=model_name)

        elif model_type == "huggingface":
            # 本地模型，无需 API Key
            # 国内环境通过 hf-mirror.com 镜像加速下载（首次 ~100MB）
            if not os.getenv("HF_ENDPOINT"):
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            return HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

        else:
            raise ValueError(f"不支持的模型类型: {model_type}")


# ===================== 对外导出模型实例 =====================
chat_model = ChatModelFactory().generator()
rewriter_model = ChatModelFactory().rewriter_generator()
embedding_model = EmbeddingFactory().generator()
