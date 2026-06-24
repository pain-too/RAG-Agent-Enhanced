"""
安全门模块（Input Guard）—— Agent 输入安全防护

对外接口：
    input_guard(user_input: str) → GuardResult

数据结构（无需 langchain 依赖，可独立导入）：
    GuardResult     — 最终判定结果
    DetectionResult — Layer 2 攻击检测结果
    SanitizeResult  — Layer 1 清洗结果
    ScopeResult     — 范围检查结果
    RewriteResult   — Layer 3 重写结果
    RewriteTrace    — 完整改写链路
    TransformStep   — 单步变换记录
    Verdict         — 判定枚举

统计指标：
    get_guard_metrics()  → GuardMetrics 单例
    persist_metrics_log() → JSONL 持久化
"""

# 数据结构无第三方依赖，直接导出
from guard.guard_types import (
    GuardResult,
    SanitizeResult,
    DetectionResult,
    ScopeResult,
    RewriteResult,
    RewriteTrace,
    TransformStep,
    Verdict,
)

# 统计指标
from guard.guard_metrics import (
    GuardMetrics,
    get_guard_metrics,
    persist_metrics_log,
)


def __getattr__(name):
    """
    懒加载 input_guard（它依赖 langchain，不是所有场景都需要）。
    只有在代码中写 from guard import input_guard 或 guard.input_guard(...) 时才触发导入。
    """
    if name == "input_guard":
        from guard.input_guard import input_guard as _input_guard
        import sys
        this_module = sys.modules[__name__]
        this_module.input_guard = _input_guard
        return _input_guard

    raise AttributeError(f"模块 'guard' 没有属性 '{name}'")


__all__ = [
    # 入口函数
    "input_guard",
    # 数据结构
    "GuardResult",
    "SanitizeResult",
    "DetectionResult",
    "ScopeResult",
    "RewriteResult",
    "RewriteTrace",
    "TransformStep",
    "Verdict",
    # 统计
    "GuardMetrics",
    "get_guard_metrics",
    "persist_metrics_log",
]
