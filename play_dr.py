#!/usr/bin/env python2

import sys
import re
import readline
import argparse
from time import sleep
from telnetlib import Telnet
from getpass import getpass
from select import select

import zmq
from lxml import etree

from eaccess import EAccess

PLATFORM = '/FE:WIZARD /VERSION:1.0.1.22 /P:Python /XML'

class StormfrontParser:
    events = []
    eventHandlerStack = []
    data_str = ''

    def __init__(self, data_socket):
        self.data_socket = data_socket

    def start(self, tag, attrib):
        self.events.append((tag, attrib))

    def data(self, data):
        if str(data).rstrip('\n'):
            self.data_str += str(data)

    def end(self, tag):
        if self.data_str.strip():
            self.data_socket.send_multipart(['text_data',
                                             '\n%s' % self.data_str])
            self.data_str = ''

    def close(self):
        events, self.events = self.events, []
        return events

def interact(remote, local):
    parser_target = StormfrontParser(local)

    parser = etree.XMLParser(recover=True, target=parser_target)
    parser.feed('<begin_parsing>')

    sys.stdout.write('cmd> ')
    sys.stdout.flush()

    while True:
        rfd, wfd, xfd = select([remote, sys.stdin], [], [])
        if remote in rfd:
            try:
                text = remote.read_eager()
            except EOFError:
                print('*** Connection closed by remote host ***')
                break
            log(text)
            parser.feed(text)
        if sys.stdin in rfd:
            line = sys.stdin.readline()
            if not line:
                break
            remote.write(line)
            sys.stdout.write('cmd> ')
            sys.stdout.flush()


def run_game(socket):
    auth = EAccess()
    username = raw_input('Enter your username: ')
    password = getpass()
    character = raw_input('Enter your character: ')
    key = auth.login(username, password, character)
    conn = Telnet('dr.simutronics.net', 11024)
    conn.write(key)
    conn.write('\r\n')
    conn.write(PLATFORM)
    conn.write('\r\n')
    conn.write('\r\n')
    sleep(1)
    conn.write('<c>')
    conn.write('\r\n')
    conn.write('<c>')
    conn.write('\r\n')

    interact(conn, socket)

def process_log(infile, socket):
        print 'Waiting for connection.'
        sleep(2)
        parser_target = StormfrontParser(socket)

        parser = etree.XMLParser(recover=True, target=parser_target)
        parser.feed('<begin_parsing>')
        with open(infile, 'r') as f:
            for line in f.readlines():
                log(line)
                parser.feed(line)

def log(log_str):
    global logfile
    logfile.write(log_str)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Play Dragonrealms')
    parser.add_argument('-f', '--file',
        help='Parse a game log instead of connecting to the server.')
    parser.add_argument('-l', '--log', default='/dev/null',
        help='Output raw connection stream to log.')
    args = parser.parse_args()

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:14256")

    with open(args.log, 'w') as output:
        logfile = output
        if args.file is None:
            print 'Connecting to server!'
            run_game(socket)
        else:
            print 'Parsing the log.'
            process_log(args.file, socket)
