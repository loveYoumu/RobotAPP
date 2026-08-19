import re

_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

def parse_robot_command(text):
    if "停止" in text or "停下" in text:
        return {"intent": "stop", "parameters": {}}
    if "灯" in text and any(word in text for word in ("打开", "开启", "开灯")):
        room = "客厅" if "客厅" in text else "厨房" if "厨房" in text else None
        return {"intent": "set_light", "parameters": {"room": room, "state": "on"}}
    if any(word in text for word in ("前往", "去", "到")) and any(place in text for place in ("厨房", "客厅", "卧室")):
        place = next(place for place in ("厨房", "客厅", "卧室") if place in text)
        return {"intent": "navigate", "parameters": {"destination": place}}
    if ("拿" in text or "取" in text) and "杯" in text:
        color = next((x for x in ("红色", "蓝色", "绿色") if x in text), None)
        destination = "桌子" if "桌" in text else None
        return {"intent": "pick_and_place", "parameters": {"object": "杯子", "color": color, "destination": destination}}
    if "转" in text or "走" in text or "移动" in text:
        direction = "left" if "左" in text else "right" if "右" in text else "forward" if "前" in text else "backward" if "后" in text else None
        match = re.search(r"([一二两三四五六七八九十0-9]+)米", text)
        distance = None
        if match:
            token = match.group(1)
            distance = int(token) if token.isdigit() else _NUM.get(token)
        return {"intent": "motion", "parameters": {"direction": direction, "distance_m": distance}}
    return {"intent": "unknown", "parameters": {}}