import os,re
import hashlib
from langchain_chroma import Chroma
import chromadb
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# 你的统一工具 & 配置
from utils.config_handler import chroma_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger
from model.factory import embedding_model  # 从工厂取模型（软编码）


# ===================== 顶层便捷入口 =====================
def ingest(data_dir: str = "data"):
    """
    递归扫描 data_dir 下所有 PDF（含子文件夹），去重后入库。
    用法: python -c "from rag.KnowledgeBaseService import ingest; ingest()"
    """
    abs_dir = get_abs_path(data_dir)
    if not os.path.isdir(abs_dir):
        logger.error(f"❌ 数据目录不存在: {abs_dir}")
        return

    kbs = KnowledgeBaseService()
    pdf_count = 0

    for root, dirs, files in os.walk(abs_dir):
        for file_name in files:
            if not file_name.lower().endswith(".pdf"):
                continue
            file_path = os.path.join(root, file_name)
            # 用相对路径作为文件名，保留目录结构，同时避免同名冲突
            rel_name = os.path.relpath(file_path, abs_dir)
            logger.info(f"📄 发现 PDF: {rel_name}")
            result = kbs.upload_entire_pdf(file_path, rel_name)
            logger.info(f"   结果: {result}")
            pdf_count += 1

    logger.info(f"✅ 入库完成，共处理 {pdf_count} 个 PDF 文件（含子文件夹）")


class KnowledgeBaseService:
    """
    王道408数据结构知识库服务
    统一PDF加载、MD5去重、向量库存储
    """

    def __init__(self):
        # ===================== 读取配置 =====================
        self.persist_directory = get_abs_path(chroma_conf.get("persist_directory", "./chroma_db"))
        self.collection_name = chroma_conf.get("collection_name", "data_structure_408")
        self.chunk_size = chroma_conf.get("chunk_size", 500)
        self.chunk_overlap = chroma_conf.get("chunk_overlap", 50)
        self.max_split_char_number = chroma_conf.get("max_split_char_number", 1000)
        self.md5_path = get_abs_path(chroma_conf.get("md5_path", "./md5_record.txt"))
        self.separators = chroma_conf.get("separators", ["\n\n", "\n", "。", "！", "？", "；", "，", " "])

        # ===================== 向量库初始化 =====================
        """
        把之前的 persist_directory 改为新写法 client 管理
        """
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.chroma = Chroma(
            client = self.client,
            collection_name = self.collection_name,
            embedding_function = embedding_model,
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators
        )

        logger.info(f"✅ KnowledgeBaseService 初始化完成")
        logger.info(f"📂 向量库路径：{self.persist_directory}")
        logger.info(f"📄 集合名称：{self.collection_name}")

        # ===================== 增加文本清洗函数 =====================

    def clean_text(self, text: str) -> str:
        """
      +--------+--------+
      |    去首尾空格     |
      +--------+--------+
               ↓
      +--------+--------+
      |   是否为空行？    | → 是 → continue → 下一行
      +--------+--------+
               ↓ 否
      +--------+--------+
      |  是否包含水印？   | → 是 → break 跳出检查 → continue → 下一行（由于要检查列表中的多个关键词，需要break配合）
      +--------+--------+
               ↓ 否
      +--------+--------+
      |  是否为页码/纯数字 | → 是 → continue → 下一行
      +--------+--------+
               ↓ 否
      +--------+--------+
      | 是否为PPT噪声词？ | → 是 → continue → 下一行
      +--------+--------+
               ↓ 否
      +--------+--------+
      |   是否过短？      | → 是 → continue → 下一行
      +--------+--------+
               ↓ 否
      +--------+--------+
      | 是否全大写短标语？ | → 是 → continue → 下一行
      +--------+--------+
               ↓ 否
      +--------+--------+
      |    保留有效行     |
      +--------+--------+
               ↓
    所有行处理完毕 → 拼接文本 → 返回清洗结果

        continue的作用：检查到这一行有问题，就立刻去检查下一行，永远不会执行cleaned_lines.append(line)
        """
        logger.info(f"🧹 clean_text 被调用，输入长度: {len(text)}")

        #把文本按换行切成一行一行的列表
        lines = text.splitlines()
        cleaned_lines = []
        for line in lines:
            line = line.strip()

            # 1. 跳过明显的垃圾行
            if not line:
                continue

            # 2. 硬编码过滤水印
            watermark_keywords = [
                "王道考研", "CSKAOYAN.COM", "cskaoyan.com", "王道计算机考研",
                "本节内容", "知识总览", "知识回顾与重要考点", "www.cskaoyan", "skaova"
            ]

            '''
            has_watermark= True  ——>  break  ——>  跳出for  ——>  执行if has_watermark  ——>  执行continue，跳过当前行，检查下一行
            has_watermark= False ——>  并且for循环中没找到关键词->  不执行if has_watermark ——>  继续下一个for循环
            
            break ： 直接结束整个循环
            continue ： 跳过当前这一次，循环继续跑
            '''
            has_watermark = False
            for keyword in watermark_keywords:
                if keyword in line:
                    has_watermark = True
                    break
            if has_watermark:
                continue

            # 3. 过滤看起来像页码、空序号或纯数字的短行
            if re.fullmatch(r'^[\d\s\.\-_]+$', line):
                # 但如果行太长（比如超过10个字符），可能是有用数据，不过滤
                if len(line) <= 10:
                    continue

            # 4. 过滤常见PPT干扰词（通常是单行的小标题或标签）
            ppt_noise_words = ["low", "high", "pivot", "i", "j", "k", "len", "child", "parent"]
            # 如果该行很短，并且完全匹配这些词，则跳过
            if len(line) < 10 and line.lower() in ppt_noise_words:
                continue

            # 5. 过滤过短的行（比如长度小于3）
            if len(line) <= 2:
                continue

            # 6. 过滤全大写且短于20字符的疑似水印行
            if line.isupper() and len(line) < 20 and not any(c.isdigit() for c in line):
                continue

            # 如果能走到这里，说明不是垃圾行，保留
            cleaned_lines.append(line)

        # 用换行符重新组合
        result = "\n".join(cleaned_lines)
        logger.info(f"🧹 clean_text 完成，输出长度: {len(result)}")
        return result



    # ===================== MD5 系统 =====================
    def calculate_md5(self, file_path: str) -> str:
        """
        放入 chunk1 → MD5 开始累计
        放入 chunk2 → MD5 继续累计
        放入 chunk3 → MD5 继续累计
        直到全部放完，计算对应整个文件的MD5并hexdigest
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                # 每次读 4096 字节
                chunk = f.read(4096)
                # b""与rb模式对应，表示空值
                if chunk == b"":
                    break
                hash_md5.update(chunk)
        #计算整个文件的MD5
        return hash_md5.hexdigest()


    def load_md5_record(self) -> set:
        """
        set集合放不可变类型md5字符串
        """
        if not os.path.exists(self.md5_path):
            return set()

        md5_set = set()
        with open(self.md5_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()

                if stripped_line:
                    md5_set.add(stripped_line)
        return md5_set


    def save_md5_record(self, md5_value: str):
        with open(self.md5_path, "a", encoding="utf-8") as f:
            f.write(md5_value + "\n")

    # ===================== 单个 PDF 按页上传 =====================
    def upload_entire_pdf(self, file_path: str, file_name: str) -> str:
        """
        calculate_md5  和  load_md5_record    属于MD5系统，在正上方定义
        """

        """
        ╔═══════════════════════════════════════════════════════════════╗
                            PDF 上传 & 向量库入库流程图                    
        ╚═══════════════════════════════════════════════════════════════╝
                                  [开始]
                                    │
                  ┌─────────────────┴─────────────────┐
                               计算文件 MD5             
                  └─────────────────┬─────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                              检查 MD5 是否已存在          
                  └─────────────────┬─────────────────┘
                                    │
                    ┌───────────────┬───────────────┐
                   已存在                          不存在
                    ↓                               ↓
                  直接返回                    PyPDFLoader 加载 PDF
                  "已存在"                生成 pages = [Document, ...]
                    └───────────────┘────────────────┘   
                                    │
                  ┌─────────────────┴─────────────────┐
                             遍历每一页 page            
                  └─────────────────┬─────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                      补充元数据 source / page_num（+1） 
                  └─────────────────┬─────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                           清洗文本 clean_text()        
                  └─────────────────┬─────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                               内容是否为空？              
                  └───┬─────────────────┬─────────────┘
                      空               非空
                      ↓                 ↓
                 continue跳过       判断文本长度是否超限
                       └──────────┬──────┘
                                  │
                  ┌───────────────┴───────────────────┐
                  是                                  否
                  ↓                                   ↓
        文本切片→生成新Document                     加入 docs
                  └─────────────────┬─────────────────┘
                                    │
      ┌─────────────────────────────┴─────────────────────────────┐
                               所有页处理完毕                        
      └─────────────────────────────┬─────────────────────────────┘
                                    │
      ┌─────────────────────────────┴─────────────────────────────┐
                           docs 是否有有效内容？                       
      └───────────┬───────────────────────────────┬───────────────┘
                  有                              无
                   ↓                              ↓
        存入向量库 add_documents()            返回 "无有效内容"
             保存 MD5 到记录                        
            返回 "上传成功"                         |
                  └───────────────────────────────┘
                                    │
                                  [结束]
        """
        try:
            md5 = self.calculate_md5(file_path)
            existed = self.load_md5_record()

            if md5 in existed:
                logger.info(f"⏭️ 文件{file_name}已存在")
                return "已存在，跳过"

            loader = PyPDFLoader(file_path)
            #加载成langchain的Document对象
            pages = loader.load()
            docs = []

            #pages是列表，元素是Document对象。每个page就是一个Document
            for page in pages:
                #loader加载出的默认页码从0开始
                page_num = page.metadata.get("page", 0) + 1
                #metadata是字典，给字典加两个键值对
                page.metadata["source"] = file_name
                page.metadata["page_num"] = page_num
                # 按页上传并清洗
                content = page.page_content.strip()
                content = self.clean_text(content)

                if not content:
                    continue

                if len(content) > self.max_split_char_number:
                    #splitter导第三方包
                    splitted = self.text_splitter.split_text(content)
                    for t in splitted:
                        # ※关键：被分片后，metadata都一样，但是content不一样，所以小片Document不一样
                        new_doc = Document(page_content = t,
                                           metadata = page.metadata)
                        docs.append(new_doc)
                else:
                    # 每页长度不是很大，就直接上传
                    docs.append(page)

            # 之前定义了docs = []，如果290行附近被continue了，则docs为空
            if docs:
                self.chroma.add_documents(docs)
                self.save_md5_record(md5)
                logger.info(f"✅ PDF 入库成功：{file_name}，总页数：{len(pages)}")
                return "上传成功"
            else:
                logger.warning(f"⚠️ 无有效内容：{file_name}")
                return "无有效内容"

        except Exception as e:
            logger.error(f"❌ 处理 PDF 失败：{file_name}，原因：{str(e)}")
            return f"处理失败：{str(e)}"

