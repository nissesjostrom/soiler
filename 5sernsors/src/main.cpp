#include <Arduino.h>
#include <TFT_eSPI.h>
#include <lvgl.h>

constexpr int STATUS_LED_PIN = 2;
constexpr int RS485_RX_PIN = 3;
constexpr int RS485_TX_PIN = 1;
constexpr int RS485_DE_RE_PIN = 4;
constexpr int TFT_BACKLIGHT_PIN = 21;
constexpr uint32_t RS485_BAUD = 9600;
constexpr uint8_t MODBUS_SLAVE_ID = 1;
constexpr uint16_t START_REGISTER = 0x0000;
constexpr uint16_t REGISTER_COUNT = 8;
constexpr uint32_t POLL_INTERVAL_MS = 2000;
constexpr uint16_t SCREEN_WIDTH = 240;
constexpr uint16_t SCREEN_HEIGHT = 320;

HardwareSerial RS485Serial(2);
TFT_eSPI tft = TFT_eSPI();

static lv_disp_draw_buf_t drawBufferDescriptor;
static lv_color_t drawBuffer[SCREEN_WIDTH * 20];
constexpr uint8_t TILE_COUNT = 9; // 8 readings + 1 status
static lv_obj_t* valueLabels[TILE_COUNT] = {nullptr};
static lv_obj_t* statusLabel = nullptr;

const char* readingNames[TILE_COUNT] = {
  "Moisture",
  "Temp",
  "EC",
  "pH",
  "Nitrogen",
  "Phosphorus",
  "Potassium",
  "Salinity",
  "Status"
};

void displayFlush(lv_disp_drv_t* driver, const lv_area_t* area, lv_color_t* colorPointer) {
  const int32_t width = (area->x2 - area->x1 + 1);
  const int32_t height = (area->y2 - area->y1 + 1);

  tft.startWrite();
  tft.setAddrWindow(area->x1, area->y1, width, height);
  tft.pushColors(reinterpret_cast<uint16_t*>(&colorPointer->full), static_cast<uint32_t>(width * height), true);
  tft.endWrite();

  lv_disp_flush_ready(driver);
}

void setReadingLabel(uint8_t index, const char* text) {
  if (index < REGISTER_COUNT && valueLabels[index] != nullptr) {
    lv_label_set_text(valueLabels[index], text);
  }
}

void showNoData() {
  for (uint8_t i = 0; i < REGISTER_COUNT; ++i) {
    setReadingLabel(i, "--");
  }
  lv_label_set_text(statusLabel, "no response");
}

void updateDashboardFromRegisters(const uint16_t* registers) {
  char text[24];

  snprintf(text, sizeof(text), "%.1f %%", registers[0] / 10.0f);
  setReadingLabel(0, text);

  snprintf(text, sizeof(text), "%.1f C", registers[1] / 10.0f);
  setReadingLabel(1, text);

  snprintf(text, sizeof(text), "%u us/cm", registers[2]);
  setReadingLabel(2, text);

  snprintf(text, sizeof(text), "%.1f", registers[3] / 10.0f);
  setReadingLabel(3, text);

  snprintf(text, sizeof(text), "%u mg/kg", registers[4]);
  setReadingLabel(4, text);

  snprintf(text, sizeof(text), "%u mg/kg", registers[5]);
  setReadingLabel(5, text);

  snprintf(text, sizeof(text), "%u mg/kg", registers[6]);
  setReadingLabel(6, text);

  snprintf(text, sizeof(text), "%.1f ppt", registers[7] / 10.0f);
  setReadingLabel(7, text);

  lv_label_set_text(statusLabel, "connected");
}

void createDashboardUi() {
  // Landscape: LVGL canvas is 320 wide x 240 tall
  // 3x3 grid filling the full screen, 2px outer margin, 3px gaps
  // Tile size: (320-4-2*3)/3 = 102 wide, (240-4-2*3)/3 = 74 tall
  constexpr int16_t GRID_W = 316;
  constexpr int16_t GRID_H = 236;
  constexpr int16_t TILE_W = 102;
  constexpr int16_t TILE_H = 74;
  constexpr int16_t GAP = 3;
  constexpr int16_t PAD = 2;

  lv_obj_t* screen = lv_scr_act();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x101010), 0);

  lv_obj_t* container = lv_obj_create(screen);
  lv_obj_set_size(container, GRID_W, GRID_H);
  lv_obj_align(container, LV_ALIGN_CENTER, 0, 0);
  lv_obj_set_style_bg_color(container, lv_color_hex(0x101010), 0);
  lv_obj_set_style_border_width(container, 0, 0);
  lv_obj_set_style_pad_all(container, PAD, 0);
  lv_obj_set_style_pad_row(container, GAP, 0);
  lv_obj_set_style_pad_column(container, GAP, 0);
  lv_obj_set_layout(container, LV_LAYOUT_FLEX);
  lv_obj_set_flex_flow(container, LV_FLEX_FLOW_ROW_WRAP);

  for (uint8_t i = 0; i < TILE_COUNT; ++i) {
    lv_obj_t* card = lv_obj_create(container);
    lv_obj_set_size(card, TILE_W, TILE_H);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x2B2B2B), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(0x4A4A4A), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_radius(card, 6, 0);
    lv_obj_set_style_pad_all(card, 5, 0);
    lv_obj_set_layout(card, LV_LAYOUT_FLEX);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(card, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER);

    lv_obj_t* title = lv_label_create(card);
    lv_label_set_text(title, readingNames[i]);
    lv_obj_set_style_text_color(title, lv_color_hex(0x9E9E9E), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_14, 0);

    valueLabels[i] = lv_label_create(card);
    lv_label_set_text(valueLabels[i], "--");
    lv_obj_set_style_text_color(valueLabels[i], lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(valueLabels[i], &lv_font_montserrat_14, 0);
  }

  // 9th tile's value label is the status indicator
  statusLabel = valueLabels[TILE_COUNT - 1];
}

uint16_t modbusCrc16(const uint8_t* data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t index = 0; index < length; ++index) {
    crc ^= data[index];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      if (crc & 0x0001) {
        crc = (crc >> 1) ^ 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

size_t readExact(uint8_t* buffer, size_t wanted, uint32_t timeoutMs) {
  size_t received = 0;
  const uint32_t start = millis();
  while (received < wanted && (millis() - start) < timeoutMs) {
    if (RS485Serial.available() > 0) {
      buffer[received++] = static_cast<uint8_t>(RS485Serial.read());
    }
  }
  return received;
}

bool readHoldingRegisters(uint8_t slaveId, uint16_t startRegister, uint16_t registerCount, uint16_t* outRegisters) {
  uint8_t request[8];
  request[0] = slaveId;
  request[1] = 0x03;
  request[2] = static_cast<uint8_t>(startRegister >> 8);
  request[3] = static_cast<uint8_t>(startRegister & 0xFF);
  request[4] = static_cast<uint8_t>(registerCount >> 8);
  request[5] = static_cast<uint8_t>(registerCount & 0xFF);
  const uint16_t requestCrc = modbusCrc16(request, 6);
  request[6] = static_cast<uint8_t>(requestCrc & 0xFF);
  request[7] = static_cast<uint8_t>(requestCrc >> 8);

  while (RS485Serial.available() > 0) {
    RS485Serial.read();
  }

  digitalWrite(RS485_DE_RE_PIN, HIGH);
  delayMicroseconds(100);
  RS485Serial.write(request, sizeof(request));
  RS485Serial.flush();
  delayMicroseconds(100);
  digitalWrite(RS485_DE_RE_PIN, LOW);

  const uint8_t expectedByteCount = static_cast<uint8_t>(registerCount * 2);
  const size_t expectedLength = static_cast<size_t>(5 + expectedByteCount);
  uint8_t response[64];
  if (expectedLength > sizeof(response)) {
    return false;
  }

  const size_t received = readExact(response, expectedLength, 1000);
  if (received != expectedLength) {
    return false;
  }

  if (response[0] != slaveId || response[1] != 0x03 || response[2] != expectedByteCount) {
    return false;
  }

  const uint16_t responseCrc = static_cast<uint16_t>(response[expectedLength - 1] << 8) | response[expectedLength - 2];
  const uint16_t computedCrc = modbusCrc16(response, expectedLength - 2);
  if (responseCrc != computedCrc) {
    return false;
  }

  for (uint16_t i = 0; i < registerCount; ++i) {
    const uint8_t hi = response[3 + (i * 2)];
    const uint8_t lo = response[4 + (i * 2)];
    outRegisters[i] = static_cast<uint16_t>((hi << 8) | lo);
  }

  return true;
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(RS485_DE_RE_PIN, OUTPUT);
  pinMode(TFT_BACKLIGHT_PIN, OUTPUT);
  digitalWrite(RS485_DE_RE_PIN, LOW);
  digitalWrite(TFT_BACKLIGHT_PIN, HIGH);

  RS485Serial.begin(RS485_BAUD, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);

  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);

  lv_init();
  lv_disp_draw_buf_init(&drawBufferDescriptor, drawBuffer, nullptr, SCREEN_WIDTH * 20);

  static lv_disp_drv_t displayDriver;
  lv_disp_drv_init(&displayDriver);
  displayDriver.hor_res = SCREEN_HEIGHT;
  displayDriver.ver_res = SCREEN_WIDTH;
  displayDriver.flush_cb = displayFlush;
  displayDriver.draw_buf = &drawBufferDescriptor;
  lv_disp_drv_register(&displayDriver);

  createDashboardUi();
  showNoData();
}

void loop() {
  static uint32_t lastLvTick = millis();
  const uint32_t now = millis();
  lv_tick_inc(now - lastLvTick);
  lastLvTick = now;
  lv_timer_handler();

  static uint32_t lastPoll = 0;
  if ((now - lastPoll) >= POLL_INTERVAL_MS) {
    lastPoll = now;

    uint16_t registers[REGISTER_COUNT] = {0};
    const bool ok = readHoldingRegisters(MODBUS_SLAVE_ID, START_REGISTER, REGISTER_COUNT, registers);

    if (ok) {
      digitalWrite(STATUS_LED_PIN, HIGH);
      updateDashboardFromRegisters(registers);
    } else {
      digitalWrite(STATUS_LED_PIN, LOW);
      showNoData();
    }
  }

  delay(5);
}
