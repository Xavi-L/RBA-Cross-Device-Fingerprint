from openai import OpenAI
import json
import re
import time
import os

# 初始化客户端，指向 LM Studio 的本地服务器地址
# LM Studio 默认不需要真实的 API Key，随便填一个 "lm-studio" 即可
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

def analyze_device_risk(session_data: dict) -> dict:
    """
    将合并后的跨端设备指纹 JSON 喂给大模型，进行风险评分
    """
    # 1. 精心设计的 System Prompt（系统提示词），赋予模型“风控专家”的人设
    system_prompt = """
    你是一个高级的无感风控（RBA）决策引擎。
    我将为你提供一份跨端（Web/WebView/Android）采集的设备指纹数据。
    请你重点检查以下异常指标：
    1. WebGL渲染器（webgl_renderer）是否包含 "Emulator", "Translator", "Virtual" 等模拟器特征。
    2. CPU算力挑战耗时（compute_task_time_ms）是否异常偏高（通常真机在 100ms 左右，模拟器往往超过 200ms）。
    3. 跨端通信状态（jsbridge_injected）是否为 true。如果为 false 说明不在 App 容器内，存在重放攻击风险。
    4. 逻辑分辨率与物理分辨率的比例是否合理（逻辑分辨率 * DPR = 物理分辨率）。

    请务必只以严格的 JSON 格式输出分析结果，包含两个字段：
    - "risk_score": 0 到 100 之间的整数（0代表绝对安全，100代表极高风险/确认是模拟器）。
    - "risk_reason": 简短的中文理由，解释扣分或判定高风险的原因。
    """

    # 2. 把你要验证的数据转成字符串，作为 User Prompt
    user_prompt = f"请分析以下设备指纹数据：\n{json.dumps(session_data, ensure_ascii=False, indent=2)}"

    # 3. 以流式方式呼叫本地大模型，实时接收分析结果
    try:
        print("正在呼叫本地风控引擎...")
        response = client.chat.completions.create(
            model="qwen3.5-9b", # 模型名会自动匹配 LM Studio 当前加载的
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            stream=True  # 保持开启流式打字效果
        )

        print("引擎实时分析中：\n")
        full_text = ""
        # 1. 逐字接收模型流式输出
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                full_text += text
        
        print("\n\n分析完毕！正在提取核心 JSON 判定结果...")

        # 2. 防爆魔法：先彻底剔除 <think> ... </think> 整个思考过程
        clean_text = re.sub(r'<think>.*?</think>', '', full_text, flags=re.DOTALL)
        
        # 3. 稳妥提取：在干净的文本里，截取从第一个 { 到最后一个 } 的内容
        start_idx = clean_text.find('{')
        end_idx = clean_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            pure_json_str = clean_text[start_idx:end_idx+1]
            try:
                return json.loads(pure_json_str)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON 内部格式化错误: \n{pure_json_str}")
                raise e
        else:
            raise ValueError("模型输出中未找到有效的 JSON 格式")

    except Exception as e:
        print(f"调用大模型失败: {e}")
        return {"risk_score": -1, "risk_reason": "风控服务异常"}

# ================= 测试与运行代码 =================
if __name__ == "__main__":
    jsonl_file = "collected_data.jsonl"

    if not os.path.exists(jsonl_file):
        print(f"找不到 {jsonl_file} 文件。请先运行 FastAPI 和 Android App 收集几条数据！")
    else:
        print(f"发现真实数据文件！开始批量进行风控分析...\n")
        
        # 读取所有的真实会话数据
        with open(jsonl_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            try:
                # 解析单行 JSON
                real_session_data = json.loads(line)
                session_id = real_session_data.get("session_id", "未知ID")
                
                print("\n" + "="*60)
                print(f"开始审查真实会话: {session_id}")
                print("="*60)

                # 把真实数据喂给你的 Qwen 3.5 引擎
                result = analyze_device_risk(real_session_data)
                
                print(f"\n会话 {session_id} 最终判定结果：")
                print(json.dumps(result, ensure_ascii=False, indent=4))
                
                # 稍微停顿2秒，让你能看清分析过程（也可以防止电脑风扇狂转）
                time.sleep(2) 

            except json.JSONDecodeError:
                print(f"跳过格式错误的行...")