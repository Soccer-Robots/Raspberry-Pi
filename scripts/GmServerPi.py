import asyncio
import socket
import websockets
import json
import os
import mmap
from inspect import signature

# from backupTag import runTrakcer


HOST = "10.42.0.1"
PORT = 1234

espSocketPath = "/tmp/gmESPSocket"

sharedMemory = "/tmp/shared_timer"

game_time = 0

runBackTracking = False

# Tracks whether EspManager has already received its
# one-time player count initialization.
playersInitialized = False

def getTime():
    return game_time


# -------------------------------------------------------------
# SHARED TIMER MEMORY
# -------------------------------------------------------------

# Allocate shared memory before communicating with EspManager.
# This helps prevent race conditions between the two processes.
timerFile = os.open(
    sharedMemory,
    os.O_CREAT | os.O_RDWR
)

os.ftruncate(timerFile, 1)

memLocation = mmap.mmap(
    timerFile,
    1
)


# -------------------------------------------------------------
# CONNECT TO ESP MANAGER
# -------------------------------------------------------------

espSocket = socket.socket(
    socket.AF_UNIX,
    socket.SOCK_STREAM
)

espSocket.connect(espSocketPath)

print("Connected to ESP Manager!")


# -------------------------------------------------------------
# GAME MANAGER WEBSOCKET
# -------------------------------------------------------------

async def serverGM(websocket):
    global playersInitialized

    while True:

        game_time = 0

        team1Score = 0
        team2Score = 0

        isReady = False

        print("Inside GM")


        # -----------------------------------------------------
        # WAIT FOR ROBOTS / MOCK ESPS TO BE READY
        # -----------------------------------------------------

        while not isReady:

            received_data = await websocket.recv()

            received = json.loads(received_data)

            print("Received message in Game Manager:")
            print(received)


            if received["type"] == "CHECK_READY":

                numPlayers = int(
                    received["payload"]["num_players"]
                )


                # EspManager expects the player count once
                # before its first "ready?" message.
                if not playersInitialized:

                    print(
                        "Sending player count to ESP Manager:",
                        numPlayers
                    )

                    espSocket.sendall(
                        bytes([numPlayers])
                    )

                    playersInitialized = True


                # Ask EspManager if all ESPs are ready
                espSocket.sendall(
                    b"ready?"
                )


                # EspManager responds with either:
                #
                # yes
                # no
                readyCheck = espSocket.recv(3).decode()


                if readyCheck == "yes":

                    print("ESP Manager reports READY")

                    isReady = True

                    await websocket.send(
                        json.dumps(
                            {
                                "type": "IS_READY",
                                "payload": True
                            }
                        )
                    )

                    break


                else:

                    print(
                        "ESP Manager reports NOT READY"
                    )

                    await websocket.send(
                        json.dumps(
                            {
                                "type": "IS_READY",
                                "payload": False
                            }
                        )
                    )


            else:

                print(
                    "Expected CHECK_READY, but received: "
                    + received["type"]
                )


        # -----------------------------------------------------
        # RECEIVE GAME TIMER
        # -----------------------------------------------------

        received_data = await websocket.recv()

        received = json.loads(
            received_data
        )


        # Debugging
        if isinstance(received, str):

            print(
                "DEBUG: received is a string:"
            )

            print(received)


        if isinstance(received["payload"], str):

            print(
                "DEBUG: received['payload'] is a string"
            )

            print(
                "DEBUG: Value:",
                received["payload"]
            )


        print(
            received["payload"],
            type(received["payload"])
        )


        print(
            "DEBUG timer value:",
            received["payload"]["timer"]
        )


        game_time = int(
            received["payload"]["timer"]
        )


        print("\nTimer:")


        # -----------------------------------------------------
        # GAME LOOP
        # -----------------------------------------------------

        while game_time >= 0 and isReady:

            # -------------------------------------------------
            # GAME END
            # -------------------------------------------------

            if game_time == 0:

                final_score_update = {
                    "type": "GAME_END",
                    "payload": {
                        "timer": 0,
                        "score1": team1Score,
                        "score2": team2Score
                    }
                }


                await websocket.send(
                    json.dumps(
                        final_score_update
                    )
                )


                isReady = False

                runBackTracking = True


                # Notify EspManager that the game ended
                memLocation[:1] = bytes([0])

                break

            # -------------------------------------------------
            # SEND SCORE
            # -------------------------------------------------

            print(
                "Send Current Time:",
                game_time
            )


            await websocket.send(
                json.dumps(
                    {
                        "type": "SCORE_UPDATE",
                        "payload": {
                            "score1": team1Score,
                            "score2": team2Score
                        }
                    }
                )
            )


            # -------------------------------------------------
            # SEND TIMER
            # -------------------------------------------------

            await websocket.send(
                json.dumps(
                    {
                        "type": "TIMER_UPDATE",
                        "payload": {
                            "timer": game_time
                        }
                    }
                )
            )


            await asyncio.sleep(1)

            game_time -= 1


        # -----------------------------------------------------
        # GAME FINISHED
        # -----------------------------------------------------

        print("\n")

        print(
            "FINAL SCORE: Team 1:",
            team1Score,
            "Team 2:",
            team2Score
        )


        # Future backtracking:
        #
        # if runBackTracking:
        #     test = runTrakcer()
        #     runBackTracking = False


# -------------------------------------------------------------
# START WEBSOCKET SERVER
# -------------------------------------------------------------

async def main():

    print("STARTED GM SERVER")

    try:

        print(
            "serverGM args:",
            signature(serverGM)
        )


        async with websockets.serve(
            serverGM,
            HOST,
            PORT
        ):

            print(
                "GM server is running and waiting for clients"
            )

            await asyncio.Future()


    except Exception as err:

        print(
            "Failed to bind itself:",
            err
        )


asyncio.run(main())
