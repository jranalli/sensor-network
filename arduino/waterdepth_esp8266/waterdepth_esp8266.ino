// ESP8266 by ESP8266 Community v3.1.2 (Board Manager)
// ===== Lib Dependencies =====
// OTA Updates
// AsyncElegantOTA by Ayush Sharma v 2.28
// ESPAsyncTCP by dvarrel v 1.2.4
// ESPAsyncWebServer by lacamera v 3.1.0

// Web Time Updates
// NTPClient by Fabrice Weinberg 3.2.1
// Time by Michael Margolis v 1.6.1

// JSON Management
// ArduinoJson by Benoit Blanchon 7.0.2 (v7 reqd)

// Sensor Control
// NewPing

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
//#include <WiFiClient.h>  
#include <NTPClient.h> 
#include <AsyncElegantOTA.h>
//#include <ESPAsyncWebServer.h>
#include <WiFiUdp.h>
#include <TimeLib.h>
//#define ARDUINOJSON_ENABLE_PROGMEM 0
#include <ArduinoJson.h> 
#include <DHT.h> 

#include <NewPing.h> 

#include <secrets.h>  // My secrets library

// Parameters for the device on the network
const char* SSID = SECRET_SSID;
const char* PASSWORD = SECRET_WIFIPASS;
const char* DATA_SERVER = "http://<SERVERIP>/sensors/";
const char* DEVID = "water-001";
const char* DEVTYPE = "water";

// Vars for the basic WiFi & data posting operations
WiFiClient client;
HTTPClient http;

// Vars for setting up the internet time polling
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org");
time_t epochTime;
bool DST = false;
int baseTZ = -5;  // hours from UTC
int DST_offset = DST ? 1 : 0;
int timeOffset = (baseTZ+DST_offset)*60*60;  // seconds from UTC

// Var for the server that handles OTA updates
AsyncWebServer ota_update_server(80);

// Vars for this device and sensor type
const int GREENPIN = D6;
const int REDPIN = D8;
const int LEDPIN = D0;

const int TRIGPIN = D1;
const int ECHOPIN = D2;
const int maxDist = 67;  // Physical maximum distance to end of tube
// NewPingESP8266 sonar(TRIGPIN, ECHOPIN, maxDist);
NewPing sonar(TRIGPIN, ECHOPIN, maxDist);

// the following variables are unsigned longs because the time, measured in
// milliseconds, will quickly become a bigger number than can be stored in an int.
unsigned long lastPtTime = 0;

unsigned long rateInterval = 1000;  // This is the sample rate
const int TICK_MILLIS = 50;
const int nData = 60;  // This is the # of samples per POST
const int BUFFER_SIZE = 30;

const int POST_ERROR_INTERVAL_MILLIS = 30000;
const int SAMPLE_INTERVAL_MILLIS = 1000;
const int DT_MILLIS = TICK_MILLIS;

// A loop counter for measuring the # of datapoints collected
int pt_buffer_pos = 0;
bool acquiring = false;

// Single point observation, reads once per loop when acquiring
struct Observation_pt 
{
  int depth;
  int millis;
};

// A single observation, that consists of n data points, this is what will go to the server
struct Observation
{
  String stamp;
  Observation_pt data_array[nData];
};

// Set up the buffer of observations
Observation buffer_data[BUFFER_SIZE];
int buffer_pos = 0;

// Set up the acquistion rate measurement offsets
unsigned long lastDataMillis = 0; // last time we started acquiring readings
unsigned long postErrorMillis = -POST_ERROR_INTERVAL_MILLIS;

// Set up 
int nextDataIntervalMillis = 0;  // Delay in millis to next measurement
unsigned int nextDataTime = 0;


void setup() {
  // Init serial communication
  Serial.begin(115200);
  delay(3000);

  // ===== Init WiFi connection =====
  WiFi.begin(SSID, PASSWORD);
  delay(100);
  Serial.println("");
  Serial.println("Connecting");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to WiFi network with IP Address: ");
  Serial.println(WiFi.localIP());
  
  // ===== Init time connection to web =====
  timeClient.begin();
  timeClient.setTimeOffset(timeOffset);
  
  timeClient.update();
  epochTime = timeClient.getEpochTime();
  
  Serial.print("Syncronized time to: ");
  Serial.print(to_time_string(epochTime));
  Serial.println("");

  // Calculate dT til our next reading.
  calcNextTime(epochToSeconds(epochTime));
  lastDataMillis = millis();  

  // ===== Init server for OTA updates =====
  // Server runs at http://<dev_ip>/update
  // Can upload a Sketch>Export binary OTA
  ElegantOTA.begin(&ota_update_server);
  ota_update_server.begin();

  // ===== Init Operations for this Sensor Device =====
  pinMode(REDPIN, OUTPUT); // set the digital pin as output.
  pinMode(GREENPIN, OUTPUT); // set the digital pin as output.
  pinMode(LEDPIN, OUTPUT);
  digitalWrite(LEDPIN, HIGH);

  delay(500);
}


void loop() {
  if (acquiring){
    if (pt_buffer_pos >= nData){
      Serial.println("Inner buffer complete, finishing reading array.");
      acquiring = false;
      pt_buffer_pos = 0;
      buffer_pos++;
    } else if (millis() - lastPtTime >= rateInterval) {
      digitalWrite(GREENPIN, HIGH);
      lastPtTime = millis();
      Observation_pt d = takeReading(lastPtTime);
      Serial.print(".");
      buffer_data[buffer_pos].data_array[pt_buffer_pos] = d;
      pt_buffer_pos++;
      digitalWrite(GREENPIN, LOW);
      delay(TICK_MILLIS);
    }
  } else {

    // Read the real world time
    timeClient.update();
    epochTime = timeClient.getEpochTime();
    
    // Test to see if we're ready to actually acquire
    if (millis() - lastPtTime >= rateInterval){
      // Reset our data timer
      lastDataMillis = millis();
      lastPtTime = 0;

      // Try to take a data reading, check if there's buffer space
      if (buffer_pos < BUFFER_SIZE){
        
        acquiring = true;
        Observation d = Observation();
        d.stamp = to_time_string(epochTime);

        // Serial report
        Serial.print("Starting readings in buffer position: ");
        Serial.println(buffer_pos);

        // Increment the buffer and time for next iteration. Save time as round interval. 
        buffer_data[buffer_pos] = d;

        // We won't increment the buffer_pos until we are done with the acquisition.
      } else {
        // The buffer is full, oops.
        Serial.println("Time to take data, but buffer full!");
      }
    } 
    if (millis() - postErrorMillis >= POST_ERROR_INTERVAL_MILLIS && buffer_pos > 0){
      // We have data so post it all back to the server
      while (buffer_pos > 0) {
        // Show status
        Serial.print("Posting data from buffer position: ");
        Serial.println(buffer_pos-1);

        // Get the data and pass to subroutine for posting, get status
        digitalWrite(LEDPIN, LOW);
        digitalWrite(REDPIN, HIGH);
        Observation d = buffer_data[buffer_pos-1];
        bool success = postReading(d);
        digitalWrite(LEDPIN, HIGH);
        digitalWrite(REDPIN, LOW);
        
        // If we succeeded, decrement and continue looping.
        if (success) {
          buffer_pos--;
        } else {
          // We failed, so set an error time entry to wait for the retry.
          postErrorMillis = millis();
          break;
        }
      }
      if (buffer_pos == 0) {
        // We've cleared the buffer, we can make sure we reset our error. 
        Serial.println("No data remains in buffer, finished posting.");
        postErrorMillis = -POST_ERROR_INTERVAL_MILLIS;
      }
    } else {
    // Don't tick faster than a limit rate when we're not working on anything. 
    delay(TICK_MILLIS);  
    }
  }
}

void addObservationDict(JsonDocument& docu, Observation obs){
  // Add the Observation object to the JSON
  // under the "reading" field. This will
  // look different for different sensors.

  JsonObject reading = docu["reading"].to<JsonObject>();
  reading["timestamp"] = obs.stamp;
  reading["tz"] = baseTZ+DST_offset;
  reading["dt"] = rateInterval/1000.0;
  JsonObject data = reading["data"].to<JsonObject>();
  JsonArray depth = data["depth"].to<JsonArray>();
  JsonArray millis = data["millis"].to<JsonArray>();
  for (int i = 0; i < nData; i++){
    Observation_pt pt = obs.data_array[i];
    depth.add(pt.depth);
    millis.add(pt.millis);
  }
}


Observation_pt takeReading(long time_millis)
{
  // Take a single reading, put it in an 
  // Observation object and return it for
  // processing. This will look different 
  // for different sensors.

  Observation_pt obspt = Observation_pt();

  // unsigned int distance = sonar.ping_cm();  // ping_in() for inches
  unsigned int distance = sonar.convert_cm(sonar.ping_median(5, 100));  // measure median distance from 5 readings with a max of 100 cm.

  // Store it into an observation
  obspt.depth = distance;
  obspt.millis = time_millis - lastDataMillis;
  
  return obspt;
}


// ======== Universal Subroutines ========

bool postReading(Observation data){
  // Post a single observation to the server.
  // This shouldn't need to change from 
  // sensor to sensor, but should be general.
  // Return true on success (http code 200)
  // and false otherwise. 

  // Connect  
  http.begin(client, DATA_SERVER);
  
  // Header type for json
  http.addHeader("Content-Type", "application/json");

  // Generate json
  String json = createJSON(data);

  // Post the data
  int httpResponseCode = http.POST(json);

  // Free resources
  http.end();

  // Take action based on success/failure
  if (httpResponseCode == 200) {
    Serial.println(json);
    return true;
  } else if (httpResponseCode == 500) {
    Serial.println("Posting failed with Server Error code 500. Possible bad data? Ignoring.");
    return true;
  } else {
    Serial.println("Posting failed with code: ");
    Serial.println(httpResponseCode);
    return false;
  }
}

String createJSON(Observation t) 
{
  // Convert an observation to JSON string
  // This should be able to work on any sensor
  // type, and only the subroutines should need
  // to be changed.

  // Store the nested data for the reading
  // Format of JSON replies is as follows.  
  //
  // Cases that require multiple data points may use 
  // arrays of readings within ["data"]
  // {
  //  "name": "DEVID",
  //  "type": "DEVTYPE",
  //  "reading": {
  //            "timestamp": 2022-04-01 12:00:00,
  //            "tz": baseTZ+DST_offset,
  //            "data": {
  //                "temperature": 65.5,
  //                "humidity": 98
  //            }
  //          }
  //  "netdata": {
  //             "ip": "192.168.0.XXX",
  //             "mac": "00:00:00:00:00:00"
  //          }
  // }

  // A holder to insert the JSON string at the end.
  String output;

  // Initialize the JSON, see https://arduinojson.org/v7/assistant
  JsonDocument doc;

  // Store the global values.
  doc["name"] = DEVID;
  doc["type"] = DEVTYPE;

  // Add the data
  addObservationDict(doc, t);

  // Add the net info
  addNetDict(doc);
  
  // Convert the doc to a string and return
  serializeJson(doc, output);
  return output;
}

void addNetDict(JsonDocument& docu){
  // Add network data to the JSON object
  // This should work for any sensor type.
  JsonObject netdata = docu["netdata"].to<JsonObject>();
  netdata["ip"] = WiFi.localIP().toString();
  netdata["mac"] = WiFi.macAddress();
}

bool dataTrigger(time_t time){
  // Function to check whether data should be read.
  // This allows for synchronization to a real world
  // time rather than just using the ticks of the 
  // crystal. Uses a NTC clock for syncing, with a 
  // resolution of seconds. Always returns true when 
  // sampling faster than 1s. 

  if (SAMPLE_INTERVAL_MILLIS >= 1000){
    // Compare with the time of day for syncing. 

    // Get the current time of day in seconds
    int t = epochToSeconds(time);

    // Check if we've passed the target time, but not gone WAY past an hour. 
    // We sometimes overshoot, and so don't want to wait a full interval to 
    // read data again, so >=. But if we don't cap the top end we have issues
    // around the midnight reset, where our delta-t will be huge. 
    if (t - nextDataTime >= 0 && (t - nextDataTime) <= 60*60){
      return true;
    } else {
      // We're not ready yet on the real world clock, so just keep waiting.
      return false;
    }
  } else {
    // We're sampling faster than the resolution of NTC, so we're always ready.
    return true;
  }
}

void calcNextTime(time_t time){
  // This function handles the calculation of how long we should wait before 
  // trying to take a reading. It gives us even intervals of the sample 
  // interval, so for example, we'd always try to sample on the minute 
  // if our sampling is minute-wise. 
  // Updates values in nextDataIntervalMillis and nextDataTime.

  // We have to handle subsecond cases here so we avoid errors. 
  if (SAMPLE_INTERVAL_MILLIS >= 1000){
    int t = epochToSeconds(time);

    // We provide it with the time of day in seconds since midnight.
    int iv = SAMPLE_INTERVAL_MILLIS/1000;  // Interval in seconds
    int tilnext = iv - (t % iv);  // Time til next reading in s. Reduces duration if we overran the last round time.
    nextDataIntervalMillis = tilnext * 1000 - DT_MILLIS;  // How long to have the crystal clock wait wait. 
    nextDataTime = (t + tilnext) % (60*60*24);  // Abs next time in s, wrapped by 24h.
  } else {
    // Just rely on the millis() to control the sampling rate.
    nextDataIntervalMillis = SAMPLE_INTERVAL_MILLIS;
    nextDataTime = 0;
  }
}

int epochToSeconds(time_t time){
  // Convert epoch time to time of day in seconds since midnight
  return hour(time) * 60*60 + minute(time) * 60 + second(time);
}

String to_time_string(time_t time){
  // Format a time instance as a readable string
  char buff[32];
  sprintf(buff, "%02d-%02d-%02d %02d:%02d:%02d", year(time), month(time), day(time), hour(time), minute(time), second(time));
  return String(buff);
  // "%4d-%02d-%02d %02d:%02d:%02d\n\n", year(time), month(time), day(time), hour(time), minute(time), second(time)
}
