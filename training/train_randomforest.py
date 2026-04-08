import json
import pandas as pd
import numpy as np
import m2cgen as m2c
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor

# =====================================================================
# 阶段 1：数据预处理 (与 MLP 逻辑对齐)
# =====================================================================
print("正在读取跨端设备指纹数据...")
data = []
with open('scored_data.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data.append(json.loads(line))

# 展平嵌套的 Web/WebView/Native 特征
df = pd.json_normalize(data)

# 目标值：大模型给出的风险评分
y = df['llm_label.risk_score']

# 剔除无关字段
cols_to_drop = [
    'session_id', 'timestamp', 'client_ip', 
    'llm_label.risk_score', 'llm_label.risk_reason'
]
X = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

# 树模型全自动特征编码
# 注意：这里我们保留原始特征，只对字符串和布尔值进行 LabelEncoding
encoders = {}
for col in X.columns:
    if X[col].dtype == 'object' or X[col].dtype == 'bool':
        X[col] = X[col].fillna("Unknown").astype(str)
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le
    else:
        X[col] = X[col].fillna(-1)

# =====================================================================
# 阶段 2：随机划分与模型训练
# =====================================================================
# 使用与神经网络脚本相同的随机种子 random_state=42，确保测试集样本一致
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"训练集规模: {len(X_train)} | 测试集规模: {len(X_test)}")

# 训练随机森林
# 适当限制深度以减小生成的 Java 代码体积，防止 Android 端 OOM 或编译过慢
model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
model.fit(X_train, y_train)

# =====================================================================
# 阶段 3：生成 Android 端部署代码 (DeviceRiskScorer.java)
# =====================================================================
print("正在生成 Android 端 Java 部署类...")
java_code = m2c.export_to_java(model, class_name="DeviceRiskScorer")
with open("DeviceRiskScorer.java", "w", encoding="utf-8") as f:
    f.write(java_code)
print("✅ DeviceRiskScorer.java 已生成。")

# =====================================================================
# 阶段 4：执行测试集预测并导出结果表格
# =====================================================================
print("正在评估树模型并导出测试报表...")

# 在 Python 中模拟 Java 逻辑进行预测
pred_scores = model.predict(X_test)

# 构建结果对比表
results_df = pd.DataFrame()
results_df['True_Score'] = y_test.values
results_df['Predicted_Score'] = pred_scores
results_df['Absolute_Error'] = np.abs(results_df['True_Score'] - results_df['Predicted_Score'])

# 拼回原始特征以便分析具体是哪些参数导致了误差
X_test_original_index = X_test.reset_index(drop=True)
final_report = pd.concat([results_df, X_test_original_index], axis=1)

# 按误差从大到小排序，方便论文中分析 Case Study
final_report = final_report.sort_values(by='Absolute_Error', ascending=False)

report_filename = "tree_test_predictions_results.csv"
final_report.to_csv(report_filename, index=False, encoding='utf-8')

print(f"✅ 详细测试结果已保存至: {report_filename}")

# 输出基本评估指标
mae = np.mean(results_df['Absolute_Error'])
print(f"\n树模型平均绝对误差 (MAE): {mae:.2f}")