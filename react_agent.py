# 第一次修改：添加时间模块用于耗时统计
import time
#第三方库
from langchain.agents import create_agent
# 项目模块
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from tools.agent_tools import ds_knowledge_search, ds_concept_compare, ds_chapter_summary
# 第一次修改：导入日志追踪相关函数
from utils.logger_handler import logger, set_request_id, get_request_id, clear_request_id


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[ds_knowledge_search, ds_concept_compare, ds_chapter_summary],
        )
        self._has_tool_call = False

    def execute_stream(self, query: str, history: list = None):
        """
        Agent 流式执行 - 支持工具调用和多轮对话记忆
        LangChain标准消息格式：字典，且字典的值是列表套字典
        
        Args:
            query: 当前用户问题
            history: 历史消息列表（可选），格式为 [{"role": "user"/"assistant", "content": "..."}]
        """
        # 第一次修改：为每个请求生成唯一的请求ID，用于全链路追踪
        request_id = set_request_id()
        # 第一次修改：记录请求开始时间，用于计算总耗时
        start_time = time.time()
        
        # 第一次修改：记录请求开始日志，包含请求ID和查询内容（前100字符）
        logger.info(f"[Agent执行] 开始处理请求 | 请求ID: {request_id} | 查询: {query[:100]}...")
        logger.info(f"[Agent执行] 历史消息轮数: {len(history) // 2 if history else 0}")
        
        self._has_tool_call = False
        
        # 构建输入消息列表
        input_messages = []
        
        # 如果有历史消息，添加到输入中
        if history:
            input_messages.extend(history)
        
        # 添加当前用户问题
        input_messages.append({"role": "user", "content": query})
        
        input_dict = {
            "messages": input_messages
        }

        try:
            # 使用 values 模式，会输出所有if,elif判断的结果
            for chunk in self.agent.stream(input_dict, stream_mode="values"):
                messages = chunk.get('messages', [])
                if not messages:
                    continue

                latest_message = messages[-1]
                # 判断消息类型并输出，没有就返回None
                message_type = getattr(latest_message, 'type', None)

                # 判断 Agent 是否在思考或调用工具
                if message_type == 'ai' and hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
                    # 获取所有AI调用的工具名，返回成列表并流式输出
                    tool_names = [tc.get('name', 'unknown') for tc in latest_message.tool_calls]
                    # 第一次修改：记录工具调用日志，包含请求ID和被调用的工具列表
                    logger.info(f"[Agent执行] 请求ID: {request_id} | 调用工具: {', '.join(tool_names)}")
                    self._has_tool_call = True
                    yield f"\n🔧  {', '.join(tool_names)} 正在被调用  \n"

                # 执行完工具后才会有tool类型的消息
                elif message_type == 'tool':
                    tool_name = getattr(latest_message, 'name', 'unknown')
                    ans_content = getattr(latest_message, 'content', '')
                    # 第一次修改：记录工具执行完成日志，包含请求ID和工具名称
                    logger.info(f"[Agent执行] 请求ID: {request_id} | 工具完成: {tool_name}")
                    yield f"✅ {tool_name} 执行完成  \n"
                    if ans_content and ans_content.strip():
                        yield ans_content

                # LLM 的最终回答（有内容时输出，兜底强制输出）
                elif message_type == 'ai':
                    content = latest_message.content
                    if content and content.strip():
                        # 第一次修改：记录回答生成日志，包含请求ID和回答长度
                        logger.info(f"[Agent执行] 请求ID: {request_id} | 生成回答 | 长度: {len(content)}")
                        yield content

                # 用户消息（跳过，不输出）
                elif message_type == 'human':
                    continue

            # 第一次修改：计算并记录请求总耗时
            elapsed_time = (time.time() - start_time) * 1000
            logger.info(f"[Agent执行] 请求完成 | 请求ID: {request_id} | 总耗时: {elapsed_time:.2f}ms")
            
        except Exception as e:
            # 第一次修改：记录请求失败日志，包含请求ID、总耗时和错误信息
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(f"[Agent执行] 请求失败 | 请求ID: {request_id} | 总耗时: {elapsed_time:.2f}ms | 错误: {str(e)}")
            raise
        finally:
            # 第一次修改：无论成功或失败，都要清除请求ID，释放线程资源
            clear_request_id()