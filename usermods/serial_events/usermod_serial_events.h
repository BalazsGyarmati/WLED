#pragma once

#include "wled.h"

class SerialEventsUsermod : public Usermod {
  private:
    static const char _name[];
    static const char _legacyName[];
    static const char _enabled[];
    static const char _timestamp[];

    enum EventType : uint8_t {
      EVT_ONLINE = 0,
      EVT_POWER,
      EVT_BRIGHTNESS,
      EVT_EFFECT,
      EVT_PALETTE,
      EVT_SPEED,
      EVT_INTENSITY,
      EVT_PRESET,
      EVT_BUTTON
    };

    struct EventRecord {
      uint8_t type;
      uint8_t value1;
      uint8_t value2;
      uint32_t sec;
      uint16_t ms;
    };

    static constexpr uint8_t QUEUE_SIZE = 16;

    bool enabled = true;
    bool includeTimestamp = true;
    bool initialized = false;

    bool lastOnline = false;
    bool lastPower = false;
    uint8_t lastBrightness = 0;
    uint8_t lastEffect = 0;
    uint8_t lastPalette = 0;
    uint8_t lastSpeed = 0;
    uint8_t lastIntensity = 0;
    uint8_t lastPreset = 0;

    EventRecord queue[QUEUE_SIZE] = {};
    uint8_t queueHead = 0;
    uint8_t queueTail = 0;

    void getEventTimestamp(uint32_t &sec, uint16_t &ms) const
    {
      if (!includeTimestamp || toki.getTimeSource() < TOKI_TS_SEC) {
        sec = 0;
        ms = 0;
        return;
      }

      Toki::Time t = toki.getTime();
      sec = t.sec;
      ms = t.ms;
    }

    void formatTimestamp(char* dest, size_t len, const EventRecord &event) const
    {
      if (event.sec == 0 && event.ms == 0) {
        strlcpy(dest, "0", len);
        return;
      }

      snprintf_P(dest, len, PSTR("%lu%03u"), event.sec, event.ms);
    }

    void captureState()
    {
      lastOnline = WLED_CONNECTED;
      lastPower = bri > 0;
      lastBrightness = bri;
      lastEffect = effectCurrent;
      lastPalette = effectPalette;
      lastSpeed = effectSpeed;
      lastIntensity = effectIntensity;
      lastPreset = currentPreset;
      initialized = true;
    }

    void queueEvent(uint8_t type, uint8_t value1, uint8_t value2 = 0)
    {
      if (!enabled || !serialCanTX) return;

      uint32_t sec;
      uint16_t ms;
      getEventTimestamp(sec, ms);

      uint8_t next = (queueHead + 1) % QUEUE_SIZE;
      if (next == queueTail) return;

      queue[queueHead] = {type, value1, value2, sec, ms};
      queueHead = next;
    }

    const char* eventCode(uint8_t type) const
    {
      switch (type) {
        case EVT_ONLINE:     return "ONL";
        case EVT_POWER:      return "PWR";
        case EVT_BRIGHTNESS: return "BRI";
        case EVT_EFFECT:     return "FX";
        case EVT_PALETTE:    return "PAL";
        case EVT_SPEED:      return "SPD";
        case EVT_INTENSITY:  return "INT";
        case EVT_PRESET:     return "PST";
        case EVT_BUTTON:     return "BTN";
        default:             return "UNK";
      }
    }

    const char* buttonActionCode(uint8_t action) const
    {
      switch (action) {
        case BUTTON_ACTION_SHORT:  return "S";
        case BUTTON_ACTION_LONG:   return "L";
        case BUTTON_ACTION_DOUBLE: return "D";
        case BUTTON_ACTION_ON:     return "ON";
        case BUTTON_ACTION_OFF:    return "OFF";
        default:                   return "?";
      }
    }

    void flushOneEvent()
    {
      if (!enabled || !serialCanTX || queueHead == queueTail || !Serial) return;

      const EventRecord &event = queue[queueTail];
      char ts[16];
      char line[64];
      formatTimestamp(ts, sizeof(ts), event);

      if (event.type == EVT_BUTTON) {
        snprintf_P(line, sizeof(line), PSTR("EV|%s|BTN|%u|%s"), ts, event.value1, buttonActionCode(event.value2));
      } else {
        snprintf_P(line, sizeof(line), PSTR("EV|%s|%s|%u"), ts, eventCode(event.type), event.value1);
      }

      Serial.println(line);
      queueTail = (queueTail + 1) % QUEUE_SIZE;
    }

  public:
    void setup() override
    {
      captureState();
    }

    void loop() override
    {
      if (!initialized) captureState();

      bool online = WLED_CONNECTED;
      if (online != lastOnline) {
        queueEvent(EVT_ONLINE, online ? 1 : 0);
        lastOnline = online;
      }

      flushOneEvent();
    }

    void onStateChange(uint8_t) override
    {
      if (!initialized) captureState();

      bool power = bri > 0;
      if (power != lastPower) {
        queueEvent(EVT_POWER, power ? 1 : 0);
        lastPower = power;
      }
      if (bri != lastBrightness) {
        queueEvent(EVT_BRIGHTNESS, bri);
        lastBrightness = bri;
      }
      if (effectCurrent != lastEffect) {
        queueEvent(EVT_EFFECT, effectCurrent);
        lastEffect = effectCurrent;
      }
      if (effectPalette != lastPalette) {
        queueEvent(EVT_PALETTE, effectPalette);
        lastPalette = effectPalette;
      }
      if (effectSpeed != lastSpeed) {
        queueEvent(EVT_SPEED, effectSpeed);
        lastSpeed = effectSpeed;
      }
      if (effectIntensity != lastIntensity) {
        queueEvent(EVT_INTENSITY, effectIntensity);
        lastIntensity = effectIntensity;
      }
      if (currentPreset != lastPreset) {
        if (currentPreset > 0) queueEvent(EVT_PRESET, currentPreset);
        lastPreset = currentPreset;
      }
    }

    void onButtonEvent(uint8_t buttonId, uint8_t action) override
    {
      queueEvent(EVT_BUTTON, buttonId, action);
    }

    void addToConfig(JsonObject& root) override
    {
      JsonObject top = root.createNestedObject(FPSTR(_name));
      top[FPSTR(_enabled)] = enabled;
      top[FPSTR(_timestamp)] = includeTimestamp;
    }

    bool readFromConfig(JsonObject& root) override
    {
      JsonObject top = root[FPSTR(_name)];
      if (top.isNull()) top = root[FPSTR(_legacyName)];
      bool configComplete = !top.isNull();

      configComplete &= getJsonValue(top[FPSTR(_enabled)], enabled, true);
      configComplete &= getJsonValue(top[FPSTR(_timestamp)], includeTimestamp, true);

      return configComplete;
    }

    uint16_t getId() override
    {
      return USERMOD_ID_SERIAL_EVENTS;
    }
};

const char SerialEventsUsermod::_name[] PROGMEM = "SerialEvents";
const char SerialEventsUsermod::_legacyName[] PROGMEM = "Serial Events";
const char SerialEventsUsermod::_enabled[] PROGMEM = "enabled";
const char SerialEventsUsermod::_timestamp[] PROGMEM = "timestamp";
