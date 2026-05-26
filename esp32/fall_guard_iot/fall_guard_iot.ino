/*
 * Fall Guard — ESP32 IoT cảnh báo té ngã (0 đồng phần cứng thêm nếu chỉ dùng LED onboard)
 *
 * Cách hoạt động:
 *   - ESP32 kết nối WiFi, mở web server cổng 80
 *   - Máy tính chạy web_app.py gọi GET http://<IP_ESP32>/alert khi phát hiện té ngã
 *   - ESP32 bật LED + buzzer (nếu có) trong vài giây
 *
 * Sửa WIFI_SSID và WIFI_PASSWORD bên dưới trước khi nạp.
 * Arduino IDE: Board = ESP32 Dev Module, thư viện WiFi có sẵn.
 */

#include <WiFi.h>
#include <WebServer.h>

// --- Cấu hình WiFi (cùng mạng với máy chạy Python) ---
const char* WIFI_SSID     = "Ten_WiFi_cua_ban";
const char* WIFI_PASSWORD = "Mat_khau_WiFi";

// GPIO: LED onboard thường là 2. Buzzer: cắm vào GPIO 4 (âm -> GND), hoặc đặt -1 nếu không có.
const int LED_PIN    = 2;
const int BUZZER_PIN = 4;   // -1 = không dùng buzzer

const unsigned long ALARM_MS = 15000;  // thời gian cảnh báo mỗi lần

WebServer server(80);

unsigned long alarmUntil = 0;
unsigned long lastAlertMs = 0;
int alertCount = 0;
String lastEvent = "none";
String lastTime = "";

void setAlarmActive(bool on) {
  digitalWrite(LED_PIN, on ? HIGH : LOW);
  if (BUZZER_PIN >= 0) {
    digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
  }
}

void startAlarm(const String& event, const String& t) {
  alarmUntil = millis() + ALARM_MS;
  lastAlertMs = millis();
  alertCount++;
  lastEvent = event.length() ? event : "fall";
  lastTime = t.length() ? t : String(millis());
  setAlarmActive(true);
  Serial.printf("[ALERT] event=%s time=%s count=%d\n", lastEvent.c_str(), lastTime.c_str(), alertCount);
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>Fall Guard ESP32</title></head><body style='font-family:sans-serif;padding:1rem'>"
    "<h1>Fall Guard IoT</h1>"
    "<p>IP: " + WiFi.localIP().toString() + "</p>"
    "<p>Trạng thái: " + String((millis() < alarmUntil) ? "<b style='color:red'>CANH BAO</b>" : "Binh thuong") + "</p>"
    "<p>Số lần cảnh báo: " + String(alertCount) + "</p>"
    "<p>Sự kiện cuối: " + lastEvent + " @ " + lastTime + "</p>"
    "<p><a href='/alert?event=test'>Thử cảnh báo</a></p>"
    "</body></html>";
  server.send(200, "text/html; charset=utf-8", html);
}

void handleStatus() {
  String json = "{";
  json += "\"device\":\"esp32\",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"alarm_active\":" + String(millis() < alarmUntil ? "true" : "false") + ",";
  json += "\"alert_count\":" + String(alertCount) + ",";
  json += "\"last_event\":\"" + lastEvent + "\",";
  json += "\"last_time\":\"" + lastTime + "\"";
  json += "}";
  server.send(200, "application/json", json);
}

void handleAlert() {
  String event = server.hasArg("event") ? server.arg("event") : "fall";
  String t = server.hasArg("time") ? server.arg("time") : "";
  startAlarm(event, t);
  server.send(200, "application/json", "{\"ok\":true,\"message\":\"alarm_started\"}");
}

void handleNotFound() {
  server.send(404, "text/plain", "Not found. Dung /alert hoac /status");
}

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Ket noi WiFi");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Loi WiFi — kiem tra SSID/mat khau.");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  if (BUZZER_PIN >= 0) {
    pinMode(BUZZER_PIN, OUTPUT);
  }
  setAlarmActive(false);

  setupWiFi();

  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/alert", HTTP_GET, handleAlert);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("HTTP server: http://<IP>/alert");
}

void loop() {
  server.handleClient();

  bool alarming = millis() < alarmUntil;
  if (alarming) {
    // Nhấp nháy LED khi đang cảnh báo (buzzer giữ HIGH nếu là loại active)
    bool blink = (millis() / 200) % 2;
    digitalWrite(LED_PIN, blink ? HIGH : LOW);
  } else {
    setAlarmActive(false);
  }
}
