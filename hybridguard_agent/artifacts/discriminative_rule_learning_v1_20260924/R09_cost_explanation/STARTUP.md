# R09 独立入口与运行边界

学习快照始终是 ../R04_freeze_r1，使用其中 dependencies/python/bin/python3.12 加 -B -I -S，在空 cwd 执行本目录脚本。真实本轮已关闭，BENCHMARK_ATTEMPT.json 会阻止在同一输出目录重试，不得删除标记或改旧产物来重跑。

实际执行顺序：原 launch.py verify → driver/benchmark.py synthetic → driver/saved_audit.py（只读旧产物）→ driver/prepare.py 封存协议/清单 → DRIVER_FREEZE_MANIFEST.json → driver/benchmark.py run → reporting/audit_synthetic.py → reporting/finalize.py（只读导出）。具体日志见 checks/；实际模块/解释器/空cwd见 workers/*/STARTUP.json。

驱动的 worker 子命令是本轮编排的固定推理子进程，无拟合接口。模型按原字节 load_model；输入仅接受预先绑定的三个R05外层成员，调用未修改的project_core与predict。没有调用core_view、single_surface_view或TrainQuantiles.fit。学习模块导入拒绝与CPython3.12局部入口监测拒绝拟合，合成反例证明边界。

driver/ 在真实计时前已绑定，reporting/ 后处理源码通过 POSTPROCESS_MANIFEST.json 独立绑定。所有CSV由已保存JSON/JSONL生成；它们不能用于新训练、择优轮次或新性能主张。运行需新授权；本轮材料可只读复核。共享预算必须读原 ledger 与 R09_TIMING_LINK 的非拟合扣账。本目录的任何清单都不授予后续拟合。
