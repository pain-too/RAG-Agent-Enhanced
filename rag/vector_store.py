from utils.config_handler import chroma_conf
from utils.logger_handler import logger
from model.factory import embedding_model
from rag.KnowledgeBaseService import KnowledgeBaseService


class VectorStoreService:
    """
    向量库封装类，通过复用 KnowledgeBaseService 已初始化好的向量库，
    提供统一的检索器接口，供ds_rag_service进行相似度检索，
    避免重复加载资源，实现
    解耦与复用
    """
    def __init__(self, embedding=None, kb_service=None):
        logger.info("初始化 VectorStoreService...")
        self.embedding = embedding_model
        if kb_service is not None:
            self.kbs = kb_service
        else:
            self.kbs = KnowledgeBaseService()
        self.vector_store = self.kbs.chroma
        logger.info("VectorStoreService 初始化完成 ✅")


    def get_retriever(self, search_kwargs=None):
        if search_kwargs is None:
            search_kwargs = {"k": chroma_conf.get("k", 3)}
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)


    def get_vector_store(self):
        return self.vector_store