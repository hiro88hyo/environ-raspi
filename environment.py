#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bme280 import BME280
from time import sleep

if __name__ == '__main__':
    sensor = BME280(debug=True)
    sensor.begin()

    sensor.readData()

    print "pressure : %7.2f hPa" % (sensor.Pressure)
    print "temp : %-6.2f ℃" % (sensor.Temperature) 
    print "hum : %6.2f ％" % (sensor.Humidity)