/*
 * Fall Guard — ESP32 IoT (buzzer D4, LED R D5, LCD I2C 0x27)
 * Python goi GET http://<IP>/alert khi phat hien te nga
 * Thu vien: LiquidCrystal I2C (ZIP johnrickman)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const char* WIFI_SSID     = "Ten_WiFi_cua_ban";
const char* WIFI_PASSWORD = "Mat_khau_WiFi";

const int LED_PIN     = 2;
const int BUZZER_PIN  = 4;
const int RGB_RED_PIN = 5;

const bool BUZZER_ACTIVE     = false;
const bool RGB_COMMON_ANODE  = false;
const unsigned long ALARM_MS = 15000;

const bool ENABLE_LCD        = true;
const uint8_t LCD_I2C_ADDR   = 0x27;
const int LCD_SDA            = 21;
const int LCD_SCL            = 22;

WebServer server(80);
LiquidCrystal_I2C lcd(LCD_I2C_ADDR, 16, 2);

unsigned long alarmUntil = 0;
unsigned long lastLcdUpdate = 0;
int alertCount = 0;
String lastEvent = "none";
String lastTime = "";
bool buzzerPwmReady = false;

void buzzerOn(bool on) {
  if (BUZZER_PIN < 0) return;
  if (BUZZER_ACTIVE) {
    digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
    return;
  }
  if (!buzzerPwmReady) {
    ledcAttach(BUZZER_PIN, 2500, 10);
    buzzerPwmReady = true;
  }
  ledcWrite(BUZZER_PIN, on ? 700 : 0);
}

void rgbRed(bool on) {
  if (RGB_RED_PIN < 0) return;
  bool level = RGB_COMMON_ANODE ? !on : on;
  digitalWrite(RGB_RED_PIN, level ? HIGH : LOW);
}

void outputsOff() {
  digitalWrite(LED_PIN, LOW);
  buzzerOn(false);
  rgbRed(false);
}

void outputsAlarm(bool on) {
  digitalWrite(LED_PIN, on ? HIGH : LOW);
  buzzerOn(on);
  rgbRed(on);
}

void updateLcd() {
  if (!ENABLE_LCD) return;
  lcd.clear();
  if (millis() < alarmUntil) {
    lcd.setCursor(0, 0);
    lcd.print("!! CANH BAO !!");
    lcd.setCursor(0, 1);
    lcd.print("TE NGA lan ");
    lcd.print(alertCount);
  } else if (WiFi.status() == WL_CONNECTED) {
    lcd.setCursor(0, 0);
    lcd.print("Fall Guard san");
    lcd.setCursor(0, 1);
    lcd.print(WiFi.localIP());
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Fall Guard");
    lcd.setCursor(0, 1);
    lcd.print("Ket noi WiFi...");
  }
}

void startAlarm(const String& event, const String& t) {
  alarmUntil = millis() + ALARM_MS;
  alertCount++;
  lastEvent = event.length() ? event : "fall";
  lastTime = t.length() ? t : String(millis());
  outputsAlarm(true);
  updateLcd();
  Serial.printf("[ALERT] %s @ %s (#%d)\n", lastEvent.c_str(), lastTime.c_str(), alertCount);
}

void handleAlert() {
  String event = server.hasArg("event") ? server.arg("event") : "fall";
  String t = server.hasArg("time") ? server.arg("time") : "";
  startAlarm(event, t);
  server.send(200, "application/json", "{\"ok\":true}");
}

void handleStatus() {
  String json = "{";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"alarm_active\":" + String(millis() < alarmUntil ? "true" : "false") + ",";
  json += "\"alert_count\":" + String(alertCount);
  json += "}";
  server.send(200, "application/json", json);
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RGB_RED_PIN, OUTPUT);
  outputsOff();

  Serial.begin(115200);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  if (ENABLE_LCD) {
    Wire.begin(LCD_SDA, LCD_SCL);
    lcd.init();
    lcd.backlight();
    updateLcd();
  }

  server.on("/alert", HTTP_GET, handleAlert);
  server.on("/status", HTTP_GET, handleStatus);
  server.begin();
  Serial.println("San sang: /alert");
}

void loop() {
  server.handleClient();

  bool alarming = millis() < alarmUntil;
  if (alarming) {
    bool blink = (millis() / 200) % 2;
    digitalWrite(LED_PIN, blink ? HIGH : LOW);
    rgbRed(true);
    buzzerOn((millis() / 120) % 2 == 0);
  } else {
    outputsOff();
  }

  if (ENABLE_LCD && millis() - lastLcdUpdate > 2000) {
    lastLcdUpdate = millis();
    updateLcd();
  }
}
