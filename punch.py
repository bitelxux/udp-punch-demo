#!/usr/bin/env python
# -*- coding: utf-8 -*-

import select
import time
import socket
import sys
import threading
import signal


class Logger(object):
    def __init__(self, name):
        self.name = name

    def log(self, msg):
        print "%s: %s" % (self.name, msg)


class RXThread(threading.Thread):

    running = False

    def __init__(self, context):
        self.context = context
        threading.Thread.__init__(self)

    def run(self):
        self.running = True
        while self.running:
            rx, _, _ = select.select([self.context.fd], [], [], 60)
            if rx:
                msg, address = self.context.fd.recvfrom(0xFFFF)
                self.context.attend(address, msg)

    def stop(self):
        self.running = False


class App(object):

    peer = None
    peers = None
    fd = None
    port = None
    name = None
    running = False

    def send(self, tar, cmd, payload, address):
        self.fd.sendto('%s:%s:%s:%s' % (self.name, tar, cmd, payload), address)

    def init_peers(self):

        self.peers = dict()
        self.peers['matchmaker'] = {}
        self.peers['matchmaker']['address'] = ('matchmaker.foo', 9999)
        self.peers['matchmaker']['ts'] = time.time()

    def attend(self, address, msg):
        src, tar, cmd, payload = msg.split(':')
        self.peers.setdefault(src,{})
        self.peers[src]['address'] = address
        self.peers[src]['ts'] = time.time()
        if cmd == 'SEA':
            if payload in self.peers and src in self.peers:
                self.send_call(src, payload)
        elif cmd == 'HEL':
            print "Received HEL from %s at %s" % (src, str(address))
        elif cmd == 'CAL':
            tar, address = payload.split("=")
            address = eval(address)
            self.send(tar, 'HEL', '', address)
        elif cmd == 'TXT':
            print "%s says: %s" %(src, payload)

    def send_call(self, src, tar):
        logger.log("Sending CAL from %s to %s" %(src, tar))
        logger.log("Sending CAL from %s to %s" %(tar, src))
        payload = "%s=%s" % (tar, self.peers[tar]['address'])
        self.send(src, 'CAL', payload, self.peers[src]['address'])
        payload = "%s=%s" % (src, self.peers[src]['address'])
        self.send(tar, 'CAL', payload, self.peers[tar]['address'])

    def publish(self):
        for peer, peer_data in self.peers.items():
            if peer != self.name:
                self.send(peer, 'HEL', '', peer_data['address'])

    def sea(self, tar):
        for peer, peer_data in self.peers.items():
            self.send(peer, 'SEA', tar, peer_data['address'])

    def __init__(self, **kw):

        if kw.get('name'):
            self.name = kw['name']
        if kw.get('port'):
            self.port = kw['port']
        if kw.get('peer'):
            self.peer = kw['peer']

        self.fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fd.setblocking(0)
        if self.port:
            self.fd.bind(('0.0.0.0', self.port))

        self.init_peers()

        self.publish()

        self.rxthread = RXThread(self)
        self.rxthread.start()

    def run(self):

        self.running = True
        msg = 0

        ts = time.time()
        while self.running:

            if self.name != "matchmaker":
                if self.peer:
                    msg += 1
                    peer_data = self.peers.get(self.peer)
                    if not peer_data:
                        self.sea(self.peer)
                    else:
                        self.send(self.peer, 'TXT', 'Hello man %d' % msg, peer_data['address'])

                if time.time() - ts > 10:
                    ts = time.time()
                    self.publish()

            time.sleep(1)

    def stop(self):
        self.rxthread.stop()
        self.fd.close()
        self.running = False


def signal_handler(signal, frame):
    global app
    print('You pressed Ctrl+C!')
    app.stop()

if __name__ == "__main__":

    global app, logger

    name = sys.argv[1]
    port = None
    if name == 'matchmaker':
        port = 9999
        peer = None
    elif name == 'nodeA':
        peer = 'nodeB'
    elif name == 'nodeB':
        peer = None

    logger = Logger(name=name)
    app = App(name=name,
              peer=peer,
              port=port)

    signal.signal(signal.SIGINT, signal_handler)
    app.run()

    print "bye"

