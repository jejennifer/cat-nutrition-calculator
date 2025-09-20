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
    age_group = st.selectbox("年齡層", ["幼貓 0-4月", "幼貓 4-6月", "結紮成貓","未結紮成貓", "老貓", "減重"])
    activity = st.selectbox("活動量", ["低", "中", "高"])

    # ➤ 係數選擇（簡化範例，可再細分）

    # --- 生理係數（年齡/結紮）
    phys_factor_map = {
        "幼貓 0-4月": 3.0,
        "幼貓 4-6月": 2.5,
        "未結紮成貓": 1.5,
        "結紮成貓": 1.3,
        "老貓": 1.0,
        "減重": 0.8,
    }

    # --- 活動量係數
    activity_factor_map = {
        "低": 1.0,
        "中": 1.2,
        "高": 1.4,
    }

    phys_mer_factor = phys_factor_map[age_group]
    act_factor   = activity_factor_map[activity]

    # ➤ 熱量計算
    rer = 70 * (weight ** 0.75)
    mer = rer * phys_mer_factor * act_factor

    # ➤ 最低營養素（以 g/day 顯示）
    min_protein_g = mer / 1000 * 65      # g/day
    min_fat_g     = mer / 1000 * 22.5    # g/day

    # ➤ 建議營養素（以 g/day 顯示）
    recommend_protein_g = min_protein_g * 1.15      # g/day
    recommend_fat_g     = min_fat_g * 1.15    # g/day

    st.subheader("📊 計算結果")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("RER", f"{rer:.0f} kcal / 天")
        st.metric("MER (建議攝取)", f"{mer:.0f} kcal / 天", help="基於年齡/結紮狀態係數")
    with col2:
        st.write("最低營養素")
        st.write(f"蛋白質 ≥ **{min_protein_g:.1f} g / 天**")
        st.write(f"脂肪   ≥ **{min_fat_g:.1f} g / 天**")
        st.caption("※ 若處方或特殊需求，可再手動調整目標值。")
    with col3:
        st.write("建議營養素")
        st.write(f"蛋白質 **{recommend_protein_g:.1f} g / 天**")
        st.write(f"脂肪   **{recommend_fat_g:.1f} g / 天**")

# --- 2B. 既有食物 DMB 分析頁 ----
elif page == "🥣 食物分析 (DMB)":
    st.title("🥣 食物營養分析（轉乾物基準）")
    df = pd.read_csv("data/food_data_test.csv")
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
