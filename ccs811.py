#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import smbus2 as smbus
from time import sleep

class CCS811:
    CCS811_HW_ID  = 0x81

    REG_STATUS          = 0x00
    REG_MEAS_MODE       = 0x01
    REG_ALG_RESULT_DATA = 0x02
    REG_RAW_DATA        = 0x03
    REG_ENV_DATA        = 0x05
    REG_NTC             = 0x06
    REG_THRESHOLDS      = 0x10
    REG_BASELINE        = 0x11
    REG_HW_ID           = 0x20
    REG_HW_VERSION      = 0x21
    REG_FW_BOOT_VERSION = 0x23
    REG_FW_APP_VERSION  = 0x24
    REG_ERROR_ID        = 0xE0
    REG_APP_START       = 0xF4
    REG_RESET           = 0xFF

    STAT_SUCCESS      = 0x00
    STAT_ID_ERROR     = 0x01
    STAT_DATA_PENDING = 0x80
    STAT_ERROR        = 0xff

    RETRY_COUNT = 5
    RETRY_BASE_WAIT = 0.2

    def __init__(self, I2C_Addr=0x5b, I2C_Bus=1, mode=1, debug=False):
        self._I2C_Addr = I2C_Addr
        self._bus = smbus.SMBus(I2C_Bus)
        self._TVOC = 0
        self._eCO2 = 0
        self._mode = mode
        self._debug = debug

    def write(self, register, value):
        register &= 0xFF
        value = value & 0xFF
        for i in range(self.RETRY_COUNT+1):
            try:
                ret = self._bus.write_byte_data(self._I2C_Addr, register, value)
            except IOError, e:
                if self._debug:
                    print("Retry: {}".format(i+1))
                sleep(self.RETRY_BASE_WAIT*(i+1))
            else:
                return ret
    
    def writeMulti(self, register, data):
        register &= 0xFF
        for i in range(self.RETRY_COUNT+1):
            try:
                ret = self._bus.write_i2c_block_data(self._I2C_Addr, register, data)
            except IOError, e:
                if self._debug:
                    print("Retry: {}".format(i+1))
                sleep(self.RETRY_BASE_WAIT*(i+1))
            else:
                return ret

    def read(self, register):
        register &= 0xFF
        for i in range(self.RETRY_COUNT+1):
            try:
                result = self._bus.read_byte_data(self._I2C_Addr, register) & 0xFF
            except IOError, e:
                if self._debug:
                    print("Retry: {}".format(i+1))
                sleep(self.RETRY_BASE_WAIT*(i+1))
            else:
                return result

    def readMulti(self, register, length):
        register &= 0xFF
        for i in range(self.RETRY_COUNT+1):
            try:
                results = self._bus.read_i2c_block_data(self._I2C_Addr, register, length)
            except IOError, e:
                if self._debug:
                    print("Retry: {}".format(i+1))
                sleep(self.RETRY_BASE_WAIT*(i+1))
            else:
                return results

    def doReset(self):
        data = [0x11, 0xE5, 0x72, 0x8A]
        ret = self.writeMulti(self.REG_RESET, data)
        if ret:
            if self._debug:
                print("doReset: {}".format(hex(ret)))
        sleep(0.1)
        return ret

    def getDriveMode(self):
        value = self.read(self.REG_MEAS_MODE)
        if self._debug:
            print("getDriveMode: REG_MEAS_MODE: {}".format(hex(value)))
        return value

    def setDriveMode(self, mode):
        if mode>4:
            mode = 4
        self._mode = mode

        value = (mode << 4) & 0xF0

        if self._debug:
            print("setDriveMode: DriveMode: {}".format(hex(value)))
        self.write(self.REG_MEAS_MODE, value)
        self.checkForStatusError()

        return self.STAT_SUCCESS

    def setEnvironmentalData(self, temp, humid):
        if (temp<-25) or (temp>50):
            return self.STAT_ERROR
        if (humid<0) or (humid>100):
            return self.STAT_ERROR

        data = [0] * 4

        humid *= 1000
        data[0] = int((humid + 250) / 500)

        temp = (temp+25) * 1000
        data[2] = int((temp + 250) / 500)

        ret = self.writeMulti(self.REG_ENV_DATA, data)

        return ret

    def readAlgorithmResults(self):
        if not self.dataAvailable():
            return False
        else:
            buf = self.readMulti(self.REG_ALG_RESULT_DATA, 8)
            self._eCO2 = ((buf[0] & 0x3F) << 8) | (buf[1])
            self._TVOC = ((buf[2] & 0x07) << 8) | (buf[3])

            if self._debug:
                print("Algorithm result: {}".format(buf))
                print("Algorithm result: eCO2: {}, TVOC: {}, Status: {}, Error_ID: {}, RAW1: {}, RAW2: {}".format(
                    self._eCO2, self._TVOC, hex(buf[4]), hex(buf[5]), hex(buf[6]), hex(buf[7])))

            if (self._eCO2<400) or (self._eCO2>8192):
                return self.STAT_DATA_PENDING
            if (self._TVOC<0) or (self._TVOC>1187):            
                return self.STAT_DATA_PENDING
            if (buf[4] & (0x1 << 0)):
                if (buf[5] & (0x1 << 1)): # READ_REG_INVALID
                    self.getErrorRegister()
                if (buf[5] & (0x1 << 2)): # MEASMODE_INVALID
                    self.getErrorRegister()
                    self.setDriveMode(self._mode)
        return self.STAT_SUCCESS

    def checkForStatusError(self):
        ret = self.read(self.REG_STATUS)
        if self._debug:
            print("checkForStatusError: {}".format(hex(ret)))
        return bool(ret & (0x1 << 0))
    
    def dataAvailable(self):
        ret = self.read(self.REG_STATUS)
        if self._debug:
            print("dataAvailable: {}".format(hex(ret)))
        return bool(ret & (0x1 << 3))

    def appValid(self):
        ret = self.read(self.REG_STATUS)
        if self._debug:
            print("appValid: {}".format(hex(ret)))
        return bool(ret & (0x1 << 4))

    def getErrorRegister(self):
        # 0: WRITE_REG_INVALID 
        # 1: READ_REG_INVALID 
        # 2: MEASMODE_INVALID 
        # 3: MAX_RESISTANCE 
        # 4: HEATER_FAULT 
        # 5: HEATER_SUPPLY 
        ret = self.read(self.REG_ERROR_ID)
        if self._debug:
            print("getErrorRegister: {}".format(hex(ret)))
        return ret

    def getBaseline(self):
        buf = [0] * 2
        buf = self.readMulti(self.REG_BASELINE, 2)        
        ret = (buf[0] << 8) | (buf[1])
        if self._debug:
            print("getBaseline: {}".format(hex(ret)))
        return ret

    def setBaseline(self, value):
        data = [0] * 2
        data[0] = (value >> 8) & 0x00FF
        data[1] = value & 0x00FF

        ret = self.writeMulti(self.REG_BASELINE, data)
        if ret:
            if self._debug:
                print("setBaseline: {}".format(hex(ret)))
        sleep(0.1)
        return ret

    def setInterrupts(self, bit):
        bit = bool(bit)
        value = self.read(self.REG_MEAS_MODE)
        if bit: # enable
            value |= (1 << 3)
        else:   # disable
            value &= ~(1<< 3)
        ret = self.write(self.REG_MEAS_MODE, value)
        return ret

    def enableInterrupts(self):
        ret = self.setInterrupts(1)
        return ret

    def disableInterrupts(self):
        ret = self.setInterrupts(0)
        return ret

    def begin(self):
        ret = self.beginWithStatus()
        return ret

    def beginCore(self):
        ret = self.read(self.REG_HW_ID)
        if self._debug:
            print("beginCore: {}".format(hex(ret)))

        if ret!=self.CCS811_HW_ID:
            raise Exception("Device ID returned is not correct! Please check your wiring.")

        return self.STAT_SUCCESS

    def beginWithStatus(self):
        ret = self.beginCore()
        ret = self.doReset()

        if(self.checkForStatusError()):
            raise Exception("There is an error on the I2C or sensor")
        if(not self.appValid()):
            raise Exception("No application firmware loaded")

        ret = self.writeMulti(self.REG_APP_START, [])
        sleep(0.1)
        self.setDriveMode(self._mode)

        return self.STAT_SUCCESS

    @property
    def eCO2(self):
        return self._eCO2

    @property
    def TVOC(self):
        return self._TVOC