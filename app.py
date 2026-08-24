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

    _CROP_HTML_TEMPLATE = '<!doctype html><html><head><meta charset="utf-8"><style>\n*{box-sizing:border-box}body{margin:0;font-family:Arial,"Microsoft JhengHei",sans-serif;color:#333}\n.help{font-size:14px;line-height:1.6;background:#f5f7fa;padding:9px;border-radius:8px}\n.viewer{position:relative;width:720px;max-width:100%;margin:0 auto;overflow:hidden;border:1px solid #bbb;border-radius:8px;background:#eee}\n#img{display:block;width:100%;height:auto;user-select:none;-webkit-user-drag:none}\n#cv{position:absolute;left:0;top:0;width:100%;height:100%;touch-action:none;z-index:10;pointer-events:auto}\n.status{font-size:14px;padding:8px 0;color:#555}.actions{display:flex;gap:8px;margin:8px 0}\nbutton{border:0;border-radius:8px;padding:10px 14px;cursor:pointer}button.primary{background:#222;color:#fff}\n.coords{font:13px/1.5 Consolas,monospace;white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:8px}\n</style></head><body>\n<div class="help"><b>操作：</b>拖曳框中央＝移動｜拖曳四角＝調整大小｜拖曳四邊＝單方向調整<br>完成後按「✂️ 裁切並下載 01～08」</div>\n<div class="viewer"><img id="img"><canvas id="cv"></canvas></div>\n<div class="status" id="status">正在載入……</div>\n<div class="actions"><button onclick="resetBoxes()">↩️ 重設4×2</button><button class="primary" onclick="downloadAll()">✂️ 裁切並下載01～08</button></div>\n<div class="coords" id="coords"></div>\n<script>\nconst B64="__IMAGE_B64__",IW=__IW__,IH=__IH__;let boxes=__BOXES__;\nconst img=document.getElementById("img"),cv=document.getElementById("cv"),ctx=cv.getContext("2d"),statusEl=document.getElementById("status"),coordsEl=document.getElementById("coords");\nconst colors=["#ff4040","#3987ff","#32ad61","#a04bd0","#ff922e","#25aeb0","#db3f9b","#956c3c"];\nlet scale=1,active=-1,mode=null,start=null,snapshot=null;\nfunction clone(b){return b.map(x=>x.map(Number))}function clamp(v,a,b){return Math.max(a,Math.min(b,v))}\nfunction defaults(){let a=[];for(let i=0;i<8;i++){let c=i%4,r=Math.floor(i/4);a.push([Math.round(c*IW/4),Math.round(r*IH/2),Math.round((c+1)*IW/4),Math.round((r+1)*IH/2)])}return a}\nfunction resize(){if(!img.naturalWidth)return;let mw=document.getElementById("viewer").clientWidth||720;mw=Math.min(720,mw);cv.width=Math.round(mw);cv.height=Math.round(mw*IH/IW);scale=cv.width/IW;draw()}\nfunction draw(){\nctx.clearRect(0,0,cv.width,cv.height);\nctx.save();ctx.globalCompositeOperation="source-over";\nfor(let i=0;i<8;i++){\n  let b=boxes[i],x=b[0]*scale,y=b[1]*scale,w=(b[2]-b[0])*scale,h=(b[3]-b[1])*scale;\n  ctx.save();ctx.strokeStyle=colors[i];ctx.lineWidth=1.5;ctx.setLineDash([8,6]);\n  ctx.strokeRect(x+1,y+1,Math.max(1,w-2),Math.max(1,h-2));ctx.setLineDash([]);\n    ctx.font="bold 18px Arial";ctx.lineWidth=4;ctx.strokeStyle="rgba(255,255,255,.9)";\n  ctx.strokeText(String(i+1).padStart(2,"0"),x+10,y+23);ctx.fillStyle=colors[i];\n  ctx.fillText(String(i+1).padStart(2,"0"),x+10,y+23);ctx.restore();\n}ctx.restore();update()}\nfunction update(){let s="";for(let i=0;i<8;i++){let b=boxes[i].map(v=>Math.round(v));s+=String(i+1).padStart(2,"0")+"：X "+b[0]+"～"+b[2]+"｜Y "+b[1]+"～"+b[3]+"｜"+(b[2]-b[0])+"×"+(b[3]-b[1])+" px\\\\n"}coordsEl.textContent=s}\nfunction pos(e){let r=cv.getBoundingClientRect();return{x:(e.clientX-r.left)*IW/r.width,y:(e.clientY-r.top)*IH/r.height}}\nfunction hit(p){for(let i=7;i>=0;i--){let b=boxes[i],t=Math.max(12,12/scale),L=Math.abs(p.x-b[0])<=t,R=Math.abs(p.x-b[2])<=t,T=Math.abs(p.y-b[1])<=t,B=Math.abs(p.y-b[3])<=t,inside=p.x>=b[0]&&p.x<=b[2]&&p.y>=b[1]&&p.y<=b[3];if(L&&T)return[i,"nw"];if(R&&T)return[i,"ne"];if(L&&B)return[i,"sw"];if(R&&B)return[i,"se"];if(T&&p.x>b[0]&&p.x<b[2])return[i,"n"];if(B&&p.x>b[0]&&p.x<b[2])return[i,"s"];if(L&&p.y>b[1]&&p.y<b[3])return[i,"w"];if(R&&p.y>b[1]&&p.y<b[3])return[i,"e"];if(inside)return[i,"move"]}return[-1,null]}\ncv.addEventListener("pointerdown",e=>{e.preventDefault();try{cv.setPointerCapture(e.pointerId)}catch(_){}let h=hit(pos(e));if(h[0]<0)return;active=h[0];mode=h[1];start=pos(e);snapshot=clone(boxes);statusEl.textContent="🖱️ 正在調整 "+String(active+1).padStart(2,"0")+"……"});\ncv.addEventListener("pointermove",e=>{if(active<0)return;e.preventDefault();let p=pos(e),b=snapshot[active],dx=p.x-start.x,dy=p.y-start.y,n=[...b],mw=Math.max(30,IW*.02),mh=Math.max(30,IH*.02);if(mode==="move"){let w=b[2]-b[0],h=b[3]-b[1],x=clamp(b[0]+dx,0,IW-w),y=clamp(b[1]+dy,0,IH-h);n=[x,y,x+w,y+h]}else{if(mode.includes("w"))n[0]=clamp(b[0]+dx,0,b[2]-mw);if(mode.includes("e"))n[2]=clamp(b[2]+dx,b[0]+mw,IW);if(mode.includes("n"))n[1]=clamp(b[1]+dy,0,b[3]-mh);if(mode.includes("s"))n[3]=clamp(b[3]+dy,b[1]+mh,IH)}boxes[active]=n;draw()});\ncv.addEventListener("pointerup",e=>{active=-1;mode=null;statusEl.textContent="✅ 裁切框已更新"});\ncv.addEventListener("pointercancel",()=>{active=-1;mode=null});\nfunction resetBoxes(){boxes=defaults();draw();statusEl.textContent="↩️ 已重設為原始4×2"}\nfunction saveBlob(blob,name){let u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)}\nfunction make(i){let b=boxes[i].map(v=>Math.round(v)),x1=clamp(b[0],0,IW-2),y1=clamp(b[1],0,IH-2),x2=clamp(b[2],x1+2,IW),y2=clamp(b[3],y1+2,IH),cw=370,ch=320,sw=x2-x1,sh=y2-y1,rat=Math.min(cw/sw,ch/sh),nw=Math.max(1,Math.round(sw*rat)),nh=Math.max(1,Math.round(sh*rat)),o=document.createElement("canvas");o.width=cw;o.height=ch;o.getContext("2d").drawImage(img,x1,y1,sw,sh,Math.round((cw-nw)/2),Math.round((ch-nh)/2),nw,nh);return new Promise(r=>o.toBlob(r,"image/png"))}\nasync function downloadAll(){statusEl.textContent="⏳ 正在製作01～08 PNG……";for(let i=0;i<8;i++){saveBlob(await make(i),String(i+1).padStart(2,"0")+".png");await new Promise(r=>setTimeout(r,180))}statusEl.textContent="🎉 01～08 已全部裁切並下載！"}\nimg.src="data:image/png;base64,"+B64;img.onload=()=>{resize();statusEl.textContent="✅ 8個裁切框已載入，可以直接用滑鼠調整。"};window.addEventListener("resize",resize);\n</script></body></html>'
    _image_b64 = base64.b64encode(st.session_state.generated_4x2_bytes).decode("ascii")
    _boxes_json = __import__("json").dumps(st.session_state.crop_boxes, ensure_ascii=False)
    _crop_html = _CROP_HTML_TEMPLATE.replace("__IMAGE_B64__", _image_b64).replace("__IW__", str(int(w))).replace("__IH__", str(int(h))).replace("__BOXES__", _boxes_json)
    import streamlit.components.v1 as components
    components.html(
        _crop_html,
        height=760,
        scrolling=False,
    )
    st.caption("V10 STEP 10C.3｜不使用 Custom Component、不使用 streamlit-drawable-canvas、不使用外部 CDN；裁切與下載完全在瀏覽器端。")
st.divider()
st.caption("V10 STEP 10C.4｜裁切尺寸與初始位置修正版")
