#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Shaper

Server
"""

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
import decimal
import sys
import os
import pathlib
import re
import copy

from configobj import ConfigObj
from configobj import flatten_errors
from validate import Validator

import easygui as eg

# set local path constants
DIR = pathlib.Path(__file__).parent.resolve()
# sys.path.insert(0, str(DIR.joinpath('res', 'scripts')))

# TODO: get this from common code, so language is set once using a common config for admin and server
# check symbadict for an example
LANG = 'en'

# local imports


# all further rounding for decimal class is rounded up
decimal.getcontext().rounding = decimal.ROUND_UP


def is_valid_ip(ip):
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    return bool(m) and all(map(lambda n: 0 <= int(n) <= 255, m.groups()))


def validate_config(a_config, set_copy=False):
    """Validates a ConfigObj instance.

    If errors are found, throws exception and reports errors.
    """
    error = False
    error_message_list = []
    res = a_config.validate(Validator(), preserve_errors=True, copy=set_copy)
    for entry in flatten_errors(a_config, res):
        section_list, key, error = entry
        if key is not None:
            section_list.append(key)
        else:
            section_list.append('[missing section]')
        section_string = ', '.join(section_list)
        if not error:
            error = 'Missing value or section.'
        error_message = ''.join([section_string, ' = ', str(error)])
        error_message_list.append(error_message)
    if error:
        error_messages = '; '.join(error_message_list)
        print(error_messages)
        raise Exception(error_messages)
    if not res:
        error = '{0} invalid\n'.format(os.path.split(a_config.filename)[1])
        raise Exception(error)


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

logging.info('INFO track')
logging.critical('CRITICAL track')
logging.debug('DEBUG track')

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


class Connections:
    player_socket = {}

    async def connect(self, websocket, path):
        name = await websocket.recv()
        print(f"< {name}")

        if name != 'admin' and None in self.player_socket.values():

            player = None
            for i in range(NUMBER_OF_PLAYERS):
                if self.player_socket[i] is None:
                    player = i
                    break

            if player is None:
                raise Exception('There should be a valid player')

            self.player_socket[player] = websocket

            greeting = f"Hello {name}! You are player {player}"

            await websocket.send(greeting)
            print(f"> {greeting}")

            await websocket.send(json.dumps({'player': player}))

            # register(websocket) sends user_event() to websocket
            await self.register(websocket)
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
                await self.unregister(websocket)
                self.player_socket[player] = None

    async def register(self, websocket):
        USERS.add(websocket)
        await self.notify_users()

    async def unregister(self, websocket):
        USERS.remove(websocket)
        await self.notify_users()

    async def notify_users(self):
        if USERS:  # asyncio.wait doesn't accept an empty list
            message = users_event()
            await asyncio.wait([user.send(message) for user in USERS])


class ConfigContainer:
    server = {}
    s_msg = {}
    exp = {}


def eg_cancel_server():
    """Shows a dialog informing the server is cancelled."""

    # eg.msgbox(cfg.s_msg['cancel program'])
    eg.msgbox('the server is cancelled')
    exit_server()


def exit_server():
    print('exit_server')
    sys.exit(0)
    # just in case we just closed a thread or exception was caught we force the exit
    os._exit(1)


def string_to_bool(some_string):
    # result = utostr(some_string)
    # return result.lower() in ['true', 'yes', 'sim']
    return some_string.lower() in ['true', 'yes', 'sim']


def get_experiment(exp_dir, define_experiment):
    if define_experiment:
        experiment = cfg.server['experiment']
        return experiment
    experiments = [x[:-4] for x in os.listdir(exp_dir) if ('.ini' in x)]
    # dialog asks for an experiment
    experiment = eg.choicebox(cfg.s_msg['run which experiment'], choices=experiments)
    if experiment is None:
        # user closed choice box
        eg_cancel_server()
    return experiment


def get_group(save_dir, define_group):
    if define_group:
        group = cfg.server['group']
        return group
    # load configs
    groups = [x for x in os.listdir(save_dir) if '.' not in x]
    add_new = cfg.s_msg['create new group']
    groups.append(add_new)

    # dialog asks for a group
    group = eg.choicebox(cfg.s_msg['run which group'], choices=groups)
    if group is None:
        # user closed choice box
        eg_cancel_server()
    elif group == add_new:
        # user chose to add a new subject
        group = ''
        while group == '':
            group = eg.enterbox(msg=cfg.s_msg['type group name'],
                                title=cfg.s_msg['new group'],
                                default='',
                                strip=True)
            if group == '':
                continue
            elif group is None:
                eg_cancel_server()
            # group = utostr(group)
            group = group.lower()
            if group in groups:
                eg.msgbox(cfg.s_msg['group exists'].format(group))
                group = ''
                continue
    return group


def main():
    global c
    # global cfg
    c = Connections()
    # cfg = Container()

    cfg_dir = DIR / 'config'
    save_dir = DIR / 'saved'
    exp_dir = cfg_dir / 'experiments'
    lang_dir = cfg_dir / 'lang' / LANG

    if not save_dir.exists():
        try:
            save_dir.mkdir()
        except IOError as ex:
            logging.critical('Could not create directory', ex)
            sys.exit(0)

    spec_dir = cfg_dir / 'spec'

    # load server messages config
    cfg.s_msg = ConfigObj(infile=str(lang_dir / 'server_messages.ini'),
                          configspec=str(spec_dir / 'spec_server_messages.ini'),
                          encoding='UTF8')

    # load server config
    cfg.server = ConfigObj(infile=str(cfg_dir / 'server.ini'),
                           configspec=str(spec_dir / 'spec_server.ini'),
                           encoding='UTF8')
    validate_config(cfg.server)

    define_group = string_to_bool(cfg.server['define group'])
    group = get_group(save_dir, define_group)

    save_dir = save_dir / group
    if not save_dir.exists():
        save_dir.mkdir()

    save_dir_files = [x for x in os.listdir(save_dir) if '.ini' in x]

    experiment_filename = group + '_experiment.ini'

    if experiment_filename in save_dir_files:
        cfg.exp = ConfigObj(infile=str(save_dir / experiment_filename),
                            configspec=str(spec_dir / 'spec_experiment.ini'))
        validate_config(cfg.exp)
    else:
        define_experiment = string_to_bool(cfg.server['define experiment'])
        experiment = get_experiment(exp_dir, define_experiment)
        experiment_config_path = exp_dir / (experiment + '.ini')
        if not experiment_config_path.exists():
            raise Exception(
                "Experiment {} doesn't exist. Fix server.ini: choose an available experiment".format(experiment))

        cfg.exp = ConfigObj(infile=str(experiment_config_path),
                            configspec=str(spec_dir / 'spec_experiment.ini'))

        # EXPERIMENT (validating but PRESERVING comments (set_copy=True also copies spec comments))
        pre_copy_comments = copy.deepcopy(cfg.exp.comments)
        pre_copy_final_comment = copy.deepcopy(cfg.exp.final_comment)
        validate_config(cfg.exp, set_copy=True)
        cfg.exp.comments = pre_copy_comments
        cfg.exp.final_comment = pre_copy_final_comment

        cfg.exp.filename = str(save_dir / experiment_filename)
        cfg.exp.initial_comment = ['# experiment: {}\n# group: {}'.format(experiment, group), ' ']
        cfg.exp.write()

    start_server = websockets.serve(c.connect, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


cfg = ConfigContainer()

try:
    main()
except Exception as e:
    logging.error(e, exc_info=True)
    raise
