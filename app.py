import streamlit as st

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 LINE 貼圖創作工作室")

st.write(
    "歡迎來到 LINE 貼圖 Web 版！"
)

st.info(
    "目前是 V10.0 Web 測試版。"
)

st.success(
    "✅ Streamlit 網頁成功啟動！"
)

st.divider()

st.subheader("🚀 下一步")

st.write(
    "接下來我們會逐步加入："
)

st.write("① AI 貼圖生成")
st.write("② 透明背景 PNG")
st.write("③ 4×2 貼圖裁切")
st.write("④ 手動調整裁切位置")
st.write("⑤ main.png / tab.png")
st.write("⑥ 125 種文字效果")
st.write("⑦ 使用者自定風格")

st.caption(
    "V10.0 Web Edition｜核心基於 V8.6.4"
)
