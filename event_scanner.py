import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import telebot
import json

st.set_page_config(page_title="Event Scanner Pro", layout="wide", page_icon="🔥")
st.title("🔥 Event Scanner Pro - Phát hiện tin dự án & thầu")

# ====================== GROK API KEY ======================
st.sidebar.header("🔑 Grok API Key (xAI)")
grok_key = st.sidebar.text_input(
    "Nhập Grok API Key",
    value="",
    type="password",
    help="Paste key từ https://console.x.ai"
)

if grok_key:
    st.sidebar.success("✅ Grok API Key đã được nhập")
else:
    st.sidebar.warning("⚠️ Chưa có Grok API Key")

# --- Telegram (giữ nguyên) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "8516741675:AAE8rdixZX6x7e-ZtXXH1YjZC-PehUFkLOA")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "1247850754")
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def send_telegram(msg):
    if bot:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, msg)
        except:
            pass

# ====================== NGUỒN CRAWLER ======================
SOURCES = {
    "cafef": {"url": "https://cafef.vn/du-an.chn", "name": "CafeF"},
    "vietstock": {"url": "https://vietstock.vn/du-an.htm", "name": "Vietstock"},
    "vnexpress": {"url": "https://vnexpress.net/kinh-doanh/du-an", "name": "VnExpress"},
    "baodautu": {"url": "https://baodautu.vn/du-an", "name": "Báo Đầu Tư"},
    "thanhnien": {"url": "https://thanhnien.vn/kinh-doanh/du-an", "name": "Thanh Niên"},
    "xamvn": {"url": "https://xamvn.com/forums/chung-khoan.12/", "name": "Xamvn Forum"},
}

STOCK_BY_SECTOR = {
    "Bất động sản - Hạ tầng": ["CII", "DIG", "KBC", "NLG", "LCG", "BCG", "VCG"],
    "Xây dựng": ["HBC", "PC1", "CTD", "HHV"],
    "Thép & Vật liệu": ["HPG", "HSG", "NKG"],
    "Điện - Năng lượng": ["REE", "GEG", "PC1", "POW", "GAS"],
    "Ngân hàng": ["VCB", "BID", "CTG", "STB", "TCB"]
}

KEYWORDS = ["thầu", "trúng thầu", "giao đất", "giao mặt bằng", "Thủ Thiêm", "dự án", "hạ tầng", "đầu tư công", "BT", "BOT", "PPP", "quy hoạch"]

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
        return []

# ====================== TEST CRAWLER ======================
if st.sidebar.button("🧪 Test Crawler (CafeF only)"):
    with st.spinner("Đang test crawler CafeF..."):
        test_articles = crawl_source("cafef", SOURCES["cafef"])
        if test_articles:
            st.success(f"✅ Thành công! Thu thập được {len(test_articles)} tin từ CafeF")
            st.write("Một số tiêu đề mẫu:")
            for art in test_articles[:6]:
                st.write(f"• {art['title']}")
        else:
            st.error("❌ Không thu thập được tin nào từ CafeF.")

# ====================== TEST GROK API ======================
if st.sidebar.button("🔍 Test Grok API"):
    if not grok_key:
        st.error("Vui lòng nhập Grok API Key trước")
    else:
        with st.spinner("Đang test Grok API..."):
            try:
                response = requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {grok_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [{"role": "user", "content": "Test connection. Reply with 'Grok is working'"}],
                        "max_tokens": 50
                    },
                    timeout=15
                )
                if response.status_code == 200:
                    st.success("✅ Grok API hoạt động tốt!")
                    st.json(response.json())
                else:
                    st.error(f"❌ Lỗi Grok API: {response.status_code}")
            except Exception as e:
                st.error(f"Lỗi kết nối Grok: {e}")

# ====================== MAIN UI ======================
st.sidebar.header("⚙️ Cài đặt quét tin")
selected_sources = st.sidebar.multiselect(
    "Chọn nguồn tin", 
    options=list(SOURCES.keys()), 
    default=list(SOURCES.keys()),
    format_func=lambda x: SOURCES[x]["name"]
)

if st.button("🚀 Bắt đầu quét tin tức", type="primary"):
    with st.spinner("Đang quét tin từ nhiều nguồn..."):
        all_articles = []
        for src_name in selected_sources:
            articles = crawl_source(src_name, SOURCES[src_name])
            all_articles.extend(articles)

        st.success(f"Đã quét xong {len(all_articles)} tin từ các nguồn.")

        # Phần phân tích bằng Grok sẽ được thêm sau nếu cần
        st.info("Chức năng phân tích Grok đang được hoàn thiện. Hiện tại tool đã quét được tin.")

st.caption("Event Scanner Pro v2.4 | Tích hợp Grok AI | Test Crawler & Test API đã có")
