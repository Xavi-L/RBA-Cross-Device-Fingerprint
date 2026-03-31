from appium import webdriver
from appium.options.android import UiAutomator2Options
import concurrent.futures
import random
import time
import sys

# --- 1. 填入你的账号与包信息 ---
USER_NAME = "lex_K4lZtL"
ACCESS_KEY = "SW3m3HLsyRufpuGh6Uvi"
APP_URL = "bs://71966f2498b11fe453d4ae28a7052f3a504d5db2"
REMOTE_URL = f"https://{USER_NAME}:{ACCESS_KEY}@hub-cloud.browserstack.com/wd/hub"

# --- 2. 动态正则机型池 ---
# 使用 .* 模糊匹配，BrowserStack 会自动在机房寻找符合前缀的空闲设备
DEVICE_POOL = [
    {"deviceName": "Samsung Galaxy S.*", "platformVersion": "1[23].*"},
    {"deviceName": "Google Pixel.*", "platformVersion": "1[234].*"},
    {"deviceName": "OnePlus.*", "platformVersion": "1[123].*"},
    {"deviceName": "Xiaomi.*", "platformVersion": "1[123].*"},
    {"deviceName": "Motorola.*", "platformVersion": "1[12].*"},
    {"deviceName": "Vivo.*", "platformVersion": "1[12].*"},
    {"deviceName": "Oppo.*", "platformVersion": "1[12].*"}
]

def run_single_device(device_info, thread_id, batch_num):
    """单个线程的设备调用与数据收集逻辑"""
    options = UiAutomator2Options()
    options.set_capability("platformName", "android")
    options.set_capability("appium:platformVersion", device_info["platformVersion"])
    options.set_capability("appium:deviceName", device_info["deviceName"])
    options.set_capability("appium:app", APP_URL)

    bstack_options = {
        "projectName": "Cross-Device RBA",
        "buildName": "Infinite-Loop-Collection",
        "sessionName": f"Batch{batch_num}-Thread{thread_id}",
        "networkLogs": "true",
    }
    options.set_capability("bstack:options", bstack_options)

    print(f"  [批次 {batch_num} | 线程 {thread_id}] 🚀 请求分配: {device_info['deviceName']} ...")
    
    try:
        # 建立连接，触发云端启动
        driver = webdriver.Remote(REMOTE_URL, options=options)
        print(f"  [批次 {batch_num} | 线程 {thread_id}] ✅ 分配成功！探针静默收集数据中 (15s)...")
        
        # 留足时间让探针前端页面加载并完成 POST
        time.sleep(15)
        driver.quit()
        return "SUCCESS"
        
    except Exception as e:
        error_msg = str(e).lower()
        print(f"  [批次 {batch_num} | 线程 {thread_id}] ❌ 运行异常: {e}")
        
        # 核心逻辑：拦截报错信息，判断额度是否耗尽
        if "expired" in error_msg or "exhausted" in error_msg or "upgrade" in error_msg or "limit reached" in error_msg:
            return "QUOTA_EXHAUSTED"
        elif "parallel" in error_msg or "in use" in error_msg:
            return "PARALLEL_LIMIT"
        return "OTHER_ERROR"

def main():
    CONCURRENT_DEVICES = 5  # 每次循环调用的设备数
    batch_num = 1
    
    print("🤖 RBA 无限自动化收割脚本已启动...\n")
    
    while True:
        print(f"{'='*50}")
        print(f"▶️ 开始执行第 {batch_num} 批次测试并发收集...")
        print(f"{'='*50}")
        
        # 每次循环随机抽取 5 个正则特征（使用 random.choices 允许抽到同品牌的不同设备）
        selected_devices = random.choices(DEVICE_POOL, k=CONCURRENT_DEVICES)
        
        quota_exhausted = False
        
        # 开启 5 个并发线程同步请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_DEVICES) as executor:
            futures = []
            for i, device in enumerate(selected_devices):
                futures.append(executor.submit(run_single_device, device, i+1, batch_num))
            
            # 监听这 5 个线程的返回结果
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                # 如果任意一个线程反馈“额度耗尽”，则打上终止标记
                if result == "QUOTA_EXHAUSTED":
                    quota_exhausted = True
        
        # 判定是否需要打破无限循环
        if quota_exhausted:
            print("\n🚨 触发拦截：检测到 BrowserStack 免费额度已完全耗尽！")
            print(f"🏁 脚本安全停止。总计执行了 {batch_num} 个批次的数据抓取。")
            break
            
        print(f"\n⏸️ 第 {batch_num} 批次释放完毕，休眠 3 秒后发起下一波攻击...")
        time.sleep(3)
        batch_num += 1

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ 收到手动中断信号 (Ctrl+C)，脚本已安全停止。")
        sys.exit(0)