from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .config import Settings
from .semantic_retrieval import MODEL_NAME, SemanticRuleIndex

REQUIRED_FIELDS = ("rule_id", "title", "category", "intents", "order_statuses", "keywords", "public_content", "key_points", "answer_strategy", "source_title", "source_url")


@dataclass(frozen=True)
class RuleSource:
    rule_id: str
    title: str
    url: str
    content: str


@dataclass(frozen=True)
class RuleMatch:
    found: bool
    code: str
    message: str
    rule: dict[str, Any] | None = None
    source: RuleSource | None = None
    score: float = 0.0
    retrieval_method: str = "none"
    model_name: str | None = None


def load_rules(settings: Settings) -> list[dict[str, Any]]:
    if not settings.rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {settings.rules_path}")
    rules = []
    for line_number, line in enumerate(settings.rules_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rule = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSONL at line {line_number}: {error}") from error
        for field in REQUIRED_FIELDS:
            if field not in rule or rule[field] in (None, ""):
                raise ValueError(f"Rule line {line_number} is missing {field}")
        rules.append(rule)
    return rules


class RuleRetriever:
    def __init__(self, rules: list[dict[str, Any]], threshold: float = 0.35, min_margin: float = 0.02) -> None:
        self.rules = rules
        self.threshold = threshold
        self.min_margin = min_margin
        self.index = SemanticRuleIndex(rules)

    def retrieve(self, question: str, intent: str, order_status: str | None, enforce_status: bool = True) -> RuleMatch:
        normalized_intent = intent.strip().lower()
        normalized_status = order_status.strip().upper() if order_status else None
        candidates: list[int] = []
        for index, rule in enumerate(self.rules):
            intents = {str(value).lower() for value in rule["intents"]}
            statuses = {str(value).upper() for value in rule["order_statuses"]}
            if normalized_intent == "bypass_identity" and normalized_intent not in intents:
                continue
            if normalized_intent != "bypass_identity" and "bypass_identity" in intents:
                continue
            if normalized_intent not in {"unknown", "bypass_identity"} and normalized_intent not in intents:
                continue
            if enforce_status and statuses and (normalized_status is None or normalized_status not in statuses):
                continue
            candidates.append(index)
        ranked = self.index.rank(question, candidates)
        if not ranked:
            return RuleMatch(False, "KNOWLEDGE_NOT_FOUND", "客服知识库中没有适用规则。", retrieval_method="embedding", model_name=MODEL_NAME)
        score, rule_index = ranked[0]
        ambiguous = normalized_intent == "unknown" and len(ranked) > 1 and score - ranked[1][0] < self.min_margin
        if score < self.threshold or ambiguous:
            return RuleMatch(False, "BELOW_SEMANTIC_THRESHOLD", "语义相似度不足，不能据此回答。", score=score, retrieval_method="embedding", model_name=MODEL_NAME)
        rule = self.rules[rule_index]
        source = RuleSource(rule["rule_id"], rule["source_title"], rule["source_url"], rule["public_content"])
        return RuleMatch(True, "RULE_FOUND", "已通过语义检索找到适用规则。", rule, source, score, "embedding", MODEL_NAME)
