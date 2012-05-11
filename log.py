import sys, os, logging
import vars as vars_


class RedoFormatter(logging.Formatter):

    def format(self, record):
        message = logging.Formatter.format(self, record)
        message = self._colorize(record.levelno, message)
        if vars_.DEBUG_PIDS:
            message = '%d ' % os.getpid() + message
        return message

    def _colorize(self, levelno, message):
        # Or rather don't colorize.
        return ''.join(["redo  ", vars_.DEPTH, message])


class ColorTermRedoFormatter(RedoFormatter):

    colors = {
        logging.INFO: "\x1b[32m", # Green.
        logging.ERROR: "\x1b[31m", # Red.
        logging.WARN: "\x1b[33m", # Yellow.
        }
    BOLD = "\x1b[1m"
    PLAIN = "\x1b[m"

    def _colorize(self, levelno, message):
        color = self.colors.get(levelno, '')
        return ''.join([color, "redo  ", vars_.DEPTH,
                        self.BOLD, message, self.PLAIN])


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
_handler = logging.StreamHandler()
_handler.setLevel(logging.DEBUG)
if sys.stderr.isatty() and (os.environ.get('TERM') or 'dumb') != 'dumb':
    _formatter = ColorTermRedoFormatter()
else:
    _formatter = RedoFormatter()
_handler.setFormatter(_formatter)
logger.addHandler(_handler)


def log(s, *args):
    logger.info(s.rstrip(), *args)

def log_(s, *args):
    logger.info(s.rstrip(), *args)

def err(s, *args):
    logger.error(s.rstrip(), *args)

def warn(s, *args):
    logger.warning(s.rstrip(), *args)


# TODO: Use custom logging levels.
def debug(s, *args):
    if vars_.DEBUG >= 1:
        logger.debug('-1- ' + s.rstrip(), *args)

def debug2(s, *args):
    if vars_.DEBUG >= 2:
        logger.debug('-2- ' + s.rstrip(), *args)

def debug3(s, *args):
    if vars_.DEBUG >= 3:
        logger.debug('-3- ' + s.rstrip(), *args)
