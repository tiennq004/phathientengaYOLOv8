# ESP32 IoT — Fall Guard (chi phí ~0đ)

## Kiến trúc

```
Camera/Video → Python (AI phát hiện té ngã) ──HTTP GET──► ESP32 (LED + buzzer)
                              ↑
                         cùng WiFi LAN
```

Không cần server cloud, MQTT broker trả phí, hay module phụ — chỉ **1 board ESP32** và WiFi nhà/trường.

## Bước 1: Nạp firmware

1. Cài [Arduino IDE](https://www.arduino.cc/en/software) + board ESP32 (Board Manager: `esp32` by Espressif).
2. Mở `esp32/fall_guard_iot/fall_guard_iot.ino`.
3. Sửa `WIFI_SSID` và `WIFI_PASSWORD` (cùng mạng với laptop chạy `web_app.py`).
4. Nạp code, mở **Serial Monitor 115200** → ghi lại dòng `ESP32 IP: 192.168.x.x`.

## Bước 2: Cấu hình Python

Trong file `.env` (copy từ `.env.example`):

```env
IOT_ENABLED=true
ESP32_ALERT_URL=http://192.168.1.50/alert
IOT_HTTP_TIMEOUT=2.5
```

Thay `192.168.1.50` bằng IP thật của ESP32.

## Bước 3: Chạy và demo cho thầy

```bash
python web_app.py
```

1. Mở trình duyệt → đăng nhập → bấm **Kiểm tra ESP32** (hoặc gọi API test).
2. Chạy giám sát webcam/video; khi có té ngã, ESP32 sáng LED / kêu buzzer ~15 giây.
3. Có thể mở `http://<IP_ESP32>/` trên điện thoại để xem trạng thái (điểm IoT minh họa).

## Phần cứng tùy chọn

| Linh kiện | Giá ước tính | Ghi chú |
|-----------|--------------|---------|
| ESP32 DevKit | (bạn đã có) | LED GPIO 2 sáng sẵn khi cảnh báo |
| Buzzer active 5V | ~5–15k | Chân `+` → GPIO 4, `-` → GND (có thể thêm trở 100Ω) |

Nếu không có buzzer: đặt `BUZZER_PIN = -1` trong file `.ino`.

## API ESP32

| URL | Mô tả |
|-----|--------|
| `GET /alert?event=fall&time=...` | Bật cảnh báo (Python gọi khi té ngã) |
| `GET /status` | JSON trạng thái |
| `GET /` | Trang web trạng thái đơn giản |

## Xử lý lỗi

- **ESP32 không nhận cảnh báo**: Kiểm tra laptop và ESP32 cùng WiFi; tắt firewall Windows cho cổng LAN; ping IP ESP32.
- **IP ESP32 đổi sau mỗi lần bật**: Vào router gán IP tĩnh cho MAC ESP32, hoặc cập nhật lại `.env`.
