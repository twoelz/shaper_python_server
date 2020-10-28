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
import socket
import urllib.request
import websockets
import json
import logging
import decimal
import sys
import os
import pathlib
import re
import copy
import ipaddress
import sys
import datetime
import pickle


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
# formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
formatter = logging.Formatter('%(name)-4s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

# Now, we can log to the root logger, or any other logger. First the root...
# logging.info('Jackdaws love my big sphinx of quartz.')

# # Now, define a couple of other loggers which might represent areas in your
# # application:
#
# logger1 = logging.getLogger('myapp.area1')
# logger2 = logging.getLogger('myapp.area2')
#
# logger1.debug('Quick zephyrs blow, vexing daft Jim.')
# logger1.info('How quickly daft jumping zebras vex.')
# logger2.warning('Jail zesty vixen who grabbed pay from quack.')
# logger2.error('The five boxing wizards jump quickly.')

# logging.info('INFO track')
# logging.critical('CRITICAL track')
# logging.debug('DEBUG track')


if 'SHAPER_EXPERIMENTER' in os.environ.keys():
    logging.info('SHAPER_EXPERIMENTER: {}'.format(os.environ['SHAPER_EXPERIMENTER']))
else:
    logging.warning('SHAPER_EXPERIMENTER environment variable not found')

if 'SHAPER_IP_BIN' in os.environ.keys():
    logging.info('SHAPER_IP_BIN: {}'.format(os.environ['SHAPER_IP_BIN']))
else:
    logging.warning('SHAPER_IP_BIN environment variable not found')

if 'SHAPER_IP_KEY' in os.environ.keys():
    logging.info('SHAPER_IP_KEY: {}'.format(os.environ['SHAPER_IP_KEY']))
else:
    logging.warning('SHAPER_IP_KEY environment variable not found')

# import urllib.request

# from google.cloud import firestore


# import firebase_admin
# from firebase_admin import credentials
# from firebase_admin import firestore
# from google.oauth2 import service_account
#
# # Use the application default credentials
# cred = credentials.Certificate.ge
# # cred = service_account.Credentials.
# firebase_admin.initialize_app(cred, {
#   'projectId': 'shaper-meta',
# })
#
# db = firestore.client()

import requests

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


def announcement_private(announce_data):
    bin_id = cfg.server['network']['announce ip bin']
    bin_key = cfg.server['network']['announce ip key']

    if str(cfg.server['network']['announce ip bin']).lower() == 'test:':
        # use test bin and password
        cfg.server['network']['announce ip bin'] = cfg.hidden['test announce ip bin']
        cfg.server['network']['announce ip key'] = cfg.hidden['test announce ip key']
    elif (cfg.server['network']['announce ip bin'] == 'default') or \
            (str(cfg.server['network']['announce ip bin']).len < 8) or \
            (str(cfg.server['network']['announce ip key']).len < 8):
        # bin and password lenght need to be larger than 7 letters
        # if not: use environment variable
        if not ('SHAPER_IP_BIN' in os.environ.keys()) and \
               ('SHAPER_IP_KEY' in os.environ.keys()):
            error = 'No ip bin or ip key set. Please set them in server.ini or environment variables.'
            logging.error(error)
            eg.msgbox(error)
            eg_cancel_server()
        cfg.server['network']['announce ip bin'] = os.environ['SHAPER_IP_BIN']
        cfg.server['network']['announce ip key'] = os.environ['SHAPER_IP_KEY']
    url = 'https://api.jsonbin.io/v3/b/{bin_id}'.format(bin_id=cfg.server['network']['announce ip bin'])

    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': cfg.server['network']['announce ip key'],
        'X-Bin-Versioning': 'false'
    }

    try:
        req = requests.put(url, json=announce_data, headers=headers)
    except Exception as err:
        error = 'could not do ip announcement (private bin): \n{}'.format(err)
        logging.error(error, exc_info=True)
        eg.msgbox(error)
        eg_cancel_server()


def announcement_public(announce_data, announce_log):
    # public announcement is done only once every X days (in hidden settings: days to keep)
    # or if the IP or port changed

    logging.info('doing public announcement')
    url = 'https://api.jsonbin.io/v3/b/{bin_id}'.format(bin_id=cfg.hidden['public announce ip bin'])
    headers = {}
    try:
        req = requests.get(url, json=None, headers=headers, timeout=4.0)
        # TODO: TimeOut error
    except Exception as err:
        error = 'could not READ ip announcement (public bin)'
        logging.error(error)
        logging.error(err, exc_info=True)
        eg.msgbox(error)
        eg_cancel_server()

    announced_experiments = req.json()['record']

    remove_announcements = []
    for experimenter in announced_experiments.keys():
        experiment_date = datetime.date(year=announced_experiments[experimenter]['year'],
                                        month=announced_experiments[experimenter]['month'],
                                        day=announced_experiments[experimenter]['day'])
        experiment_timedelta = datetime.date.today() - experiment_date
        days_before = experiment_timedelta.days
        if days_before > cfg.hidden['days to keep']:
            remove_announcements.append(experimenter)
    for experimenter in remove_announcements:
        announced_experiments.pop(experimenter)

    announced_experiments[cfg.server['experimenter']] = announce_data

    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': cfg.hidden['public announce ip key'],
        'X-Bin-Versioning': 'false'
    }

    try:
        req = requests.put(url, json=announced_experiments, headers=headers, timeout=4.0)
    except requests.exceptions.ReadTimeout as err:
        error = 'could not do ip announcement (public bin): Timed Out'
        logging.error(error)
        logging.error(err, exc_info=True)
        eg.msgbox(error)
        eg_cancel_server()
    except Exception as err:
        error = 'could not do ip announcement (public bin): check log for exception'
        logging.error(error)
        logging.error(err, exc_info=True)
        eg.msgbox(error)
        eg_cancel_server()
    logging.info('public announcement done: {}'.format(announce_data))


def bin_api_examples_dummy_method():
    pass
    # # -------------CREATE RECORD--------------
    # # create works!
    # url = 'https://api.jsonbin.io/v3/b'
    #
    # headers = {
    #     'Content-Type': 'application/json',
    #     'X-Master-Key': cfg.server['network']['announce ip key'],
    #     'X-BIN-NAME': 'ShaperServerAnnounce',
    #     'X-Collection-Id': '<MY COLLECTION ID>',  # Shaper Collection
    # }
    # data = {'ip': external_ip,
    #         'port': str(cfg.server['network']['port']),
    #         }
    #
    # req = requests.post(url, json=data, headers=headers)
    # logging.info(req.text)

    # # create works! FOR PUBLIC Bin
    # url = 'https://api.jsonbin.io/v3/b'
    #
    # headers = {
    #     'Content-Type': 'application/json',
    #     'X-Master-Key': cfg.server['network']['announce ip key'],
    #     'X-BIN-NAME': 'ShaperServerAnnouncePublic',
    #     'X-Bin-Private': 'false',
    #     'X-Collection-Id': '5f86fdea7243cd7e824f255d',  # Shaper Collection
    # }
    #
    # data = {cfg.server['experimenter']: {
    #     'ip': external_ip,
    #     'port': str(cfg.server['network']['port']),
    #     'year': datetime.date.today().year,
    #     'month': datetime.date.today().month,
    #     'day': datetime.date.today().day,
    # }}
    #
    # req = requests.post(url, json=data, headers=headers)
    # logging.info(req.text)

    # -------------UPDATE RECORD--------------
    #
    # url = 'https://api.jsonbin.io/v3/b/{bin_id}'.format(bin_id=cfg.server['network']['announce ip bin'])
    #
    # headers = {
    #     'Content-Type': 'application/json',
    #     'X-Master-Key': cfg.server['network']['announce ip key'],
    #     'X-Bin-Versioning': 'false'
    # }
    # data = {'ip': external_ip,
    #         'port': str(cfg.server['network']['port']),
    #         }
    #
    # req = requests.put(url, json=data, headers=headers)
    # logging.info(req.text)

    # # -------------READ RECORD--------------
    # # get works!
    # url = 'https://api.jsonbin.io/v3/b/{bin_id}/latest'.format(bin_id=cfg.server['network']['announce ip bin'])
    # headers = {
    #   'X-Master-Key': cfg.server['network']['announce ip key'],
    # }
    #
    # req = requests.get(url, json=None, headers=headers)
    # logging.info(req.text)

    # # -------------DELETE RECORD--------------
    # # delete works
    # url = 'https://api.jsonbin.io/v3/b/{bin_id}'.format(bin_id=cfg.server['network']['announce ip bin'])
    # headers = {
    #   'X-Master-Key': cfg.server['network']['announce ip key']
    # }
    #
    # req = requests.delete(url, json=None, headers=headers)
    # logging.info(req.text)

    # -------------UPDATE PUBLIC RECORD--------------
    #


def setup_announcement():  # using https://jsonbin.io/ service
    internet_connected = c.check_internet_connected()
    if not internet_connected:
        error = 'internet not connected. will not announce ip'
        logging.error(error)
        eg.msgbox(error)
        return
    if not cfg.server['network']['announce ip']:
        logging.warning('server config: will not announce ip')
        return
    logging.info('connected to the internet')
    external_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
    if not is_valid_ip(external_ip):
        error = 'invalid external ip. will not announce ip'
        logging.error(error)
        eg.msgbox(error)
        return
    announce_data = {
        'ip': external_ip,
        'port': str(cfg.server['network']['port']),
        'year': datetime.date.today().year,
        'month': datetime.date.today().month,
        'day': datetime.date.today().day,
    }

    # this flag needs to change to False to go ahead for public announcement
    skip_public_announcement = True

    if cfg.server['public announcement']:
        # check next if public announcement will be needed or not
        log_dir = DIR / 'log'
        announce_log = log_dir / 'announced_{}'.format(cfg.server['experimenter'])
        if announce_log.exists():
            # TODO: Try/except on file load
            file = open(announce_log, 'rb')
            previous_announced_data = pickle.load(file)
            file.close()
            if announce_data['ip'] != previous_announced_data['ip']:
                skip_public_announcement = False
            previous_experiment_date = datetime.date(year=previous_announced_data['year'],
                                                     month=previous_announced_data['month'],
                                                     day=previous_announced_data['day'])
            experiment_timedelta = datetime.date.today() - previous_experiment_date
            days_before = experiment_timedelta.days
            if days_before >= cfg.hidden['days to keep']:
                logging.info('previous public announcement too old: will announce')
                skip_public_announcement = False
        else:
            print('it doesnt exist')
            skip_public_announcement = False
            logging.info('previous public announcement not found: will announce')

    if skip_public_announcement:
        logging.info('public announcement skipped')
    else:
        announcement_public(announce_data)
        logging.info('creating log of announcement now')
        # TODO: Try/except on file write
        file = open(announce_log, 'wb')
        pickle.dump(data=announce_data,
                    file=file)
        file.close()

    announcement_private(announce_data)

def is_valid_ip(test_ip='0.0.0.0'):
    # m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", test_ip)
    # return bool(m) and all(map(lambda n: 0 <= int(n) <= 255, m.groups()))
    try:
        ip = ipaddress.ip_address(test_ip)
        logging.debug('%s is a correct IP%s address.' % (ip, ip.version))
        return True
    except ValueError:
        logging.error('address/netmask is invalid: %s' % sys.argv[1])
        return False
    except Exception as err:
        logging.error("Unexpected error checking is_ip_valid:", sys.exc_info()[0])
        raise
    return False


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
        logging.error(error_messages)
        raise Exception(error_messages)
    if not res:
        error = '{0} invalid\n'.format(os.path.split(a_config.filename)[1])
        logging.error(error)
        raise Exception(error)


# prevent import
if not __name__ == "__main__":
    raise Exception('server.py should not be imported')
    sys.exit(0)



# TODO: REMOVE STATE
STATE = {"value": 0}

USERS = set()

ADMIN = None


def state_event():
    return json.dumps({"type": "state", **STATE})


# def users_event():
#     return json.dumps({"type": "users", "count": len(self.)})


async def notify_state():
    if USERS:  # asyncio.wait doesn't accept an empty list
        message = state_event()
        await asyncio.wait([user.send(message) for user in USERS])


class Connections:
    ip_address = ''
    player_sockets = set()
    players_in = set()

    # TODO check if needed
    player_names = {}
    player_unique_ids = {}

    # chat variable
    previous_chat_sender = ''

    # def setup(self):
    #     # setup after configs are loaded, just before first websocket connection
    #     for i in range(cfg.exp['main']['number of players']):
    #         self.player_socket[i] = None

    # async def disconnect(self, player, websocket):
    #     await self.unregister_player(player, websocket)

    def check_internet_connected(self, url='http://google.com', timeout=3):
        try:
            urllib.request.urlopen(url, timeout=timeout)
            return True
        except Exception as exception:
            logging.error(exception)
        logging.error('internet not connected')
        return False

    async def send_configs(self, websocket):
        cfg.exp.dict()
        await websocket.send(json.dumps({'type': 'configs',
                                         'exp': json.dumps(cfg.exp.dict()),
                                         's_msg': json.dumps(cfg.s_msg.dict()),
                                         }))

    async def connect_admin(self, websocket):
        # TODO: admin
        pass

    async def connect(self, websocket, path):
        message = await websocket.recv()
        if message == 'admin':
            await self.connect_admin(websocket)
        elif message == 'shaper ping':
            await self.pong()
        elif len(self.player_sockets) < cfg.exp['main']['number of players']:
            await self.connect_player(message, websocket)
        else:
            logging.error('player tried to connect, room was full')
            websocket.close()

    async def pong(self, websocket):
        await websocket.send('shaper pong')

    async def connect_player(self, message, websocket):
        player = None
        try:
            name, unique_id = json.loads(message)
            print('name is: {name}, unique_id is: {unique_id}'.format(name=name, unique_id=unique_id))
        except (json.decoder.JSONDecodeError, ValueError) as error:
            logging.error('player name should be passed as a json list with name following a unique iq')
            logging.error(error)
            return

        for i in range(cfg.exp['main']['number of players']):
            if i not in self.players_in:
                player = i
                break
        if player is None:
            error = 'there should be a valid player'
            logging.error(error)
            raise Exception(error)

        # register, accept & send configs to player
        await self.register_player(player, name, websocket)
        await websocket.send(json.dumps({'type': 'accept player',
                                         'player': player,
                                         }))
        await self.send_configs(websocket)

        # listen to player
        try:
            async for message in websocket:
                logging.info(message)
                if message[:8] == '__chat__':
                    await self.player_action_received(player, 'chat', message[8:], websocket)
                else:
                    try:
                        data = json.loads(message)
                    except json.decoder.JSONDecodeError as err:
                        logging.error("JSONDecodeError: {0}".format(err))
                        data = {}
                    if 'action' not in data.keys():
                        logging.error("no action in data received: {}", data)
                    else:
                        action = data['action']
                        await self.player_action_received(player, action, data, websocket)
        finally:
            await self.unregister_player(player, websocket)

    async def player_action_received(self, player, action, data, websocket):
        if action == "disconnect":
            await self.unregister_player(player, websocket)
            return
        elif action == 'chat':
            await self.chat_message_received(data, websocket)
            logging.debug(data)
            return
        elif action == "something else":
            # do something else
            return
        else:
            logging.error("unsupported event: {}", data)

    async def chat_message_received(self, chat_message, websocket):
        logging.info(f'Player{websocket.player_number} {websocket.player_name}: {chat_message}')
        sender_name = websocket.player_name
        sender_number = websocket.player_number
        same_sender = f'{sender_number}{sender_name}' == self.previous_chat_sender

        # TODO: record chat message here
        # send it to all players registered
        for player_socket in self.player_sockets:
            await player_socket.send(json.dumps({'game data': 'chat message',
                                                 'sender number': sender_number,
                                                 'sender name': sender_name,
                                                 'same sender': same_sender,
                                                 'chat message': chat_message}))
        self.previous_chat_sender = f'{sender_number}{sender_name}'

    async def register_player(self, player, name, websocket):
        logging.info(f'Player {player} registered with name: {name}')
        websocket.player_name = name
        websocket.player_number = player
        self.player_sockets.add(websocket)
        self.players_in.add(player)
        self.player_names[player] = name
        await self.notify_users()

    async def unregister_player(self, player, websocket):
        logging.info('removing player')
        if websocket in self.player_sockets:
            self.player_sockets.remove(websocket)
        if player in self.players_in:
            self.players_in.remove(player)
        if player in self.player_names.keys():
            self.player_names[player] = ''
        await self.notify_users()

    async def notify_users(self):
        if self.players_in:  # asyncio.wait doesn't accept an empty list
            message = json.dumps({'type': 'print',
                                  'message': 'players in: {}'.format(self.players_in)})
            await asyncio.wait([player_socket.send(message) for player_socket in self.player_sockets])


class ConfigContainer:
    server = ConfigObj()
    s_msg = ConfigObj()
    exp = ConfigObj()
    hidden = ConfigObj()


def eg_cancel_server():
    """Shows a dialog informing the server is cancelled."""

    # eg.msgbox(cfg.s_msg['cancel program'])
    eg.msgbox('the server is cancelled')
    exit_server()


def exit_server():
    try:
        logging.info('exit server')
    except Exception as err:
        print(err)
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
    if experiment not in experiments:
        eg.msgbox('please create the new experiment file in config/experiments')
        eg_cancel_server()
    # if experiment ==
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


def try_to_mkdir(some_path):
    try:
        if not some_path.exists():
            some_path.mkdir()
    except IOError as ex:
        logging.critical('Could not create directory', ex)
        sys.exit(0)


def setup_configs():
    cfg_dir = DIR / 'config'
    save_dir = DIR / 'saved'
    exp_dir = cfg_dir / 'experiments'
    lang_dir = cfg_dir / 'lang' / LANG
    log_dir = DIR / 'log'

    for my_dir in [save_dir, log_dir]:
        try_to_mkdir(my_dir)

    spec_dir = cfg_dir / 'spec'

    # load hidden config
    cfg.hidden = ConfigObj(infile=str(spec_dir / 'hidden.ini'),
                           configspec=str(spec_dir / 'spec_hidden.ini'),
                           encoding='UTF8')
    validate_config(cfg.hidden)

    # load server messages config
    cfg.s_msg = ConfigObj(infile=str(lang_dir / 'server_messages.ini'),
                          configspec=str(spec_dir / 'spec_server_messages.ini'),
                          encoding='UTF8')

    # load server config
    cfg.server = ConfigObj(infile=str(cfg_dir / 'server.ini'),
                           configspec=str(spec_dir / 'spec_server.ini'),
                           encoding='UTF8')
    validate_config(cfg.server)

    if cfg.server['experimenter'] in ['', 'default']:
        if 'SHAPER_EXPERIMENTER' in os.environ.keys():
            cfg.server['experimenter'] = os.environ['SHAPER_EXPERIMENTER']
            logging.info('Default SHAPER_EXPERIMENTER: {}'.format(cfg.server['experimenter']))
        else:
            error = 'SHAPER_EXPERIMENTER environment variable not found \n' + \
                    'Either create that variable, or set the experimenter name in server config.'
            logging.error(error)
            eg.msgbox(error)
            eg_cancel_server()

    define_group = string_to_bool(cfg.server['define group'])
    group = get_group(save_dir, define_group)

    save_dir = save_dir / group

    try_to_mkdir(save_dir)

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


def main():
    setup_configs()
    setup_announcement()
    port = cfg.server['network']['port']
    logging.info('port is: {}'.format(port))
    start_server = websockets.serve(c.connect, '', port)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


c = Connections()
cfg = ConfigContainer()

try:
    main()
except Exception as e:
    logging.error(e, exc_info=True)
    raise
