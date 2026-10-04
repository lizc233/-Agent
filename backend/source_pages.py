from __future__ import annotations

from html import escape
from typing import Any


def find_rule(rules: list[dict[str, Any]], rule_id: str) -> dict[str, Any] | None:
    return next((rule for rule in rules if rule["rule_id"] == rule_id), None)


def render_rule_page(rule: dict[str, Any]) -> str:
    title = escape(rule["source_title"])
    content = escape(rule["public_content"])
    key_points = "".join(f"<li>{escape(str(point))}</li>" for point in rule.get("key_points", []))
    identifier = escape(rule["rule_id"])
    review_status = escape(rule.get("review_status", "unknown"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{title}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:"Microsoft YaHei UI",sans-serif;background:linear-gradient(135deg,#fff8e9,#fffdf8);color:#352918}}
.top{{height:10px;background:linear-gradient(90deg,#ffb21f,#f58a00)}}
.wrap{{max-width:820px;margin:56px auto;padding:0 22px}} .brand{{color:#ed8a00;font-weight:800;letter-spacing:1px}}
.card{{background:white;border:1px solid #f1dfbf;border-radius:20px;padding:34px;box-shadow:0 18px 50px rgba(112,73,14,.10)}}
h1{{margin:8px 0 22px;font-size:30px}} .content{{font-size:17px;line-height:2;background:#fff8e9;border-left:5px solid #ffad20;padding:20px;border-radius:8px}}
.points{{line-height:1.9;background:#f7fbf5;border-radius:10px;padding:14px 20px 14px 38px}}
.meta{{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}} .tag{{background:#f7efe1;border-radius:999px;padding:7px 13px;color:#755d36}}
.notice{{margin-top:24px;color:#7d6b50;font-size:14px;border-top:1px solid #eee0c9;padding-top:18px}}
</style></head>
<body><div class="top"></div><main class="wrap"><div class="brand">KANGAROO TRUST CENTER</div><section class="card">
<h1>{title}</h1><h2>客服答复要点</h2><ul class="points">{key_points}</ul><h2>完整规范</h2><div class="content">{content}</div>
<div class="meta"><span class="tag">规则编号：{identifier}</span><span class="tag">审核状态：{review_status}</span></div>
<p class="notice"><strong>可信来源说明：</strong>本页面展示课程项目使用的模拟客服规则，用于说明 Agent 回答依据，不代表平台官方政策。</p>
</section></main>
</body></html>"""
