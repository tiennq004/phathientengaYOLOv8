# ESP32 IoT — Fall Guard

## Day noi

| Thiet bi | ESP32 |
|----------|--------|
| Buzzer | D4 + GND |
| LED RGB (R) | D5 |
| LED RGB (-) | GND |
| LCD I2C GND | GND |
| LCD I2C VCC | 5V |
| LCD I2C SDA | 21 |
| LCD I2C SCL | 22 |

LCD dia chi **0x27** — xoay **POT** tren module neu sang khong chu.

## Arduino

1. Board: **ESP32 Dev Module**
2. Thu vien: **LiquidCrystal I2C** (ZIP: github.com/johnrickman/LiquidCrystal_I2C)
3. Sua WiFi trong `fall_guard_iot/fall_guard_iot.ino` → Upload
4. Serial 115200 → ghi **IP**

## Python (.env)

```env
IOT_ENABLED=true
ESP32_ALERT_URL=http://<IP>/alert
```

Chay `python web_app.py` — khi te nga: buzzer + LED + LCD canh bao.
