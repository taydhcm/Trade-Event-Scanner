import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import telebot
import json

# ====================== CẤU HÌNH ======================
st.set_page_config(page_title="Event Scanner Pro", layout="wide", page_icon="🔥")
st.title("🔥 Event Scanner Pro - Phát hiện tin dự án & thầu")

# ====================== ĐỌC API KEY TỪ SECRETS.TOML ======================
try:
    GROK_API_KEY = st.secrets["GROK_API_KEY"]
    st.sidebar.success("✅ Đã load Grok API Key từ secrets.toml")
except Exception:
    st.sidebar.error("❌ Không tìm thấy GROK_API_KEY trong secrets.toml")
    GROK_API_KEY = None

# --- Telegram (tùy chọn) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
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

# ====================== GỌI GROK API ======================
def call_grok(prompt):
    if not GROK_API_KEY:
        st.error("Grok API Key chưa được cấu hình trong secrets.toml!")
        return None

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-beta",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 800
            },
            timeout=20
        )

        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        else:
            st.warning(f"Grok API lỗi: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Lỗi kết nối Grok: {e}")
        return None

# ====================== PHÂN TÍCH BẰNG GROK ======================
def analyze_with_grok(title, link, source):
    prompt = f"""
    Bạn là chuyên gia phân tích chứng khoán Việt Nam. 
    Hãy phân tích tin tức sau và trả về **chỉ JSON thuần túy**, không giải thích thêm:

    Tiêu đề: {title}
    Nguồn: {source}
    Link: {link}

    Trả về đúng định dạng JSON sau:
    {{
      "related_stocks": ["CII", "DIG", "KBC"],
      "sector": "Bất động sản - Hạ tầng",
      "event_score": 8,
      "summary": "Tóm tắt ngắn gọn bằng tiếng Việt",
      "impact": "Cao / Trung bình / Thấp",
      "recommendation": "MUA / THEO DÕI / KHÔNG ẢNH HƯỞNG"
    }}
    """

    try:
        response_text = call_grok(prompt)
        if not response_text:
            return fallback_result()

        # Xử lý JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1]

        result = json.loads(response_text.strip())
        return result

    except Exception as e:
        st.warning(f"Lỗi phân tích Grok: {e}")
        return fallback_result()

def fallback_result():
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
            items = soup.select(".box-category-item") or soup.select("article")
            for item in items:
                title = item.select_one("a") or item.select_one(".title a")
                if title and title.text and any(kw in title.text.lower() for kw in KEYWORDS):
                    link = title.get('href', '')
                    if not link.startswith('http'):
                        link = "https://cafef.vn" + link
                    articles.append({
                        "title": title.text.strip(),
                        "link": link,
                        "source": source_info["name"],
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        return articles[:12]
    except Exception as e:
        st.warning(f"Lỗi crawl {source_info['name']}: {str(e)}")
        return []

# ====================== STREAMLIT UI ======================
st.sidebar.header("⚙️ Cài đặt quét tin")

selected_sources = st.sidebar.multiselect(
    "Chọn nguồn tin", 
    options=list(SOURCES.keys()), 
    default=list(SOURCES.keys()),
    format_func=lambda x: SOURCES[x]["name"]
)

if st.button("🚀 Bắt đầu quét tin tức", type="primary"):
    with st.spinner("Đang quét tin từ nhiều nguồn và phân tích bằng Grok..."):
        all_articles = []
        for src_name in selected_sources:
            articles = crawl_source(src_name, SOURCES[src_name])
            all_articles.extend(articles)

        results = []
        for art in all_articles:
            ai_result = analyze_with_grok(art["title"], art["link"], art["source"])
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

st.caption("Event Scanner Pro v2.4 | Tích hợp Grok AI (xAI) qua secrets.toml | Tự động quét tin dự án - thầu - giao đất")
