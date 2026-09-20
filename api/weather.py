import os
import json
import urllib.request
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vDate
from http.server import BaseHTTPRequestHandler

# 环境变量配置
API_KEY = os.environ.get("QWEATHER_KEY", "")
LOCATION = os.environ.get("LOCATION_ID", "101210606")


def get_weather_data():
    if not API_KEY:
        raise Exception("未设置 QWEATHER_KEY 环境变量，请在 Vercel 控制台中添加。")

    # 尝试开发版与商业版两个接口域名
    hosts = [
        "https://devapi.qweather.com",
        "https://api.qweather.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    last_err = ""
    for host in hosts:
        url = f"{host}/v7/weather/7d?location={LOCATION}&key={API_KEY}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode('utf-8'))
                
                # 如果遇到域名不匹配，尝试下一个域名
                if "error" in res and res.get("error", {}).get("title") == "Invalid Host":
                    last_err = f"{host} 无效域名"
                    continue
                
                code = res.get("code")
                if code == "200":
                    daily = res.get("daily", [])
                    if daily:
                        return daily
                    raise Exception("API 返回天气数组为空")
                else:
                    raise Exception(f"和风天气报错 [{code}]: {res}")
        except Exception as e:
            last_err = str(e)

    raise Exception(f"请求天气接口失败，请检查 Key 权限或限制。详情: {last_err}")


def generate_ics(daily_data):
    cal = Calendar()
    cal.add('prodid', '-//My Vercel Weather Calendar//CN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', '每日天气')
    cal.add('x-wr-timezone', 'Asia/Shanghai')

    for day in daily_data:
        date_str = day['fxDate']
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

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
            f"白天天气: {text_day}\n"
            f"夜间天气: {text_night}\n"
            f"最高温度: {temp_max}°C / 最低温: {temp_min}°C\n"
            f"降水量: {precip} mm\n"
            f"风向风力: {wind_dir} {wind_scale}级\n"
            f"相对湿度: {humidity}%"
        )

        event = Event()
        event.add('summary', summary)
        event.add('description', description)
        
        event.add('dtstart', vDate(event_date))
        event.add('dtend', vDate(event_date + timedelta(days=1)))
        event.add('transp', 'TRANSPARENT')

        cal.add_component(event)

    return cal.to_ical()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            daily_data = get_weather_data()
            ics_content = generate_ics(daily_data)

            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Cache-Control', 's-maxage=3600, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(ics_content)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Weather Calendar Error: {str(e)}".encode('utf-8'))
