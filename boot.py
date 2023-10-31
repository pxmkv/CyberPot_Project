# Establish Internet connection
from network import WLAN, STA_IF
import ntptime
import time

    wlan = WLAN(STA_IF)
    wlan.active(True)

wlan.connect('POT_MQTT', '1104Maritime')

tries = 0
while not wlan.isconnected() and tries < 10:
    print("Waiting for wlan connection")
    time.sleep(1)
    tries = tries + 1

if wlan.isconnected():
        print("WiFi connected at", wlan.ifconfig()[0])
else:
        print("Unable to connect to WiFi")
try:
    ntptime.settime()
except:
      print('can not get time from ntp server')
print(time.localtime())
# fetch NTP time




    
