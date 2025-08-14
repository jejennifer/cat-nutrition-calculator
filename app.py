import streamlit as st
import pandas as pd

st.set_page_config(page_title="貓咪營養計算機", layout="wide")

st.title("🐱 貓咪營養素計算機（初版）")

# 載入食物資料
df = pd.read_csv("data/food_data.csv")

# 選擇食物
selected = st.multiselect("請選擇食物（可複選）", df["食物名稱"].tolist())

if selected:
    st.subheader("📊 營養分析（轉換為乾物基準）")

    for name in selected:
        row = df[df["食物名稱"] == name].iloc[0]
        st.markdown(f"### 🥣 {name}（{row['類型']}）")
        moisture = row["水分"]
        protein = row["蛋白質"]
        fat = row["脂肪"]
        carb = row["碳水"]

        # 乾物基準（DMB）計算
        dmb_protein = round(protein / (100 - moisture) * 100, 1)
        dmb_fat = round(fat / (100 - moisture) * 100, 1)
        dmb_carb = round(carb / (100 - moisture) * 100, 1)

        col1, col2 = st.columns(2)
        with col1:
            st.write("💧 原始營養素（%）")
            st.write(f"蛋白質：{protein}%")
            st.write(f"脂肪：{fat}%")
            st.write(f"碳水：{carb}%")
        with col2:
            st.write("📏 乾物基準（DMB）")
            st.write(f"蛋白質：{dmb_protein}%")
            st.write(f"脂肪：{dmb_fat}%")
            st.write(f"碳水：{dmb_carb}%")

        st.markdown("---")
else:
    st.info("請先選擇至少一項食物。")