#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

'''
Shaper

Server
'''

# shaper server
# Copyright (c) 2020 Thomas Anatol da Rocha Woelz
# All rights reserved.
# BSD type license: check doc folder for details

__version__ = '0.0.1'
__docformat__ = 'restructuredtext'
__author__ = 'Thomas Anatol da Rocha Woelz'


import asyncio
import websockets
import json
import logging
import configobj
import validate
import decimal
import sys
import os
import random
import pathlib

# set local path constants
DIR = pathlib.Path(__file__).parent.resolve()
sys.path.insert(0, str(DIR.joinpath('res', 'scripts')))
cfg_dir = DIR / 'config'
save_dir = DIR / 'save'
exp_dir = DIR / 'exp'

# local imports



# all further rounding for decimal class is rounded up
decimal.getcontext().rounding = decimal.ROUND_UP

# prevent import
if not __name__ == "__main__":
    raise Exception('server.py should not be imported')
    sys.exit(0)

# logging setup
logging.basicConfig(filename='server.log',
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    level=logging.DEBUG,
                    filemode='w')

# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

# Now, we can log to the root logger, or any other logger. First the root...
logging.info('Jackdaws love my big sphinx of quartz.')

# # Now, define a couple of other loggers which might represent areas in your
# # application:
#
logger1 = logging.getLogger('myapp.area1')
logger2 = logging.getLogger('myapp.area2')

logger1.debug('Quick zephyrs blow, vexing daft Jim.')
logger1.info('How quickly daft jumping zebras vex.')
logger2.warning('Jail zesty vixen who grabbed pay from quack.')
logger2.error('The five boxing wizards jump quickly.')


logging.info(str(save_dir))
if not save_dir.exists():
    try:
        save_dir.mkdir()
    except IOError as ex:
        logging.critical('Could not create directory', ex)
        sys.exit(0)


logging.info('INFO track')
logging.critical('CRITICAL track')
logging.debug('DEBUG track')

print('hello')

# TODO: REMOVE STATE
STATE = {"value": 0}

USERS = set()

ADMIN = None

# TODO: REMOVE NUMBER OF PLAYERS, USE CONFIG INSTEAD
NUMBER_OF_PLAYERS = 4


def state_event():
    return json.dumps({"type": "state", **STATE})


def users_event():
    return json.dumps({"type": "users", "count": len(USERS)})


async def notify_state():
    if USERS:  # asyncio.wait doesn't accept an empty list
        message = state_event()
        await asyncio.wait([user.send(message) for user in USERS])


async def notify_users():
    if USERS:  # asyncio.wait doesn't accept an empty list
        message = users_event()
        await asyncio.wait([user.send(message) for user in USERS])


async def register(websocket):
    USERS.add(websocket)
    await notify_users()


async def unregister(websocket):
    USERS.remove(websocket)
    await notify_users()


async def connect(websocket, path):
    global c

    name = await websocket.recv()
    print(f"< {name}")

    if name != 'admin' and None in c.player_socket.values():

        player = None
        for i in range(NUMBER_OF_PLAYERS):
            if c.player_socket[i] is None:
                player = i
                break

        if player is None:
            raise Exception('There should be a valid player')

        c.player_socket[player] = websocket

        greeting = f"Hello {name}! You are player {player}"

        await websocket.send(greeting)
        print(f"> {greeting}")

        await websocket.send(json.dumps({'player': player}))

        # register(websocket) sends user_event() to websocket
        await register(websocket)
        try:
            await websocket.send(state_event())
            async for message in websocket:
                data = json.loads(message)
                if data["action"] == "minus":
                    STATE["value"] -= 1
                    await notify_state()
                elif data["action"] == "plus":
                    STATE["value"] += 1
                    await notify_state()
                else:
                    logging.error("unsupported event: {}", data)
        finally:
            await unregister(websocket)
            c.player_socket[player] = None


class Connections:
    player_socket = {}


class Container:
    pass


# # globals
# c = None
# cfg = None

try:
    global c
    global cfg
    c = Connections()
    cfg = Container()

    start_server = websockets.serve(connect, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
except Exception as e:
    logging.error(e, exc_info=True)
    raise

