# all the necessary imports
from machine import Pin, I2C
from machine import Pin, ADC
import network
import time
from bmp280 import BMP280
from umqtt.simple import MQTTClient
import ssl
import umail

# wifi setup for pico w
ssid = "PUT YOUR WIFI-NAME HERE"
password = "AND THE PASSWORD FOR IT"

# email alert details
sender = "whatever@gmail.com"
sender_name = "PlantPulse"
sender_password = "Generate 'App Password' in Google Account -settings"
receiver = "who@gmail.com"
subject = "Your plant needs water.."
email_alert_sent = False

# connect to wifi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

connection_timeout = 10
while connection_timeout > 0:
    if wlan.status() == 3: # connected
        break
    connection_timeout -= 1
    print('Waiting for Wi-Fi connection...')
    time.sleep(1)

# connection check
if wlan.status() != 3: 
    raise RuntimeError('[ERROR] Failed to establish a network connection')
else: 
    print('[INFO] CONNECTED!')
    network_info = wlan.ifconfig()
    print('[INFO] IP address:', network_info[0])
    
# config ssl connection w Transport Layer Security encryption (no cert)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT) # TLS_CLIENT = connect as client not server/broker
context.verify_mode = ssl.CERT_NONE # CERT_NONE = not verify server/broker cert - CERT_REQUIRED: verify

# mqtt client connect
client = MQTTClient(client_id=b'jaakko_picow', server="youruniqueservername.s1.eu.hivemq.cloud", port=8883,
                    user="IOT-Jaakko", password="********", ssl=context)

client.connect()

# setting email alerts
smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True)
smtp.login(sender, sender_password)
smtp.to(receiver)

# define I2C, BMP, led and ADC
i2c = machine.I2C(id=0, sda=Pin(20), scl=Pin(21)) # id=channel
bmp = BMP280(i2c)
led_blue = Pin(15, Pin.OUT)
moisture = ADC(Pin(28))

# when message is received on Pico W
def subscribe_callback(topic, msg):
    topic_str = topic.decode()
    msg_str = msg.decode()
    print("[INFO][SUB] Topic:", topic_str, "| Message:", msg_str)
    if topic_str == 'jaakko_picow/led':
        if msg_str == "ON":
            led_blue.value(1)
            time.sleep_ms(3000)
            led_blue.value(0)
        else:
            led_blue.value(0)

# sets subscription to a certain topic
def subscribe(mqtt_client, topic):
    mqtt_client.set_callback(subscribe_callback)
    mqtt_client.subscribe(topic)
    print("[INFO][SUB] Subscribed to:", topic)

# function for publishing data to mqtt
def publish(mqtt_client, topic, value):
    mqtt_client.publish(topic, value)
    print("[INFO][PUB] Published {} to {} topic".format(value, topic))

subscribe(client, b'jaakko_picow/led')

# loop checking the messages and making the calculations and publishing data to the HiveMQ
while True:
    client.check_msg()
    raw_value_soil = moisture.read_u16()
    dry_soil = 65535
    wet_soil = 17000
    if raw_value_soil >= dry_soil:
        moisture_percent = 0
    elif raw_value_soil <= wet_soil:
        moisture_percent = 100
    else:
        moisture_percent = (dry_soil - raw_value_soil) / (dry_soil - wet_soil) * 100
    
    moisture_str = f"{moisture_percent:.0f}"
    if moisture_percent < 30:
        if not email_alert_sent:
            smtp.write(sender_name + subject + "\n")
            smtp.write("The soil is too dry, water it to sustain the life of your plant!")
            smtp.send()
            print("[INFO] Email alert sent!")
            email_alert_sent = True
    else:
        email_alert_sent = False
        
    temperature = bmp.temperature
    temp_str = f"{temperature:.1f}"
    
    pressure = bmp.pressure
    pressure_kpa = pressure / 1000
    pressure_kpa_str = f"{pressure_kpa:.3f}"
    
    publish(client, 'jaakko_picow/moisture', moisture_str)    
    publish(client, 'jaakko_picow/temp', temp_str)
    publish(client, 'jaakko_picow/pressure', pressure_kpa_str)

    # every 5s
    for i in range (50):
        client.check_msg()
        time.sleep_ms(100)
