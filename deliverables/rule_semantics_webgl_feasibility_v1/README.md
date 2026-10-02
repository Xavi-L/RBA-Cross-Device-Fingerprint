# WebGL 候选语义与输入可行性核查

已完成固定 378 条开发记录核查。当前没有可直接接入重训的新 GPU 报警条件：Native 全部为 SwiftShader，现有硬件家族关系不适用；桌面后端字符串保持观察用途。同时确认 WebGL2 探针复用 canvas 会造成假阴性。

入口：[完整报告](REPORT.md)、[候选处置表](FEASIBILITY.json)、[七条基线引用](BASELINE.json)、[逐条证据](ROWS.jsonl)、[原始引用复核](VERIFICATION.json)。

本轮没有拟合或模型预测。下一步先修复并版本化 WebGL2 探针，再用模拟器检查合法渲染路径；现有七条模型及原始数据保留。
