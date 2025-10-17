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

# --- 1. sidebar 分頁 ---
page = st.sidebar.radio("選擇功能", ["🐱 貓咪需求計算"], horizontal=False)

# --- 2A. 主頁 ---
if page == "🐱 貓咪需求計算":
    st.title("🐱 貓咪每日熱量 & 鮮食克數計算（整合版）")

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

    fresh_candidates = df[df["類型"].str.contains("生", na=False)]
    selected_fresh = st.multiselect("選擇鮮食食材（可複選）", fresh_candidates["食物名稱"].tolist())

    ratio_map = {}
    if selected_fresh and remaining_kcal > 0:
        st.caption("輸入各食材在鮮食配方中的比例（%），總和不必剛好 100%，系統會自動正規化。")
        for name in selected_fresh:
            ratio = st.number_input(f"{name} 配比(%)", min_value=0.0, step=1.0, value=0.0, key=f"ratio_{name}")
            ratio_map[name] = ratio

        sum_ratio = sum(ratio_map.values())
        if sum_ratio > 0:
            mix_kcal_per_g = 0.0
            for name, r in ratio_map.items():
                frac = r / sum_ratio
                kcal_g = float(fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]["kcal_per_g"])
                mix_kcal_per_g += frac * kcal_g

            if mix_kcal_per_g > 0:
                total_fresh_g = remaining_kcal / mix_kcal_per_g
                st.metric("🍽️ 鮮食總克數", f"{total_fresh_g:.0f} g / 天")

                serve_rows = []
                total_prot = total_fat = total_carb = 0.0
                for name, r in ratio_map.items():
                    frac = r / sum_ratio
                    grams = total_fresh_g * frac
                    row = fresh_candidates[fresh_candidates["食物名稱"] == name].iloc[0]
                    prot_g = grams * float(row["蛋白質"]) / 100.0
                    fat_g = grams * float(row["脂肪"]) / 100.0
                    carb_g = grams * float(row["碳水"]) / 100.0
                    total_prot += prot_g
                    total_fat += fat_g
                    total_carb += carb_g
                    serve_rows.append({
                        "食材": name,
                        "分配克數(g)": round(grams, 1),
                        "蛋白(g)": round(prot_g, 1),
                        "脂肪(g)": round(fat_g, 1),
                        "碳水(g)": round(carb_g, 1),
                    })
                st.dataframe(pd.DataFrame(serve_rows), use_container_width=True)
                st.caption(f"鮮食總蛋白質：{total_prot:.1f} g，脂肪：{total_fat:.1f} g，碳水：{total_carb:.1f} g。")