import base64
import io
import streamlit as st
from PIL import Image, ImageDraw
from openai import OpenAI

st.set_page_config(page_title="GPT Image 透明背景診斷工具", page_icon="🧪", layout="centered")
st.title("🧪 GPT Image 透明背景 API 診斷工具")
st.caption("獨立測試工具，不會修改你的 V12。請使用自己的 OpenAI API Key。")

api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

def has_real_alpha(raw: bytes):
    im = Image.open(io.BytesIO(raw))
    mode = im.mode
    bands = im.getbands()
    if "A" not in bands:
        return False, mode, None, None
    alpha = im.getchannel("A")
    extrema = alpha.getextrema()
    transparent_pixels = sum(1 for p in alpha.getdata() if p < 255)
    return transparent_pixels > 0, mode, extrema, transparent_pixels

def show_result(result, label):
    if not getattr(result, "data", None):
        st.error(f"{label}：API 有回應，但沒有圖片資料。")
        return
    b64 = getattr(result.data[0], "b64_json", None)
    if not b64:
        st.error(f"{label}：沒有取得 b64_json。")
        return
    raw = base64.b64decode(b64)
    ok, mode, extrema, transparent_pixels = has_real_alpha(raw)
    st.image(raw, caption=label, use_container_width=True)
    if ok:
        st.success(f"✅ {label} 成功，而且 PNG 確實含透明像素。｜mode={mode}｜Alpha 範圍={extrema}｜非完全不透明像素={transparent_pixels:,}")
    else:
        st.warning(f"⚠️ {label} API 有成功產圖，但沒有偵測到實際透明像素。｜mode={mode}｜Alpha 範圍={extrema}")

def make_test_input():
    im = Image.new("RGB", (512, 512), "white")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((110, 110, 402, 402), radius=55, fill=(235, 235, 235), outline=(30, 30, 30), width=8)
    d.ellipse((185, 175, 225, 215), fill=(30, 30, 30))
    d.ellipse((287, 175, 327, 215), fill=(30, 30, 30))
    d.arc((195, 210, 317, 320), 15, 165, fill=(30, 30, 30), width=8)
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()

if not api_key:
    st.info("先輸入 API Key，再執行下面測試。")
    st.stop()

client = OpenAI(api_key=api_key)

st.divider()
st.subheader("測試 1｜gpt-image-2 Generate + transparent")
st.write("不帶參考人物，只確認 Generate API 在你的帳戶上是否接受原生透明背景。")
if st.button("▶ 執行測試 1", use_container_width=True):
    try:
        with st.spinner("正在測試 Generate + transparent…"):
            r = client.with_options(timeout=180).images.generate(
                model="gpt-image-2",
                prompt="Draw one simple cute red apple sticker centered in the image. The apple must be isolated on a fully transparent background. No floor, no scene, no shadow, no border, no checkerboard.",
                size="1024x1024",
                background="transparent",
                output_format="png",
                n=1,
            )
        show_result(r, "測試 1｜gpt-image-2 Generate + transparent")
    except Exception as e:
        st.error(f"❌ 測試 1 失敗｜{type(e).__name__}: {e}")

st.divider()
st.subheader("測試 2｜gpt-image-2 Edit + transparent")
st.write("使用程式產生的簡單測試圖作為輸入，確認 Edit API 是否接受原生透明背景。")
test_bytes = make_test_input()
st.image(test_bytes, caption="Edit 測試用輸入圖", width=220)
if st.button("▶ 執行測試 2", use_container_width=True):
    try:
        with st.spinner("正在測試 Edit + transparent…"):
            r = client.with_options(timeout=180).images.edit(
                model="gpt-image-2",
                image=("test_input.png", io.BytesIO(test_bytes), "image/png"),
                prompt="Edit the input into one simple cute sticker. Preserve the central subject, remove the entire background, and place the subject on a fully transparent background. No floor, no scene, no shadow, no checkerboard.",
                size="1024x1024",
                background="transparent",
                output_format="png",
            )
        show_result(r, "測試 2｜gpt-image-2 Edit + transparent")
    except Exception as e:
        st.error(f"❌ 測試 2 失敗｜{type(e).__name__}: {e}")

st.divider()
st.subheader("測試 3｜2.5 Sunburst Edit + transparent")
st.write("只有前兩項無法透明時才需要測。這項用來確認正式支援透明背景的新模型在同一 API Key 上是否可用。")
if st.button("▶ 執行測試 3", use_container_width=True):
    try:
        with st.spinner("正在測試 Sunburst Edit + transparent…"):
            r = client.with_options(timeout=180).images.edit(
                model="gpt-image-2.5-sunburst",
                image=("test_input.png", io.BytesIO(test_bytes), "image/png"),
                prompt="Edit the input into one simple cute sticker. Preserve the central subject, remove the entire background, and place the subject on a fully transparent background. No floor, no scene, no shadow, no checkerboard.",
                size="1024x1024",
                background="transparent",
                output_format="png",
            )
        show_result(r, "測試 3｜gpt-image-2.5-sunburst Edit + transparent")
    except Exception as e:
        st.error(f"❌ 測試 3 失敗｜{type(e).__name__}: {e}")

st.divider()
st.caption("建議依序測試 1 → 2。只有需要比較時再執行測試 3，以避免不必要的圖片生成費用。")
