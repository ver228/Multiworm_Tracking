# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'AnalysisProgress.ui'
#
# Created by: PyQt5 UI code generator 5.7.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_AnalysisProgress(object):
    def setupUi(self, AnalysisProgress):
        AnalysisProgress.setObjectName("AnalysisProgress")
        AnalysisProgress.resize(594, 465)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(AnalysisProgress)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.progressBar = QtWidgets.QProgressBar(AnalysisProgress)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setInvertedAppearance(False)
        self.progressBar.setObjectName("progressBar")
        self.verticalLayout.addWidget(self.progressBar)
        self.textEdit = QtWidgets.QTextEdit(AnalysisProgress)
        self.textEdit.setReadOnly(True)
        self.textEdit.setObjectName("textEdit")
        self.verticalLayout.addWidget(self.textEdit)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(AnalysisProgress)
        QtCore.QMetaObject.connectSlotsByName(AnalysisProgress)

    def retranslateUi(self, AnalysisProgress):
        _translate = QtCore.QCoreApplication.translate
        AnalysisProgress.setWindowTitle(_translate("AnalysisProgress", "Analysis Progress"))

