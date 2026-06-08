#===================================将langchain的13FileChatMessageHistory复制过来===========================================
#==============================然后在  final_rag_with_chat_history  中通过import本文件调用类===================================
import os,json

from langchain_core.messages import BaseMessage
from typing import Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import message_to_dict,messages_from_dict

from utils.path_tool import get_abs_path
from utils.config_handler import chroma_conf



class FileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        self.session_id = session_id

        # 从配置读取 + 转绝对路径
        self.storage_path = get_abs_path(chroma_conf.get("chat_history_path", "./chat_history"))

        # 最终文件路径（安全、统一、规范）
        self.file_path = os.path.join(self.storage_path, f"{session_id}.json")
        os.makedirs(self.storage_path, exist_ok=True)



    def add_messages(self,messages: Sequence[BaseMessage]) ->None:
        all_messages = list(self.messages)   #已有的消息列表
        all_messages.extend(messages)       #追加新消息（揉进去）

        #数据写入本地文件
        #类对象写到文件，得到的是一堆二进制乱码 ==>  把BaseMessage消息转成字典（借助json模块，以json字符串格式写入文件）
        #官方包"message_to_dict"：单个消息对象->字典
        new_messages = []
        for message in all_messages:
            d = message_to_dict(message)    #d代表字典对象
            new_messages.append(d)          #原本存的message现在转成了字典，还需要写入文件
        with open(self.file_path,"w",encoding = "utf-8")as f:
            json.dump(new_messages,f)


    @property
    def messages(self) -> list[BaseMessage]:
        try:
            with open(self.file_path,"r",encoding = "utf-8")as f:
                message_data = json.load(f)
            return messages_from_dict(message_data)
        except FileNotFoundError:
            return []


    def clear(self) -> None:
        with open(self.file_path,"w",encoding = "utf-8")as f:
            json.dump([],f)



# 修改后
def get_history (session_id):
    return FileChatMessageHistory(session_id)