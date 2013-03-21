#!/usr/bin/env python2

import sys
import re
import readline
import functools
import argparse
from time import sleep, strftime, localtime
from telnetlib import Telnet
from getpass import getpass
from select import select
from collections import defaultdict

import zmq
from blessings import Terminal
from lxml import etree

from eaccess import EAccess

PLATFORM = '/FE:WIZARD /VERSION:1.0.1.22 /P:Python /XML'

class keydefaultdict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError( key )
        else:
            ret = self[key] = self.default_factory(key)
            return ret

TAG_HANDLER = keydefaultdict(lambda tag: functools.partial(unhandled_tag, tag))

def handles_tags(*args):
    """A decorator to register a function as a tag handler.

    The arguments list is interpreted as the list of tags the wrapped function
    is intended to handle. Wrapped functions should take three arguments: the
    tag name, the attributes dictionary, and the data (if any) enclosed by the
    start and end tags.

    """
    def _handles_tags(f):
        for tag in args:
            TAG_HANDLER[tag] = functools.partial(f, tag)
        return f
    return _handles_tags

def unhandled_tag(tag, attrs, data=None):
    log_error('Encountered unhandled tag (%s):\n'
              '    attrs: %s\n' % (tag, repr(attrs)))
    if data is not None:
        log_error('    data: %s\n' % data)

    return '\n%s\n' % data if data is not None else None

@handles_tags('pushBold', 'popBold')
def handle_bold(tag, attrs, data=None):
    global t
    if tag.startswith('push'):
        return t.bold
    return t.normal

@handles_tags('preset', 'style')
def format_as(tag, attrs, data=None):
    global style
    if data:
        return str(style[attrs['id']]) + data + str(t.normal)
    return str(style[attrs['id']])

@handles_tags('prompt')
def format_prompt(tag, attrs, data=None):
    '''Ignore for now.'''
    return None
    return t.cyan('\n[%s] cmd> ' % strftime('%r',
        localtime(int(attrs['time']))))

@handles_tags('component', 'inv')
def divert_stream(tag, attrs, data=None):
    if data:
        data_socket.send_multipart([str(attrs['id']), '\n%s' % data])

@handles_tags('pushStream', 'popStream')
def switch_stream(tag, attrs, data=None):
    if 'id' in attrs:
        parser_target.current_stream = str(attrs['id'])
    if tag == 'popStream':
        parser_target.current_stream = 'text_data'

@handles_tags('streamWindow', 'container')
def clear_stream(tag, attrs, data=None):
    global style
    if 'title' not in attrs:
        attrs['title'] = ''
    if 'subtitle' not in attrs:
        attrs['subtitle'] = ''
    initial_str = t.clear + style['stream subtitle'](attrs['title'] + attrs['subtitle'])
    data_socket.send_multipart([str(attrs['id']), str(initial_str) + '\n'])

@handles_tags('d')
def format_direction(tag, attrs, data=None):
    global style
    return str(style['direction']) + data + str(t.normal)

@handles_tags('spell')
def update_spell(tag, attrs, data=None):
    """Update the currently active spell. (Ignored for now.)"""
    return None

class StormfrontParser:
    events = []
    eventHandlerStack = []
    raw_text = ''
    current_stream = 'text_data'

    def start(self, tag, attrib):
        if tag == 'main_stream':
            return
        if self.raw_text:
            data_socket.send_multipart([self.current_stream, '%s' % self.raw_text])
            self.raw_text = ''
        self.events.append([attrib, None])
        self.eventHandlerStack.append(TAG_HANDLER[tag])

    def data(self, data):
        try:
            if str(data):
                if self.events:
                    if self.events[-1][1] is None:
                        self.events[-1][1] = str(data)
                    else:
                        self.events[-1][1] += str(data)
                else:
                    self.raw_text += str(data)
        except Exception as err:
            log_error(str(err))

    def end(self, tag):
        try:
            data = None
            if self.events:
                event_handler = self.eventHandlerStack.pop()
                data = event_handler(*self.events.pop())
            if self.events and data:
                if self.events[-1][1] is None:
                    self.events[-1][1] = str(data)
                else:
                    self.events[-1][1] += str(data)
            elif data is not None:
                self.raw_text += str(data)
            if self.raw_text:
                data_socket.send_multipart([self.current_stream, '%s' % self.raw_text])
                self.raw_text = ''
        except Exception as err:
            log_error(str(err))

    def close(self):
        events, self.events = self.events, []
        return events

def interact(remote):
    global parser_target
    parser_target = StormfrontParser()

    parser = etree.XMLParser(recover=True, target=parser_target)
    parser.feed('<main_stream>')

    cmd_prompt = t.cyan('cmd> ')
    sys.stdout.write(cmd_prompt)
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
            line = raw_input()
            if not line:
                break
            print "Last command: %s" % line
            remote.write('%s\n' % line)
            data_socket.send_multipart(['text_data', str(cmd_prompt) +
                                        str(t.white(line)) + '\n'])
            sys.stdout.write(cmd_prompt)
            sys.stdout.flush()


def run_game():
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

    interact(conn)

def process_log(infile):
    global parser_target
    print 'Waiting for connection.'
    sleep(2)
    parser_target = StormfrontParser()

    parser = etree.XMLParser(recover=True, target=parser_target)
    parser.feed('<main_stream>')
    with open(infile, 'r') as f:
        for line in f.readlines():
            log(line)
            parser.feed(line)

def log(log_str):
    global logfile
    logfile.write(log_str)
    logfile.flush()

def log_error(log_str):
    sys.stderr.write(log_str)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Play Dragonrealms')
    parser.add_argument('-f', '--file',
        help='Parse a game log instead of connecting to the server.')
    parser.add_argument('-l', '--log', default='/dev/null',
        help='Output raw connection stream to log.')
    args = parser.parse_args()

    t = Terminal()
    style = defaultdict(lambda: t.normal)
    style['roomName'] = t.bold_white_on_blue
    style['stream subtitle'] = t.bold_red
    style['direction'] = t.yellow

    context = zmq.Context()
    data_socket = context.socket(zmq.PUB)
    data_socket.bind("tcp://*:14256")

    with open(args.log, 'w') as output:
        logfile = output
        if args.file is None:
            print 'Connecting to server!'
            run_game()
        else:
            print 'Parsing the log.'
            process_log(args.file)
