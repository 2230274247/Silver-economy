"""Fixed official endpoints, bounded responses, sanitized errors; never logs query keys."""

import logging
import math
import re
import uuid
from datetime import UTC, datetime

import httpx

from app.core.security import utc_now
from app.tasks.repository import stamp
from app.tasks.time_parse import ZONE

# httpx's INFO request logger includes URL query parameters. Amap authenticates there.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class MapFailure(Exception):
    def __init__(self, code):
        self.code = code


def text(value, limit=240):
    return value.strip()[:limit] if isinstance(value, str) else ""


def coordinate(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?,\s*-?\d+(?:\.\d+)?", value):
        raise ValueError("Invalid coordinate")
    lng, lat = map(float, value.split(","))
    if not math.isfinite(lng + lat) or not -180 <= lng <= 180 or not -90 <= lat <= 90:
        raise ValueError("Coordinate outside range")
    return f"{lng:.6f},{lat:.6f}"


def positive(value, maximum):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= maximum:
        raise ValueError("Invalid route measurement")
    return math.ceil(number)


class AmapProvider:
    name = "amap"

    def __init__(self, settings, transport=None):
        self.key = settings.amap_web_service_key.get_secret_value().strip()
        self.transport = transport

    def get(self, path, params):
        if not self.key:
            raise MapFailure("MAP_NOT_CONFIGURED")
        try:
            with httpx.Client(
                timeout=8, follow_redirects=False, transport=self.transport, trust_env=False
            ) as client:
                with client.stream(
                    "GET",
                    "https://restapi.amap.com" + path,
                    params={**params, "key": self.key, "output": "JSON"},
                ) as response:
                    if response.status_code != 200:
                        raise MapFailure("MAP_PROVIDER_ERROR")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 524288:
                            raise MapFailure("MAP_RESPONSE_FORMAT")
            import json

            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("status") != "1":
                raise MapFailure("MAP_PROVIDER_ERROR")
            return data
        except httpx.TimeoutException:
            raise MapFailure("MAP_TIMEOUT") from None
        except httpx.HTTPError:
            raise MapFailure("MAP_NETWORK_UNKNOWN") from None
        except (ValueError, TypeError):
            raise MapFailure("MAP_RESPONSE_FORMAT") from None

    def search(self, query, city, search_kind):
        address = search_kind == "address"
        data = self.get(
            "/v3/geocode/geo" if address else "/v3/place/text",
            {"address": query, "city": city}
            if address
            else {
                "keywords": query,
                "city": city,
                "citylimit": "true",
                "offset": 5,
                "page": 1,
                "extensions": "base",
            },
        )
        values = data.get("geocodes" if address else "pois", [])
        if not isinstance(values, list):
            raise MapFailure("MAP_RESPONSE_FORMAT")
        items = []
        for row in values[:20]:
            try:
                if not isinstance(row, dict):
                    continue
                level = text(row.get("level"), 40) if address else "兴趣点"
                if address and level in {"", "国家", "省", "市", "区县", "乡镇", "村庄", "未知"}:
                    continue  # Broad regions are not a verified visit address.
                name = text(row.get("formatted_address") if address else row.get("name"), 160)
                adcode = text(row.get("adcode"), 6)
                if not name or not re.fullmatch(r"\d{6}", adcode):
                    continue
                items.append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "address": text(
                            row.get("formatted_address") if address else row.get("address")
                        ),
                        "district": text(row.get("district") if address else row.get("pname"))
                        + text(row.get("cityname")),
                        "location": coordinate(row.get("location")),
                        "adcode": adcode,
                        "citycode": text(row.get("citycode"), 8),
                        "level": level,
                        "vendor_id": text(row.get("id"), 80),
                    }
                )
            except (ValueError, TypeError):
                continue
            if len(items) == 5:
                break
        return {"items": items}

    def route(self, origin, destination, mode):
        name = {
            "taxi": "driving",
            "driving": "driving",
            "walking": "walking",
            "cycling": "bicycling",
            "transit": "transit/integrated",
        }[mode]
        params = {
            "origin": origin["location"],
            "destination": destination["location"],
            "show_fields": "cost",
        }
        if mode == "transit":
            if not origin["citycode"] or not destination["citycode"]:
                raise MapFailure("MAP_CITY_REQUIRED")
            params.update(
                city1=origin["citycode"], city2=destination["citycode"], AlternativeRoute=1
            )
        data = self.get("/v5/direction/" + name, params)
        try:
            route = data["route"]
            choices = route["transits" if mode == "transit" else "paths"]
            if not choices:
                raise MapFailure("MAP_NO_ROUTE")
            chosen = choices[0]
            return {
                "distance_m": positive(chosen["distance"], 20000000),
                "duration_seconds": positive(chosen["cost"]["duration"], 604800),
                "transport": mode,
                "estimate_basis": "查询时条件估算，未来路况/班次可能变化；打车不含等车时间",
            }
        except (KeyError, IndexError, ValueError, TypeError):
            raise MapFailure("MAP_RESPONSE_FORMAT") from None

    def weather(self, destination, day):
        data = self.get(
            "/v3/weather/weatherInfo", {"city": destination["adcode"], "extensions": "all"}
        )
        try:
            forecasts = data["forecasts"]
            if not forecasts:
                return {"status": "unavailable", "reason": "MAP_NO_FORECAST"}
            forecast = forecasts[0]
            issued = datetime.strptime(forecast["reporttime"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=ZONE
            )
            age = utc_now().replace(tzinfo=UTC) - issued
            if text(forecast.get("adcode"), 6) != destination["adcode"]:
                raise ValueError("Wrong forecast area")
            if age.total_seconds() > 36 * 3600 or age.total_seconds() < -3600:
                return {"status": "unavailable", "reason": "MAP_STALE_WEATHER"}
            cast = next((c for c in forecast["casts"] if c.get("date") == day), None)
            if cast is None:
                return {"status": "unavailable", "reason": "MAP_OUT_OF_FORECAST"}
            daytime, nighttime = (
                text(cast.get("dayweather"), 40),
                text(cast.get("nightweather"), 40),
            )
            if not daytime or not nighttime:
                raise ValueError("Missing weather")
            return {
                "status": "available",
                "date": day,
                "city": text(forecast.get("city"), 80),
                "adcode": text(forecast.get("adcode"), 6),
                "reporttime": issued.isoformat(),
                "dayweather": daytime,
                "nightweather": nighttime,
                "umbrella_advice": "预报有雨雪，建议带伞并留意出行条件"
                if re.search("雨|雪|雹", daytime + nighttime)
                else "当前预报未提示雨雪，出门前请再留意天气",
            }
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise MapFailure("MAP_RESPONSE_FORMAT") from None


class MockMapProvider:
    name = "mock"

    def search(self, query, city, search_kind):
        return {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "name": f"Synthetic {query} · 候选{i + 1}",
                    "address": f"合成示例路{i + 1}号（非真实地址）",
                    "district": f"{city} · Synthetic",
                    "location": f"116.{400000 + i * 1000},39.900000",
                    "adcode": "110101",
                    "citycode": "010",
                    "level": "Synthetic",
                    "vendor_id": "",
                }
                for i in range(2)
            ]
        }

    def route(self, origin, destination, mode):
        return {
            "distance_m": 12000,
            "duration_seconds": 2100,
            "transport": mode,
            "estimate_basis": "Synthetic固定测试数据：12公里/35分钟，非实时车程",
        }

    def weather(self, destination, day):
        return {
            "status": "available",
            "date": day,
            "city": "Synthetic示例区域",
            "adcode": destination["adcode"],
            "reporttime": stamp(utc_now()),
            "dayweather": "小雨（Synthetic）",
            "nightweather": "多云（Synthetic）",
            "umbrella_advice": "Mock示例：建议带伞，非真实预报",
        }


def get_maps_provider(settings):
    if settings.maps_provider == "mock":
        return MockMapProvider()
    if (
        settings.maps_provider == "amap"
        and settings.amap_web_service_key.get_secret_value().strip()
    ):
        return AmapProvider(settings)
    raise MapFailure("MAP_NOT_CONFIGURED")
