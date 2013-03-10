#!/usr/bin/env python

import sys
import time
import re
import readline
from telnetlib import Telnet
from getpass import getpass
from select import select

from eaccess import EAccess

PLATFORM = '/FE:WIZARD /VERSION:1.0.1.22 /P:Python /XML'

xml_marker = re.compile(r'<[^>]*/>')
xml_line = re.compile(r'^<.*')

def interact(conn):
    current_line = ''
    while 1:
        rfd, wfd, xfd = select([conn, sys.stdin], [], [])
        if conn in rfd:
            try:
                text = conn.read_eager()
            except EOFError:
                print('*** Connection closed by remote host ***')
                break
            current_line += text
            while '\n' in current_line:
                line, current_line = current_line.split('\n', 1)
                if r'</prompt>' in line:
                    sys.stdout.write('cmd> ')
                    sys.stdout.flush()
                    continue
                line = re.sub(xml_marker, '', line)
                if xml_line.match(line):
                    continue
                sys.stdout.write('\r')
                sys.stdout.write(line.rstrip())
                sys.stdout.write('\n')
                sys.stdout.flush()
        if sys.stdin in rfd:
            line = sys.stdin.readline()
            if not line:
                break
            conn.write(line)
            sys.stdout.write('cmd> ')
            sys.stdout.flush()


if __name__ == '__main__':
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
    time.sleep(1)
    conn.write('<c>')
    conn.write('\r\n')
    conn.write('<c>')
    conn.write('\r\n')
    interact(conn)
