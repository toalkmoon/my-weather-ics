import os
import json
import urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler

API_KEY = os.environ.get("QWEATHER_KEY", "")
LOCATION = os.environ.get("LOCATION_ID", "101210606")


def get_weather_data():
    if not API_KEY:
        raise Exception("未检测到环境变量 QWEATHER_KEY，请先在 Vercel 中配置。")

    hosts = [
        "https://devapi.qweather.com",
        "https://api.qweather.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    last_error = ""
    for host in hosts:
        url = f"{host}/v7/weather/7d?location={LOCATION}&key={API_KEY}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode('utf-8'))
                
                if "error" in res and res.get("error", {}).get("title") == "Invalid Host":
                    last_error = f"{host} 域名不匹配"
                    continue
                
                code = res.get("code")
                if code == "200":
                    daily = res.get("daily", [])
                    if daily:
                        return daily
                    raise Exception("返回的天气数据为空")
                else:
                    raise Exception(f"和风天气报错 [{code}]: {res}")
        except Exception as e:
            last_error = str(e)

    raise Exception(f"请求失败，请检查凭据或限制。详情: {last_error}")


def generate_ics_text(daily_data):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//My Vercel Weather Calendar//CN",
        "X-WR-CALNAME:每日天气",
        "X-WR-TIMEZONE:Asia/Shanghai"
    ]

    for day in daily_data:
        date_str = day['fxDate']  # YYYY-MM-DD
        dtstart = date_str.replace("-", "")
        
        # 全天日程的结束时间为下一天的 0 点
        dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
        dtend = (dt_obj + timedelta(days=1)).strftime("%Y%m%d")

        text_day = day.get('textDay', '')
        text_night = day.get('textNight', '')
        temp_max = day.get('tempMax', '')
        temp_min = day.get('tempMin', '')
        precip = day.get('precip', '')
        wind_dir = day.get('windDirDay', '')
        wind_scale = day.get('windScaleDay', '')
        humidity = day.get('humidity', '')

        summary = f"⛅ {text_day} {temp_min}°C ~ {temp_max}°C"
        description = (
            f"白天天气: {text_day}\\n"
            f"夜间天气: {text_night}\\n"
            f"最高温度: {temp_max}°C / 最低温: {temp_min}°C\\n"
            f"降水量: {precip} mm\\n"
            f"风向风力: {wind_dir} {wind_scale}级\\n"
            f"相对湿度: {humidity}%"
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            daily_data = get_weather_data()
            ics_content = generate_ics_text(daily_data)

            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Cache-Control', 's-maxage=3600, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(ics_content.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Weather Calendar Error: {str(e)}".encode('utf-8'))
