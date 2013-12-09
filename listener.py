#!/usr/bin/env python
#
# ----------------------------------------------------------------
# The contents of this file are distributed under the CC0 license.
# See http://creativecommons.org/publicdomain/zero/1.0/
# ----------------------------------------------------------------

from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.web import client
from twisted.python import usage

from ConfigParser import SafeConfigParser
import logging
import sys

class ListernerOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b',57600, 'Serial baudrate'],
        ['port', 'p', '/dev/ttyACM0', 'Serial port to use'],
        ]

class Echo(LineReceiver):

    api_key = None

    def read_config(self):
        c = SafeConfigParser()
        c.read('config.ini')
        self.api_key = c.get('safecast', 'api_key')

    def update_safecast(self, date, lon, lat, cpm):
        if not self.api_key:
            self.read_config()

        safecastJSON = """{"captured_at":"%s","longitude":"%f","latitude":"%f","value":"%s","unit":"cpm"}"""
        url = 'http://api.safecast.org/measurements.json?api_key=%s' % self.api_key
        data_str = safecastJSON % (date, lon, lat, cpm)

        headers = {}
        headers['Content-Length'] = str(len(data_str))

        d = client.getPage(url, method='POST', postdata=data_str, headers=headers)
        d.addCallback(lambda _: logging.debug('Safecast updated ok'))
        d.addErrback(lambda _: logging.error('Error posting to Safecast'))

    def processData(self, data):
      try:
        # Nano log sample
        # $BNRDD,2023,2013-11-01T23:51:55Z,45,2,138,A,3729.6509,N,13956.5519,E,256.40,A,5,300*7D
        nanoDate = data[2]
        nanoCPM = data[3]

        # Convert from GPS format (DDDMM.MMMM..) to decimal degrees
        nanoLat = abs(float(data[7]))/100
        nanoLon = abs(float(data[9]))/100
        nanoLon = ((nanoLon-int(nanoLon))/60)*100+int(nanoLon)
        nanoLat = ((nanoLat-int(nanoLat))/60)*100+int(nanoLat)
        if "S" == data[8]: nanoLat = -nanoLat
        if "W" == data[10]: nanoLon = -nanoLon

        logging.info('Nano: Date: %s CPM: %s Latitude: %f Longitude: %f'
            % (nanoDate, nanoCPM, nanoLat, nanoLon))

        self.update_safecast(nanoDate, nanoLat, nanoLon, nanoCPM)
      except:
        logging.info('Failed to unpack the data!')

    def connectionMade(self):
        logging.info('Serial connection made!')

    def lineReceived(self, line):
        logging.debug('Line: "%s"' % line);

        try:
            data = line.split(",");
        except:
            logging.info('Failed to load data')
            return

        self.processData(data)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, \
                format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

    o = ListernerOptions()
    try:
        o.parseOptions()
    except usage.UsageError, errortext:
        logging.error('%s %s' % (sys.argv[0], errortext))
        logging.info('Try %s --help for usage details' % sys.argv[0])
        raise SystemExit, 1

    if o.opts['baudrate']:
        baudrate = int(o.opts['baudrate'])

    port = o.opts['port']

    logging.debug('About to open port %s' % port)
    s = SerialPort(Echo(), port, reactor, baudrate=baudrate)

    reactor.run()
