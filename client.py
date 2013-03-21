#!/usr/bin/env python2

import sys
import textwrap

import zmq
from blessings import Terminal

DEFAULT_STREAM = 'text_data'

if len(sys.argv) > 1:
    stream = sys.argv[1]
else:
    stream = DEFAULT_STREAM
print "Handling stream", stream

context = zmq.Context()
socket = context.socket(zmq.SUB)

print "Collecting updates from server."
socket.connect("tcp://localhost:14256")
socket.setsockopt(zmq.SUBSCRIBE, stream)

t = Terminal()
print "Waiting for an update"
last_update = ''
while True:
    _, update = socket.recv_multipart()
    if last_update.endswith('\n') and not update.strip():
        continue
    if '\n' in update:
        last_line = last_update.strip()
        lines = []
        for line in update.split('\n'):
            if not line.strip() and not last_line:
                continue
            lines.append(textwrap.fill(line, t.width))
            last_line = line.strip()
        last_update = last_line
        sys.stdout.write('\n'.join(lines))
    else:
        sys.stdout.write(update)
        last_update = update
    sys.stdout.flush()
