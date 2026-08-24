import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import random
from pathlib import Path
import streamlit.components.v1 as components

# ============================================================
# V10 STEP 10C
# 原生 HTML Canvas 滑鼠裁切版
#
# 核心：
# - 不使用 streamlit-drawable-canvas
# - 8 個裁切框同時顯示
# - 滑鼠拖曳框中央：移動
# - 拖曳四角：縮放
# - 拖曳四邊：單方向縮放
# - 顯示座標與原圖座標分離
# - 固定預覽上限，不跟 Streamlit 容器無限放大
# - Chrome 80/100/125/150% 仍以原始圖片座標計算
# - 01～08 不會送給 AI 當作圖片編號
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide",
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

COMMON_PHRASES = [
    "早安","晚安","午安","嗨","哈囉","加油","辛苦了","謝謝",
    "感謝","不客氣","沒問題","OK","收到","了解","好喔","好的",
    "太好了","讚","超讚","棒棒的","恭喜","祝福你","一起加油",
    "慢慢來","等等我","馬上來","我來了","出發","回來了","先這樣",
    "掰掰","再見","哈哈哈","笑死","真的嗎","真的假的","好開心",
    "好幸福","太可愛了","我愛你","想你","抱抱","親親","不要啦",
    "不要鬧","傻眼","無言","生氣","氣死我了","好累","累了",
    "忙死了","休息一下","我不行了","好餓","吃飯了嗎","等等再說",
    "拜託","求你了","可以嗎","好嗎","當然可以","當然好","隨便你",
    "沒事","沒關係","別擔心","放心","我懂","我知道","我明白",
    "太扯了","救命","完蛋了","糟糕","慘了","好可怕","不要怕","冷靜"
]

POPULAR_STYLES = [
    "↓ 請選擇風格","Q版黏土3D","Q版收藏公仔","3D收藏公仔",
    "療癒系Cute Wstyle","大頭小身","LINE貼圖風","柔和光影",
    "手作玩偶風","可愛漫畫風","立體卡通風",
]

CHARACTER_OPTIONS = [
    "五官比例保留","服飾配件保留","人物辨識度保留",
    "Q版收藏公仔","療癒系 Cute Wstyle","大頭小身",
    "LINE貼圖風","柔和光影",
]

for i in range(8):
    st.session_state.setdefault(f"sticker_text_{i}", "")
st.session_state.setdefault("uploaded_image_bytes", None)
st.session_state.setdefault("generated_4x2_bytes", None)
st.session_state.setdefault("last_prompt", "")
st.session_state.setdefault("crop_boxes", None)

def get_texts():
    return [st.session_state.get(f"sticker_text_{i}", "") for i in range(8)]

def set_texts(values):
    values = list(values)[:8] + [""] * 8
    for i in range(8):
        st.session_state[f"sticker_text_{i}"] = str(values[i])

def base_boxes(w, h):
    boxes = []
    for i in range(8):
        c, r = i % 4, i // 4
        x1 = round(c * w / 4)
        x2 = round((c + 1) * w / 4)
        y1 = round(r * h / 2)
        y2 = round((r + 1) * h / 2)
        boxes.append([x1, y1, x2, y2])
    return boxes

def build_prompt(style, custom_style, selected_character, custom_character,
                 texts, transparent):
    p = [
        "請以我提供的人物照片作為主要人物參考。",
        "保留人物身份辨識特徵，不任意改變人物核心外觀。",
        "請一次生成一張清楚的4×2八格LINE貼圖總圖。",
        "第一排四格、第二排四格；依使用者輸入順序由左至右、由上至下對應。",
        "八格人物維持同一人物身份與主要視覺風格。",
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "人物與該格邊界保持安全距離。",
        "不要拉伸、變形或壓縮人物。",
        "非常重要：圖片中禁止出現01、02、03、04、05、06、07、08等編號。",
        "禁止加入格號、序號、位置標籤或數字標記。",
        "只有使用者指定的貼圖文字可以出現在圖片中。",
    ]
    if style != "↓ 請選擇風格":
        p.append(f"主要貼圖風格：{style}。")
    if custom_style.strip():
        p.append(f"使用者自定風格：{custom_style.strip()}。")
    if selected_character:
        p.append("人物與畫面特色：" + "、".join(selected_character) + "。")
    if custom_character.strip():
        p.append(f"使用者自定人物／場景要求：{custom_character.strip()}。")
    for i, t in enumerate(texts):
        p.append(f"第{i+1}格的指定貼圖文字為：「{t.strip() or '（此格未指定文字）'}」。")
    if transparent:
        p.append("請使用透明背景PNG，背景保持真正透明，不要以白色或黑色填滿。")
    p.append("整體具有LINE貼圖的清楚、可讀、可愛與完整構圖感。")
    return "\n".join(p)

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.title("🎨 LINE 貼圖創作工作室")
st.caption("V10 STEP 10C｜原生 Canvas 直接拖曳裁切")
st.divider()

st.header("📷 ① 上傳人物照片")
uploaded = st.file_uploader("選擇人物照片", type=["jpg","jpeg","png","webp"])
if uploaded:
    try:
        uploaded.seek(0)
        im = Image.open(uploaded)
        im.load()
        b = BytesIO()
        im.convert("RGBA").save(b, "PNG")
        st.session_state.uploaded_image_bytes = b.getvalue()
        st.image(im, caption="人物照片", width=420)
        st.success("✅ 人物照片已載入")
    except Exception as e:
        st.error("❌ 無法讀取人物照片")
        st.code(str(e))

st.divider()
st.header("🎨 ② 貼圖風格")
style = st.selectbox("熱門風格", POPULAR_STYLES)
custom_style = st.text_area("⭐ 我的自定風格", height=90)

st.divider()
st.header("👤 ③ 人物與畫面特色")
selected_character = st.multiselect("可以複選", CHARACTER_OPTIONS)
custom_character = st.text_area("📝 自定義人物／場景需求", height=110)

st.divider()
st.header("💬 ④ 01～08 貼圖文字")
a,b,c = st.columns(3)
with a:
    if st.button("🎲 隨機填入 8 格", use_container_width=True):
        set_texts(random.sample(COMMON_PHRASES, 8))
        st.rerun()
with b:
    if st.button("🔄 清空 8 格", use_container_width=True):
        set_texts([""]*8)
        st.rerun()
with c:
    st.write(f"隨機用語池：{len(COMMON_PHRASES)} 句")

cols = st.columns(4)
for i, col in enumerate(cols):
    with col:
        st.text_input(f"{i+1:02d}", key=f"sticker_text_{i}")
cols = st.columns(4)
for i, col in enumerate(cols, start=4):
    with col:
        st.text_input(f"{i+1:02d}", key=f"sticker_text_{i}")

texts = get_texts()
filled = sum(bool(x.strip()) for x in texts)
st.info(f"已填寫 {filled} / 8 格")

with st.expander("📚 查看目前隨機用語池"):
    st.write("、".join(COMMON_PHRASES))

st.divider()
st.header("🌈 ⑤ 背景設定")
transparent = st.checkbox("使用透明背景 PNG", value=False)

prompt = build_prompt(style, custom_style, selected_character,
                      custom_character, texts, transparent)
with st.expander("🔍 查看 AI Prompt"):
    st.code(prompt, language="text")

st.header("✨ ⑥ 生成 4×2 原始總圖")
if st.button("✨ 生成 4×2 八格總圖", type="primary", use_container_width=True):
    if not st.session_state.uploaded_image_bytes:
        st.warning("請先上傳人物照片。")
        st.stop()
    if not filled:
        st.warning("請至少輸入一格貼圖文字。")
        st.stop()
    with st.spinner("AI 正在生成 4×2 原始總圖……"):
        try:
            ib = BytesIO(st.session_state.uploaded_image_bytes)
            result = client.images.edit(
                model="gpt-image-2",
                image=("person.png", ib, "image/png"),
                prompt=prompt,
                size="1536x1024",
            )
            raw = base64.b64decode(result.data[0].b64_json)
            img = Image.open(BytesIO(raw)).convert("RGBA")
            out = BytesIO()
            img.save(out, "PNG")
            st.session_state.generated_4x2_bytes = out.getvalue()
            st.session_state.crop_boxes = None
            st.success("🎉 4×2 原始總圖生成成功！")
        except Exception as e:
            st.error("❌ 生成失敗")
            st.code(str(e))

# ------------------------------------------------------------
# STEP 10C native component
# ------------------------------------------------------------
if st.session_state.generated_4x2_bytes:
    st.divider()
    st.header("✂️ ⑦ 直接用滑鼠調整 8 個裁切框")

    src = Image.open(BytesIO(st.session_state.generated_4x2_bytes)).convert("RGBA")
    w, h = src.size

    if st.session_state.crop_boxes is None:
        st.session_state.crop_boxes = base_boxes(w, h)

    st.info(
        "直接拖曳：移動裁切框。拖曳四角：改變大小。"
        "拖曳四邊：單方向調整。8 個框同時顯示，不需要逐張打開。"
    )

    # --------------------------------------------------------
    # 明確顯示原始 4×2 圖
    # 不依賴 Canvas 是否成功載入圖片。
    # 固定預覽寬度，避免隨網頁容器無限放大。
    # --------------------------------------------------------
    st.subheader("🖼️ 原始 4×2 圖片")
    st.image(
        st.session_state.generated_4x2_bytes,
        caption=f"原始生成圖：{w} × {h} px",
        width=900,
    )

    st.caption(
        "上方是原始圖片預覽；下方 Canvas 才是可直接拖曳的裁切操作區。"
    )

    component_dir = Path(__file__).parent / "crop_editor"
    crop_editor = components.declare_component(
        "line_sticker_native_crop_editor",
        path=str(component_dir),
    )

    st.subheader("🖱️ 直接拖曳裁切框")
    result = crop_editor(
        image_b64=base64.b64encode(st.session_state.generated_4x2_bytes).decode("ascii"),
        image_width=w,
        image_height=h,
        boxes=st.session_state.crop_boxes,
        max_display_width=1100,
        key="native_crop_editor",
    )

    if isinstance(result, dict) and "boxes" in result:
        boxes = result["boxes"]
        if isinstance(boxes, list) and len(boxes) == 8:
            st.session_state.crop_boxes = boxes

    b1, b2 = st.columns(2)
    with b1:
        if st.button("↩️ 重設 8 格為原始4×2", use_container_width=True):
            st.session_state.crop_boxes = base_boxes(w, h)
            st.rerun()
    with b2:
        st.download_button(
            "⬇️ 下載原始4×2 PNG",
            data=st.session_state.generated_4x2_bytes,
            file_name="sticker_4x2_original.png",
            mime="image/png",
            use_container_width=True,
        )

    st.subheader("📐 目前 8 格原圖座標")
    rows = []
    for i, box in enumerate(st.session_state.crop_boxes):
        x1,y1,x2,y2 = [int(round(float(v))) for v in box]
        rows.append(
            f"{i+1:02d}：X {x1}～{x2}｜Y {y1}～{y2}｜{x2-x1}×{y2-y1}px"
        )
    st.code("\n".join(rows))

    st.subheader("📦 ⑧ 執行裁切")
    st.caption("裁切時使用原始圖片座標，不受網頁顯示縮放影響。")

    if st.button("✂️ 確認裁切並輸出 01～08 PNG",
                 type="primary", use_container_width=True):
        files = []
        for i, box in enumerate(st.session_state.crop_boxes):
            x1,y1,x2,y2 = [int(round(float(v))) for v in box]
            x1=max(0,min(x1,w-2)); y1=max(0,min(y1,h-2))
            x2=max(x1+2,min(x2,w)); y2=max(y1+2,min(y2,h))
            crop = src.crop((x1,y1,x2,y2))
            # 等比例放入LINE常用370×320透明畫布，不拉伸人物
            cw,ch=370,320
            scale=min(cw/crop.width,ch/crop.height)
            nw=max(1,round(crop.width*scale))
            nh=max(1,round(crop.height*scale))
            resized=crop.resize((nw,nh),Image.Resampling.LANCZOS)
            canvas=Image.new("RGBA",(cw,ch),(255,255,255,0))
            canvas.alpha_composite(resized,((cw-nw)//2,(ch-nh)//2))
            ob=BytesIO(); canvas.save(ob,"PNG")
            files.append((f"{i+1:02d}.png",ob.getvalue()))
        st.session_state["cropped_files"]=files
        st.success("🎉 裁切完成！")

    if st.session_state.get("cropped_files"):
        st.subheader("🖼️ ⑨ 裁切結果")
        cols=st.columns(4)
        for i,(name,data) in enumerate(st.session_state["cropped_files"]):
            with cols[i%4]:
                st.image(data, caption=name, width=170)
                st.download_button(
                    f"⬇️ {name}", data=data, file_name=name,
                    mime="image/png", key=f"dl_{i}"
                )

st.divider()
st.caption("V10 STEP 10C｜原生 HTML Canvas｜AI負責內容、程式負責定位與裁切")
