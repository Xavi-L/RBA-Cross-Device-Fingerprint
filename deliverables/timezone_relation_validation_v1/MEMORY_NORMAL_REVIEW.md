# 上轮内存实验正常分母离线复核

本轮补充流程证据侧表，未覆盖旧报告、模型、原始记录或预测，也未重采内存数据。计划 clean 不能直接进入正常误报分母。pre 要有有效同次观测和无修改正常流程；post 另需对应操作成功、旧 App 进程确已退出、新进程正常采集、值恢复。报警结果不参与正常资格判断。

复核保存的 24 组、72/72 个预定位置。24 组有撤销与恢复支持；48/48 个正常位置满足依据，0 个正常位置依据不足。

核对了每位置的 session、runtime_context、安装标识、原始引用及值，CDP 命令响应和当前运行时值，正常阶段的 void 0 脚本，App 启停命令返回码与进程缺席，以及 pre/post 的 Native 内存、Web 内存和 CPU 值。72 个位置全部留在流向统计中；U/FAILED 不会因筛选正常分母而消失。

确认正常分母中的两条件状态：{"R_REL": {"F": 48}, "R_WEB8": {"F": 48}}。六个保存模型状态分别为：[{"NO_ALERT": 48}, {"NO_ALERT": 48}, {"NO_ALERT": 48}, {"NO_ALERT": 48}, {"NO_ALERT": 48}, {"NO_ALERT": 48}]。本次真实材料中原 0/48 报警结果保持不变，同时修正过去仅按 phase != attack 取正常分母的统计边界。

逐条证据与全部预定位置状态见 MEMORY_NORMAL_REVIEW.json。复现命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m hybridguard_agent.research.normal_collection_evidence
```
