# WebGL2 v2 成对路径验证

先读 [报告](REPORT.md)。本目录是单个已知 WebGL 修改配置的本地机制检查，不是模型实验。

## 离线复核

在仓库根目录运行：

```sh
python3 -B -m unittest discover -s deliverables/webgl2_paired_paths_v1 -p test_analysis.py
python3 -B deliverables/webgl2_paired_paths_v1/analyze.py
```

第二条命令从本目录原始 payload 和执行记录重算，并与已保存结果比较；不启动模拟器，
不训练或预测。`--write` 只允许首次创建结果文件，不覆盖既有输出。

## 运行来源

- App：上一轮 `webgl2_probe_revision_v2/runtime/featureapp-v13-local-only.apk`，仅本机端点。
- 探针：`expanded-web-67-v2`。启动前核对 APK 内的共享探针与当前源文件相同。
- AVD：项目已有 `Codex_Webdriver_Raw_API36_1`，只读模式，不改原持久化数据。
- 依赖：已有 `rule_semantics_raw_only_expansion_v1/runtime/tool_node`；本轮无安装升级。
- 攻击定义：`w9-stealth-boundary-webgl-pair-v1`；插件 `webgl.vendor` 的两个固定字符串。
- `attach_probe.mjs` 沿用现有攻击 runner 的 Connection/page adapter，但把启动及接收交给
  `run_pairs.py`，使无插件阶段也使用同一连接、导航路径。没有运行旧的整套攻击 campaign。
- 每条路径一个独立接收目录、一个 uvicorn worker；端口为 8765/9226/5670。

实际执行命令：

```sh
python3 -B deliverables/webgl2_paired_paths_v1/run_pairs.py
```

现存 `STARTED.json` 会阻止重复运行，既有路径也不允许覆盖。如需新实验，应先登记新的
协议与目录，而非删除本轮结果后重跑。原始材料包含普通基线两份、匹配正常/恢复十二份、
受控修改六份，合计二十份；重复轮次不是独立物理设备。

执行记录的 NAVIGATED 只说明命令完成。修改生效由 raw 中的目标值和前后差异判断；
恢复由十二个图形字段和状态共同判断。不可把失败/未知读数当作相等或正常通过。
