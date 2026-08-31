import socket
import os
import mmap
from ESPClient import ESPClient

socketToGm = "/tmp/gmESPSocket"
socketToControl = "/tmp/controlESPSocket"

timerSharedMemory = "/tmp/shared_timer"

espAddrs = {}

# True = test without physical ESP32s
# False = communicate with real ESP32s
MOCK_ESP = True

# Put in the addresses of the ESPs when they connect to Wi-Fi
# ammar hotspot - 172.20.10.7
espAddrs["esp0"] = "10.42.0.130"
espAddrs["esp1"] = "10.42.0.102"
espAddrs["esp2"] = "idk"
espAddrs["esp3"] = "idk"
espAddrs["esp4"] = "idk"
espAddrs["esp5"] = "idk"


# Remove Unix socket files if they already exist
if os.path.exists(socketToGm):
    os.remove(socketToGm)

if os.path.exists(socketToControl):
    os.remove(socketToControl)


# Bind Game Manager Unix socket
gmServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
gmServer.bind(socketToGm)

# Bind Controller Unix socket
controlServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
controlServer.bind(socketToControl)


# Wait for Game Manager connection
gmServer.listen(1)
print("ESP listening for game manager")

gmConn, _ = gmServer.accept()
print("GM accepted communication!")


# Wait for Controller connection
controlServer.listen(1)
print("ESP listening for controller")

controlConn, _ = controlServer.accept()
controlConn.settimeout(1)
print("Controller accepted communication!")


# Game Manager first sends number of players
numPlayers = gmConn.recv(1)[0]

print("Number of players is gonna be " + str(numPlayers) + "!")

parentPipes = [[None, None] for _ in range(numPlayers)]


# Converts XXXX controller input into movement letters.
# Example:
# 1000 -> u
# 0100 -> l
# 0010 -> d
# 0001 -> r
def getKeysFromNumbers(numInput):
    finalMessage = ""

    if numInput[0] == "1":
        finalMessage += "u"

    if numInput[1] == "1":
        finalMessage += "l"

    if numInput[2] == "1":
        finalMessage += "d"

    if numInput[3] == "1":
        finalMessage += "r"

    return finalMessage


# Create one child process for every player / ESP
for i in range(numPlayers):
    childRead, parentWrite = os.pipe()
    parentRead, childWrite = os.pipe()

    pid = os.fork()

    # ---------------------------------------------------------
    # CHILD PROCESS
    # ---------------------------------------------------------
    if pid == 0:
        del parentPipes

        os.close(parentWrite)
        os.close(parentRead)

        controlConn.close()
        gmConn.close()

        controlServer.close()
        gmServer.close()

        print(
            "We made an ESP process that will communicate with ESP #"
            + str(i)
            + "!"
        )

        # Loop restarts at the end of each match
        while True:

            # -------------------------------------------------
            # WAIT FOR READY CHECK
            # -------------------------------------------------
            readyCheck = os.read(childRead, 6).decode()

            if readyCheck == "ready?":

                # ---------------------------------------------
                # MOCK ESP MODE
                # ---------------------------------------------
                if MOCK_ESP:
                    print(
                        "[MOCK ESP] ESP #"
                        + str(i)
                        + " is ready!"
                    )

                    os.write(childWrite, b"yes")

                # ---------------------------------------------
                # REAL ESP MODE
                # ---------------------------------------------
                else:
                    connection = ESPClient(
                        espAddrs["esp" + str(i)],
                        30000
                    )

                    espConnected = connection.tryConnect(2)

                    if not espConnected:
                        print(
                            "ESP #"
                            + str(i)
                            + " failed connection!"
                        )

                        os.write(childWrite, b"no")

                    else:
                        connection.send("readyCheck")

                        answer = connection.recv(2)

                        if answer == "ready":
                            print(
                                "ESP #"
                                + str(i)
                                + " is ready!"
                            )

                            os.write(childWrite, b"yes")

                        else:
                            print(
                                "ESP #"
                                + str(i)
                                + " is not ready!"
                            )

                            os.write(childWrite, b"no")

            else:
                print(
                    "Child expected ready command, but got: "
                    + readyCheck
                )

                os.write(childWrite, b"no")

                continue


            # -------------------------------------------------
            # GAME MOVEMENT LOOP
            # -------------------------------------------------
            while True:

                # Commands are always exactly 4 bytes:
                #
                # 1000
                # 0100
                # 0010
                # 0001
                #
                # or:
                #
                # rset
                nextCommand = os.read(childRead, 4).decode()

                # ---------------------------------------------
                # RESET
                # ---------------------------------------------
                if nextCommand == "rset":

                    if MOCK_ESP:
                        print(
                            "[MOCK ESP] ESP #"
                            + str(i)
                            + " reset"
                        )

                    else:
                        connection.send("reset")

                    break


                # ---------------------------------------------
                # MOVEMENT
                # ---------------------------------------------
                formattedInput = getKeysFromNumbers(
                    nextCommand
                )

                # No movement
                if formattedInput == "":
                    formattedInput = "z"


                if MOCK_ESP:
                    print(
                        "[MOCK ESP] ESP #"
                        + str(i)
                        + " movement: "
                        + formattedInput
                        + " ("
                        + nextCommand
                        + ")"
                    )

                else:
                    connection.send(formattedInput)


        # Child cleanup
        os.close(childWrite)
        os.close(childRead)

        print("Killing child")

        os._exit(0)


    # ---------------------------------------------------------
    # PARENT PROCESS
    # ---------------------------------------------------------
    else:
        parentPipes[i][0] = parentRead
        parentPipes[i][1] = parentWrite

        os.close(childRead)
        os.close(childWrite)


print("Parent finished creating ESP children!")


# -------------------------------------------------------------
# SHARED TIMER MEMORY
# -------------------------------------------------------------

timerFile = os.open(
    timerSharedMemory,
    os.O_CREAT | os.O_RDWR
)

memLocation = mmap.mmap(
    timerFile,
    1
)


# -------------------------------------------------------------
# MAIN GAME LOOP
# -------------------------------------------------------------

while True:

    # Reset shared timer value at the beginning of each match.
    #
    # This prevents EspManager from immediately thinking
    # the next game has already ended.
    memLocation[:1] = bytes([50])


    # ---------------------------------------------------------
    # WAIT FOR READY CHECK FROM GAME MANAGER
    # ---------------------------------------------------------

    readyCheck = gmConn.recv(6).decode()


    if readyCheck == "ready?":

        # Tell all ESP children to perform their ready checks
        for i in range(numPlayers):
            os.write(
                parentPipes[i][1],
                readyCheck.encode()
            )


        # Assume all ESPs are ready unless one reports failure
        espReady = "yes"


        # Get response from every ESP child
        for i in range(numPlayers):

            askEsp = os.read(
                parentPipes[i][0],
                3
            ).decode()


            if askEsp == "no":
                print("One ESP ready check failed!")

                espReady = "no"


        # Send final result back to Game Manager
        gmConn.sendall(
            espReady.encode()
        )


        # If one or more ESPs failed, reset children
        # and wait for another ready check
        if espReady == "no":

            for i in range(numPlayers):
                os.write(
                    parentPipes[i][1],
                    b"rset"
                )

            continue


    else:
        print(
            "ESP Manager expected ready check, got: "
            + readyCheck
        )

        gmConn.sendall(b"no")

        continue


    # ---------------------------------------------------------
    # GAME STARTED
    # ---------------------------------------------------------

    while memLocation[0] != 0:

        try:

            # Receive controller data
            movementData = controlConn.recv(6).decode()


            # First character identifies the player
            playerId = int(
                movementData[0]
            )


            # Controller format:
            #
            # 0|1000
            #
            # Remove player ID and separator
            movementData = movementData[2:]


            # Send movement command to that player's child
            os.write(
                parentPipes[playerId][1],
                movementData.encode()
            )


        except socket.timeout:
            pass


    # ---------------------------------------------------------
    # GAME OVER
    # ---------------------------------------------------------

    print("Game over!")


    # Reset every ESP after the match
    for i in range(numPlayers):

        os.write(
            parentPipes[i][1],
            b"rset"
        )


# -------------------------------------------------------------
# CLEANUP
# -------------------------------------------------------------

for i in range(numPlayers):

    pid, status = os.wait()

    os.close(
        parentPipes[i][0]
    )

    os.close(
        parentPipes[i][1]
    )

    print(
        "Child "
        + str(pid)
        + " returned with status "
        + str(status)
    )


controlConn.close()
gmConn.close()

controlServer.close()
gmServer.close()

os.remove(socketToGm)
os.remove(socketToControl)

print("Killing parent")
