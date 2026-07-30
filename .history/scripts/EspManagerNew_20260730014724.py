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
gmServer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
gmServer.bind(socketToGm)

# bind with controller
controlServer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
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

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
host = '0.0.0.0'
port = 5000
server_socket.bind((host, port))
server_socket.listen()
server_socket.settimeout(0.04)

gmConn.setblocking(False)
# now open up the shared memory with game manager, or create it
timerFile = os.open(timerSharedMemory, os.O_CREAT | os.O_RDWR)
memLocation = mmap.mmap(timerFile, 1)

def receiveMessage(connection, currentBuffer):
    while True:
        currentBuffer += gmConn.recv(4096).decode()
        delimeterIndex = currentBuffer.find("|")
        if delimeterIndex != -1:
            return True, currentBuffer[:delimeterIndex], currentBuffer[delimeterIndex + 1:]

parentPipes = []
while True:
    # resets mem location shared memory at the start of each match. We want to reset it from 0 back to 50 when we starting a new match, else
    # this process will always think it's time for game over
    memLocation[:1] = bytes([50])

    try:
        espSocket, addr = server_socket.accept()
        childRead, parentWrite = os.pipe()
        parentRead, childWrite = os.pipe()
        if(os.fork() == 0):
            del parentPipes
            os.close(parentWrite)
            os.close(parentRead)
            controlConn.close()
            gmConn.close()
            print("we made a esp that will communicate with esp #" + str(addr) + "!")

            while True:
                readyCheck = os.read(childRead, 6)
                readyCheck = readyCheck.decode()
                if(readyCheck == "ready?"):
                    espSocket.sendall()
        else:
            # store pipes of parent for that child
            parentPipes.append(parentRead, parentWrite)
            os.close(childRead)
            os.close(childWrite)



    except socket.timeout:
        pass

    readyCheck = None
    try:
        readyCheck = gmConn.recv(4096)
        if not readyCheck:
            print("client disconnected!")
            break
    except BlockingIOError:
        continue

    readyCheck = readyCheck.decode()
    # if asking if ready, ask all the esps if they're ready
    delimeterIndex = readyCheck.find("|")
    if(delimeterIndex != -1 and readyCheck[:delimeterIndex] == "ready?"):
        numPlayers = readyCheck[delimeterIndex:]
        if numPlayers != len(parentPipes):
            gmConn.sendall("no".encode())
            continue

        # tell all the esp children that you have to check ready
        for i in range(numPlayers):
            os.write(parentPipes[i][1], readyCheck.encode())

        # initially set check to yes, if finding one that fails then make it "no"
        espReady = "yes"
        # now check all esp children what they return
        for i in range(numPlayers):
            askEsp = os.read(parentPipes[i][0], 3)
            askEsp = askEsp.decode()
            # if no, set entire result to no
            if(askEsp == "no"):
                print("one esp check failed!")
                espReady = "no"

        gmConn.sendall(espReady.encode())
        if(espReady == "no"):
            continue
    else:
        print("esp manager expected ready check, got this instead: " + readyCheck)
        continue

    # now, game starts! Inform all the esp bros
    for i in range(numPlayers):
        os.write(parentPipes[i][1], "start-game".encode())

    
    # while the shared memory representing the timer hasn't reached 0, continue to send movement
    while(memLocation[0] != 0):
        #next, get controller data, and send it
        try:
            #get movement data from controller
            movementData = controlConn.recv(6)
            movementData = movementData.decode()
            # first one sent is the id
            playerId = int(movementData[0])
            # for now since only one esp. Once you have more, just remove the if statement and unintend the code inside it
            # after the first two chars, that is the movement data
            movementData = movementData[2:]
            os.write(parentPipes[playerId][1], movementData.encode())
        # no big deal if we don't get data in that time
        except socket.timeout:
            pass
    print("Game over!")
    # once game over, tell all children that esp's should reset
    for i in range(numPlayers):
        os.write(parentPipes[i][1], b"rset")


controlConn.close()
gmConn.close()
os.remove(socketToGm)
os.remove(socketToControl)
print("killing parent")
