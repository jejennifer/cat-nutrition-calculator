# app.py
# --- 0. 套件與資料 ---
import streamlit as st
import pandas as pd
import math
import re

import numpy as np
from scipy.optimize import nnls

st.set_page_config(page_title="貓咪營養素計算機", layout="wide")

# =========================================================
# 0) 共用設定
# =========================================================
# ✅ CHANGED: 用 4/9/4 做「營養比例」計算（你已經改成這個）
KCAL_PER_G_PROT = 4.0
KCAL_PER_G_FAT  = 9.0
KCAL_PER_G_CARB = 4.0

TARGET_RATIO = {"protein": 0.65, "fat": 0.225, "carb": 0.125}

ATWATER_FALLBACK = {"protein": 4.0, "fat": 9.0, "carb": 4.0}  # 只用來「熱量缺漏」的估算

# =========================================================
# 1) 資料清洗
# =========================================================
def _num(s: str) -> float:
    """從字串抓第一個數字（小數也可）；抓不到回 NaN"""
    if pd.isna(s):
        return float("nan")
    m = re.search(r"[-+]?\d*\.?\d+", str(s))
    return float(m.group()) if m else float("nan")

def clean_dry(df_raw: pd.DataFrame) -> pd.DataFrame:
    """乾糧資料清洗：如 4025cal/1kg → kcal/g = 4.025"""
    df = df_raw.copy()

    for c in ["水分", "蛋白質", "脂肪", "碳水"]:
        df[c] = df[c].apply(_num)

    kcal_per_g = []
    for s in df.get("熱量", []):
        val = _num(s)
        if pd.isna(val):
            kcal_per_g.append(float("nan"))
            continue

        txt = str(s).lower()
        txt = txt.replace("／", "/").replace("（", "(").replace("）", ")")
        txt_nospace = re.sub(r"\s+", "", txt)

        if "kg" in txt_nospace:
            denom = 1000.0
        elif "100g" in txt_nospace or "每100g" in txt_nospace or "100公克" in txt_nospace:
            denom = 100.0
        else:
            denom = 1000.0 if val > 50 else 100.0

        kcal_per_g.append(val / denom)

    df["kcal_per_g"] = kcal_per_g

    mask = df["kcal_per_g"].isna()
    if mask.any():
        kcal_100g = (
            df.loc[mask, "蛋白質"] * ATWATER_FALLBACK["protein"]
            + df.loc[mask, "脂肪"] * ATWATER_FALLBACK["fat"]
            + df.loc[mask, "碳水"] * ATWATER_FALLBACK["carb"]
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
            txt = str(s).lower().replace("／", "/")
            if "/100g" in txt or "每100g" in txt:
                kcal_per_g.append(val / 100.0)
            elif "/kg" in txt:
                kcal_per_g.append(val / 1000.0)
            else:
                kcal_per_g.append(val / 100.0)
    df["kcal_per_g"] = kcal_per_g

    mask = df["kcal_per_g"].isna()
    if mask.any():
        kcal_100g = (
            df.loc[mask, "蛋白質"] * ATWATER_FALLBACK["protein"]
            + df.loc[mask, "脂肪"] * ATWATER_FALLBACK["fat"]
            + df.loc[mask, "碳水"] * ATWATER_FALLBACK["carb"]
        )
        df.loc[mask, "kcal_per_g"] = kcal_100g / 100.0

    df["類型"] = df["類型"].fillna("生食")
    return df[["食物名稱", "類型", "水分", "蛋白質", "脂肪", "碳水", "kcal_per_g"]]

# =========================================================
# 2) 載入資料
# =========================================================
dry_path   = "data/food_data_dry_20260122.csv"
fresh_path = "data/food_data_fresh_1115.csv"

df_dry   = clean_dry(pd.read_csv(dry_path)).dropna(subset=["食物名稱"])
df_fresh = clean_fresh(pd.read_csv(fresh_path)).dropna(subset=["食物名稱"])

df = pd.concat([df_dry, df_fresh], ignore_index=True)
df["水分"] = df["水分"].clip(lower=0.0, upper=99.9)

# =========================================================
# 3) 共用計算工具
# =========================================================
def food_macros_from_grams(row: pd.Series, grams: float):
    """回傳 (prot_g, fat_g, carb_g, kcal_from_label, kcal_from_macros)"""
    prot_g = grams * float(row["蛋白質"]) / 100.0
    fat_g  = grams * float(row["脂肪"])   / 100.0
    carb_g = grams * float(row["碳水"])   / 100.0

    kcal_label = grams * float(row["kcal_per_g"]) if not pd.isna(row["kcal_per_g"]) else 0.0
    kcal_macro = prot_g * KCAL_PER_G_PROT + fat_g * KCAL_PER_G_FAT + carb_g * KCAL_PER_G_CARB
    return prot_g, fat_g, carb_g, kcal_label, kcal_macro

def macro_targets_from_mer(mer_kcal: float):
    """依 65/22.5/12.5 熱量比例，把 MER 轉成目標宏量克數"""
    tgt_prot_g = mer_kcal * TARGET_RATIO["protein"] / KCAL_PER_G_PROT
    tgt_fat_g  = mer_kcal * TARGET_RATIO["fat"]     / KCAL_PER_G_FAT
    tgt_carb_g = mer_kcal * TARGET_RATIO["carb"]    / KCAL_PER_G_CARB
    return tgt_prot_g, tgt_fat_g, tgt_carb_g

def nnls_solve_grams(candidates_df: pd.DataFrame, names: list[str], b_macros: np.ndarray):
    """
    用 NNLS 解 grams >= 0，使 A*grams ~= b
    A 是 (3,N)：每 1g 食材提供的 (prot,fat,carb) 克
    b 是 (3,)：需要補的 (prot,fat,carb) 克
    """
    A_cols = []
    valid = []
    for name in names:
        rows = candidates_df[candidates_df["食物名稱"] == name]
        if rows.empty:
            continue
        r = rows.iloc[0]
        A_cols.append([
            float(r["蛋白質"]) / 100.0,
            float(r["脂肪"])   / 100.0,
            float(r["碳水"])   / 100.0,
        ])
        valid.append(name)

    if len(A_cols) == 0:
        return {}, "A 矩陣為空（沒有可用食材）"

    A = np.array(A_cols, dtype=float).T  # (3,N)
    x, _ = nnls(A, b_macros.astype(float))
    grams_map = {name: float(g) for name, g in zip(valid, x)}
    return grams_map, None

# =========================================================
# 4) UI：基本資訊
# =========================================================
st.title("🐱 貓咪每日熱量 & 鮮食克數計算（NNLS 版）")

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

# 目標宏量（整天）
target_prot_g, target_fat_g, target_carb_g = macro_targets_from_mer(mer)

st.subheader("📊 計算結果")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("RER", f"{rer:.0f} kcal / 天")
    st.metric("MER (建議攝取)", f"{mer:.0f} kcal / 天")
with c2:
    st.write("目標營養（依 65/22.5/12.5）")
    st.write(f"蛋白質：**{target_prot_g:.1f} g/天**")
    st.write(f"脂肪：**{target_fat_g:.1f} g/天**")
    st.write(f"碳水：**{target_carb_g:.1f} g/天**")
with c3:
    st.write("目標比例（熱量）")
    st.write("蛋白 65% / 脂肪 22.5% / 碳水 12.5%")

# =========================================================
# 5) 乾糧區
# =========================================================
st.markdown("---")
st.subheader("🥣 乾糧熱量扣除")

dry_candidates = df[df["類型"].str.contains("乾", na=False)]
selected_dry = st.multiselect("選擇乾糧（可複選）", dry_candidates["食物名稱"].tolist())

dry_rows = []
dry_protein_total = dry_fat_total = dry_carb_total = 0.0
dry_kcal_label_total = 0.0
dry_kcal_macro_total = 0.0

if selected_dry:
    for name in selected_dry:
        row = dry_candidates[dry_candidates["食物名稱"] == name].iloc[0]
        grams = st.number_input(
            f"{name} 每日餵食克數",
            min_value=0.0,
            step=1.0,
            value=0.0,
            key=f"dry_{name}",
        )
        prot_g, fat_g, carb_g, kcal_label, kcal_macro = food_macros_from_grams(row, grams)

        dry_protein_total += prot_g
        dry_fat_total     += fat_g
        dry_carb_total    += carb_g
        dry_kcal_label_total += kcal_label
        dry_kcal_macro_total += kcal_macro

        dry_rows.append({
            "食物名稱": name,
            "每日克數(g)": round(grams, 1),
            "蛋白(g)": round(prot_g, 1),
            "脂肪(g)": round(fat_g, 1),
            "碳水(g)": round(carb_g, 1),
            "熱量kcal(標示)": round(kcal_label, 1),
            "熱量kcal(宏量)": round(kcal_macro, 1),
        })

if dry_rows:
    dry_df = pd.DataFrame(dry_rows)
    st.dataframe(dry_df, use_container_width=True)

    total_row = pd.DataFrame([{
        "食物名稱": "➡️ 合計",
        "每日克數(g)": dry_df["每日克數(g)"].sum(),
        "蛋白(g)": dry_df["蛋白(g)"].sum(),
        "脂肪(g)": dry_df["脂肪(g)"].sum(),
        "碳水(g)": dry_df["碳水(g)"].sum(),
        "熱量kcal(標示)": dry_df["熱量kcal(標示)"].sum(),
        "熱量kcal(宏量)": dry_df["熱量kcal(宏量)"].sum(),
    }])
    st.dataframe(total_row, use_container_width=True)

# 乾糧提供熱量（保留你原本「熱量」概念：用標示熱量來做剩餘熱量顯示）
remain_kcal = max(mer - dry_kcal_label_total, 0.0)

colA, colB = st.columns(2)
with colA:
    st.metric("🔥 乾糧提供熱量(標示)", f"{dry_kcal_label_total:.0f} kcal/天")
with colB:
    st.metric("⚖️ 鮮食需補熱量(參考)", f"{remain_kcal:.0f} kcal/天")

# ✅ CHANGED: 顯示「扣除乾糧後」鮮食需補的宏量缺口（g/天）
remain_prot_g = max(target_prot_g - dry_protein_total, 0.0)
remain_fat_g  = max(target_fat_g  - dry_fat_total, 0.0)
remain_carb_g = max(target_carb_g - dry_carb_total, 0.0)

st.markdown("### 🥩 鮮食需補營養素（扣除乾糧後）")
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("需補蛋白質", f"{remain_prot_g:.1f} g/天")
with m2:
    st.metric("需補脂肪", f"{remain_fat_g:.1f} g/天")
with m3:
    st.metric("需補碳水", f"{remain_carb_g:.1f} g/天")

# =========================================================
# 6) 鮮食自動配比（NNLS）
# =========================================================
st.markdown("---")
st.subheader("🍖 鮮食自動配比（NNLS：讓宏量缺口最小）")

fresh_candidates = df[df["類型"].str.contains("生", na=False)]
selected_fresh = st.multiselect("選擇鮮食食材（可複選）", fresh_candidates["食物名稱"].tolist(), key="fresh_auto")

fresh_grams_map = {}
fresh_total_prot = fresh_total_fat = fresh_total_carb = 0.0
fresh_kcal_label_total = 0.0
fresh_kcal_macro_total = 0.0

if selected_fresh:
    st.caption("NNLS 會直接用你『需要補的蛋白/脂肪/碳水克數』去解各食材的克數（皆為非負）。")

    b = np.array([remain_prot_g, remain_fat_g, remain_carb_g], dtype=float)

    fresh_grams_map, err = nnls_solve_grams(fresh_candidates, selected_fresh, b)
    if err:
        st.error(err)
    else:
        serve_rows = []
        for name in selected_fresh:
            grams = fresh_grams_map.get(name, 0.0)
            row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
            prot_g, fat_g, carb_g, kcal_label, kcal_macro = food_macros_from_grams(row, grams)

            fresh_total_prot += prot_g
            fresh_total_fat  += fat_g
            fresh_total_carb += carb_g
            fresh_kcal_label_total += kcal_label
            fresh_kcal_macro_total += kcal_macro

            serve_rows.append({
                "食材": name,
                "建議克數(g)": round(grams, 1),
                "蛋白(g)": round(prot_g, 1),
                "脂肪(g)": round(fat_g, 1),
                "碳水(g)": round(carb_g, 1),
                "熱量kcal(標示)": round(kcal_label, 1),
                "熱量kcal(宏量)": round(kcal_macro, 1),
            })

        df_serve = pd.DataFrame(serve_rows)
        st.dataframe(df_serve, use_container_width=True)

        # 鮮食比例（用宏量熱量算，避免出現 >100%）
        fresh_kcal_total_for_ratio = fresh_total_prot * KCAL_PER_G_PROT + fresh_total_fat * KCAL_PER_G_FAT + fresh_total_carb * KCAL_PER_G_CARB
        if fresh_kcal_total_for_ratio > 0:
            prot_pct = fresh_total_prot * KCAL_PER_G_PROT / fresh_kcal_total_for_ratio * 100
            fat_pct  = fresh_total_fat  * KCAL_PER_G_FAT  / fresh_kcal_total_for_ratio * 100
            carb_pct = fresh_total_carb * KCAL_PER_G_CARB / fresh_kcal_total_for_ratio * 100
        else:
            prot_pct = fat_pct = carb_pct = 0.0

        st.caption(f"整體鮮食營養比例（以宏量熱量算）：蛋白 {prot_pct:.1f}%、脂肪 {fat_pct:.1f}%、碳水 {carb_pct:.1f}%")

        cG, cK = st.columns(2)
        with cG:
            st.metric("🍽️ 鮮食總克數", f"{sum(fresh_grams_map.values()):.0f} g/天")
        with cK:
            st.metric("🔥 鮮食熱量(宏量)", f"{fresh_kcal_macro_total:.0f} kcal/天")

# =========================================================
# 7) 固定克數模式（先扣固定，再 NNLS 解剩下要補的）
# =========================================================
st.markdown("---")
st.subheader("🥚 固定克數模式：你輸入手邊克數，其餘用 NNLS 補足")

fixed_candidates = fresh_candidates
selected_fixed = st.multiselect(
    "選擇已經有/想固定克數的食材（可複選）",
    fixed_candidates["食物名稱"].tolist(),
    key="fixed_sel"
)

fixed_input = {}
if selected_fixed:
    st.write("### 🥩 輸入手邊固定食材克數（g/天）")
    for name in selected_fixed:
        fixed_input[name] = st.number_input(
            f"{name}（g）",
            min_value=0.0,
            step=1.0,
            value=0.0,
            key=f"fixed_{name}"
        )

    # 固定食材的總宏量
    fixed_total_prot = fixed_total_fat = fixed_total_carb = 0.0
    fixed_kcal_macro_total = 0.0

    for name, grams in fixed_input.items():
        row = fixed_candidates[fixed_candidates["食物名稱"] == name].iloc[0]
        prot_g, fat_g, carb_g, _, kcal_macro = food_macros_from_grams(row, grams)
        fixed_total_prot += prot_g
        fixed_total_fat  += fat_g
        fixed_total_carb += carb_g
        fixed_kcal_macro_total += kcal_macro

    st.write(
        "### 📘 固定食材提供："
        f"蛋白 **{fixed_total_prot:.1f} g**、"
        f"脂肪 **{fixed_total_fat:.1f} g**、"
        f"碳水 **{fixed_total_carb:.1f} g**、"
        f"熱量(宏量) **{fixed_kcal_macro_total:.0f} kcal**"
    )

    # ✅ CHANGED: 固定模式的缺口 = 目標 - 乾糧 - 固定食材
    remain_prot2 = max(target_prot_g - dry_protein_total - fixed_total_prot, 0.0)
    remain_fat2  = max(target_fat_g  - dry_fat_total     - fixed_total_fat , 0.0)
    remain_carb2 = max(target_carb_g - dry_carb_total    - fixed_total_carb, 0.0)

    st.write("### ⚖️ 仍需補足（由自動補足食材提供）")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.metric("需補蛋白質", f"{remain_prot2:.1f} g/天")
    with r2:
        st.metric("需補脂肪", f"{remain_fat2:.1f} g/天")
    with r3:
        st.metric("需補碳水", f"{remain_carb2:.1f} g/天")

    # 自動補足食材：使用者輸入為 0 的那些（你原本的概念）
    auto_items = [name for name, g in fixed_input.items() if g == 0]

    auto_rows = []
    total_auto_prot = total_auto_fat = total_auto_carb = 0.0
    total_auto_kcal_macro = 0.0

    if auto_items and (remain_prot2 + remain_fat2 + remain_carb2) > 0:
        st.write("### 🧮 自動補足食材（NNLS）")

        b2 = np.array([remain_prot2, remain_fat2, remain_carb2], dtype=float)
        auto_grams_map, err = nnls_solve_grams(fixed_candidates, auto_items, b2)

        if err:
            st.error(err)
        else:
            for name in auto_items:
                grams = auto_grams_map.get(name, 0.0)
                row = fixed_candidates[fixed_candidates["食物名稱"] == name].iloc[0]
                prot_g, fat_g, carb_g, _, kcal_macro = food_macros_from_grams(row, grams)

                total_auto_prot += prot_g
                total_auto_fat  += fat_g
                total_auto_carb += carb_g
                total_auto_kcal_macro += kcal_macro

                auto_rows.append({
                    "食材": name,
                    "建議補足克數(g)": round(grams, 1),
                    "蛋白(g)": round(prot_g, 1),
                    "脂肪(g)": round(fat_g, 1),
                    "碳水(g)": round(carb_g, 1),
                    "熱量kcal(宏量)": round(kcal_macro, 1),
                })

            st.dataframe(pd.DataFrame(auto_rows), use_container_width=True)

            # 最終合併：乾糧 + 固定 + 自動
            final_prot = dry_protein_total + fixed_total_prot + total_auto_prot
            final_fat  = dry_fat_total     + fixed_total_fat  + total_auto_fat
            final_carb = dry_carb_total    + fixed_total_carb + total_auto_carb

            final_kcal_total = final_prot*KCAL_PER_G_PROT + final_fat*KCAL_PER_G_FAT + final_carb*KCAL_PER_G_CARB

            if final_kcal_total > 0:
                prot_pct = final_prot*KCAL_PER_G_PROT / final_kcal_total * 100
                fat_pct  = final_fat*KCAL_PER_G_FAT   / final_kcal_total * 100
                carb_pct = final_carb*KCAL_PER_G_CARB / final_kcal_total * 100
            else:
                prot_pct = fat_pct = carb_pct = 0.0

            st.write(
                "### 最終每日營養（乾糧 + 固定 + 自動）"
                f"\n\n- 蛋白質：**{final_prot:.1f} g**"
                f"\n- 脂肪：**{final_fat:.1f} g**"
                f"\n- 碳水：**{final_carb:.1f} g**"
                f"\n- 熱量（宏量）：**{final_kcal_total:.0f} kcal**"
            )
            st.write(
                f"##### (最終營養比例：蛋白 **{prot_pct:.1f}%**、脂肪 **{fat_pct:.1f}%**、碳水 **{carb_pct:.1f}%**)"
            )

            # --- 多天備餐模式 ---
            st.markdown("---")
            st.markdown("### 📦 備餐模式：一次準備多貓 × 多天（固定 + 自動）")

            prep_cats = st.number_input(
                "你要準備幾隻貓的鮮食？",
                min_value=1, step=1, value=1, key="prep_cats"
            )
            prep_days = st.number_input(
                "你要準備幾天的鮮食？",
                min_value=1, step=1, value=1, key="prep_days"
            )

            fixed_list = [{"食材": n, "每日克數(g)": float(g)} for n, g in fixed_input.items() if g > 0]
            fixed_df = pd.DataFrame(fixed_list) if fixed_list else pd.DataFrame(columns=["食材", "每日克數(g)"])

            auto_df = pd.DataFrame(auto_rows)
            auto_daily_df = auto_df.rename(columns={"建議補足克數(g)": "每日克數(g)"})[["食材", "每日克數(g)"]]

            all_daily_df = pd.concat([fixed_df, auto_daily_df], ignore_index=True)
            all_daily_df = all_daily_df.groupby("食材", as_index=False)["每日克數(g)"].sum()

            all_prep_df = all_daily_df.copy()
            all_prep_df["總克數(g)"] = (all_prep_df["每日克數(g)"] * prep_days * prep_cats).round(1)

            st.markdown(f"#### 🧾 全部食材總備餐清單（{prep_cats} 隻貓 × {prep_days} 天）")
            st.dataframe(all_prep_df, use_container_width=True)

# =========================================================
# 8) 最下方：整天比例（乾糧 + 自動鮮食）
#    （如果你有用上面 fresh NNLS，也會顯示）
# =========================================================
st.markdown("---")
st.subheader("📊 整天實際攝取的營養比例（乾糧＋鮮食自動配比）")

day_prot = dry_protein_total + fresh_total_prot
day_fat  = dry_fat_total     + fresh_total_fat
day_carb = dry_carb_total    + fresh_total_carb

day_kcal_total = day_prot*KCAL_PER_G_PROT + day_fat*KCAL_PER_G_FAT + day_carb*KCAL_PER_G_CARB

if day_kcal_total > 0:
    day_prot_pct = day_prot*KCAL_PER_G_PROT / day_kcal_total * 100
    day_fat_pct  = day_fat*KCAL_PER_G_FAT   / day_kcal_total * 100
    day_carb_pct = day_carb*KCAL_PER_G_CARB / day_kcal_total * 100
else:
    day_prot_pct = day_fat_pct = day_carb_pct = 0.0

st.write(
    f"蛋白質 **{day_prot_pct:.1f}%**、"
    f"脂肪 **{day_fat_pct:.1f}%**、"
    f"碳水 **{day_carb_pct:.1f}%**"
)