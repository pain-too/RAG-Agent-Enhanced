"""
安全门（Input Guard）—— 数据结构定义

每个数据类只承担「数据传输」职责，不包含业务逻辑。
"""

from dataclasses import dataclass, field
from enum import Enum
from collections import Counter


# ==================== 最终判定枚举 ====================
class Verdict(Enum):
    """
    安全门最终判定。
    PASS           — 放行，安全且在业务范围内
    BLOCK_SECURITY — 安全拦截：检测到攻击行为（注入、越狱、提示词窃取等）
    BLOCK_SCOPE    — 范围拦截：输入安全但超出 408 数据结构领域
    BLOCK_INVALID  — 无效输入：垃圾文本、超长、重复模式
    """
    PASS = "pass"
    BLOCK_SECURITY = "block_security"
    BLOCK_SCOPE = "block_scope"
    BLOCK_INVALID = "block_invalid"


# ==================== Layer 1 输出 ====================
@dataclass
class SanitizeResult:
    """ Layer 1 输入清洗的输出。
    cleaned_text    — 规范化、过滤后的文本
    is_garbage      — 是否为垃圾输入（超长 / 重复 / 无意义）
    garbage_reason  — 判定为垃圾时的原因说明
    original_length — 原始输入字符数
    cleaned_length  — 清洗后字符数
    """
    cleaned_text: str
    is_garbage: bool
    garbage_reason: str = ""
    original_length: int = 0
    cleaned_length: int = 0


# ==================== Layer 2 输出 ====================
@dataclass
class DetectionResult:
    """ Layer 2 攻击检测的输出。
    attack_detected  — 是否检测到攻击行为（布尔判定，取代旧的三分类）
    attack_types     — 攻击类型列表，如 ["PROMPT_INJECTION", "PROMPT_LEAKAGE"]
    severity         — 最高严重级别："CRITICAL" | "WARNING" | "NONE"
    matched_rules    — 命中的规则详情 [{name, attack_type, severity, matched_text}, ...]
    review_required  — 规则判定不确定时，是否需要 LLM 二次确认
    salvageable      — 攻击是否可剥离（仅 WARNING 级别命中时可精准正则删除）
    reason           — 判定理由摘要
    llm_raw_response — LLM 分类的原始输出文本（调试用）
    """
    attack_detected: bool = False
    attack_types: list[str] = field(default_factory=list)
    severity: str = "NONE"
    matched_rules: list = field(default_factory=list)
    review_required: bool = False
    salvageable: bool = False
    reason: str = ""
    llm_raw_response: str = ""


# ==================== Scope Check 输出 ====================
@dataclass
class ScopeResult:
    """ 业务范围检查的输出。
    in_scope — 是否属于 408 数据结构领域
    method   — 判定方式："rule"（关键词快速检查）| "llm"（LLM 分类）
    category — "408_data_structure" | "out_of_scope"
    reason   — 判定理由
    """
    in_scope: bool = True
    method: str = "rule"
    category: str = "408_data_structure"
    reason: str = ""


# ==================== Layer 3: Rewrite Trace ====================
@dataclass
class TransformStep:
    """ 查询改写过程中的单步变换记录。
    stage  — 阶段名：security_strip / term_normalize / noise_remove / llm_disambiguate
    input  — 变换前文本
    output — 变换后文本
    method — "rule" | "llm" | "none"（none 表示该步骤无需处理，原样透传）
    detail — 阶段特定的元数据
    """
    stage: str
    input: str
    output: str
    method: str = "none"
    detail: dict = field(default_factory=dict)


@dataclass
class RewriteTrace:
    """ 完整改写链路。
    记录从用户原始输入到最终查询之间每一步变换，
    用于前端展示、调试定位、评测统计。
    """
    original: str = ""
    steps: list = field(default_factory=list)  # list[TransformStep]
    final: str = ""

    @property
    def total_modifications(self) -> int:
        """实际改变的步骤数"""
        return sum(1 for s in self.steps if s.input != s.output)

    @property
    def method_summary(self) -> dict:
        """各方法使用次数统计"""
        return dict(Counter(s.method for s in self.steps))


@dataclass
class RewriteResult:
    """ Layer 3 查询改写的输出。
    rewritten_query  — 改写后的最终查询文本
    action           — "PASS" 放行 / "REWRITE" 已改写 / "BLOCK" 拒绝（剥离后无效）
    method           — "rule" / "llm" / "hybrid" / "none"
    stripped_content — 安全剥离时删除的可疑内容
    reason           — 执行该动作的理由
    trace            — 完整改写链路
    """
    rewritten_query: str = ""
    action: str = "PASS"
    method: str = "none"
    stripped_content: str = ""
    reason: str = ""
    trace: RewriteTrace | None = None

# ==================== 安全门最终输出 ====================
@dataclass
class GuardResult:
    """ 安全门的最终输出，对下游唯一的调用结果。
    verdict        — "PASS" | "BLOCK_SECURITY" | "BLOCK_SCOPE" | "BLOCK_INVALID"
    query          — 最终传给 Agent 的安全 + 优化后文本
    original_query — 原始用户输入（审计日志用）
    reason         — 判定理由摘要
    attack_types   — 攻击类型列表（PASS 时为空）
    trace          — 各层详情，供前端展示和调试
    rewrite_trace  — 查询改写完整链路（PASS 时有值）
    """
    verdict: str = ""
    query: str = ""
    original_query: str = ""
    reason: str = ""
    attack_types: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)
    rewrite_trace: RewriteTrace | None = None
