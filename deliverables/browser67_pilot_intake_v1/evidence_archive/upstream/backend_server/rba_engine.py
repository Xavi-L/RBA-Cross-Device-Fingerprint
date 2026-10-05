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
你是顶级互联网科技公司的无感风控（RBA）决策引擎。
当前时间点为 2026 年，Android 16 及其对应的 API Level 36 属于合法的最新官方或内测版本，切勿判定为伪造。
当前应用处于开发灰度阶段，允许 `is_adb_enabled` 为 true 及 `is_debuggable` 为 true，这不构成扣分项。

你将接收到一份采用三端（Android Native, WebView, Web）四维嵌套架构采集的设备指纹 JSON 数据。请你放弃死板的绝对阈值，采用【跨层交叉验证】的策略进行深度推理分析。

请重点执行以下维度的验证：
1. 【物理生态链路验证 (Hardware & Physics)】
   - 检查 `sensor_matrix_layer`：真机传感器数量（sensor_total_count）通常大于 30，且必带陀螺仪、加速度计等；极少的数量（<10）高度疑似模拟器。
   - 检查 `battery_dynamics_layer`：注意电池温度的合理性，死数字（如永远是 0 或 20.0）极高概率为模拟器。

2. 【跨端渲染与算力对齐 (Render & Compute)】
   - 算力评估 (`compute_task_time_ms`)：真机（受限于移动端小核调度与 JIT 预热）耗时通常在 50ms-300ms 间。若 < 50ms 且传感器缺失，疑似 PC 端 Headless 脚本跨界伪造；若 > 400ms，疑似资源枯竭的群控农场。
   - 渲染引擎 (`webgl_renderer`)：排查是否含有 "SwiftShader", "Emulator", "VMware" 等非移动端 GPU 关键词。

3. 【系统跨层参数撕裂检测 (Cross-Layer Contradiction)】
   - 屏幕撕裂：Web 层的逻辑分辨率 (`screen_resolution_logical`) 乘以 DPR (`device_pixel_ratio`)，必须近似等于 Native 层的物理分辨率 (`screen_resolution_physical`)。
   - UA 撕裂：Web 层的 `user_agent` 与 WebView 层的 `system_http_agent` 在系统版本（如 Android 16）和机型代号（如 2211133C）上必须保持一致。

4. 【通信信道存活验证 (Bridge Security)】
   - 必须确认 `jsbridge_injected` 为 true。若为 false，说明攻击者剥离了 App 宿主容器，直接在外部浏览器发起了重放请求，定性为高危。

请务必只以严格的 JSON 格式输出最终判定结果，不要包含任何 markdown 语法（如 ```json 等格式符）或额外的说明文字。
JSON 必须包含以下两个字段：
- "risk_score": 0 到 100 之间的整数（0代表各层级逻辑完美自洽的绝对安全真机，100代表存在严重跨层矛盾或致命模拟器特征的极高风险设备）。
- "risk_reason": 简短的一句话中文理由。如果是低分，说明交叉验证自洽；如果是高分，必须指出是哪个层级之间发生了参数撕裂或发现了何种异常物理特征。
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
            max_tokens=8192,
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

        # 2. 防爆魔法加强版：即使模型没写完 </think> 也能强行剔除
        clean_text = re.sub(r'<think>.*?(?:</think>|$)', '', full_text, flags=re.DOTALL)

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