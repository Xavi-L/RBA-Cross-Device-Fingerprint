import json
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# =====================================================================
# 阶段 1：数据预处理 (Data Preprocessing)
# =====================================================================
print("阶段 1：正在读取并处理数据...")

# 1. 读取并展平数据
data = []
with open('scored_data.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data.append(json.loads(line))

df = pd.json_normalize(data)

# 2. 提取目标标签 (Label)
y = df['llm_label.risk_score']

# 3. 剔除无用字段和高维复杂文本/哈希
cols_to_drop = [
    'session_id', 'timestamp', 'client_ip', 
    'llm_label.risk_score', 'llm_label.risk_reason',
    'android_native_data.build_fingerprint', 
    'web_data.user_agent',                   
    'web_data.canvas_hash'                   
]
X = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

# 4. 自动区分连续特征和类别特征
categorical_cols = X.select_dtypes(include=['object', 'bool']).columns.tolist()
numeric_cols = X.select_dtypes(include=['float64', 'int64']).columns.tolist()

# 5. 填补缺失值 (Imputation)
X[categorical_cols] = X[categorical_cols].fillna("Unknown").astype(str)
X[numeric_cols] = X[numeric_cols].fillna(X[numeric_cols].median())

# 6. 类别特征独热编码 (One-Hot Encoding)
X = pd.get_dummies(X, columns=categorical_cols, drop_first=False).astype(float)

# 7. 随机划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 8. 连续特征标准化 (Standardization)
scaler = StandardScaler()
X_train[numeric_cols] = scaler.fit_transform(X_train[numeric_cols])
X_test[numeric_cols] = scaler.transform(X_test[numeric_cols])

# 9. 转换为 PyTorch 张量
X_train_tensor = torch.FloatTensor(X_train.values)
y_train_tensor = torch.FloatTensor(y_train.values).view(-1, 1)
X_test_tensor = torch.FloatTensor(X_test.values)
y_test_tensor = torch.FloatTensor(y_test.values).view(-1, 1)

print(f"数据准备完毕！最终特征维度: {X_train_tensor.shape[1]}")


# =====================================================================
# 阶段 2：构建与训练神经网络 (Neural Network Training)
# =====================================================================
print("\n阶段 2：开始初始化并训练神经网络...")

# 1. 定义浅层 MLP 网络结构
class ShallowRiskNet(nn.Module):
    def __init__(self, input_dim):
        super(ShallowRiskNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.3),  # 防止小样本过拟合
            
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(32, 1)  # 输出最终的风险分数
        )

    def forward(self, x):
        return self.network(x)

input_dim = X_train_tensor.shape[1]
model = ShallowRiskNet(input_dim)

# 2. 定义损失函数与优化器
criterion = nn.MSELoss()  # 均方误差
optimizer = optim.Adam(model.parameters(), lr=0.005)

# 3. 开始训练循环
epochs = 150
for epoch in range(epochs):
    model.train()
    
    # 前向传播
    outputs = model(X_train_tensor)
    loss = criterion(outputs, y_train_tensor)
    
    # 反向传播与优化
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    
    # 每 30 轮打印一次进度
    if (epoch + 1) % 30 == 0:
        print(f'Epoch [{epoch+1}/{epochs}], Training Loss: {loss.item():.4f}')


# =====================================================================
# 阶段 3：模型评估 (Model Evaluation)
# =====================================================================
print("\n阶段 3：在未知数据（测试集）上进行评估...")

model.eval()  # 切换到评估模式，关闭 Dropout
with torch.no_grad():
    predictions = model(X_test_tensor)
    
    # 计算平均绝对误差 (MAE)：预测分数和真实分数平均差了多少分
    mae = torch.mean(torch.abs(predictions - y_test_tensor))
    print(f'模型最终测试集 MAE: {mae.item():.2f} 分')
    
    # 直观展示前 5 个测试样本的预测结果
    print("\n[直观对比 - 前 5 个测试样本]")
    for i in range(5):
        pred_val = predictions[i].item()
        true_val = y_test_tensor[i].item()
        print(f"样本 {i+1} -> 预测分数: {pred_val:.1f} | 大模型真实打分: {true_val:.1f}")
        
# =====================================================================
# 阶段 3.5：保存测试集的详细预测结果 (Save Predictions to CSV)
# =====================================================================
print("\n正在将测试集预测结果导出为 CSV 文件...")

# 1. 将 PyTorch 的 Tensor 转换回普通的 Numpy 数组，并展平为一维
true_scores = y_test_tensor.numpy().flatten()
pred_scores = predictions.numpy().flatten()

# 2. 创建一个空的表格 (DataFrame) 来存放结果
results_df = pd.DataFrame()
results_df['True_Score'] = true_scores        # 大模型的真实打分
results_df['Predicted_Score'] = pred_scores   # 神经网络的预测打分

# 3. 增加一列“误差绝对值”，方便你找出预测最离谱的样本
results_df['Absolute_Error'] = np.abs(true_scores - pred_scores)

# 4. （高阶技巧）把测试集的设备特征也拼在一块儿！
# 为了保证行号对齐，需要把原来的 X_test 的索引重置一下
X_test_features = X_test.reset_index(drop=True)
# 横向拼接：左边是分数，右边是这个分数对应的设备特征
final_results_df = pd.concat([results_df, X_test_features], axis=1)

# 5. 按照误差从大到小排序，让你一眼看到模型最容易算错的设备
final_results_df = final_results_df.sort_values(by='Absolute_Error', ascending=False)

# 6. 保存为 CSV 文件
csv_filename = "test_predictions_results.csv"
final_results_df.to_csv(csv_filename, index=False, encoding='utf-8')

print(f"✅ 测试结果已成功保存至: {csv_filename}")
print("💡 建议：你可以用 Excel 打开这个文件，重点分析排在最前面（误差最大）的设备特征。")

# =====================================================================
# 阶段 4：保存训练好的模型 (Model Saving)
# =====================================================================
print("\n阶段 4：正在保存训练好的神经网络模型...")

# 1. 指定保存的文件名（通常以 .pth 或 .pt 结尾）
model_save_path = "shallow_risk_net.pth"

# 2. 获取并保存模型内部的所有权重和偏置参数 (state_dict)
torch.save(model.state_dict(), model_save_path)

print(f"✅ 模型参数已成功保存至: {model_save_path}")

# ================= 重要提示 =================
# 注意：如果你在其他文件里想要加载这个模型，你需要用到你刚才拟合好的 scaler！
# 神经网络的输入必须和训练时的缩放比例一模一样，所以 scaler 也必须保存。
import joblib
scaler_save_path = "feature_scaler.pkl"
joblib.dump(scaler, scaler_save_path)
print(f"✅ 数据归一化器 (Scaler) 已成功保存至: {scaler_save_path}")