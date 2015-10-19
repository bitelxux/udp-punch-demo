#!/usr/bin/env python
# -*- coding: utf-8 -*-

import select
import time
import socket
import sys
import threading
import signal
import argparse

DEAD_MAN_TIME = 15

class Logger(object):
    def __init__(self, name):
        self.name = name

    def log(self, msg):
        print "[%s] %s" % (self.name, msg)

class RXThread(threading.Thread):

    running = False

    def __init__(self, context):
        self.context = context
        threading.Thread.__init__(self)

    def run(self):
        self.running = True

        while self.running:
            rx, _, _ = select.select([self.context.fd], [], [], 1)
            if rx:
                msg, address = self.context.fd.recvfrom(0xFFFF)
	        logger.log("RCV %s: %s" % (str(address), msg))

	        try:
	            self.context.attend(address, msg)
	        except:
	            # I do not want to manage the error in this demo
	            pass

    def stop(self):
        self.running = False


class App(object):

    peer = None
    peers = None
    fd = None
    port = None
    name = None
    running = False
    presenter = None

    def send(self, tar, cmd, payload, address):
        self.fd.sendto('%s:%s:%s:%s' % (self.name, tar, cmd, payload), address)

    def add_peer(self, peer, expires=DEAD_MAN_TIME):
        
        self.peers[peer[0]] = {}
        self.peers[peer[0]]['address'] = (peer[0], peer[1])
        self.peers[peer[0]]['expires'] = time.time() + expires

    def attend(self, address, msg):
        src, tar, cmd, payload = msg.split(':')
        self.peers.setdefault(src,{})
        self.peers[src]['address'] = address
        self.peers[src].setdefault('expires', time.time() + DEAD_MAN_TIME)
        if time.time() + DEAD_MAN_TIME > self.peers[src]['expires']:
            self.peers[src]['expires'] = time.time() + DEAD_MAN_TIME
        if cmd == 'SEA':
            logger.log("Received SEA from %s for %s" % (src, payload))
            if payload in self.peers and src in self.peers:
                self.send_call(src, payload)
        elif cmd == 'HEL':
            logger.log("Received HEL from %s at %s" % (src, str(address)))
        elif cmd == 'CAL':
            tar, address = payload.split("=")
            address = eval(address)
            self.send(tar, 'HEL', '', address)
        elif cmd == 'TXT':
            logger.log("%s says: %s" %(src, payload))
            #time.sleep(1)
	    #self.send(src, 'TXT', 'Got it !!', address)

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

        self.peers = dict()

        if kw.get('name'):
            self.name = kw['name']
        if kw.get('port'):
            self.port = kw['port']
        if kw.get('peer'):
            self.peer = kw['peer']
        if kw.get('presenter'):
            self.presenter = kw['presenter']

        self.fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fd.setblocking(0)
        if self.port:
            self.fd.bind(('0.0.0.0', self.port))

        if self.presenter:
            self.add_peer(self.presenter, expires=84600*365)

        self.publish()

        self.rxthread = RXThread(self)
        self.rxthread.start()

    def purge(self):
        for peer, peer_data in self.peers.items():
            if time.time() > peer_data['expires']:
                logger.log("Purging peer %s" % peer)
                del self.peers[peer]

    def run(self):

        self.running = True
        msg = 0

        dead_man_ts = time.time()
        purge_ts = time.time()
        while self.running:

            if time.time() - dead_man_ts > DEAD_MAN_TIME - 5:
                dead_man_ts = time.time()
                self.publish()

            if time.time() - purge_ts > DEAD_MAN_TIME:
             	purge_ts = time.time()
                self.purge()

            if self.peer:
                msg += 1
                peer_data = self.peers.get(self.peer)
                if not peer_data:
                    self.sea(self.peer)
                else:
                    self.send(self.peer, 'TXT', 'Hello man %d' % msg, peer_data['address'])

            time.sleep(1)

    def stop(self):
        self.rxthread.stop()
        self.fd.close()
        self.running = False


def signal_handler(signal, frame):
    global app
    print('You pressed Ctrl+C!')
    app.stop()

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("--presenter", help="Presenter")
    parser.add_argument("-u", "--uuid", help="UUID")
    parser.add_argument("--peer", help="peer")    
    return parser.parse_args()

if __name__ == "__main__":

    global app, logger
    args = parse_arguments()
    print args

    name = args.uuid
    peer = args.peer
    port = args.port and int(args.port) or None
    if args.presenter:
        presenter_ip, presenter_port = args.presenter.split(':')
        presenter_address = (presenter_ip, int(presenter_port))
    else:
        presenter_address = None

    logger = Logger(name=name)
    app = App(name=name,
              peer=peer,
              port=port,
              presenter=presenter_address)

    signal.signal(signal.SIGINT, signal_handler)
    app.run()

    print "bye"

