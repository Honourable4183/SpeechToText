#include <Arduino.h>
#include <driver/i2s.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// ------------------ WiFi and Telegram Credentials -------------------
const char* ssid = "AmanK50i";
const char* password = "8characters";
const String BotToken = "7961972146:AAGkgOnZafCIueCp8gRjGtFOzaqbt-jiDRU";
const String chatID = "1928618212";

// ------------------ Pin Configuration -------------------
#define I2S_WS      25
#define I2S_SCK     26
#define I2S_SD      33

#define SD_CS       5
#define SD_SCK      18
#define SD_MOSI     23
#define SD_MISO     19

#define BUTTON_PIN  4

// ------------------ Recording Parameters -------------------
#define SAMPLE_RATE     16000
#define SAMPLE_BITS     I2S_BITS_PER_SAMPLE_32BIT
#define CHANNEL_FORMAT  I2S_CHANNEL_FMT_ONLY_LEFT
#define RECORD_BUFFER   1024

File audioFile;
bool isRecording = false;
String filename;

WiFiClientSecure client;

// ------------------ WAV Header Functions -------------------
void writeWavHeader(File file) {
  const int headerSize = 44;
  byte header[headerSize];

  uint32_t sampleRate = SAMPLE_RATE;
  uint16_t bitsPerSample = 16;
  uint16_t numChannels = 1;

  uint32_t byteRate = sampleRate * numChannels * bitsPerSample / 8;
  uint16_t blockAlign = numChannels * bitsPerSample / 8;

  // RIFF header
  memcpy(header, "RIFF", 4);
  uint32_t chunkSize = 0; // will be updated later
  memcpy(header + 4, &chunkSize, 4);
  memcpy(header + 8, "WAVE", 4);

  // fmt subchunk
  memcpy(header + 12, "fmt ", 4);
  uint32_t subChunk1Size = 16;
  uint16_t audioFormat = 1;
  memcpy(header + 16, &subChunk1Size, 4);
  memcpy(header + 20, &audioFormat, 2);
  memcpy(header + 22, &numChannels, 2);
  memcpy(header + 24, &sampleRate, 4);
  memcpy(header + 28, &byteRate, 4);
  memcpy(header + 32, &blockAlign, 2);
  memcpy(header + 34, &bitsPerSample, 2);

  // data subchunk
  memcpy(header + 36, "data", 4);
  uint32_t subChunk2Size = 0; // will be updated later
  memcpy(header + 40, &subChunk2Size, 4);

  file.write(header, headerSize);
}

void updateWavHeader(File file) {
  uint32_t fileSize = file.size();
  uint32_t dataSize = fileSize - 44;
  uint32_t chunkSize = 36 + dataSize;

  file.seek(4);
  file.write((uint8_t*)&chunkSize, 4);
  file.seek(40);
  file.write((uint8_t*)&dataSize, 4);
}

// ------------------ I2S Setup -------------------
void setupI2S() {
  const i2s_config_t i2s_config = {
    .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = SAMPLE_BITS,
    .channel_format = CHANNEL_FORMAT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
}

// ------------------ SD Card Setup -------------------
void setupSD() {
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("SD card init failed!");
    while (1);
  }
  Serial.println("SD card initialized.");
}

// ------------------ WiFi -------------------
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi connected.");
  client.setInsecure();
}

// ------------------ Telegram Upload -------------------
bool sendToTelegram(const String& filePath) {
  File file = SD.open(filePath);
  if (!file) {
    Serial.println("Failed to open file for sending");
    return false;
  }

  if (!client.connect("api.telegram.org", 443)) {
    Serial.println("Connection to Telegram failed");
    file.close();
    return false;
  }

  String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
  String startRequest =
    "--" + boundary + "\r\n" +
    "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n" +
    chatID + "\r\n" +
    "--" + boundary + "\r\n" +
    "Content-Disposition: form-data; name=\"document\"; filename=\"" + filePath + "\"\r\n" +
    "Content-Type: audio/wav\r\n\r\n";

  String endRequest = "\r\n--" + boundary + "--\r\n";
  uint32_t contentLength = startRequest.length() + file.size() + endRequest.length();

  client.println("POST /bot" + BotToken + "/sendDocument HTTP/1.1");
  client.println("Host: api.telegram.org");
  client.println("Content-Type: multipart/form-data; boundary=" + boundary);
  client.println("Content-Length: " + String(contentLength));
  client.println("Connection: close");
  client.println();
  client.print(startRequest);

  uint8_t buffer[1024];
  size_t bytesRead;
  while ((bytesRead = file.read(buffer, sizeof(buffer))) > 0) {
    client.write(buffer, bytesRead);
  }

  file.close();
  client.print(endRequest);

  Serial.println("Waiting for Telegram response...");
  unsigned long timeout = millis();
  while (client.connected() && millis() - timeout < 10000) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      if (line.indexOf("\"ok\":true") != -1) {
        Serial.println("Upload successful.");
        return true;
      }
    }
    delay(10);
  }

  client.stop();
  return false;
}

// ------------------ Recording Functions -------------------
void startRecording() {
  Serial.println("Button pressed - Start recording...");
  filename = "/record_" + String(millis()) + ".wav";
  audioFile = SD.open(filename, FILE_WRITE);
  if (!audioFile) {
    Serial.println("Failed to open file!");
    return;
  }
  writeWavHeader(audioFile);
  isRecording = true;
}

void stopRecording() {
  Serial.println("Button released - Stop recording...");
  isRecording = false;
  updateWavHeader(audioFile);
  audioFile.close();
  Serial.print("Saved file: ");
  Serial.println(filename);

  int retries = 3;
  while (retries-- > 0) {
    if (sendToTelegram(filename)) {
      SD.remove(filename);
      Serial.println("File deleted after successful upload.");
      break;
    } else {
      Serial.println("Retrying...");
      delay(2000);
    }
  }
}

// ------------------ Arduino Setup/Loop -------------------
void setup() {
  Serial.begin(115200);
  connectWiFi();
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  setupI2S();
  setupSD();
  Serial.println("Ready. Press button to record.");
}

void loop() {
  static bool lastButtonState = HIGH;
  bool buttonState = digitalRead(BUTTON_PIN);

  if (lastButtonState == HIGH && buttonState == LOW) {
    startRecording();
  }

  if (lastButtonState == LOW && buttonState == HIGH && isRecording) {
    stopRecording();
  }

  lastButtonState = buttonState;

  if (isRecording) {
    uint8_t i2sData[RECORD_BUFFER];
    size_t bytesRead;
    i2s_read(I2S_NUM_0, &i2sData, RECORD_BUFFER, &bytesRead, portMAX_DELAY);
    if (bytesRead > 0) {
      int32_t* samples = (int32_t*)i2sData;
      size_t sampleCount = bytesRead / sizeof(int32_t);
      for (size_t i = 0; i < sampleCount; i++) {
        int16_t sample16 = samples[i] >> 14; // shift from 32-bit to 16-bit
        audioFile.write((uint8_t*)&sample16, sizeof(sample16));
      }

      // audioFile.flush(); // optional for SD safety
    }
  }
}
