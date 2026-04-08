import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ================= 1. 基础设置与中文字体 =================
# 设置清晰的图表风格
sns.set_theme(style="whitegrid")
# 解决 matplotlib 无法显示中文的问题（兼容 Windows 和 Mac）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Songti SC', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False # 解决负号显示为方块的问题

# ================= 2. 读取之前保存的 CSV 数据 =================
try:
    mlp_df = pd.read_csv("test_predictions_results.csv")
    tree_df = pd.read_csv("tree_test_predictions_results.csv")
except FileNotFoundError:
    print("错误：找不到 CSV 文件，请确保它们和此脚本在同一个目录下。")
    exit()

# =========================================================
# 图表 1：真实值 vs 预测值 拟合散点图 (横向对比双子图)
# =========================================================
fig1, axes1 = plt.subplots(1, 2, figsize=(14, 6))

# 设置理想的拟合参考线 (y = x)
min_val = min(mlp_df['True_Score'].min(), mlp_df['Predicted_Score'].min()) - 5
max_val = max(mlp_df['True_Score'].max(), mlp_df['Predicted_Score'].max()) + 5

# 左图：随机森林
sns.scatterplot(data=tree_df, x='True_Score', y='Predicted_Score', 
                alpha=0.7, color='#2ca02c', ax=axes1[0], edgecolor='w', s=60)
axes1[0].plot([min_val, max_val], [min_val, max_val], 'k--', lw=2, label='完美拟合线 (y=x)')
axes1[0].set_title("树模型 (Random Forest) - 拟合效果", fontsize=14, fontweight='bold')
axes1[0].set_xlabel("大模型真实打分 (True Score)", fontsize=12)
axes1[0].set_ylabel("端侧模型预测打分 (Predicted Score)", fontsize=12)
axes1[0].legend()

# 右图：神经网络 MLP
sns.scatterplot(data=mlp_df, x='True_Score', y='Predicted_Score', 
                alpha=0.7, color='#1f77b4', ax=axes1[1], edgecolor='w', s=60)
axes1[1].plot([min_val, max_val], [min_val, max_val], 'k--', lw=2, label='完美拟合线 (y=x)')
axes1[1].set_title("浅层神经网络 (MLP) - 拟合效果", fontsize=14, fontweight='bold')
axes1[1].set_xlabel("大模型真实打分 (True Score)", fontsize=12)
axes1[1].set_ylabel("端侧模型预测打分 (Predicted Score)", fontsize=12)
axes1[1].legend()

# 调整布局并保存
plt.tight_layout()
fig1.savefig("Figure1_Scatter_Fit.png", dpi=300, bbox_inches='tight')
print("✅ 第一张图已保存：Figure1_Scatter_Fit.png")


# =========================================================
# 图表 2：绝对误差 (Absolute Error) 密度分布对比图
# =========================================================
plt.figure(figsize=(10, 6))

# 使用 KDE (核密度估计) 平滑显示误差分布
sns.kdeplot(data=tree_df, x='Absolute_Error', fill=True, 
            color='#2ca02c', label='树模型 (Random Forest)', alpha=0.4, linewidth=2)
sns.kdeplot(data=mlp_df, x='Absolute_Error', fill=True, 
            color='#1f77b4', label='浅层神经网络 (MLP)', alpha=0.4, linewidth=2)

plt.title("模型预测绝对误差分布对比", fontsize=16, fontweight='bold')
plt.xlabel("绝对误差分值 (|真实分 - 预测分|)", fontsize=13)
plt.ylabel("样本密度 (Density)", fontsize=13)
plt.xlim(0, max(tree_df['Absolute_Error'].max(), mlp_df['Absolute_Error'].max()) + 2)
plt.legend(fontsize=12)

# 添加一条垂直的基准线（比如 5 分以内的误差被认为是优秀的）
plt.axvline(x=5, color='red', linestyle=':', lw=2, label='5分误差阈值')

plt.tight_layout()
plt.savefig("Figure2_Error_Distribution.png", dpi=300, bbox_inches='tight')
print("✅ 第二张图已保存：Figure2_Error_Distribution.png")

plt.show() # 如果你在 Pycharm/Jupyter 运行，这会直接弹出窗口展示图表