# -*- coding: utf-8 -*-
"""
Created on Sat Feb 24 17:36:10 2018

@author: JohnPaul

@version: 1.0.0

"""

import sys
import os
import csv
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QLineEdit, QFileDialog,
QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QStackedLayout,
QGraphicsScene, QGraphicsView, QDesktopWidget, QGraphicsEllipseItem,
QGraphicsItem)
from PyQt5.QtGui import QIcon, QImage, QPixmap, QColor, QBrush, QPen
from PyQt5.QtCore import Qt, QRect, pyqtSignal
#this is the pyserial package (can be installed using pip)
import serial
import serial.tools.list_ports

class GraphicsView(QGraphicsView):
    itemClickedEvent = pyqtSignal(QGraphicsItem)
    
    def __inti__(self, parent=None):
        super(GraphicsView, self).__init__(parent)
        
    def mousePressEvent(self, event):
        scenePosition = self.mapToScene(event.pos()).toPoint()
        itemClicked = self.itemAt(scenePosition)
        self.itemClickedEvent.emit(itemClicked)

class App(QWidget):
    cleanupEvent = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.versionNumber = '1.0.0'
        self.title = 'Monkey See Monkey Do   v'+self.versionNumber
        self.left = 10
        self.top = 80
        self.width = 640
        self.height = 100
        self.folderName = ''
        self.imageList = []
        self.numImages = 0
        self.currentImageNumber = 0
        self.hotSpotFilename = 'hotspots.csv'
        self.hotSpotFile = None
        self.hotSpotSize = 50
        self.currentHotSpot = None
        self.startTime = None
        self.endTime = None
        self.screen = QDesktopWidget().screenGeometry()
        self.initUI()
 
    def initUI(self):
        self.portLabel = QLabel('Port: ', self)
        self.portDisplay = QLineEdit(self)
        self.portDisplay.setEnabled(False)
        
        comPort = self.findPort()
        if(comPort is not None):
            self.robot = serial.Serial(comPort)
            self.robot.baudrate = 115200
            self.robot.timeout = 0.05
            self.portDisplay.setText(comPort)
            self.connected = True
        else:
            self.robot = None
            self.connected = False
        
        self.folderButton = QPushButton('Select Folder', self)
        self.folderButton.setToolTip('Select the folder that contains the content you would like to play')
        self.folderButton.clicked.connect(self.folderButtonClicked)
        
        self.folderLabel = QLabel('Selected Folder:', self)
        
        self.selectedFolder = QLineEdit(self)
        self.selectedFolder.setEnabled(False)
        
        self.numLevelsLabel = QLabel('Number of Levels:', self)
        self.numLevelsDisplay = QLineEdit(self)
        self.numLevelsDisplay.setEnabled(False)
        
        self.numImagesLabel = QLabel('Number of Images:', self)
        self.numImagesDisplay = QLineEdit(self)
        self.numImagesDisplay.setEnabled(False)
        
        self.startLabel = QLabel('Press "Start" to begin game', self)
        
        self.startButton = QPushButton('Start', self)
        self.startButton.setToolTip('Start Game')
        self.startButton.clicked.connect(self.startButtonClicked)
        self.startButton.setEnabled(False)
        
        self.hboxPort = QHBoxLayout()
        self.hboxPort.addWidget(self.portLabel)
        self.hboxPort.addWidget(self.portDisplay)

        self.hbox = QHBoxLayout()
        self.hbox.addWidget(self.folderLabel)
        self.hbox.addWidget(self.selectedFolder)
        
        self.hboxNumLevels = QHBoxLayout()
        self.hboxNumLevels.addWidget(self.numLevelsLabel)
        self.hboxNumLevels.addWidget(self.numLevelsDisplay)
        
        self.hboxNumImages = QHBoxLayout()
        self.hboxNumImages.addWidget(self.numImagesLabel)
        self.hboxNumImages.addWidget(self.numImagesDisplay)
        
        self.vbox = QVBoxLayout()
        self.vbox.addLayout(self.hboxPort)
        self.vbox.addWidget(self.folderButton)
        self.vbox.addLayout(self.hbox)
        self.vbox.addLayout(self.hboxNumLevels)
        self.vbox.addLayout(self.hboxNumImages)
        self.vbox.addWidget(self.startLabel)
        self.vbox.addWidget(self.startButton)
        self.vbox.addStretch(4)
        
        self.startPage = QWidget()
        self.startPage.setLayout(self.vbox)
        
        self.scene = QGraphicsScene()
        self.graphicsView = GraphicsView(self.scene)
        self.graphicsView.itemClickedEvent.connect(self.hotSpotClickedHandler)
        
        self.graphicsLayout = QVBoxLayout()
        self.graphicsLayout.addWidget(self.graphicsView)
        self.graphicsLayout.setContentsMargins(0,0,0,0)
        
        self.gamePage = QWidget()
        self.gamePage.setLayout(self.graphicsLayout)
        
        self.stackedLayout = QStackedLayout()
        self.stackedLayout.addWidget(self.startPage)
        self.stackedLayout.addWidget(self.gamePage)
        self.stackedLayout.setCurrentIndex(0)
        
        self.setLayout(self.stackedLayout)
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowIcon(QIcon('MSMD32.png'))
        self.cleanupEvent.connect(self.cleanupStuff)
        self.show()
        self.bringToFront()
    
    def bringToFront(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()
        
    def folderButtonClicked(self):
        self.folderName = QFileDialog.getExistingDirectory(self, "Select Folder Location for Recorded Content")
        print(self.folderName)
        if os.path.isdir(self.folderName):
            self.numLevels = 0
            self.numTotalImages = 0
            self.listOfFilesInSelectedFolder = os.listdir(self.folderName)
            self.folderList = []
            for name in self.listOfFilesInSelectedFolder:
                fullFileName = os.path.join(self.folderName, name)
                if os.path.isdir(fullFileName):
                    result = self.loadLevel(fullFileName)
                    if(result<0):
                        return
                    self.folderList.append(fullFileName)
                    self.numLevels += 1
                    self.numTotalImages += result

            if(self.numLevels>0):
                #multiLevel game selected
                self.loadLevel(self.folderList[0])
                self.numLevelsDisplay.setText(str(self.numLevels))
            else:
                result = self.loadLevel(self.folderName)
                if(result<0):
                    return
                self.numTotalImages = result
                self.numLevelsDisplay.setText('1')
            
            self.currentLevel = 0
            self.numImagesDisplay.setText(str(self.numTotalImages))
            self.startButton.setEnabled(True)
            self.selectedFolder.setText(self.folderName)
        else:
            QMessageBox.warning(self, 'Folder Error!', 'The folder does not exist!\nPlease select a valid folder', QMessageBox.Ok)
        
    def loadLevel(self, levelToLoad):
        try:
                self.hotSpotFile = open(levelToLoad+os.path.sep+self.hotSpotFilename, 'r')
                self.hotSpotCsv = csv.reader(self.hotSpotFile)
                next(self.hotSpotCsv)
                self.numHotSpotRecords = sum(1 for row in self.hotSpotCsv)
                self.hotSpotFile.seek(0)
                next(self.hotSpotCsv) #skip column labels on first line
        except IOError:
            QMessageBox.critical(self, 'Error: No hotspots.csv', 'hotspots.csv does not exist\nA Hot Spot file is required to play the game. Please select a complete and valid content folder', QMessageBox.Ok)
            self.selectedFolder.setText('Error: No hotspots.csv')
            return -1
        self.imageList = []
        try:
            for imageFile in os.listdir(levelToLoad):
                if(imageFile.endswith('.png')):
                    self.imageList.append(QImage(levelToLoad+os.path.sep+imageFile))
        except IOError:
            QMessageBox.critical(self, 'Error: images reading', 'Images could not be read\nPlease select a complete and valid content folder', QMessageBox.Ok)
            return -1
        self.numImages = len(self.imageList)
        if(self.numImages != self.numHotSpotRecords):
            QMessageBox.critical(self, 'Error: number of images in level "'+str(levelToLoad)+'" do not match the number of hot spot records', QMessageBox.Ok)
            return -1
        return self.numImages

    def startButtonClicked(self):
        print('start')
        self.stackedLayout.setCurrentIndex(1)
        self.paintImageIndex(0)
        self.showMaximized()
        self.setPower(125)
        self.startTime = time.time()
        
    def paintImageIndex(self, imageNumber):
        self.scene.clear()
        hotSpotLine = next(self.hotSpotCsv)
        self.currentPixmap = QPixmap.fromImage(self.imageList[imageNumber]).copy(QRect(0,0,1920,1020))
        
        self.scene.addPixmap(self.currentPixmap)
        
        brush = QBrush(QColor(180, 180, 180, 100))
        pen = QPen(QColor(255,0,0,128))
        self.currentHotSpot = QGraphicsEllipseItem()
        self.currentHotSpot.setRect(int(hotSpotLine[1])-self.hotSpotSize//2, int(hotSpotLine[2])-self.hotSpotSize//2, self.hotSpotSize, self.hotSpotSize)
        self.currentHotSpot.setBrush(brush)
        self.currentHotSpot.setPen(pen)
        self.scene.addItem(self.currentHotSpot)
        
    def hotSpotClickedHandler(self, itemClicked):
        if itemClicked is self.currentHotSpot:
            print('clicked on hot spot!')
            self.currentImageNumber += 1
            if self.currentImageNumber >= self.numImages:
                self.levelCompleted()
            else:
                self.paintImageIndex(self.currentImageNumber)
        else:
            print('wrong spot clicked')
    
    def levelCompleted(self):
        print('completed level: ', self.currentLevel+1)
        powerLevel = (((self.currentLevel+1)*127)//(self.numLevels+1))+127
        self.setPower(powerLevel)

        self.currentLevel += 1
        if(self.currentLevel>=self.numLevels):
            self.gameCompleted()
        else:
            self.currentImageNumber = 0
            self.loadLevel(self.folderList[self.currentLevel])
            self.paintImageIndex(0)
    
    def gameCompleted(self):
        self.endTime = time.time()
        self.scene.clear()
        self.currentHotSpot = None
        self.currentImageNumber = 0
        self.currentPixmap = None
        buttonReply = QMessageBox.information(self, 'You Win!', 'Congradulations, You Won!\nYou completed the game in ' + str(self.endTime-self.startTime) + 'seconds', QMessageBox.Ok | QMessageBox.Close)
        if buttonReply == QMessageBox.Ok:
            self.stackedLayout.setCurrentIndex(0)
            self.showNormal()
            if(self.numLevels>0):
                self.loadLevel(self.folderList[0])
            else:
                self.loadLevel(self.folderName)
            self.currentLevel = 0
    
    def findPort(self):
        ports = list(serial.tools.list_ports.comports())
        #microcontrollerPort = None
        for port in ports:
            if 'Silicon Labs' in str(port[1]):
                return port[0]
        return None
    
    def setPower(self, desiredPowerLevel):
        if(desiredPowerLevel>255):
            raise ValueError('Power level cannot be set above 255')
        if(desiredPowerLevel<0):
            raise ValueError('Power level cannot be set below 0')
        desiredPowerLevel = desiredPowerLevel-45
        if(self.robot is not None):
            print('connected to BaseStation, attempting to set power to ', desiredPowerLevel)
            self.robot.write(bytes([0,0,desiredPowerLevel])+b'\n')
            self.robot.write(bytes([0,0,desiredPowerLevel])+b'\n')
        else:
            print('BaseStation not connected, cannot change power level')
    
    def closeEvent(self, event):
        print('emitting cleanup event')
        self.cleanupEvent.emit()
    
    def cleanupStuff(self):
        if self.robot is not None:
            self.robot.close()
        print('closing')
            
        
if __name__ == '__main__':
    app = 0
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
