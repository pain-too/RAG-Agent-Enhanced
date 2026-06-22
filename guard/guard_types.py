"""
安全门（Input Guard）—— 数据结构定义

定义三层防御中各层的结果类与判定枚举。
每个数据类只承担「数据传输」职责，不包含业务逻辑。
"""

# 系统模块
from dataclasses import dataclass, field
from enum import Enum


# ==================== 判定枚举 ====================

class Verdict(Enum):
    """
    Layer 2 注入检测的判定结论（三个互斥选项）

    ALLOW    — 输入安全，直接放行，无需任何处理
    SANITIZE — 输入中混入了可疑内容，尝试剥离后放行
    BLOCK    — 明确攻击或严重违规，直接拒绝
    """
    ALLOW = "allow"
    SANITIZE = "sanitize"
    BLOCK = "block"


# ==================== Layer 1 输出 ====================

@dataclass
class SanitizeResult:
    """
    Layer 1 输入清洗的输出

    cleaned_text    — 经过规范化、过滤后的文本
    is_garbage      — 是否为垃圾输入（超长/重复/无意义）
    garbage_reason  — 判定为垃圾时的原因说明
    original_length — 原始输入的字符数
    cleaned_length  — 清洗后的字符数
    """
    cleaned_text: str
    is_garbage: bool
    garbage_reason: str = ""
    original_length: int = 0
    cleaned_length: int = 0


# ==================== Layer 2 输出 ====================

@dataclass
class DetectionResult:
    """
    Layer 2 注入检测的输出

    verdict          — 判定结论（ALLOW / SANITIZE / BLOCK）
    reason           — 判定理由（如"命中 CRITICAL 规则：直接指令覆盖"）
    confidence       — 置信度，0.0 到 1.0
    matched_patterns — 命中的规则名称列表（审计日志用）
    llm_raw_response — LLM 分类的原始输出文本（调试用，规则判定时为空）
    """
    verdict: Verdict
    reason: str
    confidence: float
    matched_patterns: list = field(default_factory=list)
    llm_raw_response: str = ""


# ==================== Layer 3 输出 ====================

@dataclass
class RewriteResult:
    """
    Layer 3 查询重写的输出

    rewritten_query  — 重写后的安全查询文本
    action           — 最终动作："PASS" 放行 / "REWRITE" 已重写 / "BLOCK" 拒绝
    stripped_content — 从原始输入中剥离的可疑内容（审计用）
    reason           — 执行该动作的理由
    """
    rewritten_query: str
    action: str
    stripped_content: str = ""
    reason: str = ""


# ==================== 安全门最终输出 ====================

@dataclass
class GuardResult:
    """
    安全门三层的综合输出，对外唯一的调用结果

    verdict         — 最终判定："PASS" 放行 / "BLOCK" 拒绝
    query           — 最终传给下游 Agent 的问题文本
    original_query  — 保留原始输入（写入审计日志）
    reason          — 判定理由摘要
    trace           — 各层详情，结构为 {"layer1": {...}, "layer2": {...}, "layer3": {...}}
                      用于调试定位是哪一层拦截的
    """
    verdict: str
    query: str
    original_query: str
    reason: str = ""
    trace: dict = field(default_factory=dict)
