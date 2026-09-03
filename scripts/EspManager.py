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


def recvExact(sock, numBytes):
    data = b""

    while len(data) < numBytes:
        chunk = sock.recv(numBytes - len(data))

        if not chunk:
            raise ConnectionError("Socket closed while receiving data")

        data += chunk

    return data


# Put in the addresses of the ESPs when they connect to Wi-Fi
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
numPlayers = recvExact(gmConn, 1)[0]

print("Number of players is gonna be " + str(numPlayers) + "!")

parentPipes = [[None, None] for _ in range(numPlayers)]


# Converts XXXX controller input into movement letters.
#
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


# -------------------------------------------------------------
# CREATE ESP CHILD PROCESSES
# -------------------------------------------------------------

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

        # Loop restarts after every match
        while True:

            # -------------------------------------------------
            # WAIT FOR READY CHECK
            # -------------------------------------------------

            readyCheck = os.read(
                childRead,
                6
            ).decode()

            if readyCheck == "ready?":

                espConnected = False
                connection = None

                # ---------------------------------------------
                # MOCK ESP MODE
                # ---------------------------------------------

                if MOCK_ESP:
                    print(
                        "[MOCK ESP] ESP #"
                        + str(i)
                        + " is ready!"
                    )

                    os.write(
                        childWrite,
                        b"1"
                    )

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

                        os.write(
                            childWrite,
                            b"0"
                        )

                    else:
                        connection.send(
                            "readyCheck"
                        )

                        answer = connection.recv(2)

                        if answer == "ready":
                            print(
                                "ESP #"
                                + str(i)
                                + " is ready!"
                            )

                            os.write(
                                childWrite,
                                b"1"
                            )

                        else:
                            print(
                                "ESP #"
                                + str(i)
                                + " is not ready!"
                            )

                            os.write(
                                childWrite,
                                b"0"
                            )

            else:
                print(
                    "Child expected ready command, but got: "
                    + readyCheck
                )

                os.write(
                    childWrite,
                    b"0"
                )

                continue


            # -------------------------------------------------
            # GAME MOVEMENT / RESET LOOP
            # -------------------------------------------------

            while True:

                # Expected values:
                #
                # 1000
                # 0100
                # 0010
                # 0001
                #
                # or:
                #
                # rset

                nextCommand = os.read(
                    childRead,
                    4
                ).decode()


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

                    elif (
                        connection is not None
                        and espConnected
                    ):
                        connection.send(
                            "reset"
                        )

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

                elif (
                    connection is not None
                    and espConnected
                ):
                    connection.send(
                        formattedInput
                    )


        # Normally unreachable while the child loop runs
        os.close(childWrite)
        os.close(childRead)

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

    # Reset shared timer state for the next match
    memLocation[:1] = bytes([50])


    # ---------------------------------------------------------
    # WAIT FOR READY CHECK FROM GAME MANAGER
    # ---------------------------------------------------------

    readyCheck = recvExact(
        gmConn,
        6
    ).decode()


    if readyCheck == "ready?":

        # Tell every ESP child to perform its ready check
        for i in range(numPlayers):
            os.write(
                parentPipes[i][1],
                readyCheck.encode()
            )


        # Assume every ESP is ready
        espReady = True


        # Collect one-byte result from every ESP child
        for i in range(numPlayers):

            askEsp = os.read(
                parentPipes[i][0],
                1
            ).decode()


            if askEsp != "1":
                print(
                    "One ESP ready check failed!"
                )

                espReady = False


        # Send exactly one byte back to GmServerPi
        #
        # 1 = ready
        # 0 = not ready
        if espReady:
            gmConn.sendall(b"1")

        else:
            gmConn.sendall(b"0")


        # If readiness failed, reset all children
        # and wait for another ready request.
        if not espReady:

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

        gmConn.sendall(b"0")

        continue


    # ---------------------------------------------------------
    # GAME STARTED
    # ---------------------------------------------------------

    # ControllerPi sends six-byte commands:
    #
    # 0|1000
    # 1|0100
    #
    # SOCK_STREAM may split or combine messages, so maintain
    # a persistent buffer for the duration of the match.
    controlBuffer = bytearray()


    while memLocation[0] != 0:

        try:

            chunk = controlConn.recv(
                1024
            )


            if not chunk:
                raise ConnectionError(
                    "ControllerPi closed its connection"
                )


            controlBuffer.extend(
                chunk
            )


        except socket.timeout:
            pass


        # Process every complete six-byte command currently
        # stored in the stream buffer.
        while len(controlBuffer) >= 6:

            rawCommand = bytes(
                controlBuffer[:6]
            )

            del controlBuffer[:6]


            movementData = rawCommand.decode()


            # Expected format:
            #
            # 0|1000
            if movementData[1] != "|":
                print(
                    "Invalid controller command:",
                    movementData
                )

                continue


            try:
                playerId = int(
                    movementData[0]
                )

            except ValueError:
                print(
                    "Invalid player ID:",
                    movementData
                )

                continue


            # Make sure the requested player exists
            if (
                playerId < 0
                or playerId >= numPlayers
            ):
                print(
                    "Controller command for invalid player:",
                    playerId
                )

                continue


            movement = movementData[2:]


            # Movement must contain exactly four binary values
            if (
                len(movement) != 4
                or any(
                    value not in "01"
                    for value in movement
                )
            ):
                print(
                    "Invalid movement command:",
                    movementData
                )

                continue


            os.write(
                parentPipes[playerId][1],
                movement.encode()
            )


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
