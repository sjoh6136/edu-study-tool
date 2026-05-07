import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import random
from streamlit_image_coordinates import streamlit_image_coordinates

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="교육학 암기 마스터", layout="wide")

st.markdown("""
    <style>
    .stRadio > label { font-weight: bold; font-size: 1.1em; color: #1E88E5; }
    .stButton > button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; background-color: #f8f9fa; }
    .stButton > button:hover { border: 2px solid #1E88E5; color: #1E88E5; }
    
    /* 페이지 선택 박스 너비 조절 (1/3 수준) */
    [data-testid="stSelectbox"] {
        max-width: 33%;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎓 교육학 정밀 5단계 학습 시스템")
st.caption("파란색 핵심 용어를 단계별로 가려줍니다. 가려진 박스를 클릭하면 정답이 나타납니다.")

uploaded_file = st.file_uploader("해설편 PDF 파일을 업로드하세요", type="pdf")

if uploaded_file is not None:
    # 세션 상태 초기화
    if 'clicked_ids' not in st.session_state: st.session_state.clicked_ids = set()
    if 'random_seed' not in st.session_state: st.session_state.random_seed = 42

    # 사이드바 제어판
    with st.sidebar:
        st.header("🛠️ 난이도 조절")
        step = st.select_slider(
            "가리기 단계 설정",
            options=["1단계", "2단계", "3단계", "4단계", "5단계(전체)"],
            value="2단계",
            help="단계가 높을수록 가려지는 단어의 개수가 늘어납니다."
        )
        
        st.write("---")
        if st.button("🎲 블랭크 위치 섞기"):
            st.session_state.random_seed = random.randint(1, 1000)
            st.session_state.clicked_ids = set()
            st.rerun()
        
        if st.button("🔄 다시 가리기 (리셋)"):
            st.session_state.clicked_ids = set()
            st.rerun()
        
        # 가이드 박스 제거됨

    # PDF 데이터 처리
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # 페이지 선택 (너비가 CSS에 의해 1/3로 제한됨)
    page_num = st.selectbox("페이지 선택", range(len(doc)), format_func=lambda x: f"{x+1} 페이지")
    page = doc[page_num]

    # 1. 단어 좌표 및 색상 데이터 정밀 추출
    word_list = page.get_text("words") 
    blue_word_boxes = []
    raw_dict = page.get_text("dict")
    
    for b in raw_dict["blocks"]:
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    color = s["color"]
                    r, g, b_val = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
                    if b_val > r and b_val > g and b_val > 45:
                        blue_word_boxes.append(s["bbox"])

    # 2. 파란색 영역과 단어 좌표 매칭
    final_blue_targets = []
    for w in word_list:
        w_box = w[:4]
        mid_x, mid_y = (w_box[0] + w_box[2]) / 2, (w_box[1] + w_box[3]) / 2
        for bb in blue_word_boxes:
            if bb[0]-2 <= mid_x <= bb[2]+2 and bb[1]-2 <= mid_y <= bb[3]+2:
                final_blue_targets.append(w_box)
                break

    # 3. 단계별 블랭크 생성 로직
    display_targets = []
    random.seed(st.session_state.random_seed)

    if step == "5단계(전체)":
        display_targets = list(final_blue_targets)
    else:
        line_groups = {}
        for target in final_blue_targets:
            line_key = round(target[1] / 3) * 3 
            if line_key not in line_groups: line_groups[line_key] = []
            line_groups[line_key].append(target)

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

    # 4. 이미지 렌더링 및 가림막 그리기
    zoom = 3.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    draw = ImageDraw.Draw(img)
    
    for box in display_targets:
        tid = f"{page_num}_{box}"
        if tid not in st.session_state.clicked_ids:
            draw_box = [v * zoom for v in box]
            draw.rectangle([draw_box[0], draw_box[1]+2, draw_box[2], draw_box[3]-2], fill="black")

    # 5. 인터랙티브 클릭 감지
    res = streamlit_image_coordinates(img, key=f"v_{st.session_state.random_seed}_{page_num}_{step}", use_column_width=True)
    
    if res:
        rx, ry = img.size[0] / res["width"], img.size[1] / res["height"]
        cx, cy = res["x"] * rx, res["y"] * ry
        
        for box in display_targets:
            tid = f"{page_num}_{box}"
            x0, y0, x1, y1 = [v * zoom for v in box]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                if tid not in st.session_state.clicked_ids:
                    st.session_state.clicked_ids.add(tid)
                    st.rerun()

    st.write("---")
    if step == "5단계(전체)":
        st.success(f"🔥 마스터 모드: 총 {len(display_targets)}개의 파란색 용어를 모두 가렸습니다.")
    else:
        st.info(f"📍 {step} 진행 중")

else:
    st.info("해설편 PDF 파일을 업로드하세요.")