import datetime
import J2534
import sys

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.terminal.flush()
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def dtn():
    return str(datetime.datetime.now())

showErr = True  # Show debug info
logfile = 'logs\\' + dtn().replace(':', '_')[:-3] + ' E38-KEYFCKR.log'

sys.stdout = Logger(logfile)
J2534.SetErrorLog(showErr)