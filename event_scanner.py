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

# Cấu hình Gemini (sửa model name)
GEMINI_KEY = "AIzaSyBcCfM3ckkMRImYzMdHwlGTvJG3xvoLbFs"

try:
    genai.configure(api_key=GEMINI_KEY)
    # Sử dụng model ổn định nhất hiện nay
    model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp')   # ← ĐÃ SỬA Ở ĐÂY
    st.success("✅ Kết nối Gemini AI thành công (gemini-2.0-flash-thinking-exp)")
except Exception as e:
    st.error(f"Lỗi kết nối Gemini: {e}")
    model = None

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
    if not model:
        return {
            "related_stocks": [],
            "sector": "Khác",
            "event_score": 0,
            "summary": "Gemini không khả dụng",
            "impact": "Thấp",
            "recommendation": "KHÔNG ẢNH HƯỞNG"
        }

    prompt = f"""
    Bạn là chuyên gia phân tích chứng khoán Việt Nam, chuyên phát hiện tin tức ảnh hưởng đến cổ phiếu.

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
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Xử lý trường hợp Gemini trả về có ```json
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1]

        # Convert string thành dict
        import json
        result = json.loads(text)

        return result

    except Exception as e:
        st.warning(f"Lỗi phân tích Gemini: {e}")
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        }
        r = requests.get(source_info["url"], timeout=15, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        articles = []

        if source_name == "cafef":
            # Thử nhiều selector khác nhau
            items = soup.select(".box-category-item") or soup.select(".cate-news-item") or soup.select("article")
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
        return articles[:10]

    except Exception as e:
        st.error(f"Lỗi crawl {source_info['name']}: {str(e)}")
        return []

# ====================== STREAMLIT UI ======================
st.sidebar.header("⚙️ Cài đặt quét tin")

if st.sidebar.button("🔍 Test All Sources"):
    with st.spinner("Đang test tất cả nguồn..."):
        total = 0
        for src_name in SOURCES:
            articles = crawl_source(src_name, SOURCES[src_name])
            total += len(articles)
            st.write(f"{SOURCES[src_name]['name']}: {len(articles)} tin")
        st.success(f"Tổng cộng thu thập được {total} tin từ tất cả nguồn")

col1, col2 = st.columns(2)

with col1:
    if st.button("🧪 Test Crawler (CafeF only)", type="secondary"):
        with st.spinner("Đang test crawler CafeF..."):
            test_articles = crawl_source("cafef", SOURCES["cafef"])
            if test_articles:
                st.success(f"✅ Thành công! Thu thập được {len(test_articles)} tin từ CafeF")
                st.write("Một số tiêu đề mẫu:")
                for art in test_articles[:5]:
                    st.write(f"• {art['title']}")
            else:
                st.error("❌ Không thu thập được tin nào từ CafeF. Có thể trang đã thay đổi cấu trúc.")

with col2:
    if st.button("🔍 Test Gemini AI", type="secondary"):
        test_title = "TP.HCM giao mặt bằng sạch dự án Thủ Thiêm cho CII"
        test_link = "https://example.com"
        result = analyze_with_gemini(test_title, test_link, "Test")
        st.write("Kết quả phân tích Gemini:")
        st.json(result)

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
