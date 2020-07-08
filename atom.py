#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ccs811 import CCS811
from time import sleep

if __name__ == '__main__':
    sensor = CCS811(debug=True)
    sensor.begin()
    sensor.setEnvironmentalData(22.0, 40.0)

    tick = 1
    while not sensor.dataAvailable():
        sleep(0.1)

    while True:
        print("Tick: {}".format(tick))
        if not sensor.dataAvailable():
            sleep(1)
            continue
        if sensor.readAlgorithmResults()==CCS811.STAT_SUCCESS:
            print("eCO2: {} ppm, TVOC: {} ppb".format(sensor.eCO2, sensor.TVOC))
            sensor.getDriveMode()
        else:
            print("Pending")
        sleep(2)
        tick += 1