import os
import time
import json
import gzip
import urllib.request
import jwt
from http.server import BaseHTTPRequestHandler

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


# ==================== 2. Vercel 必须的 HTTP 入口 Handler ====================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            weather_data = fetch_weather_data()
            
            # 返回 200 成功与 JSON 数据
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            
            response_body = json.dumps(weather_data, ensure_ascii=False)
            self.wfile.write(response_body.encode('utf-8'))

        except Exception as e:
            # 捕获异常，输出具体的报错信息，便于定位
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            
            error_body = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(error_body.encode('utf-8'))
