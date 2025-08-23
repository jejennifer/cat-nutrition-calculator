# --- 0. 套件與資料 ---
import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="貓咪營養素計算機", layout="wide")

# --- 1. sidebar 分頁 ---
page = st.sidebar.radio(
    "選擇功能",
    ["🐱 貓咪需求計算", "🥣 食物分析 (DMB)"],
    horizontal=False,
)

# --- 2A. 貓咪每日需求計算 ---
if page == "🐱 貓咪需求計算":
    st.title("🐱 貓咪每日熱量 & 營養素需求")

    # ➤ 基本輸入
    weight = st.number_input("體重 (kg)", min_value=0.1, step=0.1, value=4.0)
    age_group = st.selectbox("年齡層", ["成貓", "幼貓 <4月", "幼貓 4-6月", "老貓 / 減重"])
    activity = st.selectbox("活動量", ["低", "中", "高"])
    neutered = st.checkbox("已結紮？", value=True)

    # ➤ 係數選擇（簡化範例，可再細分）
    factor_map = {
        "成貓": 1.2 if neutered else 1.4,
        "幼貓 <4月": 3.0,
        "幼貓 4-6月": 2.5,
        "老貓 / 減重": 1.0,
    }
    mer_factor = factor_map[age_group]

    # ➤ 熱量計算
    rer = 70 * (weight ** 0.75)
    mer = rer * mer_factor

    # ➤ 最低營養素（以 g/day 顯示）
    min_protein_g = 5.0 * weight   # 5 g/kg
    min_fat_g     = 2.0 * weight   # 2 g/kg

    st.subheader("📊 計算結果")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("RER", f"{rer:.0f} kcal / 天")
        st.metric("MER (建議攝取)", f"{mer:.0f} kcal / 天", help="基於年齡/結紮狀態係數")
    with col2:
        st.write("### 最低營養素 (NRC 成貓維持)")
        st.write(f"蛋白質 ≥ **{min_protein_g:.1f} g / 天**")
        st.write(f"脂肪   ≥ **{min_fat_g:.1f} g / 天**")
        st.caption("※ 若處方或特殊需求，可再手動調整目標值。")

# --- 2B. 既有食物 DMB 分析頁 ----
elif page == "🥣 食物分析 (DMB)":
    st.title("🥣 食物營養分析（轉乾物基準）")
    df = pd.read_csv("data/food_data.csv")
    selected = st.multiselect("請選擇食物（可複選）", df["食物名稱"].tolist())
    if selected:
        st.subheader("分析結果")
        for name in selected:
            row = df[df["食物名稱"] == name].iloc[0]
            moisture = row["水分"]
            protein  = row["蛋白質"]
            fat      = row["脂肪"]
            carb     = row["碳水"]

            dmb_protein = round(protein / (100 - moisture) * 100, 1)
            dmb_fat     = round(fat     / (100 - moisture) * 100, 1)
            dmb_carb    = round(carb    / (100 - moisture) * 100, 1)

            st.markdown(f"### 🐟 {name} ({row['類型']})")
            c1, c2 = st.columns(2)
            with c1:
                st.write("💧 **原始營養素**")
                st.write(f"蛋白質：{protein}%")
                st.write(f"脂肪：{fat}%")
                st.write(f"碳水：{carb}%")
            with c2:
                st.write("📏 **乾物基準 (DMB)**")
                st.write(f"蛋白質：{dmb_protein}%")
                st.write(f"脂肪：{dmb_fat}%")
                st.write(f"碳水：{dmb_carb}%")
            st.markdown("---")
    else:
        st.info("請先勾選至少一項食物。")
