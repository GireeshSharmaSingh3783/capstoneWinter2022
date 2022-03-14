#!/usr/bin/python

from threading import Thread
import time
import RPi.GPIO as GPIO
import smbus
#import firebase
import json
#import pyrebase
import requests
import sys
import os
from ctypes import c_short
from ctypes import c_byte
from ctypes import c_ubyte

global cycle
cycle = 0.0

class Hello5Program:
    def __init__(self):
        self._running = True

    def terminate(self):  
        self._running = False  

    def run(self):
        global cycle
        while self._running:
            time.sleep(5) #Five second delay
            cycle = cycle + 1.0
            #print("5 Second Thread cycle+1.0 - ", cycle)
            #BME CODE
            
            DEVICE = 0x76 # Default device I2C address


            bus = smbus.SMBus(1) # Rev 2 Pi, Pi 2 & Pi 3 uses bus 1
                                 # Rev 1 Pi uses bus 0

            def getShort(data, index):
              # return two bytes from data as a signed 16-bit value
              return c_short((data[index+1] << 8) + data[index]).value

            def getUShort(data, index):
              # return two bytes from data as an unsigned 16-bit value
              return (data[index+1] << 8) + data[index]

            def getChar(data,index):
              # return one byte from data as a signed char
              result = data[index]
              if result > 127:
                result -= 256
              return result

            def getUChar(data,index):
              # return one byte from data as an unsigned char
              result =  data[index] & 0xFF
              return result

            def readBME280ID(addr=DEVICE):
              # Chip ID Register Address
              REG_ID     = 0xD0
              (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
              return (chip_id, chip_version)

            def readBME280All(addr=DEVICE):
              # Register Addresses
              REG_DATA = 0xF7
              REG_CONTROL = 0xF4
              REG_CONFIG  = 0xF5

              REG_CONTROL_HUM = 0xF2
              REG_HUM_MSB = 0xFD
              REG_HUM_LSB = 0xFE

              # Oversample setting - page 27
              OVERSAMPLE_TEMP = 2
              OVERSAMPLE_PRES = 2
              MODE = 1

              # Oversample setting for humidity register - page 26
              OVERSAMPLE_HUM = 2
              bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)

              control = OVERSAMPLE_TEMP<<5 | OVERSAMPLE_PRES<<2 | MODE
              bus.write_byte_data(addr, REG_CONTROL, control)

              # Read blocks of calibration data from EEPROM
              # See Page 22 data sheet
              cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
              cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
              cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

              # Convert byte data to word values
              dig_T1 = getUShort(cal1, 0)
              dig_T2 = getShort(cal1, 2)
              dig_T3 = getShort(cal1, 4)

              dig_P1 = getUShort(cal1, 6)
              dig_P2 = getShort(cal1, 8)
              dig_P3 = getShort(cal1, 10)
              dig_P4 = getShort(cal1, 12)
              dig_P5 = getShort(cal1, 14)
              dig_P6 = getShort(cal1, 16)
              dig_P7 = getShort(cal1, 18)
              dig_P8 = getShort(cal1, 20)
              dig_P9 = getShort(cal1, 22)

              dig_H1 = getUChar(cal2, 0)
              dig_H2 = getShort(cal3, 0)
              dig_H3 = getUChar(cal3, 2)

              dig_H4 = getChar(cal3, 3)
              dig_H4 = (dig_H4 << 24) >> 20
              dig_H4 = dig_H4 | (getChar(cal3, 4) & 0x0F)

              dig_H5 = getChar(cal3, 5)
              dig_H5 = (dig_H5 << 24) >> 20
              dig_H5 = dig_H5 | (getUChar(cal3, 4) >> 4 & 0x0F)

              dig_H6 = getChar(cal3, 6)

              # Wait in ms (Datasheet Appendix B: Measurement time and current calculation)
              wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
              time.sleep(wait_time/1000)  # Wait the required time  

              # Read temperature/pressure/humidity
              data = bus.read_i2c_block_data(addr, REG_DATA, 8)
              pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
              temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
              hum_raw = (data[6] << 8) | data[7]

              #Refine temperature
              var1 = ((((temp_raw>>3)-(dig_T1<<1)))*(dig_T2)) >> 11
              var2 = (((((temp_raw>>4) - (dig_T1)) * ((temp_raw>>4) - (dig_T1))) >> 12) * (dig_T3)) >> 14
              t_fine = var1+var2
              temperature = float(((t_fine * 5) + 128) >> 8);

              # Refine pressure and adjust for temperature
              var1 = t_fine / 2.0 - 64000.0
              var2 = var1 * var1 * dig_P6 / 32768.0
              var2 = var2 + var1 * dig_P5 * 2.0
              var2 = var2 / 4.0 + dig_P4 * 65536.0
              var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
              var1 = (1.0 + var1 / 32768.0) * dig_P1
              if var1 == 0:
                pressure=0
              else:
                pressure = 1048576.0 - pres_raw
                pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
                var1 = dig_P9 * pressure * pressure / 2147483648.0
                var2 = pressure * dig_P8 / 32768.0
                pressure = pressure + (var1 + var2 + dig_P7) / 16.0

              # Refine humidity
              humidity = t_fine - 76800.0
              humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity)))
              humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
              if humidity > 100:
                humidity = 100
              elif humidity < 0:
                humidity = 0

              return temperature/100.0,pressure/100.0,humidity
            
            def main():

              (chip_id, chip_version) = readBME280ID()
              print("Chip ID     :", chip_id)
              print("Version     :", chip_version)

                
            while True:
                time.sleep(3.000)
                temperature,pressure,humidity = readBME280All()
                
                press = pressure
                press = '{0:.8g}'.format(press)
                
                print("Temperature : ", temperature, "C")
                print("Pressure : ", press, "hPa")
                
                url= "https://safesmarthome-cdf48-default-"
                data = {
                    "BME":{
                    "Temp": temperature,
                    "Pressure": press
                    }
                    }
                #tem = temperature
                headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
                r = requests.post(url, data=json.dumps(data), headers=headers)

            time.sleep(3.000)

            if __name__=="__main__":
               main()


class Hello2Program:
    
    def __init__(self):
        self._running = True

    def terminate(self):  
        self._running = False  

    def run(self):
        global cycle
        while self._running:
            time.sleep(2) #Five second delay
            try:
              GPIO.setmode(GPIO.BCM)

              PIN_TRIGGER = 4
              PIN_ECHO = 27
              
              GPIO.setwarnings(False)
              GPIO.setup(PIN_TRIGGER, GPIO.OUT)
              GPIO.setup(PIN_ECHO, GPIO.IN)
              
              GPIO.output(PIN_TRIGGER, GPIO.LOW)
              

              print ("Waiting for sensor to settle")

              time.sleep(2)

              print ("Calculating distance")
              
              
              while True:
              
               GPIO.output(PIN_TRIGGER, GPIO.HIGH)

               time.sleep(0.00001)

               GPIO.output(PIN_TRIGGER, GPIO.LOW)

               while GPIO.input(PIN_ECHO)==0:
                    pulse_start_time = time.time()
               while GPIO.input(PIN_ECHO)==1:
                    pulse_end_time = time.time()

               pulse_duration = pulse_end_time - pulse_start_time
               distance = round(pulse_duration * 17150, 2)
               print ("Distance:",distance,"cm")
               
               url= "https://safesmarthome-cdf48-defau"
               
               data = distance
               headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
               r = requests.post(url, data=json.dumps(data), headers=headers)
               
               time.sleep(0.055)
            
            finally:
                    GPIO.cleanup()
                    
class LEDD:
    def __init__(self):
        self._running = True

    def terminate(self):  
        self._running = False  

    def run(self):
        global cycle
        while self._running:
            try:
                import RPi.GPIO as GPIO
            except RuntimeError:
                print("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")

            PIN_18=23     #GPIO18  -- this LED is driven by GPIO 18. i.e., GPIO 18 is connected to the Base of the transistor.  
            PIN_17=17     #GPIO17  -- not used in the LED circuit, but used as another example.

            GPIO_Out_List=[PIN_17,PIN_18]   # use a list to declare the output ports used in the code. 

            def blinkLED():                 # function to blinkLED 1000 times at 1HZ rate. def is used to declare the function. 
               i = 0; 
               for i in range (0, 1000):   # repeat 1000 times. 
                  turnON()
                  sleep(0.5)  # delay for 0.5 second.
                  turnOFF()
                  sleep(0.5)   # delay for 0.5 second.
                  i+= 1
               return

            def turnOFF():
                GPIO.output(PIN_18, GPIO.LOW)    # Turn OFF the LED connected to GPIO 18.
                #print ('turn OFF the LED')
                return

            def turnON():
                GPIO.output(PIN_18, GPIO.HIGH)    # Turn ON the LED connected to GPIO 18.
                #print ('turn ON the LED')
                return
               
            def main():  # main function to start. 
                global PIN_17
                global PIN_18    
                global GPIO_Chan_List

                print ('Start LED blinking')    
                GPIO.setmode(GPIO.BCM)   # use this BCM (Board GPIO number) instead of using Board Pin numbers. 
                GPIO.setwarnings(False)
                
                GPIO.setup(GPIO_Out_List, GPIO.OUT)  #Initialize the Channel List PIN_17 and PIN_18 as outputs. 

                blinkLED()    # Blink the LEDs (On for 0.5 second, Off for 0.5 second) 

                
            if __name__ == "__main__":    # Declare the code starts from main().
              main()


              
                        
        
 #Create Class
FiveSecond = Hello5Program()
#Create Thread
FiveSecondThread = Thread(target=FiveSecond.run) 
#Start Thread 
FiveSecondThread.start()


 #Create Class
TwoSecond = Hello2Program()
#Create Thread
TwoSecondThread = Thread(target=TwoSecond.run) 
#Start Thread 
TwoSecondThread.start()

 #Create Class
ThreeThird = LEDD()
#Create Thread
ThreeThirdThread = Thread(target=ThreeThird.run) 
#Start Thread 
ThreeThirdThread.start()

print("Starting Project")