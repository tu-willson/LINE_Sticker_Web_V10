import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

# =========================
# OpenAI
# =========================

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

# =========================
# 網頁
# =========================

st.title("🎨 LINE 貼圖創作工作室")

st.caption("V10.0 Web Edition｜AI 圖片生成測試")

st.divider()

prompt = st.text_area(
    "✏️ 請輸入你想生成的貼圖",
    value="Q版可愛人物，開心揮手，LINE貼圖風格，透明背景",
    height=120
)

generate = st.button(
    "✨ 生成圖片",
    type="primary"
)

# =========================
# AI 圖片生成
# =========================

if generate:

    if not prompt.strip():
        st.warning("請先輸入貼圖描述。")
        st.stop()

    with st.spinner("🎨 AI 正在生成圖片，請稍候……"):

        try:

            result = client.images.generate(
                model="gpt-image-2",
                prompt=prompt,
                size="1024x1024"
            )

            image_base64 = result.data[0].b64_json

            image_bytes = base64.b64decode(image_base64)

            image = Image.open(
                BytesIO(image_bytes)
            )

            st.success("🎉 圖片生成成功！")

            st.image(
                image,
                caption="AI 生成結果",
                use_container_width=True
            )

        except Exception as e:

            st.error("❌ 圖片生成失敗")

            st.code(
                str(e)
            )
