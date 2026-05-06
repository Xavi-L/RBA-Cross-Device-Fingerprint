# RBA-Cross-Device-Fingerprint

HybridGuard 是一个面向移动端无感风控的三端融合设备指纹原型系统。项目重点不是提出新的机器学习算法，而是打通 Android Native、WebView 宿主容器、Web 前端运行环境三类原本割裂的指纹源，并在同一会话下完成采集、对齐、跨层语义规则分析和本地轻量评分闭环。

## 项目定位

系统验证的核心问题：

1. 三端设备指纹是否能相互形成呼应，例如 Native 物理屏幕与 Web DPR/逻辑屏幕、Native Build 信息与 Web UA、WebView JSBridge 与 App 宿主真实性。
2. 是否可以利用 LLM 分析不同层 feature 的语义对齐关系，形成规则知识库，避免只靠死板阈值打分。
3. 是否可以把 LLM/规则知识库产生的风险判断能力压缩成端侧轻量评分器，在 App 内完成“采集数据 + 本地评分”。

答辩和论文叙事请突出系统贡献：三端融合采集、会话对齐、跨层语义规则知识库、端侧闭环。随机森林和 MLP 只是轻量评分器的工程选型对比，不是本文算法创新点。

## 目录概览

```text
.
├── android_app/HybridGuard/        # Android App：Native 采集、WebView 容器、JSBridge
├── backend_server/                 # FastAPI 后端：前端探针托管、数据接收、会话合并
├── scoring/                        # 数据扩充、高危样本生成、LLM 批量打分脚本和中间数据
├── training/                       # MLP/随机森林训练、评估图表、Java 端侧推理代码
├── run_browserstack.py             # BrowserStack 云真机采集脚本
├── 毕业论文大纲.md                 # 当前论文大纲，已按系统贡献重写
└── 毕业论文参考模板.docx           # 学校/导师参考模板
```

## 核心数据流

1. Android App 启动并生成 `session_id`。
2. `MainActivity.kt` 采集 Android Native 特征：构建指纹、内存、物理屏幕、电池、传感器、安全配置等。
3. WebView 加载后端托管的 `index.html`，通过 `WebAppInterface.kt` 获取 WebView 宿主特征。
4. 前端探针采集 Web 特征：Navigator、逻辑屏幕、WebGL、Canvas、算力挑战、时区等。
5. FastAPI 后端按 `session_id` 合并异步上报数据，并写入 JSON/JSONL。
6. LLM 根据跨层语义规则知识库输出 `risk_score` 和 `risk_reason`。
7. 训练脚本用带标签数据训练轻量评分器，当前随机森林效果和部署路径更适合端侧。
8. 后续目标是把 `DeviceRiskScorer.java` 集成进 App，实现本地评分闭环。

## 关键文件

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/MainActivity.kt`  
  Android Native 特征采集与上报入口。

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/WebAppInterface.kt`  
  JSBridge 与 WebView 宿主环境特征采集入口。

- `backend_server/index.html`  
  Web 前端探针，采集浏览器/WebView 运行环境、WebGL、Canvas 和算力特征。

- `backend_server/main.py`  
  FastAPI 服务，负责接收、校验、合并、持久化三端数据。

- `backend_server/rba_engine.py`、`scoring/sorting.py`  
  调用本地 LLM 进行风险分析和批量标签生成。

- `scoring/augment_device_data.py`、`scoring/generate_bad_data.py`  
  真实样本扩充和高危样本生成。

- `training/train_randomforest.py`、`training/train_mlp.py`  
  轻量评分器训练与评估。随机森林可通过 `m2cgen` 导出 Java。

- `training/DeviceRiskScorer.java`  
  生成的随机森林 Java 推理代码，目前尚未完整集成到 Android App。

## 当前状态

已完成：

- Android Native / WebView / Web 三端特征采集原型。
- FastAPI 会话合并和本地持久化。
- 真实数据、扩充数据、高危模拟数据构建。
- 本地 LLM 风险标签生成流程。
- MLP 与随机森林轻量评分器训练和对比。
- 论文大纲初稿，重点已调整为系统贡献。

待完成：

- 将随机森林评分模块集成进 App。
- 在端侧补齐训练侧一致的特征顺序、缺失值处理和类别编码。
- 完成三端特征消融实验，验证 Native、WebView、Web 三类特征源的必要性。
- 完成本地评分闭环实验和系统开销评估。

## 实验叙事建议

实验优先顺序建议如下：

1. 三端采集完整性与会话合并成功率。
2. 规则知识库与跨层语义对齐案例分析。
3. 三端特征消融实验。
4. App 本地评分闭环与端侧开销。
5. 轻量评分器工程选型：随机森林 vs MLP。

随机森林优先于神经网络的理由：成本低、响应快、小样本结构化数据更稳定、端侧 Java 部署直接、打分依据更容易解释。不要把它包装成算法创新。

## 运行提示

Python 运行环境使用 Miniconda，环境名为 `cross-device-fingerprint`：

```bash
conda activate cross-device-fingerprint
```

后端本地运行通常在 `backend_server/` 下启动：

```bash
python3 main.py
```

LLM 打分脚本默认依赖本地 LM Studio OpenAI-compatible API，例如 `http://127.0.0.1:1234/v1`。运行前需要确认本地模型服务已启动，并检查脚本中的模型名。

Android App 中存在硬编码 ngrok URL，运行前需要根据当前后端地址修改。`run_browserstack.py` 也包含云真机采集相关配置，公开提交或共享前请先移除账号、密钥和临时 URL。

## Agent Notes

- 先读 `毕业论文大纲.md`，再读代码。当前论文叙事已经明确：系统贡献优先，算法只是工程组件。
- 不要把第二章写成“相关技术介绍”，导师要求删除模板中的该章。
- 后续改 App 时，最危险的是训练侧特征编码和端侧 `double[] input` 顺序不一致。
- 若补实验，优先做三端消融和采集完整性统计，而不是继续堆模型。
- 不要提交真实密钥、BrowserStack 凭证、长期可用 ngrok 地址或原始隐私数据。
