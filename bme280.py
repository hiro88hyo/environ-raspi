#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import smbus2 as smbus
from time import sleep

class BME280:
	RETRY_COUNT = 3
	RETRY_BASE_WAIT = 0.2

	def __init__(self, I2C_Addr=0x76, I2C_Bus=1, debug=False):
		self._I2C_Addr = I2C_Addr
		self._bus = smbus.SMBus(I2C_Bus)
		self._debug = debug
		self._digT = []
		self._digP = []
		self._digH = []
		self._t_fine = 0.0

		self._Humidity = None
		self._Temperature = None
		self._Pressure = None

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

	def get_calib_param(self):
		calib = []
		for i in range (0x88,0x88+24):
			calib.append(self.read(i))
		calib.append(self.read(0xA1))
		for i in range (0xE1,0xE1+7):
			calib.append(self.read(i))

		self._digT.append((calib[1] << 8) | calib[0])
		self._digT.append((calib[3] << 8) | calib[2])
		self._digT.append((calib[5] << 8) | calib[4])
		self._digP.append((calib[7] << 8) | calib[6])
		self._digP.append((calib[9] << 8) | calib[8])
		self._digP.append((calib[11]<< 8) | calib[10])
		self._digP.append((calib[13]<< 8) | calib[12])
		self._digP.append((calib[15]<< 8) | calib[14])
		self._digP.append((calib[17]<< 8) | calib[16])
		self._digP.append((calib[19]<< 8) | calib[18])
		self._digP.append((calib[21]<< 8) | calib[20])
		self._digP.append((calib[23]<< 8) | calib[22])
		self._digH.append( calib[24] )
		self._digH.append((calib[26]<< 8) | calib[25])
		self._digH.append( calib[27] )
		self._digH.append((calib[28]<< 4) | (0x0F & calib[29]))
		self._digH.append((calib[30]<< 4) | ((calib[29] >> 4) & 0x0F))
		self._digH.append( calib[31] )
						
		for i in range(1,2):
			if self._digT[i] & 0x8000:
				self._digT[i] = (-self._digT[i] ^ 0xFFFF) + 1
		
		for i in range(1,8):
			if self._digP[i] & 0x8000:
				self._digP[i] = (-self._digP[i] ^ 0xFFFF) + 1
				
		for i in range(0,6):
			if self._digH[i] & 0x8000:
				self._digH[i] = (-self._digH[i] ^ 0xFFFF) + 1

	def compensate_P(self, adc_P):
		pressure = 0.0
		
		v1 = (self._t_fine / 2.0) - 64000.0
		v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * self._digP[5]
		v2 = v2 + ((v1 * self._digP[4]) * 2.0)
		v2 = (v2 / 4.0) + (self._digP[3] * 65536.0)
		v1 = (((self._digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8)  + ((self._digP[1] * v1) / 2.0)) / 262144
		v1 = ((32768 + v1) * self._digP[0]) / 32768
		
		if v1 == 0:
			return 0
			
		pressure = ((1048576 - adc_P) - (v2 / 4096)) * 3125
		if pressure < 0x80000000:
			pressure = (pressure * 2.0) / v1
		else:
			pressure = (pressure / v1) * 2
			
		v1 = (self._digP[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
		v2 = ((pressure / 4.0) * self._digP[7]) / 8192.0
		pressure = pressure + ((v1 + v2 + self._digP[6]) / 16.0)
		
		#print "pressure : %7.2f hPa" % (pressure/100)
		self._Pressure = pressure/100

	def compensate_T(self, adc_T):
		v1 = (adc_T / 16384.0 - self._digT[0] / 1024.0) * self._digT[1]
		v2 = (adc_T / 131072.0 - self._digT[0] / 8192.0) * (adc_T / 131072.0 - self._digT[0] / 8192.0) * self._digT[2]
		self._t_fine = v1 + v2
		temperature = self._t_fine / 5120.0
		
		#print "temp : %-6.2f ℃" % (temperature) 
		self._Temperature = temperature

	def compensate_H(self, adc_H):
		var_h = self._t_fine - 76800.0
		if var_h != 0:
			var_h = (adc_H - (self._digH[3] * 64.0 + self._digH[4]/16384.0 * var_h)) * (self._digH[1] / 65536.0 * (1.0 + self._digH[5] / 67108864.0 * var_h * (1.0 + self._digH[2] / 67108864.0 * var_h)))
		else:
			return 0
			
		var_h = var_h * (1.0 - self._digH[0] * var_h / 524288.0)
		if var_h > 100.0:
			var_h = 100.0
		elif var_h < 0.0:
			var_h = 0.0
		
		#print "hum : %6.2f ％" % (var_h)
		self._Humidity = var_h

	def readData(self):
		data = []

		for i in range (0xF7, 0xF7+8):
			data.append(self.read(i))
		pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
		temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
		hum_raw  = (data[6] << 8)  |  data[7]

		self.compensate_T(temp_raw)
		self.compensate_P(pres_raw)
		self.compensate_H(hum_raw)
		
	def begin(self):
		osrs_t = 1			#Temperature oversampling x 1
		osrs_p = 1			#Pressure oversampling x 1
		osrs_h = 1			#Humidity oversampling x 1
		mode   = 3			#Normal mode
		t_sb   = 5			#Tstandby 1000ms
		filter = 0			#Filter off
		spi3w_en = 0		#3-wire SPI Disable
		
		ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
		config_reg    = (t_sb << 5) | (filter << 2) | spi3w_en
		ctrl_hum_reg  = osrs_h
		
		self.write(0xF2,ctrl_hum_reg)
		self.write(0xF4,ctrl_meas_reg)
		self.write(0xF5,config_reg)
		
		self.get_calib_param()

	
	@property
	def Pressure(self):
		return self._Pressure

	@property
	def Temperature(self):
		return self._Temperature

	@property
	def Humidity(self):
		return self._Humidity
