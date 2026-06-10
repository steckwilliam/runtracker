STORM_CODES = {95, 96, 99}


def weather_code_display(code):
    code = int(code) if code is not None else 0
    if code in (0,):
        return {"icon": "☀️", "label": "Clear"}
    if code in (1, 2):
        return {"icon": "⛅", "label": "Partly cloudy"}
    if code == 3:
        return {"icon": "☁️", "label": "Cloudy"}
    if code in (45, 48):
        return {"icon": "🌫️", "label": "Fog"}
    if code in (51, 53, 55, 56, 57):
        return {"icon": "🌦️", "label": "Drizzle"}
    if code in (61, 63, 65, 66, 67):
        return {"icon": "🌧️", "label": "Rain"}
    if code in (80, 81, 82):
        return {"icon": "🌧️", "label": "Showers"}
    if code in (71, 73, 75, 77, 85, 86):
        return {"icon": "🌨️", "label": "Snow"}
    if code in STORM_CODES:
        return {"icon": "⛈️", "label": "Storm"}
    return {"icon": "⛅", "label": "Partly cloudy"}
