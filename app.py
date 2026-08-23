import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

st.title("🎨 LINE 貼圖創作工作室")
st.caption("V10.0 Web Edition｜STEP 8.1 人物參考生成修正版")
st.divider()

st.header("📷 ① 上傳人物照片")
st.write("請上傳你希望 AI 參考的人物照片。")

uploaded_file = st.file_uploader(
    "選擇人物照片",
    type=["jpg", "jpeg", "png", "webp"],
    help="支援 JPG、JPEG、PNG、WEBP"
)

if uploaded_file is not None:
    try:
        image = Image.open(uploaded_file)
        image.load()
        width, height = image.size

        st.success("✅ 人物照片已成功載入")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.image(
                image,
                caption="📷 AI 將參考這張人物照片",
                use_container_width=True
            )

        with col2:
            st.subheader("📐 圖片資訊")
            st.write(f"寬度：{width} px")
            st.write(f"高度：{height} px")
            st.write(f"格式：{image.format or '未知'}")
            st.write(f"模式：{image.mode}")

    except Exception as e:
        st.error("❌ 無法讀取圖片")
        st.code(str(e))

st.divider()
st.header("✏️ ② 告訴 AI 你想做什麼")

prompt = st.text_area(
    "貼圖要求",
    value=(
        "請以我提供的人物照片作為主要人物參考。"
        "保留人物的臉部特徵、五官比例、髮型與服飾辨識度。"
        "將人物轉換成可愛的 Q 版 LINE 貼圖風格。"
        "人物完整呈現，不要裁切頭部、身體或四肢。"
        "畫面簡潔，具有貼圖感。"
        "透明背景。"
        "人物表情開心，正在揮手。"
    ),
    height=180
)

generate = st.button(
    "✨ 使用人物照片生成貼圖",
    type="primary",
    use_container_width=True
)

if generate:
    if uploaded_file is None:
        st.warning("📷 請先上傳人物照片。")
        st.stop()

    if not prompt.strip():
        st.warning("✏️ 請輸入貼圖要求。")
        st.stop()

    with st.spinner("🎨 AI 正在參考人物照片製作貼圖……"):
        try:
            uploaded_file.seek(0)

            input_image = Image.open(uploaded_file)
            input_image.load()

            image_buffer = BytesIO()
            input_image.convert("RGBA").save(
                image_buffer,
                format="PNG"
            )
            image_buffer.seek(0)

            result = client.images.edit(
                model="gpt-image-2",
                image=(
                    "person.png",
                    image_buffer,
                    "image/png"
                ),
                prompt=prompt,
                size="1024x1024"
            )

            image_base64 = result.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)

            generated_image = Image.open(
                BytesIO(image_bytes)
            )

            st.success("🎉 人物參考生成成功！")
            st.image(
                generated_image,
                caption="🤖 AI 生成結果",
                use_container_width=True
            )

        except Exception as e:
            st.error("❌ 人物參考生成失敗")
            st.code(str(e))

st.divider()
st.caption(
    "V10.0 Web Edition｜STEP 8.1：人物參考生成修正版"
)
