import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
import json

# ====================== CẤU HÌNH ======================
SOURCES = {
    "cafef": "https://cafef.vn",
    "vietstock": "https://vietstock.vn",
    "vnexpress": "https://vnexpress.net",
    "baodautu": "https://baodautu.vn",
    "thanhnien": "https://thanhnien.vn"
}

KEYWORDS = [
    "thầu", "trúng thầu", "giao đất", "giao mặt bằng", "Thủ Thiêm", 
    "dự án", "hạ tầng", "đầu tư công", "BT", "BOT", "PPP"
]

# Danh sách công ty bất động sản - xây dựng nhạy tin tức dự án
STOCK_MAPPING = {
    "CII": ["CII", "CII Corp", "CTCP Đầu tư Hạ tầng Kỹ thuật TP.HCM"],
    "DIG": ["DIG", "Đầu tư Phát triển Xây dựng"],
    "KBC": ["KBC", "Kinh Bắc City"],
    "NLG": ["NLG", "Nam Long Group"],
    "LCG": ["LCG", "LCG Corp"],
    "HBC": ["HBC", "Hòa Bình"],
    "HT1": ["HT1", "Xi măng Hà Tiên"],
    "VCG": ["VCG", "Vinaconex"],
    # Thêm nhiều mã khác nếu cần
}

# ====================== CRAWLER ======================
def crawl_cafef():
    url = "https://cafef.vn/du-an.chn"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        articles = []
        for item in soup.select(".box-category-item"):
            title = item.select_one(".box-category-title a")
            if title and any(kw in title.text.lower() for kw in KEYWORDS):
                articles.append({
                    "title": title.text.strip(),
                    "link": "https://cafef.vn" + title['href'],
                    "source": "CafeF",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
        return articles
    except:
        return []

# Thêm crawler cho các nguồn khác (Vietstock, VnExpress...) tương tự

# ====================== EVENT DETECTOR ======================
def detect_event(text):
    score = 0
    related_stocks = []
    
    text_lower = text.lower()
    
    for stock, keywords in STOCK_MAPPING.items():
        if any(kw.lower() in text_lower for kw in keywords):
            related_stocks.append(stock)
            score += 3  # Điểm cho mỗi cổ phiếu liên quan
    
    if any(kw in text_lower for kw in ["trúng thầu", "giao đất", "giao mặt bằng", "thủ thiêm"]):
        score += 5
    
    return {
        "event_score": score,
        "related_stocks": related_stocks,
        "is_important": score >= 6
    }

# ====================== MAIN SCANNER ======================
def run_scanner():
    print(f"[{datetime.now()}] Đang quét tin tức dự án...")

    all_articles = []
    all_articles.extend(crawl_cafef())
    # Thêm crawl các nguồn khác ở đây

    recommendations = []

    for article in all_articles:
        result = detect_event(article["title"])
        if result["is_important"] and result["related_stocks"]:
            recommendations.append({
                "Thời gian": article["time"],
                "Tiêu đề": article["title"],
                "Nguồn": article["source"],
                "Link": article["link"],
                "Cổ phiếu liên quan": ", ".join(result["related_stocks"]),
                "Mức độ quan trọng": result["event_score"]
            })

    if recommendations:
        df = pd.DataFrame(recommendations)
        df = df.sort_values(by="Mức độ quan trọng", ascending=False)
        
        print("\n🔥 Tin tức quan trọng phát hiện được:")
        print(df.to_string(index=False))
        
        # Lưu file
        df.to_excel(f"Event_Scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx", index=False)
        print(f"\nĐã lưu file Excel: Event_Scanner_*.xlsx")
    else:
        print("Không phát hiện tin tức quan trọng trong lần quét này.")

# Chạy định kỳ
if __name__ == "__main__":
    while True:
        run_scanner()
        print("Đang chờ 10 phút để quét lần tiếp theo...\n")
        time.sleep(600)  # Quét mỗi 10 phút
