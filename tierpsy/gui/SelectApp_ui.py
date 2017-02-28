# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'SelectApp.ui'
#
# Created by: PyQt5 UI code generator 5.7.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_SelectApp(object):
    def setupUi(self, SelectApp):
        SelectApp.setObjectName("SelectApp")
        SelectApp.resize(304, 249)
        self.centralwidget = QtWidgets.QWidget(SelectApp)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.pushButton_paramGUI = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_paramGUI.setObjectName("pushButton_paramGUI")
        self.verticalLayout.addWidget(self.pushButton_paramGUI)
        self.pushButton_batchProcess = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_batchProcess.setObjectName("pushButton_batchProcess")
        self.verticalLayout.addWidget(self.pushButton_batchProcess)
        self.pushButton_MWViewer = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_MWViewer.setObjectName("pushButton_MWViewer")
        self.verticalLayout.addWidget(self.pushButton_MWViewer)
        self.pushButton_SWViewer = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_SWViewer.setObjectName("pushButton_SWViewer")
        self.verticalLayout.addWidget(self.pushButton_SWViewer)
        self.verticalLayout_2.addLayout(self.verticalLayout)
        SelectApp.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(SelectApp)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 304, 22))
        self.menubar.setObjectName("menubar")
        SelectApp.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(SelectApp)
        self.statusbar.setObjectName("statusbar")
        SelectApp.setStatusBar(self.statusbar)

        self.retranslateUi(SelectApp)
        QtCore.QMetaObject.connectSlotsByName(SelectApp)

    def retranslateUi(self, SelectApp):
        _translate = QtCore.QCoreApplication.translate
        SelectApp.setWindowTitle(_translate("SelectApp", "Select App"))
        self.pushButton_paramGUI.setText(_translate("SelectApp", "Set parameters / Process individual file"))
        self.pushButton_batchProcess.setText(_translate("SelectApp", "Batch processing multiple files"))
        self.pushButton_MWViewer.setText(_translate("SelectApp", "Multi-worm tracker viewer"))
        self.pushButton_SWViewer.setText(_translate("SelectApp", "Single-worm tracker viewer"))

