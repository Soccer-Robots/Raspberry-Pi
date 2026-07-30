import socket
import os
import mmap
from ESPClient import ESPClient

socketToGm = "/tmp/gmESPSocket"
socketToControl = "/tmp/controlESPSocket" 

timerSharedMemory = "/tmp/shared_timer"

espAddrs = {}

# removing these files if they exist, so we can recreate them
if(os.path.exists(socketToGm)):
    os.remove(socketToGm)

if(os.path.exists(socketToControl)):
    os.remove(socketToControl)

# bind with server
gmServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
gmServer.bind(socketToGm)

# bind with controller
controlServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
controlServer.bind(socketToControl)

# wait on server connect, then control connect
gmServer.listen(1)
print("ESp listening for game manager")

gmConn, _ = gmServer.accept()
print("gm accepted communication!")
gmServer.close()

controlServer.listen(1)
print("ESP listening for controller")

controlConn, _ = controlServer.accept()
controlConn.settimeout(1)
print("controller accepted communication!")
controlServer.close()

# this function gets the numeric input in the form XXXX (where x is either 0 or 1), and maps that to letters that
# can be sent to the esp to signal direction of movement
def getKeysFromNumbers(numInput):
    finalMessage = ""
    if(numInput[0] == "1"):
        finalMessage += "u"
    if(numInput[1] == "1"):
        finalMessage += "l"
    if(numInput[2] == "1"):
        finalMessage += "d"
    if(numInput[3] == "1"):
        finalMessage += "r"
    return finalMessage

while True:
    

controlConn.close()
gmConn.close()
os.remove(socketToGm)
os.remove(socketToControl)
print("killing parent")
