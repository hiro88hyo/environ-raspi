#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import urllib
import urllib2
from ccs811 import CCS811
from bme280 import BME280
from time import sleep

import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import subprocess

def post2thinger(temp, hum, press, co2):
    url = os.environ['THINGER_ENDPOINT'] 
    method = "POST"
    headers = {"Content-Type" : "application/json",
    "Authorization" : "Bearer "+ os.environ['THINGER_AUTH_KEY']
    }

    data = {"temperature" : "{:-6.2f}".format(temp),
            "humidity" : "{:6.2f}".format(hum),
            "pressure": "{:7.2f}".format(press),
            "eco2" : str(co2)}
    json_data = json.dumps(data).encode("utf-8")

    print(json_data)
    request = urllib2.Request(url, data=json_data, headers=headers)
    f = urllib2.urlopen(request)
    print(f.read())

def display(disp, draw, font, temp, hum, press, co2):
    width = disp.width
    height = disp.height
    padding = -2
    top = padding
    bottom = height-padding

    draw.rectangle((0,0,width,height), outline=0, fill=0)

    draw.text((0, top+2),     u"温度：  {:6.1f} ℃".format(temp),  font=font, fill=255)
    draw.text((0, top+18),    u"湿度：  {:6.1f} %".format(hum), font=font, fill=255)
    draw.text((0, top+34),    u"気圧：{:6.1f} hPa".format(press),  font=font, fill=255)
    draw.text((0, top+50),    u"CO2 ：{:6.1f} ppm".format(co2),  font=font, fill=255)

    disp.image(image)
    disp.display()

if __name__ == '__main__':
    # initialize variables
    is_thinger = True
    is_display = True
    SSD1306_I2C_Address = 0x3C

    # initialize Air sensor
    air_sensor = CCS811(debug=False)
    air_sensor.begin()

    # Initialize Environment sensor
    env_sensor = BME280(debug=True)
    env_sensor.begin()
    env_sensor.readData()

    # Initialize display
    disp = Adafruit_SSD1306.SSD1306_128_64(rst=None, i2c_address=SSD1306_I2C_Address)
    disp.begin()
    disp.clear()
    disp.display()

    air_sensor.setEnvironmentalData(env_sensor.Temperature, env_sensor.Humidity)

    image = Image.new('1', (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0,0,disp.width,disp.height), outline=0, fill=0)
    font = ImageFont.truetype('./font/KH-Dot-Kodenmachou-16.ttf', 16, encoding='unic')

    tick = 1
    while not air_sensor.dataAvailable():
        sleep(0.1)

    while True:
        print("Tick: {}".format(tick))
        if not air_sensor.dataAvailable():
            sleep(1)
            continue
        if air_sensor.readAlgorithmResults()==CCS811.STAT_SUCCESS:
            temp = env_sensor.Temperature
            hum = env_sensor.Humidity
            press = env_sensor.Pressure
            co2 = air_sensor.eCO2

            if is_thinger:
                post2thinger(temp, hum, press, co2)
            if is_display:
                display(disp, draw, font, temp, hum, press, co2)

            print("eCO2: {} ppm, TVOC: {} ppb".format(air_sensor.eCO2, air_sensor.TVOC))
            print("Temperature: {:-6.2f}, Humidity: {:6.2f}, Pressure: {:7.2f}".format(env_sensor.Temperature, env_sensor.Humidity, env_sensor.Pressure))
            air_sensor.getDriveMode()
            air_sensor.getBaseline()
            air_sensor.setEnvironmentalData(env_sensor.Temperature, env_sensor.Humidity)
            env_sensor.readData()
        else:
            print("Pending")
        sleep(60)
        tick += 1