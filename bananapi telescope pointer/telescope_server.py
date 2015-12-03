#!/usr/bin/env python
""" removed the astrobeano skysafari stuff for stellariumConnect
TODO- more astropy stuff
"""

#More references on Alt/Az horizontal coordinates to equatorial:
#http://pythonhosted.org/Astropysics/coremods/obstools.html#astropysics.obstools.Site
#https://github.com/eteq/astropysics/issues/21
#https://github.com/astropy/astropy-api/pull/6
#http://infohost.nmt.edu/tcc/help/lang/python/examples/sidereal/ims/

import socket
import os
import sys
import commands
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import time
import datetime
from math import pi, sin, cos, asin, acos, atan2, modf

#TODO - Try astropy if I can get it to compile on Mac OS X...
from astropysics import coords
from astropysics import obstools

#Local import
from gy80 import GY80

config_file = "telescope_server.ini"
if not os.path.isfile(config_file):
    print("Using default settings")
    h = open("telescope_server.ini", "w")
    h.write("[server]\nname=10.0.0.1\nport=4030\n")
    #Default to Greenwich as the site
    h.write("[site]\nlatitude=+51d28m38s\nlongitude=0\n")
    #Default to no correction of the angles
    h.write("[offsets]\nazimuth=0\naltitude=0\n")
    h.close()

print("Connecting to sensors...")
imu = GY80()
print("Connected to GY-80 sensor")

print("Opening network port...")
config = configparser.ConfigParser()
config.read("telescope_server.ini")
server_name = config.get("server", "name") #e.g. 10.0.0.1
server_port = config.getint("server", "port") #e.g. 4030
#server_name = socket.gethostbyname(socket.gethostname())
#if server_name.startswith("127.0."): #e.g. 127.0.0.1
#    #This works on Linux but not on Mac OS X or Windows:
#    server_name = commands.getoutput("/sbin/ifconfig").split("\n")[1].split()[1][5:]
##server_name = "10.0.0.1" #Override for wifi access
#server_port = 4030 #Default port used by SkySafari

#If default to low precision, SkySafari turns it on anyway:
high_precision = True

#Default to Greenwich, GMT - Latitude 51deg 28' 38'' N, Longitude zero
local_site = obstools.Site(coords.AngularCoordinate(config.get("site", "latitude")),
                           coords.AngularCoordinate(config.get("site", "longitude")),
                           tz=0)
#Rather than messing with the system clock, will store any difference
#between the local computer's date/time and any date/time set by the
#client (which should match any location set by the client).
local_time_offset = 0

#This will probably best be inferred by calibration...
#For Greenwich, magnetic north is estimated to be 2 deg 40 min west
#of grid north at Greenwich in July 2013.
#http://www.geomag.bgs.ac.uk/data_service/models_compass/gma_calc.html
#local_site_magnetic_offset = -2.67 * pi / 180.0

#These will come from sensor information... storing them in radians
local_alt = 85 * pi / 180.0
local_az = 30 * pi / 180.0
offset_alt = config.getfloat("offsets", "altitude")
offset_az = config.getfloat("offsets", "azimuth")

#These will come from the client... store them in radians
target_ra = 0.0
target_dec = 0.0

#Turn on for lots of logging...
debug = False

def save_config():
    global condig, config_file
    with open(config_file, "w") as handle:
        config.write(handle)

def _check_close(a, b, error=0.0001):
    if isinstance(a, (tuple, list)):
        assert isinstance(b, (tuple, list))
        assert len(a) == len(b)
        for a1, b1 in zip(a, b):
            diff = abs(a1-b1)
            if diff > error:
                raise ValueError("%s vs %s, for %s vs %s difference %s > %s"
                         % (a, b, a1, b1, diff, error))
        return
    diff = abs(a-b)
    if diff > error:
        raise ValueError("%s vs %s, difference %s > %s"
                         % (a, b, diff, error))

def update_alt_az():
    global imu, offset_alt, offset_az, local_alt, local_az
    yaw, pitch, roll = imu.current_orientation_euler_angles_hybrid()
    #yaw, pitch, roll = imu.current_orientation_euler_angles_mag_acc_only()
    #Yaw is measured from (magnetic) North,
    #Azimuth is measure from true North:
    local_az = (offset_az + yaw) % (2*pi)
    #Pitch is measured downwards (using airplane style NED system)
    #Altitude is measured upwards
    local_alt = (offset_alt + pitch) % (2*pi)
    #We don't care about the roll for the Meade LX200 protocol.

def site_time_gmt_as_epoch():
    global local_time_offset
    return time.time() + local_time_offset

def site_time_gmt_as_datetime():
    return datetime.datetime.fromtimestamp(site_time_gmt_as_epoch())

def site_time_local_as_datetime():
    global local_site
    return site_time_gmt_as_datetime() - datetime.timedelta(hours=local_site.tz)

def debug_time():
    global local_site
    if local_site.tz:
        sys.stderr.write("Effective site date/time is %s (local time), %s (GMT/UTC)\n"
                         % (site_time_local_as_datetime(), site_time_gmt_as_datetime()))
    else:
        sys.stderr.write("Effective site date/time is %s (local/GMT/UTC)\n"
                         % site_time_gmt_as_datetime())

def greenwich_sidereal_time_in_radians():
    """Calculate using GMT (according to client's time settings)."""
    #Function astropysics.obstools.epoch_to_jd wants a decimal year as input
    #Function astropysics.obstools.calendar_to_jd can take a datetime object
    gmt_jd = obstools.calendar_to_jd(site_time_gmt_as_datetime())
    #Convert from hours to radians... 24hr = 2*pi
    return coords.greenwich_sidereal_time(gmt_jd) * pi / 12

def alt_az_to_equatorial(alt, az, gst=None):
    global local_site #and time offset used too
    if gst is None:
        gst = greenwich_sidereal_time_in_radians()
    lat = local_site.latitude.r
    #Calculate these once only for speed
    sin_lat = sin(lat)
    cos_lat = cos(lat)
    sin_alt = sin(alt)
    cos_alt = cos(alt)
    sin_az = sin(az)
    cos_az = cos(az)
    dec  = asin(sin_alt*sin_lat + cos_alt*cos_lat*cos_az)
    hours_in_rad = acos((sin_alt - sin_lat*sin(dec)) / (cos_lat*cos(dec)))
    if sin_az > 0.0:
        hours_in_rad = 2*pi - hours_in_rad
    ra = gst - local_site.longitude.r - hours_in_rad
    return ra % (pi*2), dec

def equatorial_to_alt_az(ra, dec, gst=None):
    global local_site #and time offset used too
    if gst is None:
        gst = greenwich_sidereal_time_in_radians()
    lat = local_site.latitude.r
    #Calculate these once only for speed
    sin_lat = sin(lat)
    cos_lat = cos(lat)
    sin_dec = sin(dec)
    cos_dec = cos(dec)
    h = gst - local_site.longitude.r - ra
    sin_h = sin(h)
    cos_h = cos(h)
    alt = asin(sin_lat*sin_dec + cos_lat*cos_dec*cos_h)
    az = atan2(-cos_dec*sin_h, cos_lat*sin_dec - sin_lat*cos_dec*cos_h)
    return alt, az % (2*pi)
#This test implicitly assumes time between two calculations not significant:
_check_close((1.84096, 0.3984), alt_az_to_equatorial(*equatorial_to_alt_az(1.84096, 0.3984)))
#_check_close(parse_hhmm("07:01:55"), 1.84096) # RA
#_check_close(parse_sddmm("+22*49:43"), 0.3984) # Dec

#This ensures identical time stamp used:
gst = greenwich_sidereal_time_in_radians()
for ra in [0.1, 1, 2, 3, pi, 4, 5, 6, 1.99*pi]:
    for dec in [-0.49*pi, -1.1, -1, 0, 0.001, 1.55, 0.49*pi]:
        alt, az = equatorial_to_alt_az(ra, dec, gst)
        _check_close((ra, dec), alt_az_to_equatorial(alt, az, gst))
del gst, ra, dec

while True:
    # Stellarium via socat opens it and keeps it open using:
    # $ ./socat GOPEN:/dev/ptyp0,ignoreeof TCP:raspberrypi8:4030
    # (probably socat which is maintaining the link)
    #sys.stdout.write("waiting for a connection\n")
    connection, client_address = sock.accept()
    data = ""
    try:
        #sys.stdout.write("Client connected: %s, %s\n" % client_address)
        while True:
            data += connection.recv(16)
            if not data:
                imu.update()
                break
            if debug:
                sys.stdout.write("Processing %r\n" % data)
            #For stacked commands like ":RS#:GD#",
            #but also lone NexStar ones like "e"
            while data:
                while data[0:1] == "#":
                    #Stellarium seems to send '#:GR#' and '#:GD#'
                    #(perhaps to explicitly close and prior command?)
                    #sys.stderr.write("Problem in data: %r - dropping leading #\n" % data)
                    data = data[1:]
                if not data:
                    break
                if "#" in data:
                    raw_cmd = data[:data.index("#")]
                    #sys.stderr.write("%r --> %r as command\n" % (data, raw_cmd))
                    data = data[len(raw_cmd)+1:]
                    cmd, value = raw_cmd[:3], raw_cmd[3:]
                else:
                    #This will break on complex NexStar commands,
                    #but don't care - Meade LX200 is the prority.
                    raw_cmd = data
                    cmd = raw_cmd[:3]
                    value = raw_cmd[3:]
                    data = ""
                if not cmd:
                    sys.stderr.write("Eh? No command?\n")
                elif cmd in command_map:
                    if value:
                        if debug:
                            sys.stdout.write("Command %r, argument %r\n" % (cmd, value))
                        resp = command_map[cmd](value)
                    else:
                        resp = command_map[cmd]()
                    if resp:
                        if debug:
                            sys.stdout.write("Command %r, sending %r\n" % (cmd, resp))
                        connection.sendall(resp)
                    else:
                        if debug:
                            sys.stdout.write("Command %r, no response\n" % cmd)
                else:
                    sys.stderr.write("Unknown command %r, from %r (data %r)\n" % (cmd, raw_cmd, data))
	
	import socket, sys, angles, struct, time, select

	class stellariumConnect(object):
		def __init__(self,host,port):
			self.serverAddress=(host,port)
			
			# Create a TCP/IP socket
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.sock.bind(self.serverAddress)
			self.sock.settimeout(600)#Throws a timeout exception if connections are idle for 10 minutes
			self.sock.listen(1)#set the socket to listen, now it's a server!
			self.connected = False
			
		def handshakeStellarium(self):
			try:
				while True:
					# Wait for a connection
					self.connection, self.clientAddress = self.sock.accept() 
					if self.connection != None:
						self.connected = True
						break
			except Exception:
				print "Failed handshake with Stellarium: %s" % (Exception.message)
				
			
		def sendStellariumCoords(self,Ra,Dec):
			[RaInt,DecInt] = self.angleToStellarium(Ra, Dec)
			data = struct.pack("3iIii", 24, 0, time.time(), RaInt, DecInt, 0)##//TODO time reported here does not include the offset (if any). This may not be an issue but you should check. 
			self.sendStellariumData(data)
		
		def receiveStellariumCoords(self,timeout):
			incomingData = self.receiveStellariumData(timeout)
			if incomingData != None:
				data = struct.unpack("3iIi", incomingData)
				[Ra,Dec] = self.stellariumToAngle(data[3], data[4])
				return [Ra,Dec]
			else:
				return [False,False]
		
		def receiveStellariumData(self,timeout):
			try:
				incomingData = None
				ready = select.select([self.connection], [], [], timeout)
				if ready[0]:
					incomingData = self.connection.recv(640)
				return incomingData
			except Exception, e:
				print "failed to receive light data from Stellarium: %s" % e
				
		def sendStellariumData(self,data):
			try:
				for i in range(10):##Stellarium likes to recieve the coordinates 10 times.
					self.connection.send(data)
			except Exception, e:
				print "failed to send data to Stellarium: %s" % e
				
		def angleToStellarium(self,Ra,Dec):
			return [int(Ra.h*(2147483648/12.0)), int(Dec.d*(1073741824/90.0))]
		
		def stellariumToAngle(self,RaInt,DecInt):
			Ra = angles.Angle(h=(RaInt*12.0/2147483648))
			Dec = angles.Angle(d=(DecInt*90.0/1073741824))
			return [Ra, Dec]
			
		#def stellariumTime(self,mtime):
		#    time_s = math.floor(mtime / 1000000)
		#    stellTime = datetime.datetime(localtime(time_s))
		#    return stellTime
			
		def closeConnection(self):
			self.connection.close()
			self.sock.close()
			sys.stdout.flush()
    
        
    finally:
        connection.close()
