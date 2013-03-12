#!/usr/bin/env python2

import sys
import re
import readline
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
    consume_newline = False

    def __init__(self, data_socket):
        self.data_socket = data_socket

    def start(self, tag, attrib):
        self.events.append((tag, attrib))

    def data(self, data):
        if not self.consume_newline or str(data).rstrip('\n'):
            self.data_socket.send('line %s' % str(data))
            self.consume_newline = False

    def end(self, tag):
        self.consume_newline = True

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
            parser.feed(text)
        if sys.stdin in rfd:
            line = sys.stdin.readline()
            if not line:
                break
            remote.write(line)
            sys.stdout.write('cmd> ')
            sys.stdout.flush()


if __name__ == '__main__':
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:14256")

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
