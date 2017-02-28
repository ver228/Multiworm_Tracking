import shutil
import sys
import os
import tables
import warnings
from MWTracker import AUX_FILES_DIR

from threading import Thread
from queue import Queue, Empty


WLAB = {'U': 0, 'WORM': 1, 'WORMS': 2, 'BAD': 3, 'GOOD_SKE': 4}

# pytables filters.
TABLE_FILTERS = tables.Filters(
        complevel=5,
        complib='zlib',
        shuffle=True,
        fletcher32=True)

def print_flush(msg):
    print(msg)
    sys.stdout.flush()


class ReadEnqueue():
    def __init__(self, pipe, timeout=-1):
        def _target_fun(out, queue):
            for line in iter(out.readline, b''):
                queue.put(line)
            out.close

        self.timeout = timeout
        self.queue = Queue()
        self.thread = Thread( target=_target_fun, args=(pipe, self.queue))
        self.thread.start()

    def read(self):
        try:
            if self.timeout > 0:
                line = self.queue.get(timeout=self.timeout)
            else:
                line = self.queue.get_nowait()
            line = line.decode("utf-8")
        except Empty:
            line  = None
        return line


# get the correct path for ffmpeg. First we look in the aux
# directory, otherwise we look in the system path.
def get_local_or_sys_path(file_name):
    file_source = os.path.join(AUX_FILES_DIR, file_name)
    if not os.path.exists(file_source):
        file_source = shutil.which(file_name)

    if not file_source:
        raise FileNotFoundError('command not found: %s' % file_name)
    return file_source


try:
    if sys.platform == 'win32':
        FFMPEG_CMD = get_local_or_sys_path('ffmpeg.exe')
    elif sys.platform == 'darwin':
        FFMPEG_CMD = get_local_or_sys_path('ffmpeg22')
    elif sys.platform == 'linux':
        FFMPEG_CMD = get_local_or_sys_path('ffmpeg')
except FileNotFoundError:
    FFMPEG_CMD = ''
    warnings.warn('ffmpeg do not found. This might cause problems while reading .mjpeg files.')

# get the correct path for ffprobe. First we look in the aux
    # directory, otherwise we look in the system path.
try:
    if os.name == 'nt':
        FFPROBE_CMD = get_local_or_sys_path('ffprobe.exe')
    else:
        FFPROBE_CMD = get_local_or_sys_path('ffprobe')
except FileNotFoundError: 
    FFPROBE_CMD = ''
    warnings.warn('ffprobe do not found. This might cause problems while extracting the raw videos timestamps.')
