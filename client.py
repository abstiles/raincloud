#!/usr/bin/env python2

import sys

import zmq

context = zmq.Context()
socket = context.socket(zmq.SUB)

print "Collecting updates from server."
socket.connect("tcp://localhost:14256")
socket.setsockopt(zmq.SUBSCRIBE, 'text_data')

print "Waiting for an update"
while True:
    _, update = socket.recv_multipart()
    sys.stdout.write(update)
