import os
import time
import json
import gzip
import urllib.request
import jwt
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from icalendar import Calendar, Event

# ==================== 1. 从环境变量获取配置 ====================
API_HOST = os.getenv("QWEATHER_API_HOST", "https://n85khxxf87.re.qweatherapi.com")
DEVELOPER_ID = os.getenv("QWEATHER_DEVELOPER_ID", "")
PROJECT_ID = os.getenv("QWEATHER_PROJECT_ID", "")
KEY_ID = os.getenv("QWEATHER_KEY_ID", "")
RAW_PRIVATE_KEY = os.getenv("QWEATHER_PRIVATE_KEY", "")

LATITUDE = os.getenv("LATITUDE", "28.85")      # 仙居纬度
LONGITUDE = os.getenv("LONGITUDE", "120.73")  # 仙居经度
FORECAST_DAYS = os.getenv("FORECAST_DAYS", "7")


def format_private_key(raw_key):
    """规范化处理私钥格式"""
    clean = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip()
    clean = "".join(clean.split())
    lines = [clean[i:i+64] for i in range(0, len(clean), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----"


def generate_jwt_token():
    if not RAW_PRIVATE_KEY or not DEVELOPER_ID:
        raise ValueError("Missing QWEATHER_DEVELOPER_ID or QWEATHER_PRIVATE_KEY environment variables.")
    
    formatted_key = format_private_key(RAW_PRIVATE_KEY)
    now = int(time.time())
    
    payload = {
        'iss': DEVELOPER_ID,
        'sub': PROJECT_ID,
        'iat': now - 30,
        'exp': now + 3600
    }
    headers = {
        'alg': 'EdDSA',
        'kid': KEY_ID
    }
    return jwt.encode(payload, formatted_key, algorithm='EdDSA', headers=headers)


def fetch_weather_data():
    token = generate_jwt_token()
    url = f"{API_HOST}/weather/v1/daily/{LATITUDE}/{LONGITUDE}?days={FORECAST_DAYS}&localTime=true"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Encoding": "gzip"
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        content_encoding = resp.info().get('Content-Encoding')
        raw_data = resp.read()

        if content_encoding == 'gzip' or raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)

        return json.loads(raw_data.decode('utf-8'))


def generate_ics(weather_data):
    """将和风天气 JSON 转换为 ICS 文本格式"""
    cal = Calendar()
    cal.add('prodid', '-//My Weather ICS//NONSGML v1.0//EN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', '仙居天气预报')  # 苹果日历中显示的订阅名称
    cal.add('x-wr-timezone', 'Asia/Shanghai')

    daily_forecasts = weather_data.get('daily', [])
    for day in daily_forecasts:
        event = Event()
        
        # 解析预报日期 (格式如: 2026-09-20)
        fx_date = datetime.strptime(day['fxDate'], '%Y-%m-%d').date()
        
        # 预报参数提取
        cond_day = day.get('textDay', '未知')
        cond_night = day.get('textNight', '')
        temp_min = day.get('tempMin', '')
        temp_max = day.get('tempMax', '')
        wind_dir = day.get('windDirDay', '')
        wind_scale = day.get('windScaleDay', '')
        precip = day.get('precip', '0.0')

        # 拼接日程标题：天气状况与最高/最低气温
        summary = f"🌤 {cond_day} {temp_min}°C ~ {temp_max}°C"
        
        # 拼接详细描述信息
        description = (
            f"日间天气：{cond_day}\n"
            f"夜间天气：{cond_night}\n"
            f"气温：{temp_min}°C ~ {temp_max}°C\n"
            f"风向风力：{wind_dir} {wind_scale}级\n"
            f"降水量：{precip} mm"
        )

        event.add('summary', summary)
        event.add('description', description)
        event.add('dtstart', fx_date)
        # 苹果全天日程在 iCalendar 规范中结束日期需为次日
        event.add('dtend', fx_date + timedelta(days=1))
        
        cal.add_component(event)

    return cal.to_ical()


# ==================== 2. Vercel 必须的 HTTP 入口 Handler ====================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            weather_data = fetch_weather_data()
            ics_bytes = generate_ics(weather_data)
            
            # 返回 200 成功与 text/calendar 响应头（让苹果日历能够正确识别）
            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            
            self.wfile.write(ics_bytes)

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            
            error_body = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(error_body.encode('utf-8'))
