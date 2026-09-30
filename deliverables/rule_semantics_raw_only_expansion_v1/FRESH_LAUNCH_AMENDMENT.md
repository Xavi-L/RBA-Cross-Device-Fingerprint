# API36 Activity 启动修订

API36 修订 campaign 的冒烟成功。紧接着第一次 clean_pre 的 `am start` stderr 明确记录：`Activity not started, intent has been delivered to currently running top-most instance.` 该位置在75秒内没有产生新会话，原尝试按计划失败并停止，余下35个位置未执行。其时尚未调用本组任何攻击配置，不能把这次失败算作攻击检出或漏检。

日志支持“未启动新的Activity/采集会话”，不能仅凭现有日志确定Android内部的具体竞态原因。新增本地启动合同：每个位置先 force-stop，再通过 ps 连续两次确认采集App进程不存在；直接启动使用 `am start -S -W`，要求系统执行强制停止及等待启动。旧的会话/runtime_context/独一原始包检查继续保留。进程退出确认失败则停止，不在同一位置反复发起启动。

API36 为此修订单独登记 fresh4 campaign，仍只采尚无完整三轮的四个配置，共37个位置。两项CDP模拟继续使用前一修订的运行时锚点 + 完整clean_post恢复核查。其他环境已完成材料不重采；旧API36失败记录与原35个未执行位置全部保留。该修订发生在任何本轮fit/predict之前。
