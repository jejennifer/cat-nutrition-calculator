# --- 0. 套件與資料 ---
import streamlit as st
import pandas as pd
import math
import re

st.set_page_config(page_title="貓咪營養素計算機", layout="wide")

# --- 讀入乾糧與鮮食資料 + 單位清洗 ---
ATWATER = {"protein": 3.5, "fat": 8.5, "carb": 3.5}  # kcal/g

def _num(s: str) -> float:
    """從字串抓第一個數字（小數也可）；抓不到回 NaN"""
    if pd.isna(s):
        return float("nan")
    m = re.search(r"[-+]?\d*\.?\d+", str(s))
    return float(m.group()) if m else float("nan")

def clean_dry(df_raw: pd.DataFrame) -> pd.DataFrame:
    """乾糧資料清洗：如 4025cal/1kg → kcal/g = 4.025"""
    df = df_raw.copy()

    # 先把營養素欄位轉成數字（8.1 或 8.1% 都可）
    for c in ["水分", "蛋白質", "脂肪", "碳水"]:
        df[c] = df[c].apply(_num)

    kcal_per_g = []
    for s in df.get("熱量", []):
        val = _num(s)  # 例如 3179
        if pd.isna(val):
            kcal_per_g.append(float("nan"))
            continue

        # 正規化字串：轉小寫、全形→半形、去空白
        txt = str(s).lower()
        txt = txt.replace("／", "/")  # 全形斜線 → 半形
        txt = txt.replace("（", "(").replace("）", ")")
        txt_nospace = re.sub(r"\s+", "", txt)  # 移除所有空白

        # 更寬鬆的判斷：只要看到 "kg" 就視為每公斤；看到 "100g" 視為每 100g
        if "kg" in txt_nospace:
            denom = 1000.0
        elif "100g" in txt_nospace or "每100g" in txt_nospace or "100公克" in txt_nospace:
            denom = 100.0
        else:
            # 後備判斷：若數值很大（>50），多半是每公斤；否則視為每 100g
            denom = 1000.0 if val > 50 else 100.0

        kcal_per_g.append(val / denom)

    df["kcal_per_g"] = kcal_per_g

    # 若缺熱量，用宏量估算
    mask = df["kcal_per_g"].isna()
    if mask.any():
        kcal_100g = (
            df.loc[mask, "蛋白質"] * ATWATER["protein"]
            + df.loc[mask, "脂肪"] * ATWATER["fat"]
            + df.loc[mask, "碳水"] * ATWATER["carb"]
        )
        df.loc[mask, "kcal_per_g"] = kcal_100g / 100.0

    df["類型"] = df["類型"].fillna("乾糧")
    return df[["食物名稱", "類型", "水分", "蛋白質", "脂肪", "碳水", "kcal_per_g"]]

def clean_fresh(df_raw: pd.DataFrame) -> pd.DataFrame:
    """鮮食資料清洗：如 104cal/100g → kcal/g = 1.04"""
    df = df_raw.copy()
    for c in ["水分", "蛋白質", "脂肪", "碳水"]:
        df[c] = df[c].apply(_num)

    kcal_per_g = []
    for s in df.get("熱量", []):
        val = _num(s)
        if pd.isna(val):
            kcal_per_g.append(float("nan"))
        else:
            txt = str(s).lower()
            if "/100g" in txt:
                kcal_per_g.append(val / 100.0)
            elif "/kg" in txt:
                kcal_per_g.append(val / 1000.0)
            else:
                kcal_per_g.append(val / 100.0)
    df["kcal_per_g"] = kcal_per_g

    # 若缺熱量，用 Atwater 估算
    mask = df["kcal_per_g"].isna()
    if mask.any():
        kcal_100g = (
            df.loc[mask, "蛋白質"] * ATWATER["protein"]
            + df.loc[mask, "脂肪"] * ATWATER["fat"]
            + df.loc[mask, "碳水"] * ATWATER["carb"]
        )
        df.loc[mask, "kcal_per_g"] = kcal_100g / 100.0

    df["類型"] = df["類型"].fillna("生食")
    return df[["食物名稱", "類型", "水分", "蛋白質", "脂肪", "碳水", "kcal_per_g"]]

# --- 匯入兩份資料 ---
dry_path   = "data/food_data_dry_test.csv"
fresh_path = "data/food_data_fresh_test.csv"

df_dry   = clean_dry(pd.read_csv(dry_path))
df_fresh = clean_fresh(pd.read_csv(fresh_path))

df = pd.concat([df_dry, df_fresh], ignore_index=True)
df["水分"] = df["水分"].clip(lower=0.0, upper=99.9)

# --- 主頁 ---
st.title("🐱 貓咪每日熱量 & 鮮食克數計算")

    # ➤ 基本輸入
weight = st.number_input("體重 (kg)", min_value=0.1, step=0.1, value=4.0)
age_group = st.selectbox("年齡層", ["幼貓 0-4月", "幼貓 4-6月", "結紮成貓", "未結紮成貓", "老貓", "減重"])
activity = st.selectbox("活動量", ["低", "中", "高"])

phys_factor_map = {
    "幼貓 0-4月": 3.0,
    "幼貓 4-6月": 2.5,
    "未結紮成貓": 1.5,
    "結紮成貓": 1.3,
    "老貓": 1.0,
    "減重": 0.8,
}
activity_factor_map = {"低": 1.0, "中": 1.2, "高": 1.4}

rer = 70 * (weight ** 0.75)
mer = rer * phys_factor_map[age_group] * activity_factor_map[activity]

min_protein_g = mer / 1000 * 65
min_fat_g = mer / 1000 * 22.5
recommend_protein_g = min_protein_g * 1.15
recommend_fat_g = min_fat_g * 1.15

st.subheader("📊 計算結果")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("RER", f"{rer:.0f} kcal / 天")
    st.metric("MER (建議攝取)", f"{mer:.0f} kcal / 天")
with col2:
    st.write("最低營養素")
    st.write(f"蛋白質 ≥ **{min_protein_g:.1f} g / 天**")
    st.write(f"脂肪 ≥ **{min_fat_g:.1f} g / 天**")
with col3:
    st.write("建議營養素")
    st.write(f"蛋白質 **{recommend_protein_g:.1f} g / 天**")
    st.write(f"脂肪 **{recommend_fat_g:.1f} g / 天**")

# --- 乾糧區 ---
st.markdown("---")
st.subheader("🥣 乾糧熱量扣除")

dry_candidates = df[df["類型"].str.contains("乾", na=False)]
selected_dry = st.multiselect("選擇乾糧（可複選）", dry_candidates["食物名稱"].tolist())

dry_total_kcal = 0.0
dry_rows = []  # 顯示每項 gram / kcal 與宏量(g)

if selected_dry:
    for name in selected_dry:
        row = dry_candidates[dry_candidates["食物名稱"] == name].iloc[0]
        grams = st.number_input(
            f"{name} 每日餵食克數",
            min_value=0.0,
            step=1.0,
            value=0.0,
            key=f"dry_{name}"
        )
        kcal_g = float(row["kcal_per_g"])
        kcal   = grams * kcal_g

        # 以標示百分比換算成「克」：g = % × 克數 / 100
        prot_g = grams * float(row["蛋白質"]) / 100.0
        fat_g  = grams * float(row["脂肪"])   / 100.0
        carb_g = grams * float(row["碳水"])   / 100.0

        dry_total_kcal += kcal
        dry_rows.append({
            "食物名稱": name,
            "kcal/g": round(kcal_g, 3),
            "每日克數(g)": round(grams, 1),
            "提供熱量(kcal)": round(kcal, 1),
            "蛋白(g)": round(prot_g, 1),
            "脂肪(g)": round(fat_g, 1),
            "碳水(g)": round(carb_g, 1),
        })

# 若有選擇，顯示每項與總計
if dry_rows:
    dry_df = pd.DataFrame(dry_rows)
    st.dataframe(dry_df, use_container_width=True)

    # 總計列
    total_row = pd.DataFrame([{
        "食物名稱": "➡️ 合計",
        "kcal/g": "",
        "每日克數(g)": dry_df["每日克數(g)"].sum(),
        "提供熱量(kcal)": dry_df["提供熱量(kcal)"].sum().round(1),
        "蛋白(g)": dry_df["蛋白(g)"].sum().round(1),
        "脂肪(g)": dry_df["脂肪(g)"].sum().round(1),
        "碳水(g)": dry_df["碳水(g)"].sum().round(1),
    }])

    st.dataframe(total_row, use_container_width=True)

st.metric("乾糧提供熱量", f"{dry_total_kcal:.0f} kcal / 天")

remaining_kcal = max(mer - dry_total_kcal, 0.0)
st.metric("⚖️ 鮮食需補熱量", f"{remaining_kcal:.0f} kcal / 天")


# --- 鮮食區 ---
st.markdown("---")
st.subheader("🥗 鮮食配方與克數計算")

# 🔹 先顯示乾糧提供與鮮食需補資訊
if "dry_df" in locals() and not dry_df.empty:
    dry_protein_total = dry_df["蛋白(g)"].sum()
    dry_fat_total = dry_df["脂肪(g)"].sum()
else:
    dry_protein_total = dry_fat_total = 0.0

target_protein = max(recommend_protein_g - dry_protein_total, 0)
target_fat = max(recommend_fat_g - dry_fat_total, 0)

colA, colB = st.columns(2)
with colA:
    st.write(f"乾糧提供蛋白質：**{dry_protein_total:.1f} g** / 脂肪：**{dry_fat_total:.1f} g**")
with colB:
    st.write(f"鮮食需補蛋白質：**{target_protein:.1f} g** / 脂肪：**{target_fat:.1f} g**")

# 再顯示食材選擇
st.markdown("---")
fresh_candidates = df[df["類型"].str.contains("生", na=False)]
selected_fresh = st.multiselect("選擇鮮食食材（可複選）", fresh_candidates["食物名稱"].tolist())

ratio_map = {}
if selected_fresh:
    st.caption("輸入整體配比（例如 1:1:1 或 3:2:1），系統會依比例自動分配食材。")
    ratio_input = st.text_input("輸入比例（以冒號分隔）", value="1:1")

    # 將輸入轉成數字比例清單，例如 "2:1" → [2, 1]
    try:
        ratio_values = [float(x) for x in ratio_input.split(":") if x.strip()]
    except ValueError:
        ratio_values = []

    # 比例數量需與選擇食材數相同
    if selected_fresh and len(ratio_values) != len(selected_fresh):
        st.warning(f"⚠️ 請輸入與食材數量相同的比例（目前選了 {len(selected_fresh)} 種食材）")
        ratio_map = {}
    else:
        ratio_map = dict(zip(selected_fresh, ratio_values))

    sum_ratio = sum(ratio_map.values())

    if sum_ratio > 0:

        # 3️⃣ 根據配比計算每種鮮食食材的平均蛋白與脂肪比例
        mix_protein_pct = 0.0
        mix_fat_pct = 0.0
        for name, r in ratio_map.items():
            frac = r / sum_ratio
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
            mix_protein_pct += frac * float(row["蛋白質"])
            mix_fat_pct += frac * float(row["脂肪"])

        # 4️⃣ 根據鮮食組成估算平均熱量、蛋白、脂肪密度
        mix_kcal_per_g = 0.0
        for name, r in ratio_map.items():
            frac = r / sum_ratio
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
            mix_kcal_per_g += frac * float(row["kcal_per_g"])

        # 以「熱量缺口」為主導估算鮮食總克數
        if mix_kcal_per_g > 0:
            total_fresh_g_kcal = remaining_kcal / mix_kcal_per_g
        else:
            total_fresh_g_kcal = 0

        # 同時計算蛋白/脂肪需求推估的克數（供比較）
        if mix_protein_pct > 0:
            total_fresh_g_protein = target_protein / (mix_protein_pct / 100.0)
        else:
            total_fresh_g_protein = 0

        if mix_fat_pct > 0:
            total_fresh_g_fat = target_fat / (mix_fat_pct / 100.0)
        else:
            total_fresh_g_fat = 0

        # 取三者中「最大值」以確保三種條件都滿足
        total_fresh_g = max(total_fresh_g_kcal, total_fresh_g_protein, total_fresh_g_fat)
        st.metric("🍽️ 鮮食總克數（達成熱量與營養）", f"{total_fresh_g:.0f} g / 天")

        # 5️⃣ 分配到各個食材
        serve_rows = []
        total_prot = total_fat = total_carb = total_kcal = 0.0
        for name, r in ratio_map.items():
            frac = r / sum_ratio
            grams = total_fresh_g * frac
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
            prot_g = grams * float(row["蛋白質"]) / 100.0
            fat_g = grams * float(row["脂肪"]) / 100.0
            carb_g = grams * float(row["碳水"]) / 100.0
            kcal = grams * float(row["kcal_per_g"])
            total_prot += prot_g
            total_fat += fat_g
            total_carb += carb_g
            total_kcal += kcal
            serve_rows.append({
                "食材": name,
                "分配克數(g)": round(grams, 1),
                "蛋白(g)": round(prot_g, 1),
                "脂肪(g)": round(fat_g, 1),
                "碳水(g)": round(carb_g, 1),
                "熱量(kcal)": round(kcal, 1),
            })

        st.dataframe(pd.DataFrame(serve_rows), use_container_width=True)
        st.caption(
            f"鮮食總蛋白質：{total_prot:.1f} g，脂肪：{total_fat:.1f} g，碳水：{total_carb:.1f} g，熱量約 {total_kcal:.0f} kcal。"
        )