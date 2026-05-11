from openai import OpenAI
import argparse
import json
import os
from pathlib import Path
import re


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RULE_KB = SCRIPT_DIR / "rule_knowledge_base.json"
DEFAULT_INPUT = SCRIPT_DIR / "simulated_bad_data.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "simulated_bad_data_rule_kb_scored.jsonl"

client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", timeout=None)


def load_rule_knowledge_base(rule_kb_path: str | Path) -> dict:
    with Path(rule_kb_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def compact_rule_kb(rule_kb: dict) -> dict:
    """Keep the prompt focused on fields the LLM needs for scoring."""
    return {
        "name": rule_kb.get("name"),
        "version": rule_kb.get("version"),
        "field_conventions": rule_kb.get("field_conventions", {}),
        "score_bands": rule_kb.get("score_bands", []),
        "evaluation_order": rule_kb.get("evaluation_order", []),
        "rules": rule_kb.get("rules", []),
        "output_contract": rule_kb.get("output_contract", {}),
    }


def build_system_prompt(rule_kb: dict) -> str:
    rules_json = json.dumps(compact_rule_kb(rule_kb), ensure_ascii=False, indent=2)
    return f"""
你是 HybridGuard 的离线风险标签生成引擎。你将接收一份三端设备指纹 JSON 数据，请严格依据下方【综合规则知识库】进行评分。

评分时必须遵守以下原则：
1. 先执行 short_circuit=true 的一票否决规则。只要命中，不得再用低风险规则降级。
2. 再识别模拟器、无头浏览器、接口重放、云机房或测试机架等组合场景。
3. 再综合 Native-Web、Native-WebView、WebView-Web 三组跨层一致性规则。
4. 最后应用容错规则。ADB、debuggable、cleartext、屏幕高度误差、Web deviceMemory 近似差异、Chrome 小版本差异不能单独判为高危。
5. 低风险结论只能在没有命中高危规则时使用。

【综合规则知识库 JSON】
{rules_json}

输出格式必须满足：
第一行：草稿。写出主要命中规则 ID、关键字段值和评分区间。
第二行：严格输出纯 JSON，且只包含 risk_score 和 risk_reason 两个字段。

risk_score 必须是 0 到 100 的整数。risk_reason 必须是一句中文短理由，禁止包含英文双引号、反斜杠和换行符。
"""


def extract_risk_json(text: str) -> dict:
    candidates = re.findall(
        r'\{\s*"risk_score"\s*:\s*-?\d+\s*,\s*"risk_reason"\s*:\s*"[^"]*"\s*\}',
        text,
        flags=re.DOTALL,
    )
    if not candidates:
        raise ValueError("未匹配到包含 risk_score 和 risk_reason 的 JSON 对象")

    pure_json_str = candidates[-1]
    pure_json_str = pure_json_str.replace("\\*", "*").replace("\\times", "x")
    try:
        return json.loads(pure_json_str)
    except json.JSONDecodeError:
        fixed_json = pure_json_str.replace("，", ",").replace("“", '"').replace("”", '"')
        return json.loads(fixed_json)


def analyze_device_risk(session_data: dict, rule_kb: dict, model: str, max_tokens: int) -> dict:
    system_prompt = build_system_prompt(rule_kb)
    user_prompt = f"请分析以下设备指纹数据：\n{json.dumps(session_data, ensure_ascii=False, indent=2)}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
            stream=False,
        )

        msg_dict = response.choices[0].message.model_dump()
        content = msg_dict.get("content", "").strip()
        reasoning = msg_dict.get("reasoning_content", "").strip()
        target_text = content if content else reasoning
        return extract_risk_json(target_text)
    except Exception as exc:
        print(f"调用或解析失败: {exc}")
        return {"risk_score": -1, "risk_reason": f"解析异常: {exc}"}


def read_processed_session_ids(output_file: Path) -> set[str]:
    processed_session_ids: set[str] = set()
    if not output_file.exists():
        return processed_session_ids

    with output_file.open("r", encoding="utf-8") as out_f:
        for line in out_f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                session_id = data.get("session_id")
                if session_id:
                    processed_session_ids.add(session_id)
            except json.JSONDecodeError:
                pass
    return processed_session_ids


def batch_process(
    input_file: str | Path,
    output_file: str | Path,
    rule_kb_path: str | Path,
    model: str,
    max_tokens: int,
    limit: int | None = None,
) -> None:
    input_file = Path(input_file)
    output_file = Path(output_file)

    if not input_file.exists():
        print(f"找不到输入文件: {input_file}")
        return

    rule_kb = load_rule_knowledge_base(rule_kb_path)
    processed_session_ids = read_processed_session_ids(output_file)
    if processed_session_ids:
        print(f"检测到已处理 {len(processed_session_ids)} 条记录，将跳过这些记录。")

    with input_file.open("r", encoding="utf-8") as in_f:
        lines = [line.strip() for line in in_f if line.strip()]

    if limit is not None:
        lines = lines[:limit]

    total_lines = len(lines)
    print(f"开始批量处理，共计 {total_lines} 条数据。")
    print(f"规则知识库: {rule_kb_path}")
    print(f"输出文件: {output_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("a", encoding="utf-8") as out_f:
        for idx, line in enumerate(lines, 1):
            try:
                session_data = json.loads(line)
                session_id = session_data.get("session_id", "Unknown")
                if session_id in processed_session_ids:
                    continue

                print(f"[{idx}/{total_lines}] 分析 Session: {session_id} ...", end=" ")
                llm_result = analyze_device_risk(session_data, rule_kb, model, max_tokens)
                session_data["llm_label"] = {
                    "risk_score": llm_result.get("risk_score", -1),
                    "risk_reason": llm_result.get("risk_reason", "未知"),
                }
                out_f.write(json.dumps(session_data, ensure_ascii=False) + "\n")
                out_f.flush()
                print(
                    f"得分: {llm_result.get('risk_score')} | "
                    f"理由: {llm_result.get('risk_reason')}"
                )
            except json.JSONDecodeError:
                print(f"[{idx}/{total_lines}] 数据格式错误，跳过。")
            except Exception as exc:
                print(f"[{idx}/{total_lines}] 处理异常: {exc}")

    print("批量分析完成。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch score device fingerprints with HybridGuard rule knowledge base."
    )
    parser.add_argument("--input", default=os.fspath(DEFAULT_INPUT), help="Input JSONL file.")
    parser.add_argument("--output", default=os.fspath(DEFAULT_OUTPUT), help="Output JSONL file.")
    parser.add_argument(
        "--rule-kb",
        default=os.fspath(DEFAULT_RULE_KB),
        help="Rule knowledge base JSON file.",
    )
    parser.add_argument("--model", default="gemma-4-e4b-it", help="LM Studio model name.")
    parser.add_argument("--max-tokens", type=int, default=2048, help="LLM max output tokens.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to process.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    batch_process(
        input_file=args.input,
        output_file=args.output,
        rule_kb_path=args.rule_kb,
        model=args.model,
        max_tokens=args.max_tokens,
        limit=args.limit,
    )
