#!/usr/bin/env python3
"""Score selected original rows with GLM direct risk_score output.

This is a manifest-aware variant of zhipu_glm_eval/score_with_glm.py for K0/K1
knowledge ablation. It keeps the same output shape used by existing analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = REPO_ROOT / "training" / "scored_data.jsonl"
DEFAULT_RULE_KB = REPO_ROOT / "scoring" / "rule_knowledge_base.json"
DEFAULT_MANIFEST = SCRIPT_DIR / "validation_sample_manifest.csv"
DEFAULT_OUTPUT = SCRIPT_DIR / "outputs" / "glm52_direct_k1_targeted.jsonl"
DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return rows


def load_selected_row_indices(manifest: Path, filter_name: str) -> list[int]:
    selected = []
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if filter_name not in (reader.fieldnames or []):
            raise ValueError(f"{filter_name} not found in manifest columns: {reader.fieldnames}")
        for row in reader:
            if str(row.get(filter_name, "")).strip().lower() in {"1", "true", "yes"}:
                selected.append(int(row["row_index"]))
    return selected


def compact_rule_kb(rule_kb: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": rule_kb.get("name"),
        "version": rule_kb.get("version"),
        "field_conventions": rule_kb.get("field_conventions", {}),
        "score_bands": rule_kb.get("score_bands", []),
        "evaluation_order": rule_kb.get("evaluation_order", []),
        "rules": rule_kb.get("rules", []),
        "output_contract": rule_kb.get("output_contract", {}),
    }


def build_system_prompt(rule_kb: dict[str, Any]) -> str:
    rules_json = json.dumps(compact_rule_kb(rule_kb), ensure_ascii=False, indent=2)
    return f"""
你是 HybridGuard 的离线风险评分引擎。你将接收一份三端设备指纹 JSON 数据，请严格依据下方【综合规则知识库】进行评分。

评分原则：
1. 先执行 short_circuit=true 的一票否决规则。只要命中，不得再用低风险规则降级。
2. 再识别模拟器、无头浏览器、接口重放、云机房或测试机架等组合场景。
3. 再综合 Native-Web、Native-WebView、WebView-Web 三组跨层一致性规则。
4. 最后应用容错规则。ADB、debuggable、cleartext、屏幕高度误差、Web deviceMemory 近似差异、Chrome 小版本差异不能单独判为高危。
5. 低风险结论只能在没有命中高危规则时使用。
6. Google 官方知识只用于理解字段语义和容错边界。当前数据没有 Play Integrity verdict、Key Attestation 证书链或 WebView URL/origin 时，不要在理由中声称这些强证据已经命中。

【综合规则知识库 JSON】
{rules_json}

输出必须是纯 JSON，且只包含 risk_score 和 risk_reason 两个字段：
{{"risk_score": 0, "risk_reason": "一句中文短理由"}}

不要输出推理过程、规则逐条分析、Markdown、代码块或额外解释。只能输出上述 JSON 对象本身。
risk_score 必须是 0 到 100 的整数。risk_reason 禁止包含英文双引号、反斜杠和换行符。
"""


def sample_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload.pop("llm_label", None)
    return payload


def read_processed_indices(path: Path) -> set[int]:
    processed = set()
    if not path.exists():
        return processed
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "row_index" in item and not item.get("error"):
                processed.add(int(item["row_index"]))
    return processed


def extract_risk_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        if "risk_score" in parsed and "risk_reason" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.findall(
        r'\{\s*"risk_score"\s*:\s*-?\d+\s*,\s*"risk_reason"\s*:\s*"[^"]*"\s*\}',
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"Could not parse risk JSON from response: {text[:300]}")
    return json.loads(match[-1])


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key_stdin:
        if sys.stdin.isatty():
            import termios

            fd = sys.stdin.fileno()
            old_attrs = termios.tcgetattr(fd)
            try:
                new_attrs = termios.tcgetattr(fd)
                new_attrs[3] = new_attrs[3] & ~termios.ECHO
                termios.tcsetattr(fd, termios.TCSADRAIN, new_attrs)
                api_key = sys.stdin.readline().strip()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
                print()
        else:
            api_key = sys.stdin.readline().strip()
        if not api_key:
            raise ValueError("Empty API key from stdin.")
        return api_key
    if args.api_key_file:
        return Path(args.api_key_file).read_text(encoding="utf-8").strip()
    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing API key. Use ZHIPU_API_KEY, --api-key-file, or --api-key-stdin.")
    return api_key


def call_glm(
    args: argparse.Namespace,
    api_key: str,
    system_prompt: str,
    row: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    request_body: dict[str, Any] = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "请分析以下设备指纹数据：\n"
                + json.dumps(sample_payload(row), ensure_ascii=False, indent=2),
            },
        ],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": False,
    }
    if args.response_format_json:
        request_body["response_format"] = {"type": "json_object"}
    if args.disable_thinking:
        request_body["thinking"] = {"type": "disabled"}

    raw = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    last_error: Exception | None = None
    for attempt in range(1, args.retries + 2):
        try:
            req = urllib.request.Request(args.endpoint, data=raw, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            message = payload["choices"][0].get("message", {})
            candidate_texts = [
                message.get("content", ""),
                message.get("reasoning_content", ""),
                message.get("reasoning", ""),
                message.get("output_text", ""),
            ]
            content = next((text for text in candidate_texts if isinstance(text, str) and text.strip()), "")
            if not content:
                preview = json.dumps(message, ensure_ascii=False)[:800]
                raise ValueError(f"Empty assistant message. message_preview={preview}")
            return extract_risk_json(content), content
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
            last_error = exc
            if attempt <= args.retries:
                time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"GLM call failed after retries: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score selected rows with GLM direct risk scores.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Scored JSONL input.")
    parser.add_argument("--rule-kb", default=str(DEFAULT_RULE_KB), help="Rule KB JSON path.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest CSV.")
    parser.add_argument("--manifest-filter", default="rule_targeted_candidate", help="Boolean manifest column.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSONL.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Zhipu endpoint.")
    parser.add_argument("--model", default="glm-5.2", help="Model name.")
    parser.add_argument("--knowledge-version", default="K1_official", help="Ablation label.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens.")
    parser.add_argument("--timeout", type=int, default=90, help="HTTP timeout seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retry count per row.")
    parser.add_argument("--response-format-json", action="store_true", help="Request JSON mode.")
    parser.add_argument("--disable-thinking", action="store_true", help="Disable thinking if supported.")
    parser.add_argument("--api-key-file", default=None, help="File containing only API key.")
    parser.add_argument("--api-key-stdin", action="store_true", help="Read API key from stdin.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = get_api_key(args)
    rows = load_jsonl(Path(args.input))
    selected_indices = load_selected_row_indices(Path(args.manifest), args.manifest_filter)
    if args.limit is not None:
        selected_indices = selected_indices[: args.limit]
    rule_kb = json.loads(Path(args.rule_kb).read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(rule_kb)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed = read_processed_indices(output_path)

    print(f"Selected {len(selected_indices)} rows. Output: {output_path}")
    with output_path.open("a", encoding="utf-8") as out_f:
        for position, row_index in enumerate(selected_indices, start=1):
            if row_index in processed:
                print(f"[{position}/{len(selected_indices)}] row={row_index} skipped")
                continue
            row = rows[row_index]
            session_id = row.get("session_id", "")
            teacher_score = row.get("llm_label", {}).get("risk_score")
            print(f"[{position}/{len(selected_indices)}] row={row_index} session={session_id} ...", end=" ")
            try:
                result, raw_response = call_glm(args, api_key, system_prompt, row)
                score = max(0, min(100, int(result.get("risk_score"))))
                record = {
                    "row_index": row_index,
                    "evidence_id": f"orig-{row_index}",
                    "session_id": session_id,
                    "model": args.model,
                    "knowledge_version": args.knowledge_version,
                    "teacher_score": teacher_score,
                    "glm_label": {
                        "risk_score": score,
                        "risk_reason": str(result.get("risk_reason", "")),
                    },
                    "raw_response": raw_response,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                print(f"glm_score={score} teacher={teacher_score}")
            except Exception as exc:
                record = {
                    "row_index": row_index,
                    "evidence_id": f"orig-{row_index}",
                    "session_id": session_id,
                    "model": args.model,
                    "knowledge_version": args.knowledge_version,
                    "teacher_score": teacher_score,
                    "error": str(exc),
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
