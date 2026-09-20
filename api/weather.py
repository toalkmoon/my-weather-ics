import os
import time
import json
import gzip
import urllib.request
import jwt  # 需要安装 pip install cryptography PyJWT

# ==================== 1. 从环境变量读取和风天气凭据配置 ====================
API_HOST = os.getenv("QWEATHER_API_HOST", "https://n85khxxf87.re.qweatherapi.com")

DEVELOPER_ID = os.getenv("QWEATHER_DEVELOPER_ID", "")
PROJECT_ID = os.getenv("QWEATHER_PROJECT_ID", "")
KEY_ID = os.getenv("QWEATHER_KEY_ID", "")
RAW_PRIVATE_KEY = os.getenv("QWEATHER_PRIVATE_KEY", "")

# ==================== 2. 经纬度设置 ====================
LATITUDE = os.getenv("LATITUDE", "28.85")      # 仙居纬度
LONGITUDE = os.getenv("LONGITUDE", "120.73")  # 仙居经度
FORECAST_DAYS = os.getenv("FORECAST_DAYS", "7")  # 预报天数


# ==================== 3. 规范化私钥与动态生成 JWT Token ====================
def format_private_key(raw_key):
    """清理环境变量中可能传入的杂质，重新格式化为标准 PEM 格式"""
    clean = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip()
    clean = "".join(clean.split())
    lines = [clean[i:i+64] for i in range(0, len(clean), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----"


def generate_jwt_token():
    if not RAW_PRIVATE_KEY or not DEVELOPER_ID:
        raise ValueError("缺少必要的环境变量配置，请检查 QWEATHER_DEVELOPER_ID 与 QWEATHER_PRIVATE_KEY！")
    
    formatted_key = format_private_key(RAW_PRIVATE_KEY)
    now = int(time.time())
    
    payload = {
        'iss': DEVELOPER_ID,
        'sub': PROJECT_ID,
        'iat': now - 30,     # 签发时间（提前30秒防止与服务器时钟差异）
        'exp': now + 3600    # 1小时后过期
    }
    headers = {
        'alg': 'EdDSA',
        'kid': KEY_ID
    }
    return jwt.encode(payload, formatted_key, algorithm='EdDSA', headers=headers)


# ==================== 4. 请求天气 API 主逻辑 ====================
def get_weather():
    try:
        token = generate_jwt_token()
    except Exception as e:
        print(f"❌ JWT Token 生成失败: {e}")
        return None

    url = f"{API_HOST}/weather/v1/daily/{LATITUDE}/{LONGITUDE}?days={FORECAST_DAYS}&localTime=true"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Encoding": "gzip"
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_encoding = resp.info().get('Content-Encoding')
            raw_data = resp.read()

            # 解压 gzip 响应数据
            if content_encoding == 'gzip' or raw_data[:2] == b'\x1f\x8b':
                raw_data = gzip.decompress(raw_data)

            res = json.loads(raw_data.decode('utf-8'))
            return res

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 请求错误: {e.code} ({e.reason})")
    except Exception as e:
        print(f"❌ 请求发生异常: {str(e)}")
    
    return None


if __name__ == "__main__":
    data = get_weather()
    if data and "days" in data:
        print("✅ 成功获取到天气数据！")
        for day in data["days"]:
            print(f"日期: {day.get('forecastStartTime', '')[:10]} | 白天: {day.get('daytime', {}).get('condition', {}).get('text')} | 气温: {day.get('temperatureMin', {}).get('value')}°C ~ {day.get('temperatureMax', {}).get('value')}°C")
