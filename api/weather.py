import os
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event
from http.server import BaseHTTPRequestHandler

# 和风天气 API 配置（也可以从环境变量获取）
API_KEY = os.environ.get("QWEATHER_KEY", "你的和风天气KEY")
LOCATION = os.environ.get("LOCATION_ID", "101010100")  # 默认北京，按需修改


def get_weather_data():
    # 调取 7 天天气预报接口
    url = f"https://devapi.qweather.com/v7/weather/7d?location={LOCATION}&key={API_KEY}"
    res = requests.get(url).json()
    return res.get("daily", [])


def generate_ics(daily_data):
    cal = Calendar()
    cal.add('prodid', '-//My Vercel Weather Calendar//CN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', '每日天气')
    cal.add('x-wr-timezone', 'Asia/Shanghai')

    for day in daily_data:
        date_str = day['fxDate']  # 格式如 2026-09-20
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # 提取关键信息
        text_day = day['textDay']  # 白天天气（如 晴）
        temp_max = day['tempMax']  # 最高温
        temp_min = day['tempMin']  # 最低温
        precip = day['precip']  # 降水量
        wind_dir = day['windDirDay']  # 白天风向

        # 拼接标题与详细描述
        summary = f"⛅ {text_day} {temp_min}°C ~ {temp_max}°C"
        description = (
            f"白天天气: {text_day}\n"
            f"夜间天气: {day['textNight']}\n"
            f"最高温度: {temp_max}°C / 最低温: {temp_min}°C\n"
            f"降水量: {precip} mm\n"
            f"风向风力: {wind_dir} {day['windScaleDay']}级\n"
            f"相对湿度: {day['humidity']}%"
        )

        event = Event()
        event.add('summary', summary)
        event.add('description', description)
        event.add('dtstart', event_date)
        event.add('dtend', event_date + timedelta(days=1))
        event.add('transp', 'TRANSPARENT')  # 设为“空闲”，不标记为忙碌

        cal.add_component(event)

    return cal.to_ical()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            daily_data = get_weather_data()
            ics_content = generate_ics(daily_data)

            # 返回标准的 iCalendar 格式内容
            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Cache-Control', 's-maxage=3600, stale-while-revalidate')  # 设置 1 小时缓存
            self.end_headers()
            self.wfile.write(ics_content)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Error generating calendar: {str(e)}".encode('utf-8'))