#!/usr/bin/env python2

import sys

import zmq

context = zmq.Context()
socket = context.socket(zmq.SUB)

print "Collecting updates from server."
socket.connect("tcp://localhost:14256")
socket.setsockopt(zmq.SUBSCRIBE, 'line')

print "Waiting for an update"
while True:
    update = socket.recv().split(None, 1)
    if len(update) == 2:
        update_type, update = update
        if update_type == 'line':
            print update
            continue
        print "What? (%s): %s" % (update_type, update)
