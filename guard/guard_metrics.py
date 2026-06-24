""" 安全门统计指标（Guard Metrics）

guard_metrics.py
├── ① GuardMetrics 类        ← 内存计数器（「大的类」）
│     ├── 计数字段               total_requests, passed, blocked_*, ...
│     ├── 计算属性               block_total, pass_rate, avg_llm_calls_*
│     ├── record_request()      每次请求调一次，所有计数器 += 1
│     └── to_dict()             导出当前快照给前端/API
│
├── ② get_guard_metrics()     ← 单例工厂（一行代码）
│     全局唯一一个 GuardMetrics 实例，全应用共享
│
└── ③ persist_metrics_log()   ← 写 JSONL 日志文件（「写日志」）
     把单次请求的详细信息追加到 eval/guard_logs/日期.jsonl
"""

import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ========================================================================
# 指标数据结构
# ========================================================================

@dataclass
class GuardMetrics:
    """ 安全门统计指标。
    分类说明：
      - 请求概览:     total / passed / blocked (security + scope + invalid)
      - 攻击类型分布:   attack_type_counts
      - 规则命中分布:   rule_hit_counts
      - LLM 调用统计:  llm_classification_calls / llm_disambiguation_calls
      - 改写统计:      rewrites_total / rewrites_by_rule / rewrites_by_llm
    """

    # ──── 请求概览 ────
    total_requests: int = 0
    passed: int = 0
    blocked_security: int = 0
    blocked_scope: int = 0
    blocked_invalid: int = 0

    @property
    def blocked_total(self) -> int:
        return self.blocked_security + self.blocked_scope + self.blocked_invalid

    @property
    def pass_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.passed / self.total_requests

    #攻击类型分布      示例: {"PROMPT_INJECTION": 12, "ROLE_ESCAPE": 5, ...}
    attack_type_counts: dict = field(default_factory=lambda: defaultdict(int))
    #规则命中分布      示例: {"direct_instruction_override": 8, "role_hijack_identity": 4, ...}
    rule_hit_counts: dict = field(default_factory=lambda: defaultdict(int))
    #LLM 调用统计
    llm_classification_calls: int = 0     # Layer 2 LLM 分类调用次数
    llm_disambiguation_calls: int = 0     # Layer 3 LLM 消歧义调用次数

    @property
    def avg_llm_calls_per_request(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.llm_classification_calls + self.llm_disambiguation_calls) / self.total_requests

    # 改写统计
    rewrites_total: int = 0
    rewrites_by_rule: int = 0
    rewrites_by_llm: int = 0
    security_strips: int = 0            # 触发安全剥离的次数

    # Verdict 分布（细粒度）    示例: {"PASS": 850, "BLOCK_SECURITY": 30, "BLOCK_SCOPE": 100, "BLOCK_INVALID": 20}
    verdict_counts: dict = field(default_factory=lambda: defaultdict(int))

    # 线程安全
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_request(
        self,
        verdict: str,
        attack_types: list[str] | None = None,
        matched_rules: list[str] | None = None,
        llm_classification_used: bool = False,
        llm_disambiguation_used: bool = False,
        rewrite_method: str = "none",
        security_stripped: bool = False,
    ):
        """
        记录一次安全门请求的统计。

        参数:
            verdict:                  最终判定 "PASS" / "BLOCK_SECURITY" / "BLOCK_SCOPE" / "BLOCK_INVALID"
            attack_types:            检测到的攻击类型列表
            matched_rules:           命中的规则名列表
            llm_classification_used: Layer 2 是否调用了 LLM 分类
            llm_disambiguation_used: Layer 3 是否调用了 LLM 消歧义
            rewrite_method:          改写方式 "rule" / "llm" / "hybrid" / "none"
            security_stripped:       是否进行了安全剥离
        """
        with self._lock:
            self.total_requests += 1
            self.verdict_counts[verdict] += 1

            if verdict == "PASS":
                self.passed += 1
            elif verdict == "BLOCK_SECURITY":
                self.blocked_security += 1
            elif verdict == "BLOCK_SCOPE":
                self.blocked_scope += 1
            elif verdict == "BLOCK_INVALID":
                self.blocked_invalid += 1

            # 攻击类型统计
            if attack_types:
                for at in attack_types:
                    self.attack_type_counts[at] += 1

            # 规则命中统计
            if matched_rules:
                for rn in matched_rules:
                    self.rule_hit_counts[rn] += 1

            # LLM 调用统计
            if llm_classification_used:
                self.llm_classification_calls += 1
            if llm_disambiguation_used:
                self.llm_disambiguation_calls += 1

            # 改写统计
            if rewrite_method != "none":
                self.rewrites_total += 1
                if rewrite_method == "rule":
                    self.rewrites_by_rule += 1
                elif rewrite_method in ("llm", "hybrid"):
                    self.rewrites_by_llm += 1
                # hybrid 同时计入 rule 和 llm
                if rewrite_method == "hybrid":
                    self.rewrites_by_rule += 1

            if security_stripped:
                self.security_strips += 1

    def to_dict(self) -> dict:
        """导出为可序列化的字典（供 API / 仪表盘用）。"""
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "passed": self.passed,
                "blocked_security": self.blocked_security,
                "blocked_scope": self.blocked_scope,
                "blocked_invalid": self.blocked_invalid,
                "blocked_total": self.blocked_total,
                "pass_rate": round(self.pass_rate, 4),
                "attack_type_counts": dict(self.attack_type_counts),
                "rule_hit_counts": dict(self.rule_hit_counts),
                "llm_classification_calls": self.llm_classification_calls,
                "llm_disambiguation_calls": self.llm_disambiguation_calls,
                "avg_llm_calls_per_request": round(self.avg_llm_calls_per_request, 4),
                "rewrites_total": self.rewrites_total,
                "rewrites_by_rule": self.rewrites_by_rule,
                "rewrites_by_llm": self.rewrites_by_llm,
                "security_strips": self.security_strips,
                "verdict_counts": dict(self.verdict_counts),
            }


# ========================================================================
# 单例
# ========================================================================
_guard_metrics = GuardMetrics()
def get_guard_metrics() -> GuardMetrics:
    """获取 GuardMetrics 单例。"""
    return _guard_metrics


# ========================================================================
# 请求日志持久化（JSONL）
# ========================================================================
def persist_metrics_log(entry: dict, log_dir: str | None = None):
    """
    将单条请求日志追加写入 JSONL 文件。
    """

    if log_dir is None:
        log_dir = str(Path(__file__).resolve().parent.parent / "eval" / "guard_logs")

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 按日期分文件，避免单文件过大
    date_str = datetime.now().strftime("%Y%m%d")
    log_path = Path(log_dir) / f"guard_log_{date_str}.jsonl"

    entry.setdefault("timestamp", datetime.now().isoformat())

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[GuardMetrics] 日志持久化失败: {str(e)}")
