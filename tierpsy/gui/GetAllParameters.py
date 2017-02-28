import sys
import os
import json

from PyQt5.QtWidgets import QDialog, QApplication, QGridLayout, QLabel, \
    QSpinBox,  QDoubleSpinBox, QCheckBox, QPushButton, QLineEdit, QSizePolicy, \
    QMessageBox, QSpacerItem, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

from tierpsy.helper.tracker_param import tracker_param, param_help, dflt_param_list
from tierpsy.gui.HDF5VideoPlayer import lineEditDragDrop


def save_params_json(json_file, param4file):
    # save data into the json file
    with open(json_file, 'w') as fid:
        json.dump(param4file, fid, indent=4, sort_keys=True)

def _read_widget(widget):
    if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        return widget.value()
    elif isinstance(widget, QCheckBox):
        return widget.isChecked()
    elif isinstance(widget, QLineEdit):
        return widget.text()
    elif isinstance(widget, QGridLayout):
        return [widget.itemAt(ii).widget().value() for ii in range(widget.count())]
            
    else:
        raise('unknown type {}'.format(type(widget)))

class GetAllParameters(QDialog):
    file_saved = pyqtSignal(str)

    def __init__(self, param_file='', param_per_row=5):
        super(GetAllParameters, self).__init__()
        self.param_file = param_file
        self.param_per_row = param_per_row
        self.initUI()

        self.pushbutton_save.clicked.connect(self.saveParamFile)
        self.pushbutton_file.clicked.connect(self.getParamFile)

    def closeEvent(self, event):
        currentparams = self._readParams()
        if self.lastreadparams != currentparams:
            reply = QMessageBox.question(
                self,
                'Message',
                '''You select new parameters. Do you want to save them?''',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if reply == QMessageBox.Yes:
                if not self.saveParamFile():
                    return
        super(GetAllParameters, self).closeEvent(event)

    def initUI(self):
        grid = QGridLayout()
        self.setLayout(grid)

        def _ini_spinbox(name, value):
            spinbox = QSpinBox() if value_type is int else QDoubleSpinBox()
            spinbox.setMinimum(int(-1e10))
            spinbox.setMaximum(int(1e10))
            spinbox.setValue(value)
            return spinbox

        self.widgetlabels = {}
        for ii, (name, value, info) in enumerate(dflt_param_list):
            row = ii // self.param_per_row * 2
            col = (ii % self.param_per_row)

            value_type = type(value)
            if value_type is bool:
                checkbox = QCheckBox(name)
                checkbox.setChecked(value)
                grid.addWidget(checkbox, row, col, 2, 1)
                self.widgetlabels[name] = checkbox
            else:
                label = QLabel(name)
                label.setWhatsThis(info)
                grid.addWidget(label, row, col, 1, 1)
                
                if value_type is int or value_type is float:
                    spinbox = _ini_spinbox(name, value)
                    grid.addWidget(spinbox, row+1, col, 1, 1)
                    self.widgetlabels[name] = spinbox
                    
                elif value_type is str:
                    lineedit = QLineEdit(value)
                    grid.addWidget(lineedit, row + 1, col, 1, 1)
                    self.widgetlabels[name] = lineedit
                
                elif value_type is list or value_type is tuple:
                    grid_loc = QGridLayout()
                    grid.addLayout(grid_loc, row + 1, col, 1, 1)
                    
                    for icol, val in enumerate(value):
                        spinbox = _ini_spinbox(name, val)
                        grid_loc.addWidget(spinbox, row, icol, 1, 1)
                    
                    self.widgetlabels[name] = grid_loc
        assert all(x for x in self.widgetlabels)

        spacer = QSpacerItem(
            40,
            20,
            QSizePolicy.Preferred,
            QSizePolicy.Preferred)

        self.pushbutton_save = QPushButton('Save')
        self.pushbutton_file = QPushButton('Select File')
        self.lineEdit_file = QLineEdit(self.param_file)

        last_row = len(dflt_param_list) // self.param_per_row * 2 + 3
        last_col = max(self.param_per_row - 1, 3)
        grid.addWidget(self.pushbutton_save, last_row, 0, 1, 1)
        grid.addWidget(self.pushbutton_file, last_row, last_col, 1, 1)
        grid.addWidget(self.lineEdit_file, last_row, 1, 1, last_col - 1)
        grid.addItem(spacer, last_row - 1, 0, 1, 1)

        lineEditDragDrop(
            self.lineEdit_file,
            self.updateParamFile,
            os.path.isfile)

        # used to find if anything was modified.
        self.lastreadparams = self._readParams()

        self.show()
        self.setAttribute(Qt.WA_DeleteOnClose)

    # file dialog to the the hdf5 file
    def getParamFile(self):
        json_file, _ = QFileDialog.getOpenFileName(
            self, "Find parameters file", '', "JSON files (*.json);; All (*)")
        if json_file:
            self.updateParamFile(json_file)

    def updateParamFile(self, json_file):
        # set the widgets with the default parameters, in case the parameters are not given
        # by the json file.
        if os.path.exists(json_file):
            try:
                params = tracker_param(json_file)
                json_param = params.input_param

            except (OSError, UnicodeDecodeError, json.decoder.JSONDecodeError):
                QMessageBox.critical(
                    self,
                    'Cannot read parameters file.',
                    "Cannot read parameters file. Try another file",
                    QMessageBox.Ok)
                return
        else:
            json_param = {}

        for param_name in json_param:
            if param_name not in self.widgetlabels:
                QMessageBox.critical(
                    self, '', "'%s' is not a valid variable. Please correct the parameters file" %
                    param_name, QMessageBox.Ok)
                return

        # Set the parameters in the correct widget. Any paramter not contained
        # in the json file will be keep with the default value.
        for name in self.widgetlabels:
            widget = self.widgetlabels[name]
            value = json_param[
                name] if name in json_param else default_param[name]

            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
            elif isinstance(widget, QGridLayout):
                for ii, val in enumerate(value):
                    widget.itemAt(ii).widget().setValue(val)
            else:
                raise('unknown type {}'.format(type(widget)))

        self.lineEdit_file.setText(json_file)
        # used to find if anything was modified.
        self.lastreadparams = self._readParams()

    def _readParams(self):
        # read all the values in the GUI
        parameters = {}
        for name in self.widgetlabels:
            widget = self.widgetlabels[name]
            parameters[name] = _read_widget(widget)
        return parameters

    @pyqtSlot()
    def saveParamFile(self):
        json_file = self.lineEdit_file.text()
        print(json_file)
        if not json_file:
            QMessageBox.critical(
                self,
                'No parameter file name given.',
                'No parameter file name given. Please select name using the "Parameters File" button',
                QMessageBox.Ok)
            return 0

        if os.path.exists(json_file):

            reply = QMessageBox.question(
                self,
                'Message',
                '''The parameters file already exists. Do you want to overwrite it?''',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)

            if reply == QMessageBox.No:
                return 0

        # read all the values in the GUI
        param4file = self._readParams()
        self.lastreadparams = param4file
        save_params_json(json_file, param4file)

        self.file_saved.emit(json_file)
        return 1


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GetAllParameters()
    sys.exit(app.exec_())
