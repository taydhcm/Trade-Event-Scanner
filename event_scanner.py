import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import json
import re
import telebot
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai
import json

# Cấu hình API
GEMINI_KEY = "AIzaSyCwUSo80dlrFJ6ew4NaKaAn4cKeKgpe-9g"
MODEL_NAME = "gemini-2.0-flash-thinking-exp"

genai.configure(api_key=GEMINI_KEY)

# ================== CẤU HÌNH ==================
st.set_page_config(page_title="Event Scanner Pro", layout="wide")
st.title("🔥 Event Scanner Pro - Phát hiện tin dự án & thầu")

# --- Telegram Bot ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "8516741675:AAE8rdixZX6x7e-ZtXXH1YjZC-PehUFkLOA")  # Dùng st.secrets nếu deploy
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "1247850754")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN != "8516741675:AAE8rdixZX6x7e-ZtXXH1YjZC-PehUFkLOA" else None

def send_telegram(message):
    if bot:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message)
        except:
            pass

# --- Danh sách nguồn tin ---
SOURCES = {
    "cafef": {"url": "https://cafef.vn/du-an.chn", "name": "CafeF"},
    "vietstock": {"url": "https://vietstock.vn/du-an.htm", "name": "Vietstock"},
    "vnexpress": {"url": "https://vnexpress.net/kinh-doanh/du-an", "name": "VnExpress"},
    "baodautu": {"url": "https://baodautu.vn/du-an", "name": "Báo Đầu Tư"},
    "thanhnien": {"url": "https://thanhnien.vn/kinh-doanh/du-an", "name": "Thanh Niên"},
}

KEYWORDS = ["thầu", "trúng thầu", "giao đất", "giao mặt bằng", "Thủ Thiêm", "dự án", "hạ tầng", "đầu tư công", "BT", "BOT", "PPP", "quy hoạch"]

# Danh sách cổ phiếu nhạy tin dự án
STOCK_MAPPING = {
    "CII": ["CII", "CII Corp", "Hạ tầng Kỹ thuật"],
    "DIG": ["DIG", "Đầu tư Phát triển"],
    "KBC": ["KBC", "Kinh Bắc"],
    "NLG": ["NLG", "Nam Long"],
    "LCG": ["LCG"],
    "HBC": ["HBC", "Hòa Bình"],
    "HT1": ["HT1"],
    "VCG": ["VCG", "Vinaconex"],
    "PC1": ["PC1"],
    "BCG": ["BCG", "Bamboo Capital"],
}

# ================== CRAWLER ==================
def crawl_source(source_name, source_info):
    try:
        r = requests.get(source_info["url"], timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')
        articles = []

        # CafeF
        if source_name == "cafef":
            for item in soup.select(".box-category-item"):
                title_tag = item.select_one(".box-category-title a")
                if title_tag and any(kw in title_tag.text.lower() for kw in KEYWORDS):
                    articles.append({
                        "title": title_tag.text.strip(),
                        "link": "https://cafef.vn" + title_tag['href'],
                        "source": source_info["name"],
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        # Thêm logic cho các nguồn khác (tương tự)
        # ... (có thể mở rộng)

        return articles
    except Exception as e:
        st.warning(f"Lỗi crawl {source_info['name']}: {e}")
        return []

# ================== AI ANALYZER ==================

def analyze_with_ai(title, link):
    # Khởi tạo model
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json", # Ép model trả về JSON
        }
    )

    prompt = f"""
    Bạn là một chuyên gia phân tích chứng khoán Việt Nam. 
    Hãy phân tích tin tức dưới đây và trả lời theo đúng định dạng JSON yêu cầu.
    Lưu ý: "related_stocks" phải là các mã cổ phiếu đang niêm yết trên sàn HOSE, HNX hoặc UPCoM.

    Định dạng JSON:
    {{
        "related_stocks": ["MÃ 1", "MÃ 2"],
        "event_score": (Thang điểm từ 1-10 về mức độ quan trọng),
        "summary": "Tóm tắt ngắn gọn trong 1 câu",
        "impact": "Tích cực/Tiêu cực/Trung tính và lý do ngắn gọn"
    }}

    Tiêu đề tin tức: {title}
    Link chi tiết: {link}
    """

    try:
        # Gọi API
        response = model.generate_content(prompt)
        
        # Parse kết quả từ text sang dictionary
        result = json.loads(response.text)
        return result

    except Exception as e:
        print(f"Lỗi khi gọi Gemini API: {e}")
        return {
            "related_stocks": [],
            "event_score": 0,
            "summary": "Không thể phân tích tin tức",
            "impact": "N/A"
        }

# ================== STREAMLIT UI ==================
st.sidebar.header("⚙️ Cài đặt")
selected_sources = st.sidebar.multiselect("Chọn nguồn tin", list(SOURCES.keys()), default=list(SOURCES.keys()))
interval = st.sidebar.slider("Thời gian quét (phút)", 5, 30, 10)

if st.button("🚀 Bắt đầu quét tin tức", type="primary"):
    with st.spinner("Đang quét các nguồn tin..."):
        all_articles = []
        for src_name, src_info in SOURCES.items():
            if src_name in selected_sources:
                articles = crawl_source(src_name, src_info)
                all_articles.extend(articles)

        recommendations = []
        for art in all_articles:
            ai_result = analyze_with_ai(art["title"], art["link"])
            if ai_result["related_stocks"]:
                for stock in ai_result["related_stocks"]:
                    recommendations.append({
                        "Thời gian": art["time"],
                        "Tiêu đề": art["title"],
                        "Nguồn": art["source"],
                        "Link": art["link"],
                        "Cổ phiếu": stock,
                        "Mức độ": ai_result["event_score"],
                        "Tóm tắt": ai_result["summary"]
                    })

        if recommendations:
            df = pd.DataFrame(recommendations)
            df = df.sort_values(by="Mức độ", ascending=False)
            
            st.success(f"🔥 Phát hiện {len(df)} tin tức quan trọng!")
            st.dataframe(df, use_container_width=True)

            # Gửi Telegram
            if bot:
                for _, row in df.head(5).iterrows():
                    msg = f"🔥 Tin nóng!\n{row['Tiêu đề']}\nCổ phiếu: {row['Cổ phiếu']}\nMức độ: {row['Mức độ']}/10\nLink: {row['Link']}"
                    send_telegram(msg)

            # Xuất Excel
            filename = f"Event_Scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            df.to_excel(filename, index=False)
            with open(filename, "rb") as f:
                st.download_button("📥 Tải file Excel", f, filename)
        else:
            st.info("Không phát hiện tin quan trọng trong lần quét này.")

st.caption("Event Scanner Pro v2.0 | Tự động quét tin dự án - thầu - giao đất")
