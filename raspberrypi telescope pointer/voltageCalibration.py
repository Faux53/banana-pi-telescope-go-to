# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 13:37:48 2015

@author: simon
"""
import sys,csv
import numpy as np
import matplotlib.pyplot as plt
from configParser import calibrationParser

def sendToConfig(flag, coefs):
    cString = ','.join(['%.5f' % num for num in coefs])
    cParser = calibrationParser("instrumentCalibration.xml")
    if flag == "-az":
        cParser.setAzimuthCalibration(cString)
    elif flag == "-al":
        cParser.setAltitudeCalibration(cString)
    elif flag == "-azup":
        cParser.setAzimuthUpCalibration(cString)
    elif flag == "-azdn":
        cParser.setAzimuthDownCalibration(cString)
    elif flag == "-alup":
        cParser.setAltitudeUpCalibration(cString)
    elif flag == "-aldn":
        cParser.setAltitudeDownCalibration(cString)
    else:
        raise ValueError("Flag %s is not recognised" % flag)
    
def polyFit(voltages,angles,order):
        coefs = np.polyfit(voltages, angles,4)
        x = np.linspace(min(voltages),max(voltages),500)
        coefs = coefs[::-1]
        y = coefs[0] + coefs[1]*x + coefs[2]*x**2 + coefs[3]*x**3 + coefs[4]*x**4
        plt.plot(x,y,'r-')
        plt.plot(voltages,angles,'bx')
        plt.xlabel("Voltage")
        plt.ylabel("angle (degrees)")
        plt.legend(["fit","data"])
        return coefs
    

def fitData(flag, fileName):
    angles = []
    voltages = []
    try:
        fData = open(fileName)
        csData = csv.reader(fData, delimiter = ',', quoting = csv.QUOTE_NONNUMERIC)
        for row in csData:
            if not isinstance(row[0],float) or not isinstance(row[1],float):
                raise TypeError("some of the data in %s, could not be interpreted as a floating point number" % fileName)
            else:
                angles.append(row[0])
                voltages.append(row[1])
        
        print "file \"%s\" read successfully" % fileName
        
        if max(angles) > 360 or max(angles) < 75 or min(angles) < 0:
            pass
            #raise ValueError("It looks like the angles data are not in degrees. Try using \"scaleToDegrees.py\" to convert it")
        coefs = polyFit(voltages,angles,5)
        try:        
            sendToConfig(flag,coefs)
            print "Voltage calibration %s successfully set" % flag
        except IOError:
            print "Error: Could not find the instrumentCalibration.xml. Check that you are running this in the iTelComputer directory."

        
    except IOError:
        print "Error: Could not find the file called \"%s\"" % fileName


##fitData('-al','AltCalExample.csv')#just for my checks,,,

if __name__ == '__main__':
    flags = ['-az','-al','-azup','-azdn','-alup','-aldn','-h']
    #flagNames = ['azimulth','altitude', 'azimuth increasing', 'azimuth decreasing', 'altitude increasing'
    for flag in flags:#TODO include a -h flag text..
        try:
            ind = sys.argv.index(flag)
            print "%s flag found, processing data file" % flag
            if "-h" in flag:
                print "a helpful message!"
            else:
                fitData(flag,sys.argv[ind+1])
            
        except ValueError:##TODO this except loop catches too many errors
            pass
        except IndexError:
            print "Error no filename given following flag"