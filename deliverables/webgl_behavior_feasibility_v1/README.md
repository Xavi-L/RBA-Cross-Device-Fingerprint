# WebGL 行为一致性可行性 v1

[报告](REPORT.md) 区分两个结果：参数等价性单项在四组成对记录中得到本地支持；
两个检查的组合仍有正常 UNKNOWN，原整体验收保持 NOT_ESTABLISHED。
未训练模型或新增注册规则。

```sh
python3 -B deliverables/webgl_behavior_feasibility_v1/analyze.py
python3 -B deliverables/webgl_behavior_feasibility_v1/diagnose.py
python3 -B -m unittest discover -s deliverables/webgl_behavior_feasibility_v1 -p test_classify.py -v
```

前两个命令只读保存材料并核对结果，不启动模拟器、不访问网络、不训练。
`--write` 只重建本目录分析结果；不能改变冻结的协议或判定器。

十二份 App 原始数据与十二份额外行为记录通过会话绑定；额外行为记录不属于正式 177 字段。
`run_pairs.py` 已执行完成，启动标记阻止重复执行。修改方案需另存新协议和新目录，保留本轮所有结果。
