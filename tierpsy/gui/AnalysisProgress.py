
import sys
import traceback
import time
import os
import queue


from PyQt5.QtWidgets import QWidget, QApplication, QDialog, QVBoxLayout, \
    QProgressBar, QPushButton, QPlainTextEdit, QTextEdit, QMessageBox

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, Qt
from PyQt5.QtGui import QTextCursor


from tierpsy.gui.AnalysisProgress_ui import Ui_AnalysisProgress
from tierpsy.helper.runMultiCMD import GUI_CLEAR_SIGNAL


# based on http://stackoverflow.com/questions/21071448/redirecting-stdout-and-stderr-to-a-pyqt4-qtextedit-from-a-secondary-thread
# The new Stream Object which replaces the default stream associated with sys.stdout
# This object just puts data in a queue!

# A QObject (to be run in a QThread) which sits waiting for data to come through a Queue.Queue().
# It blocks until data is available, and one it has got something from the queue, it sends
# it to the "MainThread" by emitting a Qt Signal
class TxtReceiver(QThread):
    recieved = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        QObject.__init__(self, *args, **kwargs)
        self.queue = queue.Queue()
        self.is_running = True

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        pass

    @pyqtSlot()
    def run(self):
        while self.is_running:
            try:
                text = self.queue.get(timeout=1)
                self.recieved.emit(text)
                self.queue.task_done()
            except queue.Empty:
                # print('timeout')
                pass
        self.exit(0)

    def break_run(self):
        self.is_running = False


class WorkerFunQt(QThread):
    task_done = pyqtSignal()

    def __init__(self, worker_fun, worker_args, parent=None):
        super(WorkerFunQt, self).__init__(parent)
        self.worker_args = worker_args
        self.worker_fun = worker_fun

    @pyqtSlot()
    def run(self):
        try:
            self.worker_fun(**self.worker_args)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(
                exc_type,
                exc_value,
                exc_traceback,
                limit=2,
                file=sys.stdout)

        self.task_done.emit()
        self.exit(0)

# An Example application QWidget containing the textedit to redirect stdout to


class AnalysisProgress(QDialog):

    def __init__(self, process_thread):
        super(AnalysisProgress, self).__init__()
        self.ui = Ui_AnalysisProgress()
        self.ui.setupUi(self)
        self.ui.progressBar.setValue(0)

        self.setAttribute(Qt.WA_DeleteOnClose)

        self.process_thread = process_thread
        self.startRecieverThread()

        self.process_thread.task_done.connect(self.task_done)
        self.process_thread.task_done.connect(self.reciever.break_run)

        self.process_thread.start()

    def closeEvent(self, event):
        self.reciever.break_run()
        self.process_thread.terminate()
        self.reciever.terminate()
        sys.stdout = self.original_stdout
        super(AnalysisProgress, self).closeEvent(event)

    def task_done(self):
        sys.stdout = self.original_stdout
        self.ui.progressBar.setValue(100)

    def startRecieverThread(self):
        # redirect the stdout to reciever
        self.original_stdout = sys.stdout
        sys.stdout = self.reciever = TxtReceiver()
        self.reciever.recieved.connect(self.appendText)
        self.reciever.start()

    def appendText(self, text):
        # GUI CLEAR SIGNAL is a string that will be printed by runMultiCMD to
        # indicate a clear screen to this widget
        if text == GUI_CLEAR_SIGNAL:
            self.ui.textEdit.clear()
            return

        self.ui.textEdit.moveCursor(QTextCursor.End)
        self.ui.textEdit.insertPlainText(text)


def dumfun(N):
    for i in range(N):
        print(i)
    print(GUI_CLEAR_SIGNAL)
    for i in range(N):
        print(2 * i)
        time.sleep(1)
    raise


if __name__ == '__main__':
    from tierpsy.processing.trackSingleWorker import checkpoint

    compress_argvs = {
        'video_file': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/Capture_Ch1_18062015_140908.mjpg',
        'mask_dir': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/MaskedVideos',
        'json_file': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/Capture_Ch1_18062015_140908.json',
        }

    track_argvs = {
        'masked_image_file': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/MaskedVideos/Capture_Ch1_18062015_140908.hdf5',
        'results_dir': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/Results',
        'json_file': '/Users/ajaver/OneDrive - Imperial College London/tierpsy/Tests/test_1/RawVideos/Capture_Ch1_18062015_140908.json',
        'start_point': -1, 'end_point': checkpoint['END'],
        'use_manual_join': False, 'cmd_original': 'GUI'}

    # Create Queue and redirect sys.stdout to this queue

    # initialize the analysis thread
    worker_fun = WorkerFunQt(dumfun, {'N': 2})

    # Create QApplication and QWidget
    qapp = QApplication(sys.argv)
    app = AnalysisProgress(worker_fun)
    app.show()
    qapp.exec_()
