# all the necessary imports
from machine import Pin, I2C
from machine import Pin, ADC
import network
import time
from bmp280 import BMP280
from umqtt.simple import MQTTClient
import ssl
import umail
import ntptime
import gc

# timestamp for evaluation experiments
def get_finland_timestamp_ms():
    finland_offset = 2 #for winter time (UTC +2)
    y,m,d,hh,mm,ss,*_ = time.localtime()
    hh = (hh + finland_offset) % 24
    ms = time.ticks_ms() % 1000
    return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"

# wifi setup for pico w
ssid = "YOUR WIFI ROUTER NAME"
password = "AND PASSWORD FOR THAT"

# email alert details
sender = "who@gmail.com"
sender_name = "PlantPulse"
sender_password = "IF GMAIL, GET APP PASSWORD FROM GOOGLE ACCOUNT SETTINGS AND PASTE HERE"
receiver = "you@gmail.com"
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

# internet connection check
if wlan.status() != 3: 
    raise RuntimeError('[ERROR] Failed to establish a network connection')
else: 
    print('[INFO] CONNECTED!')
    network_info = wlan.ifconfig()
    print('[INFO] IP address:', network_info[0])

#sync pico w time with NTP server
ntptime.settime()
print("UTC time:", time.localtime())
print("Finland time:", get_finland_timestamp_ms())

# create SSL context to enable TLS
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT) # connect as client instead of server/broker
context.verify_mode = ssl.CERT_NONE # server certificate verification not needed

# mqtt client connect
client = MQTTClient(
    client_id=b'jaakko_picow',
    server="SERVER URL HERE",
    port=8883,
    user="USERNAME",
    password="******",
    ssl=context
)

client.connect()

# email information and text for it
def send_email_alert():
    smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True) # 465 is only for GMAIL
    smtp.login(sender, sender_password)
    smtp.to(receiver)
    smtp.write(sender_name + subject + "\n")
    smtp.write("The soil is too dry, water it to sustain the life of your plant!")
    smtp.send()
    smtp.quit()

# define I2C, BMP, led and ADC
i2c = machine.I2C(id=0, sda=Pin(20), scl=Pin(21)) # id=channel
bmp = BMP280(i2c)
led_blue = Pin(15, Pin.OUT)
moisture = ADC(Pin(28))

# decode bytes into string
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
            
# callback function for messages incoming to pico w         
def subscribe(mqtt_client, topic):
    mqtt_client.set_callback(subscribe_callback)
    mqtt_client.subscribe(topic)
    print("[INFO][SUB] Subscribed to:", topic)

# function for publishing data to mqtt
def publish(mqtt_client, topic, value):
    mqtt_client.publish(topic, value)
    print("[INFO][PUB] Published {} to {} topic".format(value, topic))

subscribe(client, b'jaakko_picow/led')

while True:
    client.check_msg()
    
    # getting soil moisture values
    raw_value_soil = moisture.read_u16()
    dry_soil = 65535 # calibrated with moisture sensor in the air
    wet_soil = 17000 # calibrated with moisture sensor in glass of water

    # calculating percentage form from raw moisture values for clarity
    if raw_value_soil >= dry_soil:
        moisture_percent = 0
    elif raw_value_soil <= wet_soil:
        moisture_percent = 100
    else:
        moisture_percent = (dry_soil - raw_value_soil) / (dry_soil - wet_soil) * 100
    moisture_str = f"{moisture_percent:.0f}"
    
    #logic for when email alert is sent
    if moisture_percent < 30:
        if not email_alert_sent:
            send_email_alert()
            print("[INFO] Email alert sent!")
            email_alert_sent = True
    else:
        email_alert_sent = False

    # formatting raw value to one decimal form
    temperature = bmp.temperature
    temp_str = f"{temperature:.1f}"

    # formatting raw value into kPa with three decimals
    pressure = bmp.pressure
    pressure_kpa = pressure / 1000
    pressure_kpa_str = f"{pressure_kpa:.3f}"

    # all the values are in string-form but they contain only numbers (adding units like kPa happens in mobile app code blocks)
    print(get_finland_timestamp_ms(), " / Moisture:", moisture_str)
    print(get_finland_timestamp_ms(), " / Temp:", temp_str)
    print(get_finland_timestamp_ms(), " / Pressure:", pressure_kpa_str)

    # calling publish-function to send the values into hivewmq
    publish(client, 'jaakko_picow/moisture', moisture_str)    
    publish(client, 'jaakko_picow/temp', temp_str)
    publish(client, 'jaakko_picow/pressure', pressure_kpa_str)

    # every 120s (= 2 min)
    for i in range (1200):
        client.check_msg()
        time.sleep_ms(100)
        
    # just to make sure memory is freed from temporary variables
    gc.collect()


