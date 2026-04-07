import json
import random
import uuid
import copy

def augment_device_data(input_filepath, output_filepath, target_count=300):
    """
    读取原始 jsonl 数据，通过修改动态特征将其扩充到指定数量。
    """
    # 1. 读取原始数据
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            original_data = [json.loads(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"找不到文件: {input_filepath}")
        return

    if not original_data:
        print("原始数据为空！")
        return

    print(f"成功加载 {len(original_data)} 条原始数据。开始扩展至 {target_count} 条...")
    
    # 将原始数据也保留在最终结果中
    augmented_data = list(original_data)

    # 2. 循环生成新数据直到满足目标数量
    while len(augmented_data) < target_count:
        # 随机挑选一条真实数据作为“模板”
        base_record = copy.deepcopy(random.choice(original_data))

        # --- 修改全局特征 ---
        # 时间戳：在原基础上随机偏移前后 7 天内的某个时间 (单位是秒)
        time_offset = random.randint(-86400 * 7, 86400 * 7) 
        base_record['timestamp'] += time_offset
        
        # 赋予全新的 Session ID (根据原始特征决定格式)
        original_session_id = base_record.get('session_id', '')
        
        if original_session_id.startswith('fallback-web-'):
            # 前端 JS 的 Date.now() 是毫秒级，而 payload 里的 timestamp 是秒级
            # 所以我们要把新的秒级时间戳乘以 1000，再加上随机的毫秒尾数，保证逻辑严密
            random_ms = random.randint(0, 999)
            new_ms_timestamp = base_record['timestamp'] * 1000 + random_ms
            base_record['session_id'] = f"fallback-web-{new_ms_timestamp}"
        else:
            # 原生端生成的，通常是 UUID，直接生成新的 UUID
            base_record['session_id'] = str(uuid.uuid4())

        # --- 修改 Native 特征 ---
        if 'android_native_data' in base_record:
            native = base_record['android_native_data']
            
            # 随机开机时间：10分钟 到 30天
            native['uptime_ms'] = random.randint(600_000, 2_592_000_000)
            
            # --- 新代码（完美模拟真实底层的字节换算） ---
            total_mem_gb = native.get('total_memory_gb', 8.0)
            
            # 1. 确定上下限的字节数 (Bytes)
            min_bytes = int(0.5 * 1024**3)
            max_bytes = int(max(0.6, total_mem_gb - 1.0) * 1024**3)
            
            # 2. 生成一个随机的真实字节整数
            random_avail_bytes = random.randint(min_bytes, max_bytes)
            
            # 3. 模拟底层的除法换算，自然产生 13~15 位的小数精度
            native['avail_memory_gb'] = random_avail_bytes / (1024**3)
            
            # 低内存状态判定保持不变
            native['is_low_memory'] = native['avail_memory_gb'] < 1.5
            
            # 电池状态模拟
            native['battery_level_pct'] = round(random.uniform(1.0, 100.0), 1)
            # 电池温度：20度 到 42度
            native['battery_temp_celsius'] = round(random.uniform(20.0, 42.0), 1)
            # 20% 的概率正在充电
            native['is_charging'] = random.choices([True, False], weights=[0.2, 0.8])[0]

        # --- 修改 WebView 特征 ---
        if 'webview_data' in base_record:
            wv = base_record['webview_data']
            if 'bridge_latency_ms' in wv:
                # 桥接延迟：基于原数据在 0.5倍 到 1.5倍 之间随机浮动
                latency = wv['bridge_latency_ms'] * random.uniform(0.5, 1.5)
                wv['bridge_latency_ms'] = round(latency, 2)

        # --- 修改 Web 特征 ---
        if 'web_data' in base_record:
            web = base_record['web_data']
            if 'compute_task_time_ms' in web:
                # 性能耗时：基于原数据在 0.8倍 到 1.3倍 之间随机浮动
                compute_time = web['compute_task_time_ms'] * random.uniform(0.8, 1.3)
                web['compute_task_time_ms'] = round(compute_time, 2)

        # 加入扩展列表
        augmented_data.append(base_record)

    # 3. 写入新的 jsonl 文件
    with open(output_filepath, 'w', encoding='utf-8') as f:
        for record in augmented_data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"数据扩展完成！已将 {len(augmented_data)} 条数据保存至 {output_filepath}")

# 使用示例
if __name__ == "__main__":
    # 假设你的原始文件叫 input.jsonl，你想扩展到 300 条并保存到 output.jsonl
    INPUT_FILE = 'real_data.jsonl'
    OUTPUT_FILE = 'output.jsonl'
    TARGET_RECORDS = 300 
    
    augment_device_data(INPUT_FILE, OUTPUT_FILE, TARGET_RECORDS)