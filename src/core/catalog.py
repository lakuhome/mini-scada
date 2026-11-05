"""Register metadata. Bus and archive keep raw uint16 values."""

TAG_CATALOG = {
    "Boiler_Temp_01": {"register": 0, "title": "Температура котла", "unit": "°C", "divisor": 10},
    "System_Pressure_01": {"register": 1, "title": "Давление", "unit": "бар", "divisor": 100},
    "Pump_01_Status": {"register": 2, "title": "Насос", "unit": "", "divisor": 1},
    "Alarm_Code_01": {"register": 3, "title": "Код аварии", "unit": "", "divisor": 1},
    "Temp_Setpoint_01": {"register": 4, "title": "Уставка температуры", "unit": "°C", "divisor": 10},
}
