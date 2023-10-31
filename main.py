from machine import Pin, PWM, Timer, ADC, unique_id
import dht
import _thread
from umqtt.simple import MQTTClient
import ubinascii

#already imported on boot.py
#import time 
#from network import WLAN 

# screen /dev/tty.usbserial-01E4EE42  115200
# screen /dev/tty.usbserial-01E4EDCA  115200
# ampy --port /dev/tty.usbserial-01E4EE42 --baud 115200 put boot.py 
# ampy --port /dev/tty.usbserial-01E4EDCA --baud 115200 put boot.py 
# ampy --port /dev/tty.usbserial-01E4EDCA --baud 115200 put main.py 

ldr   = ADC(Pin(34))
soil  = ADC(Pin(33))
relay = Pin(23, mode=Pin.OUT)
sev   = Pin(22, mode=Pin.OUT)
led   = Pin(13, mode=Pin.OUT)
d     = dht.DHT11(Pin(32)) 

ldr.atten (ADC.ATTN_11DB)       #Full range: 3.3v
soil.atten(ADC.ATTN_11DB)       #Full range: 3.3v

def led_flash():
  for x in range(1,10):
    led(1)
    time.sleep(0.2)
    led(0)
    time.sleep(0.2)

led_flash()

def pump(t):    #t=time of watering
    relay(1)
    time.sleep(t)
    relay(0)

def LDR_get():  #return LDR reading
  return ldr.read()

def Soil_get(): #return soil moisture
  return soil.read()

def rotate(n,t):   #rotate the plant n degree
  sevro=PWM (sev,freq=100)
  if n== 1:
    sevro.duty(90)
  else:
    sevro.duty(180)
  time.sleep(t/10)
  sevro.duty(0)

def get_temp(): #return air temp
  try:
    d.measure()
    return d.temperature()
  except OSError:
    print("OSError,will return 20")
    return 20
def get_humidity(): #return humidity
  try:
    d.measure()
    return d.humidity()
  except OSError:
    print("OSError,will return 50%")
    return 50

DLTS_P=1/43200
SOIL_P=1/4096
TEMP_P=1/20
CONS_O=4

MQTT_watered=False
MQTT_rotated=False

dlt=0 #s
h,m,s=8,54,0#daily watering time and reset dlt

def daily_light_time(valve=3400): #valve is around 3000
  global dlt
  while True:
    if LDR_get()>valve:
      dlt+=1
      time.sleep(1)
      print("today's light time = ",dlt,"s")

# I call it quaternary control，what a genius idea!
position =0
counter  =0

def auto_rotate(count=3,delay=3600):
  global position
  global counter
  global MQTT_rotated
  if counter < count:
    counter+=1
  else:
    counter=0
    time.sleep(delay)#will rotate after 1h
    if position <3:
      rotate(0,1)
      position+=1
    else:
      rotate(1,14) #back to start position
      position=0
    MQTT_rotated=True
  #print(counter,position)

def daily_watering():
  global dlt,MQTT_watered
  while True:
    time.sleep(0.5)#reduce loop times
    if time.localtime()[3]==h and time.localtime()[4]==m and time.localtime()[5]==s:
      time_watering=Soil_get()*SOIL_P + get_temp()*TEMP_P + dlt * DLTS_P + CONS_O
      pump(time_watering)
      dlt=0
      print("dlt reset!")
      MQTT_watered=True
      auto_rotate()

def update_watering_time(t):
  global h,m,s
  s=t%100
  m=t//100%100
  h=t//10000%100
  print('Watering time updated! New watering time is ',h,m,s)

def update_DLTS(DLTS):
  global DLTS_P
  DLTS_P=1/DLTS
  print('DLT Parameter updated, New parameter is',DLTS_P)

def update_SOIL(SOIL):
  global SOIL_P
  SOIL_P=1/SOIL
  print('SOIL Parameter updated, New parameter is',SOIL_P)

def update_TEMP(TEMP):
  global TEMP_P
  TEMP_P=1/TEMP
  print('TEMP Parameter updated, New parameter is',TEMP_P)

def update_CONS(CONS):
  global CONS_O
  CONS_O=CONS
  print('CONS Parameter updated, New parameter is',CONS_O)


#MQTT
mqtt_server = '192.168.100.4' #192.168.100.4 
client_id = ubinascii.hexlify(unique_id())
topic_pub = b'pot_log'

topic_time= b'pot_time'
topic_dlts= b'pot_dlts'
topic_soil= b'pot_soil'
topic_temp= b'pot_temp'
topic_cons= b'pot_cons'

def sub_cb(topic, msg):
  print((topic, msg))
  if topic == topic_time:
    update_watering_time(int.from_bytes(msg,"big"))
  if topic == topic_dlts:
    update_DLTS(int.from_bytes(msg,"big"))
  if topic == topic_soil:
    update_SOIL(int.from_bytes(msg,"big"))
  if topic == topic_temp:
    update_TEMP(int.from_bytes(msg,"big"))  
  if topic == topic_cons:
    update_CONS(int.from_bytes(msg,"big"))  

  """
  # declaring byte value
  byte_val = b'\x00\x01'
  # converting to int
  # byteorder is big where MSB is at start
  int_val = int.from_bytes(byte_val, "big")
  # printing int equivalent
  print(int_val)
  """

def connect_and_subscribe():
  global client_id, mqtt_server
  global topic_cons, topic_soil, topic_temp, topic_time,topic_dlts
  client = MQTTClient(client_id, mqtt_server)
  client.set_callback(sub_cb)
  client.connect()
  client.subscribe(topic_time)
  client.subscribe(topic_dlts)
  client.subscribe(topic_soil)
  client.subscribe(topic_temp)
  client.subscribe(topic_cons)
  print('Connected to %s MQTT broker' % mqtt_server)
  return client

def mqtt_thread():
  global MQTT_watered,MQTT_rotated
  last_log = 0
  message_interval = 5 #1800 # send current soil moistrue and ldr reading to mqtt server every 30 min
  while True:
    try:
      client = connect_and_subscribe()
      while True:
        try:
          client.check_msg()
          if (time.time() - last_log) > message_interval:
            msg = b'Soil Moisture :%d' % Soil_get() + b'Light :%d' % LDR_get() + b'Light times:%d' % dlt
            client.publish(topic_pub, msg)
            last_log = time.time()
          if MQTT_watered:
            msg = b'Watered'
            client.publish(topic_pub, msg)
            MQTT_watered=False
          if MQTT_rotated:
            msg = b'Rotated'
            client.publish(topic_pub, msg)
            MQTT_rotated=False
        except OSError as e:
          print("Error: disconnected")
          break
    except OSError as e:
      print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(1)

thread1= _thread.start_new_thread(daily_light_time, ())
if wlan.isconnected():
  thread2= _thread.start_new_thread(mqtt_thread,())
daily_watering() #watering thread
