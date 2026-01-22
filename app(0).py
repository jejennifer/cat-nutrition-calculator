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
dry_path   = "data/food_data_dry_20260122.csv"
fresh_path = "data/food_data_fresh_1115.csv"

df_dry   = clean_dry(pd.read_csv(dry_path)).dropna(subset=["食物名稱"])
df_fresh = clean_fresh(pd.read_csv(fresh_path)).dropna(subset=["食物名稱"])

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

remain_kcal = max(mer - dry_total_kcal, 0.0)

# 兩個重點指標：總克數 & 鮮食提供熱量
col_g, col_kcal = st.columns(2)
with col_g:
    st.metric("🔥乾糧提供熱量", f"{dry_total_kcal:.0f} kcal / 天")
with col_kcal:
    # total_kcal 已在上面彙總；若你想保險，也可用 df_serve["熱量(kcal)"].sum()
    st.metric("⚖️鮮食需補熱量", f"{remain_kcal:.0f} kcal / 天")

# >>> NEW: 先彙總乾糧提供的營養素（g/天）
if dry_rows:
    dry_protein_total = float(dry_df["蛋白(g)"].sum())
    dry_fat_total     = float(dry_df["脂肪(g)"].sum())
    dry_carb_total    = float(dry_df["碳水(g)"].sum())
else:
    dry_protein_total = dry_fat_total = dry_carb_total = 0.0

# >>> NEW: 計算「鮮食需補」的營養素（用整天目標扣掉乾糧）
# 你前面已經有 recommend_protein_g / recommend_fat_g / target_carb_g（或你用的目標變數）
remain_prot = max(recommend_protein_g - dry_protein_total, 0.0)
remain_fat  = max(recommend_fat_g     - dry_fat_total, 0.0)
#remain_carb = max(target_carb_g       - dry_carb_total, 0.0)

# >>> NEW: 顯示鮮食需補的營養素
st.markdown("### 🥩 鮮食需補營養素（扣除乾糧後）")
#c1, c2, c3 = st.columns(3)
c1, c2 = st.columns(2)
with c1:
    st.metric("需補蛋白質", f"{remain_prot:.1f} g / 天")
with c2:
    st.metric("需補脂肪", f"{remain_fat:.1f} g / 天")
# with c3:
#     st.metric("需補碳水", f"{remain_carb:.1f} g / 天")

# --- 食材選擇與自動配比（依 65:22.5:12.5 熱量比例）---
st.markdown("---")

# 乾糧貢獻（如果有選乾糧才會有 dry_df）
if "dry_df" in locals() and not dry_df.empty:
    dry_protein_total = float(dry_df["蛋白(g)"].sum())
    dry_fat_total     = float(dry_df["脂肪(g)"].sum())
    dry_carb_total    = float(dry_df["碳水(g)"].sum())
    dry_kcal_total    = float(dry_df["提供熱量(kcal)"].sum())
else:
    dry_protein_total = dry_fat_total = dry_carb_total = dry_kcal_total = 0.0

# 目標：整天（乾糧＋所有鮮食）要達到的營養量
target_total_kcal = float(mer)
target_protein_g  = float(recommend_protein_g)   # 之前算好的建議蛋白質（含 1.15 安全係數）
target_fat_g      = float(recommend_fat_g)       # 之前算好的建議脂肪
target_carb_g     = target_total_kcal * 0.125 / 4.0  # 12.5% 熱量來自碳水

fresh_candidates = df[df["類型"].str.contains("生", na=False)]
selected_fresh = st.multiselect("選擇鮮食食材（可複選）", fresh_candidates["食物名稱"].tolist())

ratio_map = {}
if selected_fresh:
    st.caption("系統已依 65% 蛋白、22.5% 脂肪、12.5% 碳水 的熱量比例，自動推薦每日鮮食份量。")

    # --- 鮮食需要補的營養缺口（扣掉乾糧） ---
    remain_protein_g = max(target_protein_g - dry_protein_total, 0)
    remain_fat_g     = max(target_fat_g     - dry_fat_total, 0)
    remain_carb_g    = max(target_carb_g    - dry_carb_total, 0)

    # 將「剩餘營養克數」換算成「每 kcal 所需的營養密度（g / kcal）」
    # 用於後續權重計算，讓鮮食配比依據「實際尚未補足的營養缺口」
    if remain_kcal > 0:
        t_prot_per_kcal = remain_protein_g / remain_kcal
        t_fat_per_kcal  = remain_fat_g     / remain_kcal
        t_carb_per_kcal = remain_carb_g    / remain_kcal
    else:
        # 避免除以 0，若無剩餘熱量則設為 0
        t_prot_per_kcal = t_fat_per_kcal = t_carb_per_kcal = 0.0

    # 距離越接近目標宏量比例 → 權重越高
    weights = []
    for name in selected_fresh:
        row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
        kcal_g = float(row["kcal_per_g"]) if not pd.isna(row["kcal_per_g"]) else 0.0
        if kcal_g <= 0:
            w = 1e-6
        else:
            ppk = (float(row["蛋白質"]) / 100.0) / kcal_g
            fpk = (float(row["脂肪"]) / 100.0) / kcal_g
            cpk = (float(row["碳水"]) / 100.0) / kcal_g
            d = math.sqrt(
                (ppk - t_prot_per_kcal)**2 +
                (fpk - t_fat_per_kcal)**2 +
                (cpk - t_carb_per_kcal)**2
            )
            w = 1.0 / (d + 1e-6)
        weights.append((name, w))

    # 轉成比例 map
    sumw = sum(w for _, w in weights)
    ratio_map = {name: (w if sumw > 0 else 1.0) for name, w in weights}
    sum_ratio = sum(ratio_map.values())

    # 🧮 根據熱量缺口計算建議總克數與每項食材克數
    if "remain_kcal" in locals():
        mix_kcal_per_g = 0.0
        for name, r in ratio_map.items():
            frac = r / sum_ratio
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
            mix_kcal_per_g += frac * float(row["kcal_per_g"])

        total_fresh_g = remain_kcal / mix_kcal_per_g if mix_kcal_per_g > 0 else 0

        serve_rows = []
        total_prot = total_fat = total_carb = total_kcal = 0.0

        for name, r in ratio_map.items():
            frac = r / sum_ratio
            grams = total_fresh_g * frac
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]

            prot_g = grams * float(row["蛋白質"]) / 100.0
            fat_g  = grams * float(row["脂肪"])   / 100.0
            carb_g = grams * float(row["碳水"])   / 100.0
            kcal   = grams * float(row["kcal_per_g"])

            total_prot += prot_g
            total_fat += fat_g
            total_carb += carb_g
            total_kcal += kcal

            serve_rows.append({
                "食材": name,
                "建議克數(g)": round(grams, 1),
                "蛋白(g)": round(prot_g, 1),
                "脂肪(g)": round(fat_g, 1),
                "碳水(g)": round(carb_g, 1),
                "熱量(kcal)": round(kcal, 1),
            })

        df_serve = pd.DataFrame(serve_rows)
        st.dataframe(df_serve, use_container_width=True)

        # 🔹 顯示整份鮮食的營養比例
        if total_kcal > 0:
            prot_pct = (total_prot * 4 / total_kcal) * 100
            fat_pct  = (total_fat * 9 / total_kcal) * 100
            carb_pct = (total_carb * 4 / total_kcal) * 100
            st.caption(
                f"整體鮮食營養比例：蛋白質 {prot_pct:.1f}%、脂肪 {fat_pct:.1f}%、碳水 {carb_pct:.1f}%"
            )

        # 兩個重點指標：總克數 & 鮮食提供熱量
        col_g, col_kcal = st.columns(2)
        with col_g:
            st.metric("🍽️ 鮮食總克數（達成熱量與營養）", f"{total_fresh_g:.0f} g / 天")
        with col_kcal:
            # total_kcal 已在上面彙總；若你想保險，也可用 df_serve["熱量(kcal)"].sum()
            st.metric("🔥 鮮食提供熱量", f"{total_kcal:.0f} kcal / 天")

# --- 固定克數模式（使用者輸入多種食材克數 → 補足某一食材） ---
st.markdown("---")
st.subheader("🥚 固定克數模式：輸入已有食材克數，系統幫你算補足量")

st.caption("選擇任意多種鮮食食材，輸入你手邊的克數，並選擇要用哪個補足剩餘營養與熱量。")

fixed_candidates = df[df["類型"].str.contains("生", na=False)]
selected_fixed = st.multiselect(
    "選擇已有克數的食材（可複選）",
    fixed_candidates["食物名稱"].tolist(),
    key="fixed_sel"
)

fixed_input = {}
if selected_fixed:
    st.write("### 🥩 輸入手邊食材克數")
    for name in selected_fixed:
        grams = st.number_input(
            f"{name}（g）",
            min_value=0.0,
            step=1.0,
            value=0.0,
            key=f"fixed_{name}"
        )
        fixed_input[name] = grams

    # 👉 計算固定食材提供的營養與熱量
    fixed_total_prot = fixed_total_fat = fixed_total_carb = fixed_total_kcal = 0.0

    for name, grams in fixed_input.items():
        row = fixed_candidates[fixed_candidates["食物名稱"] == name].iloc[0]

        prot_g = grams * float(row["蛋白質"]) / 100.0
        fat_g  = grams * float(row["脂肪"])   / 100.0
        carb_g = grams * float(row["碳水"])   / 100.0
        kcal   = grams * float(row["kcal_per_g"])

        fixed_total_prot += prot_g
        fixed_total_fat  += fat_g
        fixed_total_carb += carb_g
        fixed_total_kcal += kcal

    st.write("### 📘 固定食材提供的營養：",f"蛋白質**{fixed_total_prot:.1f} g**",f"、脂肪**{fixed_total_fat:.1f} g**",f"、碳水**{fixed_total_carb:.1f} g**",f"、熱量**{fixed_total_kcal:.1f} kcal**")

    # 👉 計算剩餘需求（扣除乾糧 + 固定食材）
    remain_kcal = max(mer - dry_total_kcal - fixed_total_kcal, 0)
    remain_prot = max(recommend_protein_g - dry_protein_total - fixed_total_prot, 0)
    remain_fat  = max(recommend_fat_g     - dry_fat_total     - fixed_total_fat , 0)
    remain_carb  = max(target_carb_g     - dry_carb_total     - fixed_total_carb , 0)

    st.write("### ⚖️ 仍需補足的每日營養")
    colR1, colR2, colR3, colR4 = st.columns(4)
    with colR1:
        st.metric("需補熱量", f"{remain_kcal:.0f} kcal/天")
    with colR2:
        st.metric("需補蛋白質", f"{remain_prot:.1f} g/天")
    with colR3:
        st.metric("需補脂肪", f"{remain_fat:.1f} g/天")
    with colR4:
        st.metric("需補碳水", f"{remain_carb:.1f} g/天")
    
    # --- 找出需要自動計算的食材（使用者未輸入克數者） ---
    auto_items = [name for name, g in fixed_input.items() if g == 0]

    if auto_items and remain_kcal > 0:

        st.write("### 🧮 自動計算補足食材（依 65/22.5/12.5 營養比例）")

        #目標能量比例下的 g/kcal（缺口專用）
        t_prot_per_kcal = remain_prot / remain_kcal if remain_kcal > 0 else 0
        t_fat_per_kcal  = remain_fat  / remain_kcal if remain_kcal > 0 else 0
        t_carb_per_kcal = remain_carb  / remain_kcal if remain_kcal > 0 else 0

        # --- 計算每個食材與缺口營養差距 → 權重 ---
        weights = []
        for name in auto_items:
            row = fixed_candidates[fixed_candidates["食物名稱"] == name].iloc[0]
            kcal_g = float(row["kcal_per_g"])

            if kcal_g <= 0:
                w = 1e-6
            else:
                ppk = (float(row["蛋白質"]) / 100) / kcal_g
                fpk = (float(row["脂肪"]) / 100)   / kcal_g
                cpk = (float(row["碳水"]) / 100)   / kcal_g

                d = math.sqrt(
                    (ppk - t_prot_per_kcal)**2 +
                    (fpk - t_fat_per_kcal)**2 +
                    (cpk - t_carb_per_kcal)**2
                )
                w = 1 / (d + 1e-6)
            weights.append((name, w))

        sum_w = sum(w for _, w in weights) or 1

        # --- 分配剩餘熱量給 auto items ---
        auto_rows = []
        total_auto_prot = total_auto_fat = total_auto_carb = total_auto_kcal = 0.0

        for name, w in weights:
            share = w / sum_w
            kcal_i = remain_kcal * share

            row = fixed_candidates[fixed_candidates["食物名稱"] == name].iloc[0]
            kcal_g = float(row["kcal_per_g"])

            grams_i = kcal_i / kcal_g if kcal_g > 0 else 0

            prot_i = grams_i * float(row["蛋白質"]) / 100
            fat_i  = grams_i * float(row["脂肪"])   / 100
            carb_i  = grams_i * float(row["碳水"])   / 100
            kcal_i = grams_i * kcal_g

            total_auto_prot += prot_i
            total_auto_fat  += fat_i
            total_auto_carb += carb_i
            total_auto_kcal += kcal_i

            auto_rows.append({
                "食材": name,
                "建議補足克數(g)": round(grams_i, 1),
                "蛋白(g)": round(prot_i, 1),
                "脂肪(g)": round(fat_i, 1),
                "碳水(g)": round(carb_i, 1),
                "熱量(kcal)": round(kcal_i, 1),
            })

        st.dataframe(pd.DataFrame(auto_rows), use_container_width=True)

        # --- 最終整體營養 ---
        final_prot = fixed_total_prot + total_auto_prot + dry_protein_total
        final_fat  = fixed_total_fat + total_auto_fat + dry_fat_total
        final_carb  = fixed_total_carb + total_auto_carb + dry_carb_total
        final_kcal = fixed_total_kcal + total_auto_kcal + dry_total_kcal

        # --- 🔢 最終營養比例（含乾糧 + 所有鮮食） ---
        total_kcal_all = final_kcal

        if total_kcal_all > 0:
            prot_pct = (final_prot * 4 / total_kcal_all) * 100
            fat_pct  = (final_fat  * 9 / total_kcal_all) * 100
            carb_pct = (final_carb * 4 / total_kcal_all) * 100
        else:
            prot_pct = fat_pct = carb_pct = 0

        st.write("### 最終每日營養：",f"蛋白質**{final_prot:.1f} g**",f"、脂肪**{final_fat:.1f} g**",f"、碳水**{final_carb:.1f} g**",f"、熱量**{final_kcal:.1f} kcal**")
        st.write(
            f"##### (最終營養比例"
            f"：蛋白質 **{prot_pct:.1f}%**、脂肪 **{fat_pct:.1f}%**、碳水 **{carb_pct:.1f}%**)"
        )

        # --- 多天備餐模式 ---
        st.markdown("---")
        auto_df = pd.DataFrame(auto_rows)

        # 使用者輸入要準備幾天的鮮食 → 計算總備餐克數
        st.markdown("### 📦 備餐模式：一次準備多天（依自動計算補足表）")

        # 輸入要準備幾隻貓
        prep_cats = st.number_input(
            "你要準備幾隻貓的鮮食？",
            min_value=1,
            step=1,
            value=1,
            key="prep_cats"
        )

        # 輸入要準備幾天
        prep_days = st.number_input(
            "你要準備幾天的鮮食？",
            min_value=1,
            step=1,
            value=1,
            key="prep_days"
        )

        # 固定食材 + 自動補足食材 合併成「總備餐清單」
        fixed_list = []
        for name, grams in fixed_input.items():
            if grams > 0:
                fixed_list.append({"食材": name, "每日克數(g)": float(grams)})

        fixed_df = pd.DataFrame(fixed_list) if fixed_list else pd.DataFrame(columns=["食材", "每日克數(g)"])
        auto_daily_df = auto_df.rename(columns={"建議補足克數(g)": "每日克數(g)"})[["食材", "每日克數(g)"]]

        all_daily_df = pd.concat([fixed_df, auto_daily_df], ignore_index=True)

        # 同名食材合併（以防同一食材同時在固定與補足裡）
        all_daily_df = all_daily_df.groupby("食材", as_index=False)["每日克數(g)"].sum()

        all_prep_df = all_daily_df.copy()
        all_prep_df["總克數(g)"] = (
            all_prep_df["每日克數(g)"] * prep_days * prep_cats
        ).round(1)

        st.markdown(f"### 🧾 全部食材總備餐清單（{prep_cats} 隻貓 × {prep_days} 天）")
        st.dataframe(all_prep_df, use_container_width=True)