#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>  
#include <WiFiUdp.h>
#include <NTPClient.h>              // By Fabrice Weinberg
#include <ArduinoJson.h>            // ArduinoJson by Benoit Blanchon 
#include <TimeLib.h>                // Time library by Paul Stoffregen
#include <DHT.h>                    // DHT sensor libary by Adafruit


// Constants 
const String  SSID    = "SSID";
const String  PASS    = "PASSWORD";
const String  SERVER  = "http://<IPADDR>:8080/DataLogger/log";
const String  NODE    = "HZ18551"; // Change this to match the record in the database
const int     RATE    = 60000;                                                      // Take reading rate
const int     BUFFER  = 500;                                                        // Buffer Size
const int     LED     = D1;                                                         // Status LED

// Structure to hold the data
struct Observation 
{
  float temp;
  float humidity;
  time_t stamp;
};

// Variables
unsigned long lastTime = 0;       // Holds last time in MS for readings
unsigned long errorTime = 0;      // Holds last time in MS for re-transmission during an error
int pos = 0;                      // Holds current position
bool netError = false;            // Used to indicate a network error
bool dhtError = false;            // Used to indicate a temp error
bool dataToTransmit = false;      // Determins if there is data ready to transmit
Observation data[BUFFER];         // Used to buffer data

// Objects for the HTTP connection
WiFiClient client;
HTTPClient http;

// Time server objects and variables
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "<IPADDR>", 3600*-5, 60000);
time_t epochTime;

// Variables and object for temp sensor
#define DHTDATA D5
#define DHTPOWER D6
#define DHTTYPE DHT22
DHT dht(DHTDATA, DHTTYPE); 


void setup() 
{
  // Init serial communication
  Serial.begin(115200);

  // Delay for 2 seconds so we don't miss any of the messages
  delay(2000);  

  // Set LED pin as output
  pinMode(LED, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(DHTPOWER, OUTPUT);
  digitalWrite(DHTPOWER, HIGH);
  
  // Enable the temp sensor
  dht.begin();

  // Display Identification
  Serial.println();
  Serial.println();
  Serial.println();
  Serial.println("Penn State Hazleton");
  Serial.println("Sensor Node: " + NODE);
  Serial.println("SSID: " + SSID);
  Serial.print("MAC: ");
  Serial.print(WiFi.macAddress() + "\n");
  Serial.println("");

  // Init WiFi connection
  WiFi.begin(SSID, PASS);
  Serial.println("Attempting to connect to the network.");
  Serial.print("Connecting");

  // Wait to connect and print dots. Checks the status every 500ms
  while(WiFi.status() != WL_CONNECTED) 
  {
    // Turn LED ON
    digitalWrite(LED, HIGH);
    digitalWrite(LED_BUILTIN, LOW);
    delay(250);

    // Turn LED OFF
    digitalWrite(LED, LOW);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(250);

    // Print out dots to indicate connecting
    Serial.print(".");
  }
  Serial.println("");

  // Turn LED off
  digitalWrite(LED, LOW);
  digitalWrite(LED_BUILTIN, LOW);

  // Display success message
  Serial.println("Connected to the WiFi network.");
  Serial.println();

  // Display the network information
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  // Get the time  and display it
  timeClient.begin();
  timeClient.update();
  epochTime = timeClient.getEpochTime();
  Serial.print("Syncronized time to: ");
  Serial.print(timeClient.getFormattedTime());
  Serial.printf("%4d-%02d-%02d %02d:%02d:%02d\n\n", year(epochTime), month(epochTime), day(epochTime), hour(epochTime), minute(epochTime), second(epochTime));

  // Experimental addition to auto update IP and MAC in database. Useful for troubleshooting
  http.begin(client,"http://<IPADDR>:8080/DataLogger/device");
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  uint8_t MAC_array[6];
  char MAC_char[18];

  String formattedMAC = "";

  // Convert the MAC to a character array
  WiFi.macAddress(MAC_array);
  for (int i = 0; i < sizeof(MAC_array); ++i){
    sprintf(MAC_char,"%s%02x:", MAC_char, MAC_array[i]);
  }

 
  // Remove the last character
  MAC_array[17] = '\0';

  String test = WiFi.macAddress();
 

  // Post the data to the server
  String httpRequestData = "node=" + NODE + "&ip=" + WiFi.localIP().toString()  + "&mac=" + test + "";   
  Serial.println("Registering the IP address and MAC address to the server.");   
  Serial.println(httpRequestData);     
  Serial.println();  
  int httpResponseCode = http.POST(httpRequestData);
}


void loop() 
{
  // If there is an error turn on the LED
  if (netError || dhtError)
  {
    digitalWrite(LED, HIGH);
    digitalWrite(LED_BUILTIN, LOW);
  }
  else
  {
    digitalWrite(LED, LOW);
    digitalWrite(LED_BUILTIN, HIGH);
  }

  // Take a reading based on a MS delay
  if (millis() - lastTime > RATE) 
  {
    // Update the MS
    lastTime = millis();
    
    // Add the reading to the buffer
    takeReading(); 
  }

  // Attempt to post any data in the buffer
  if (!netError)
    postData();
  else if (millis() - errorTime > 60000)  // Waits one minute if there was an error before trying again
    postData();
}

String createJSON(Observation t) 
{
  // Will hold the JSON
  String output;

  // Document size set to 96 based on calcaulator at https://arduinojson.org/v6/assistant/#/step1
  StaticJsonDocument<96> doc;

  // Store the values in the doc
  doc["node"] = NODE;
  doc["temperature"] = t.temp;
  doc["humidity"] = t.humidity;
  doc["stamp"] = t.stamp;
      
  // Convert the doc to a string
  serializeJson(doc, output);

  return output;
}


void takeReading()
{
  // Add to the buffer if there is room
  if (pos < BUFFER)
  {
    dhtError = false;

    // Get the current time
    timeClient.update();
    epochTime = timeClient.getEpochTime();

    // Get the sensor data
    float f = dht.readTemperature(true);
    float h = dht.readHumidity();


    if (isnan(h) || isnan(f))
    {
      Serial.println("Null data from temperature sensor.");
      dhtError = true;
    }
    else
    {
      // Write the data to the array
      data[pos].temp = f;
      data[pos].humidity = h;
      data[pos].stamp = epochTime;

      // Print an update to the screen
      Serial.print("Writting data to buffer position ");
      Serial.println(pos + 1);

      // Indicate there is now data ready to transmit
      dataToTransmit = true;

      // Increment the position
      pos++;
    }
  }
  else
  {
    // Output that the budder is full indicating data was not recorded
    Serial.println("Buffer is full");
  }
}


void shiftArray()
{
  // Move everything one position to the left
  for (int i = 0; i < BUFFER - 1; i++)
  {
    data[i] = data[i+1];
  }
}


void postData()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    netError = true;
    Serial.print("Attempting to reconnect to the WIFI network");
    // Attempt to reconnect to the network if we lost connection
    WiFi.reconnect();
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    netError = false;
    // If there is data in the array attempt to transmit it
    if (dataToTransmit)
    {
      // Format the post
      http.begin(client, SERVER);
            
      // Header type for hson
      http.addHeader("Content-Type", "application/json");

      // Generate json
      String json = createJSON(data[0]);

      // Post the data
      int httpResponseCode = http.POST(json);
      Serial.print("Posting data to server from buffer position 1 of ");
      Serial.println(pos);
      Serial.println(json);
      Serial.println();
      
      // Free resources
      http.end();
          
      // Determine if the data was received
      if (httpResponseCode != 200)
      {
        Serial.println();

        // There was an error 
        netError = true;

        // Print the response code
        Serial.println("An error has occured transmitting the data.");

        // Print the response code
        Serial.print("HTTP Response code: ");
        Serial.println(httpResponseCode);

        // Record the current time
        // Print an error message to the screen
        Serial.println("Waiting one minute before trying again.");
        Serial.println();
      } 
      else
      {
        // There was no error
        netError = false;

        // Remove data from the buffer
        pos--;
        if (pos == 0)
          // We have transmitted all of the data
          dataToTransmit = false;
        else
          // There is more data to transmit, move it to position 0
          shiftArray();
      } 
      errorTime = millis();   
    }
  }
}