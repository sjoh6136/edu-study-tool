import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import random
from streamlit_image_coordinates import streamlit_image_coordinates

# 1. 페이지 설정 및 레이아웃 최적화
st.set_page_config(page_title="교육학 암기 마스터", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSelectbox"] { max-width: 33%; }
    .stRadio > label { font-weight: bold; font-size: 1.1em; color: #1E88E5; }
    .stButton > button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- [캐싱 엔진: 데이터만 미리 뽑아두기] ---
@st.cache_data(show_spinner="페이지를 정밀 분석 중입니다...")
def get_cached_analysis(pdf_bytes, page_num):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    
    # 단어 위치 및 텍스트 구조 추출
    word_list = page.get_text("words") 
    raw_dict = page.get_text("dict")
    
    # 파란색 영역 지도 생성
    blue_word_boxes = []
    for b in raw_dict["blocks"]:
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    color = s["color"]
                    r, g, b_val = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
                    # 기존에 가장 잘 작동했던 파란색 판정 로직
                    if b_val > r and b_val > g and b_val > 45:
                        blue_word_boxes.append(s["bbox"])

    # 단어와 파란색 영역 매칭 (자석 효과)
    final_blue_targets = []
    for w in word_list:
        w_box = w[:4]
        mid_x, mid_y = (w_box[0] + w_box[2]) / 2, (w_box[1] + w_box[3]) / 2
        for bb in blue_word_boxes:
            if bb[0]-2 <= mid_x <= bb[2]+2 and bb[1]-2 <= mid_y <= bb[3]+2:
                final_blue_targets.append(w_box)
                break
    return final_blue_targets

@st.cache_resource(show_spinner=False)
def get_cached_image(pdf_bytes, page_num, zoom=3.0):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- [메인 실행부] ---
st.title("❤ 여보 사랑해 화이팅 😍🤞")

uploaded_file = st.file_uploader("해설편 PDF 파일을 업로드하세요", type="pdf")

if uploaded_file is not None:
    if 'clicked_ids' not in st.session_state: st.session_state.clicked_ids = set()
    if 'random_seed' not in st.session_state: st.session_state.random_seed = 42

    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    page_num = st.selectbox("페이지 선택", range(len(doc)), format_func=lambda x: f"{x+1} 페이지")
    
    with st.sidebar:
        st.header("🛠️ 난이도 조절")
        step = st.select_slider(
            "가리기 단계 설정",
            options=["1단계", "2단계", "3단계", "4단계", "5단계(전체)"],
            value="2단계"
        )
        st.write("---")
        if st.button("🎲 블랭크 위치 섞기"):
            st.session_state.random_seed = random.randint(1, 1000)
            st.session_state.clicked_ids = set()
            st.rerun()
        if st.button("🔄 다시 가리기 (리셋)"):
            st.session_state.clicked_ids = set()
            st.rerun()

    # 1. 캐싱된 데이터 호출 (가장 빠른 속도)
    final_blue_targets = get_cached_analysis(pdf_bytes, page_num)
    base_img = get_cached_image(pdf_bytes, page_num)

    # 2. 행 단위 그룹화 (이 부분은 사용자가 슬라이더 바꿀 때마다 실행)
    display_targets = []
    random.seed(st.session_state.random_seed)

    if step == "5단계(전체)":
        display_targets = list(final_blue_targets)
    else:
        line_groups = {}
        for target in final_blue_targets:
            # 기존의 정확했던 행 구분 로직 (3px 오차 허용)
            line_key = round(target[1] / 3) * 3 
            if line_key not in line_groups: line_groups[line_key] = []
            line_groups[line_key].append(target)

        # 사용자 요청에 의한 정밀 단계 매핑
        step_map = {
            "1단계": (1, 1),
            "2단계": (1, 2),
            "3단계": (2, 3),
            "4단계": (3, 5)
        }
        min_cnt, max_cnt = step_map[step]

        for l_key in sorted(line_groups.keys()):
            row = line_groups[l_key]
            count = random.randint(min_cnt, max_cnt)
            count = min(len(row), count)
            selected = random.sample(row, count)
            display_targets.extend(selected)

    # 3. 그리기 및 화면 출력
    zoom = 3.0
    img_draw = base_img.copy() # 원본 보존을 위해 복사본 사용
    draw = ImageDraw.Draw(img_draw)
    
    for box in display_targets:
        tid = f"{page_num}_{box}"
        if tid not in st.session_state.clicked_ids:
            # 기존의 가장 예뻤던 박스 크기 보정 (+2, -2)
            db = [v * zoom for v in box]
            draw.rectangle([db[0], db[1]+2, db[2], db[3]-2], fill="black")

    # 4. 클릭 감지 (이전과 동일한 정확도)
    res = streamlit_image_coordinates(img_draw, key=f"v_{st.session_state.random_seed}_{page_num}_{step}", use_column_width=True)
    
    if res:
        rx, ry = img_draw.size[0] / res["width"], img_draw.size[1] / res["height"]
        cx, cy = res["x"] * rx, res["y"] * ry
        for box in display_targets:
            tid = f"{page_num}_{box}"
            db = [v * zoom for v in box]
            if db[0] <= cx <= db[2] and db[1] <= cy <= db[3]:
                if tid not in st.session_state.clicked_ids:
                    st.session_state.clicked_ids.add(tid)
                    st.rerun()

    st.write("---")
    if step == "5단계(전체)":
        st.success(f"🔥 모든 파란색 용어를 가렸습니다.")
    else:
        st.info(f"📍 {step} 진행 중")
else:
    st.info("파일을 업로드하면 최적화된 학습이 시작됩니다.")
