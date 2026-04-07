from openai import OpenAI
import json
import re
import time
import os

# 初始化客户端
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", timeout=None)

def analyze_device_risk(session_data: dict) -> dict:
    """
    调用本地大模型进行风险评分（为了批量处理效率，关闭了流式输出）
    """
    system_prompt = """
你是顶级风控决策引擎。你将接收一份设备指纹 JSON 数据，请严格按照以下【一票否决制】逻辑执行校验。

【核心提取变量】：
变量 S = `android_native_data.sensor_total_count` (若无此字段视作0)
变量 J = `webview_data.jsbridge_injected` (若无此字段视作false)
变量 A = `webview_data.installer_package`
变量 B = `android_native_data.is_adb_enabled`
变量 C = `web_data.timezone_offset`
变量 D = `android_native_data.battery_level_pct`

【风险判定逻辑表（🚨短路评估原则：只要命中上一条，立即停止向下评估，不得降级打分！）】：
1. 绝对一票否决（打分 90-100）：如果 变量S < 10，或者 变量J == false。这是纯正的黑产模拟器或无头PC。此时【无论它是否伪装了 manual 来源或 ADB】，直接打高分！不得降级！
2. 云机房判定（打分 35-45）：在【未命中逻辑1】的前提下。如果 变量A 严格等于 "manual" 且 (变量C == 0 或 变量B == true)；或者 变量B == true 且 变量D >= 97.0。这是插线的真机群控。
3. 官方白名单（打分 0-20）：未命中逻辑1和2，且 变量A 包含 "packageinstaller", "browser" 等字眼。
4. 容错规则：Web高度超出、内存误差3GB内、极速启动均不扣分。

🚨【JSON 格式最高红线】：
输出的 JSON 中，`risk_reason` 内【绝对禁止】包含双引号 (")、反斜杠 (\\) 和换行符！乘法用英文字母 x。

必须按以下格式输出：
第一行：草稿区。格式为：S=[值], J=[值], A=[值], B=[值], C=[值], D=[值]。命中逻辑[X]。
第二行：严格输出纯 JSON。

【输出示例 1：触发一票否决的模拟器（即使有云机房特征也被逻辑1拦截）】
草稿：S=1, J=true, A=manual, B=true, C=-480, D=100.0。S<10触发一票否决，短路拦截，命中逻辑1。
{
  "risk_score": 95,
  "risk_reason": "检测到核心传感器严重缺失，虽带有其他混淆特征，但底层暴露了黑产模拟器或PC环境的致命死穴，极高风险。"
}

【输出示例 2：未触发逻辑1的高级云机房】
草稿：S=42, J=true, A=com.miui.packageinstaller, B=true, C=-480, D=100.0。传感器正常未命中1，命中逻辑2。
{
  "risk_score": 40,
  "risk_reason": "传感器正常，但ADB调试常开且电量满载，暴露了长期接电的机架测试设备特征。"
}

【输出示例 3：未触发任何拦截的正常用户】
草稿：S=35, J=true, A=com.android.packageinstaller, B=false, C=-480, D=65.0。命中逻辑3。
{
  "risk_score": 15,
  "risk_reason": "硬件参数完美自洽，安装来源合法，无异常特征。"
}
"""

    user_prompt = f"请分析以下设备指纹数据：\n{json.dumps(session_data, ensure_ascii=False, indent=2)}"

    try:
        response = client.chat.completions.create(
            model="gemma-4-e4b-it", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            # max_tokens 不要设太小，给思考过程留足空间，比如 2048
            max_tokens=1024, 
            stream=False 
        )
        
        # 2. 终极数据捕获法：把模型所有的输出全盘接收
        msg_dict = response.choices[0].message.model_dump()
        content = msg_dict.get("content", "").strip()
        reasoning = msg_dict.get("reasoning_content", "").strip()
        
        print(f"\n[DEBUG] 思考引擎输出长度: {len(reasoning)} 字符")
        print(f"[DEBUG] 正式文本输出长度: {len(content)} 字符")

        # 1. 优先使用纯净的 content，如果 content 为空才去 reasoning 里找
        target_text = content if content else reasoning

        # 2. 精准匹配：寻找包含 risk_score 的 JSON 对象，放弃贪婪匹配
        match = re.search(r'\{\s*"risk_score"\s*:\s*\d+.*?"risk_reason"\s*:\s*"[^"]+"\s*\}', target_text, re.DOTALL)
        
        if match:
            pure_json_str = match.group(0)
            # 👇 --- 新增：专门针对数学算式的防爆清洗 ---
            # 1. 替换 Markdown 习惯的星号转义
            pure_json_str = pure_json_str.replace('\\*', '*')
            # 2. 替换可能出现的 LaTeX 乘号转义
            pure_json_str = pure_json_str.replace('\\times', 'x')
            # 👆 --------------------------------------
            try:
                return json.loads(pure_json_str)
            except json.JSONDecodeError:
                # 容错：替换可能出现的中文符号
                fixed_json = pure_json_str.replace('，', ',').replace('“', '"').replace('”', '"')
                return json.loads(fixed_json)
        else:
            print(f"❌ 提取失败！目标文本前200字: {target_text[:200]}...")
            raise ValueError("未匹配到规范的 JSON 结构")

    except Exception as e:
        print(f"调用失败: {e}")
        return {"risk_score": -1, "risk_reason": f"解析异常: {e}"}
    
def batch_process(input_file: str, output_file: str):
    if not os.path.exists(input_file):
        print(f"❌ 找不到输入文件: {input_file}")
        return

    # 1. 尝试读取已经处理过的数据，实现断点续传
    processed_session_ids = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as out_f:
            for line in out_f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        processed_session_ids.add(data.get("session_id"))
                    except json.JSONDecodeError:
                        pass
        print(f"✅ 检测到已处理 {len(processed_session_ids)} 条记录，将跳过这些记录。")

    # 2. 读取所有原始数据
    with open(input_file, "r", encoding="utf-8") as in_f:
        lines = [line.strip() for line in in_f if line.strip()]

    total_lines = len(lines)
    print(f"🚀 开始批量处理，共计 {total_lines} 条数据...\n")

    # 3. 逐行处理并实时追加写入
    with open(output_file, "a", encoding="utf-8") as out_f:
        for idx, line in enumerate(lines, 1):
            try:
                session_data = json.loads(line)
                session_id = session_data.get("session_id", "Unknown")

                # 如果已经处理过，直接跳过
                if session_id in processed_session_ids:
                    continue
                
                print(f"⏳ [{idx}/{total_lines}] 正在分析 Session: {session_id}...", end=" ")
                
                # 呼叫大模型打分
                llm_result = analyze_device_risk(session_data)
                
                # 将标签无缝融合进原始数据中，便于后续训练
                session_data["llm_label"] = {
                    "risk_score": llm_result.get("risk_score", -1),
                    "risk_reason": llm_result.get("risk_reason", "未知")
                }

                # 写入新的 JSONL 文件
                out_f.write(json.dumps(session_data, ensure_ascii=False) + "\n")
                out_f.flush() # 强制写入磁盘，防止中途崩溃丢失数据
                
                print(f"得分: {llm_result.get('risk_score')} | 理由: {llm_result.get('risk_reason')}")

            except json.JSONDecodeError:
                print(f"❌ [{idx}/{total_lines}] 数据格式错误，跳过。")
            except Exception as e:
                print(f"❌ [{idx}/{total_lines}] 处理异常: {e}")

    print("\n🎉 批量分析完成！带有标签的数据已保存至:", output_file)

if __name__ == "__main__":
    INPUT_JSONL = "simulated_bad_data.jsonl"   # 你扩充好的数据文件
    OUTPUT_JSONL = "bad_data_scored.jsonl"     # 生成带有大模型标签的数据文件
    
    batch_process(INPUT_JSONL, OUTPUT_JSONL)