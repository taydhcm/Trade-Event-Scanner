import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import telebot
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor

# ====================== CẤU HÌNH ======================
st.set_page_config(page_title="Event Scanner Pro", layout="wide", page_icon="🔥")
st.title("🔥 Event Scanner Pro - Phát hiện tin dự án & thầu")

# --- Gemini API ---
GEMINI_KEY = "AIzaSyCwUSo80dlrFJ6ew4NaKaAn4cKeKgpe-9g"
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp')

# --- Telegram ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "8516741675:AAE8rdixZX6x7e-ZtXXH1YjZC-PehUFkLOA")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "1247850754")
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def send_telegram(msg):
    if bot:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, msg)
        except:
            pass

# ====================== DANH SÁCH NGUỒN ======================
SOURCES = {
    "cafef": {"url": "https://cafef.vn/du-an.chn", "name": "CafeF"},
    "vietstock": {"url": "https://vietstock.vn/du-an.htm", "name": "Vietstock"},
    "vnexpress": {"url": "https://vnexpress.net/kinh-doanh/du-an", "name": "VnExpress"},
    "baodautu": {"url": "https://baodautu.vn/du-an", "name": "Báo Đầu Tư"},
    "thanhnien": {"url": "https://thanhnien.vn/kinh-doanh/du-an", "name": "Thanh Niên"},
    "xamvn": {"url": "https://xamvn.com/forums/chung-khoan.12/", "name": "Xamvn Forum"},
}

# ====================== CỔ PHIẾU THEO NGÀNH ======================
STOCK_BY_SECTOR = {
    "Bất động sản - Hạ tầng": ["CII", "DIG", "KBC", "NLG", "LCG", "BCG", "VCG"],
    "Xây dựng": ["HBC", "PC1", "CTD", "HHV"],
    "Thép & Vật liệu": ["HPG", "HSG", "NKG"],
    "Điện - Năng lượng": ["REE", "GEG", "PC1", "POW", "GAS"],
    "Ngân hàng": ["VCB", "BID", "CTG", "STB", "TCB"]
}

KEYWORDS = ["thầu", "trúng thầu", "giao đất", "giao mặt bằng", "Thủ Thiêm", "dự án", "hạ tầng", "đầu tư công", "BT", "BOT", "PPP", "quy hoạch"]

# ====================== PHÂN TÍCH BẰNG GEMINI ======================
def analyze_with_gemini(title, link, source):
    prompt = f"""
    Bạn là chuyên gia phân tích chứng khoán Việt Nam.
    Hãy phân tích tin tức sau và trả về **chỉ JSON** (không giải thích thêm):

    Tiêu đề: {title}
    Nguồn: {source}
    Link: {link}

    Trả về JSON với cấu trúc sau:
    {{
      "related_stocks": ["CII", "DIG", ...],
      "sector": "Bất động sản - Hạ tầng",
      "event_score": 8,
      "summary": "Tóm tắt ngắn gọn bằng tiếng Việt",
      "impact": "Mức độ ảnh hưởng đến cổ phiếu (Cao/Trung bình/Thấp)",
      "recommendation": "MUA / THEO DÕI / KHÔNG ẢNH HƯỞNG"
    }}
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Lấy phần JSON (tránh lỗi markdown)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1]
        
        result = eval(text)  # Chuyển string thành dict
        return result
    except Exception as e:
        st.warning(f"Lỗi Gemini: {e}")
        return {
            "related_stocks": [],
            "sector": "Khác",
            "event_score": 0,
            "summary": "Không phân tích được",
            "impact": "Thấp",
            "recommendation": "KHÔNG ẢNH HƯỞNG"
        }

# ====================== CRAWLER ======================
def crawl_source(source_name, source_info):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_info["url"], timeout=15, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        articles = []

        if source_name == "cafef":
            for item in soup.select(".box-category-item"):
                title = item.select_one(".box-category-title a")
                if title and any(kw in title.text.lower() for kw in KEYWORDS):
                    articles.append({
                        "title": title.text.strip(),
                        "link": "https://cafef.vn" + title['href'],
                        "source": source_info["name"],
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

        elif source_name == "xamvn":
            for item in soup.select("a.thread-title"):
                title = item.text.strip()
                if any(kw in title.lower() for kw in KEYWORDS):
                    articles.append({
                        "title": title,
                        "link": "https://xamvn.com" + item['href'],
                        "source": "Xamvn Forum",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

        return articles[:12]
    except Exception as e:
        st.warning(f"Lỗi crawl {source_info['name']}: {e}")
        return []

# ====================== STREAMLIT UI ======================
st.sidebar.header("⚙️ Cài đặt quét tin")

selected_sources = st.sidebar.multiselect(
    "Chọn nguồn tin", 
    options=list(SOURCES.keys()), 
    default=list(SOURCES.keys()),
    format_func=lambda x: SOURCES[x]["name"]
)

scan_interval = st.sidebar.slider("Thời gian quét tự động (phút)", 5, 30, 10)

if "scan_history" not in st.session_state:
    st.session_state.scan_history = []

if st.button("🚀 Bắt đầu quét tin tức", type="primary"):
    with st.spinner("Đang quét tin từ nhiều nguồn và phân tích bằng Gemini..."):
        all_articles = []
        for src_name in selected_sources:
            articles = crawl_source(src_name, SOURCES[src_name])
            all_articles.extend(articles)

        results = []
        for art in all_articles:
            ai_result = analyze_with_gemini(art["title"], art["link"], art["source"])
            if ai_result["related_stocks"]:
                for stock in ai_result["related_stocks"]:
                    results.append({
                        "Thời gian": art["time"],
                        "Tiêu đề": art["title"],
                        "Nguồn": art["source"],
                        "Link": art["link"],
                        "Cổ phiếu": stock,
                        "Ngành": ai_result["sector"],
                        "Mức độ": ai_result["event_score"],
                        "Tóm tắt": ai_result["summary"],
                        "Khuyến nghị": ai_result["recommendation"]
                    })

        # Lưu lịch sử
        scan_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles": len(all_articles),
            "important_events": len(results),
            "results": results
        }
        st.session_state.scan_history.append(scan_record)

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Mức độ", ascending=False)
            
            st.success(f"🔥 Phát hiện {len(df)} tin quan trọng!")
            st.dataframe(df, use_container_width=True)

            # Gửi Telegram
            if bot and TELEGRAM_CHAT_ID:
                for _, row in df.head(5).iterrows():
                    msg = f"🔥 Tin nóng!\n{row['Tiêu đề']}\nCổ phiếu: {row['Cổ phiếu']}\nNgành: {row['Ngành']}\nMức độ: {row['Mức độ']}/10\nKhuyến nghị: {row['Khuyến nghị']}\nLink: {row['Link']}"
                    send_telegram(msg)
        else:
            st.info("✅ Không phát hiện tin quan trọng trong lần quét này.")

        # Hiển thị lịch sử quét
        st.subheader("📜 Lịch sử quét gần đây")
        if st.session_state.scan_history:
            history_df = pd.DataFrame([{
                "Thời gian": r["time"],
                "Tổng tin quét": r["total_articles"],
                "Tin quan trọng": r["important_events"]
            } for r in st.session_state.scan_history[-10:]])
            st.dataframe(history_df, use_container_width=True)

st.caption("Event Scanner Pro v2.2 | Tích hợp Gemini AI | Tự động quét tin dự án - thầu - giao đất")
