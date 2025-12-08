import numpy as np

# === 1. 食材資料：每 1g 食材的營養素（這段用你的實際數值） ===
# 假設三種食材：雞胸肉、雞肝、雞蛋
# 單位：g nutrient / g food
protein_per_g = np.array([0.23, 0.18, 0.12])   # 每 1g 食材提供的蛋白質
fat_per_g     = np.array([0.02, 0.06, 0.10])   # 每 1g 食材提供的脂肪
carb_per_g    = np.array([0.00, 0.01, 0.01])   # 每 1g 食材提供的碳水

# 把它們組成 3xN 的矩陣 A（N = 食材數）
A = np.vstack([protein_per_g, fat_per_g, carb_per_g])   # shape = (3, N)

# === 2. 目標：一天想要達到的「總營養克數」 ===
total_kcal_target = 200  # 例如目標 200 kcal（隨便示範，用你的 MER 比較準）

# 65% 蛋白、22.5% 脂肪、12.5% 碳水 → 各自的 kcal
kcal_prot_target = total_kcal_target * 0.65
kcal_fat_target  = total_kcal_target * 0.225
kcal_carb_target = total_kcal_target * 0.125

# 轉成「目標克數」
prot_g_target = kcal_prot_target / 4.0
fat_g_target  = kcal_fat_target  / 9.0
carb_g_target = kcal_carb_target / 4.0

b = np.array([prot_g_target, fat_g_target, carb_g_target])  # shape = (3,)

print("目標營養（克）：")
print(f"  蛋白質: {prot_g_target:.2f} g")
print(f"  脂肪  : {fat_g_target:.2f} g")
print(f"  碳水  : {carb_g_target:.2f} g")
print()

# ====================================================
# === 3. ★★★ 改成：NNLS（非負最小平方法） ★★★
# ====================================================
### 🔥 UPDATED — 匯入 NNLS 函式
import scipy
from scipy.optimize import nnls

### 🔥 UPDATED — 使用 nnls() 取代 lstsq()
x_nnls, rnorm = nnls(A, b)

print("建議食材克數（NNLS 非負解）：")
for name, grams in zip(["雞胸肉", "雞肝", "雞蛋"], x_nnls):
    print(f"  {name}: {grams:.1f} g")
print()

# === 4. 用 NNLS 解算實際營養 ===
actual_macros = A @ x_nnls
actual_prot, actual_fat, actual_carb = actual_macros

print("實際提供的營養（由 NNLS 解計算）：")
print(f"  蛋白質: {actual_prot:.2f} g")
print(f"  脂肪  : {actual_fat:.2f} g")
print(f"  碳水  : {actual_carb:.2f} g")
print()

# === 5. 把實際營養換算成 kcal → 算比例 ===
actual_kcal_prot = actual_prot * 4.0
actual_kcal_fat  = actual_fat  * 9.0
actual_kcal_carb = actual_carb * 4.0

actual_kcal_total = actual_kcal_prot + actual_kcal_fat + actual_kcal_carb

pct_prot = actual_kcal_prot / actual_kcal_total * 100 if actual_kcal_total > 0 else 0
pct_fat  = actual_kcal_fat  / actual_kcal_total * 100 if actual_kcal_total > 0 else 0
pct_carb = actual_kcal_carb / actual_kcal_total * 100 if actual_kcal_total > 0 else 0

print("✅ 實際熱量比例：")
print(f"  蛋白質: {pct_prot:.1f}%")
print(f"  脂肪  : {pct_fat:.1f}%")
print(f"  碳水  : {pct_carb:.1f}%")
