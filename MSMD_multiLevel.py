# -*- coding: utf-8 -*-
"""
Created on Sat Feb 24 17:36:10 2018

@author: JohnPaul

@version: 1.2.6 - levels compound and are gated by a time limit. 
                    Each level must be completed in the proper time to move on.


Version History:
    1.2.5 - updated to chuck and russ' version - includes playing sound files (with fix)
    1.2.4 - updated to be compatible with all screen sizes
    1.2.3 - added multiple base station capability
    1.2.2 - added reference file creation tool
    1.2.1 - added game mode that changes the amount of time the robot can move instead of the robots speed
    1.2.0 - added config file. created option to upgrade robot after every hotspot or every level. Added refresh port button. Added different robot upgrade modes (selectable only in config file)
    1.1.1 - fixed left and right alt key bugs
    1.1.0 - Added keyboard input
    1.0.0 - Initial release (only includes mouse clicks)

"""

import sys
import os
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLineEdit, QFileDialog,
    QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QStackedLayout,
    QGraphicsScene, QGraphicsView, QDesktopWidget, QGraphicsEllipseItem,
    QGraphicsItem)
from PyQt5.QtGui import QIcon, QImage, QPixmap, QColor, QBrush, QPen
from PyQt5.QtCore import Qt, QRect, pyqtSignal, QThread
# this is the pyserial package (can be installed using pip)
import serial
import serial.tools.list_ports
import json
import configparser
import yaml  # this is the PyYaml package (install using pip)
from Settings import Settings
import pyautogui
import pyaudio
import wave


class GraphicsView(QGraphicsView):
    itemClickedEvent = pyqtSignal(QGraphicsItem, Qt.KeyboardModifiers, Qt.MouseButton)
    keyPressed = pyqtSignal(int, str, Qt.KeyboardModifiers)

    def __inti__(self, parent=None):
        super(GraphicsView, self).__init__(parent)

    def mousePressEvent(self, event):
        scenePosition = self.mapToScene(event.pos()).toPoint()
        itemClicked = self.itemAt(scenePosition)
        keyModifiers = event.modifiers()
        mouseButton = event.button()
        self.itemClickedEvent.emit(itemClicked, keyModifiers, mouseButton)

    def keyPressEvent(self, event):
        super(GraphicsView, self).keyPressEvent(event)
        # print(event)
        # print('key', event.key(), 'modifiers', event.modifiers(), 'nativeModifiers', event.nativeModifiers(), 'nativeScanCode', event.nativeScanCode(), 'nativeVirtualKey', event.nativeVirtualKey(), 'text', event.text())

        self.keyPressed.emit(event.nativeScanCode(), event.text(), event.modifiers())


class App(QWidget):
    cleanupEvent = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.versionNumber = '1.2.6'
        self.title = 'Monkey See Monkey Do   v'+self.versionNumber
        self.left = 10
        self.top = 80
        self.width = 640
        self.height = 100
        self.folderName = ''
        self.imageList = []
        self.numImages = 0
        self.currentImageNumber = 0
        self.currentTotalImageNumber = 0
        self.hotSpotFilename = 'hotspots.json'
        self.hotSpotFile = None
        self.hotSpotSize = 50
        self.currentHotSpot = None
        self.startTime = None
        self.endTime = None
        self.screen = QDesktopWidget().availableGeometry()
        print(self.screen)
        print('width', self.screen.width(), 'height', self.screen.height())
        self.initUI()

    def initUI(self):
        self.readConfig()

        self.portLabel = QLabel('Port(s): ', self)
        self.portDisplay = QLineEdit(self)
        self.portDisplay.setEnabled(False)
        self.portRefreshButton = QPushButton(self)
        self.portRefreshButton.setToolTip('Press to detect port of connected base station')
        self.portRefreshButton.clicked.connect(self.refreshPorts)
        self.portRefreshButton.setIcon(QIcon('refresh.png'))
        self.portRefreshButton.setFixedWidth(24)

        self.settingsButton = QPushButton()
        self.settingsButton.setToolTip('Open the Settings Dialog')
        self.settingsButton.setIcon(QIcon('settings.png'))
        self.settingsButton.setMaximumWidth(24)
        self.settingsButton.clicked.connect(self.openSettings)

        self.connected = False
        self.refreshPorts()
        if self.showReferenceCreator:
            self.referenceCreator = QPushButton('Create Reference', self)
            self.referenceCreator.setToolTip('Create a reference file from the selected image set')
            self.referenceCreator.clicked.connect(self.createReferenceFile)
            self.referenceCreator.setEnabled(False)

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
        self.hboxPort.addWidget(self.portRefreshButton)
        self.hboxPort.addWidget(self.settingsButton)

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
        if self.showReferenceCreator:
            self.vbox.addWidget(self.referenceCreator)
        self.vbox.addWidget(self.startLabel)
        self.vbox.addWidget(self.startButton)
        self.vbox.addStretch(4)

        self.startPage = QWidget()
        self.startPage.setLayout(self.vbox)

        self.scene = QGraphicsScene()
        self.graphicsView = GraphicsView(self.scene)
        self.graphicsView.itemClickedEvent.connect(self.hotSpotClickedHandler)
        self.graphicsView.keyPressed.connect(self.keyPressedHandler)

        self.graphicsLayout = QVBoxLayout()
        self.graphicsLayout.addWidget(self.graphicsView)
        self.graphicsLayout.setContentsMargins(0, 0, 0, 0)

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

    def readConfig(self):
        self.config = configparser.ConfigParser()
        fileCheck = self.config.read('config.ini')
        if(fileCheck == []):
            QMessageBox.critical(self, 'Config Error!', 'config.ini was not found', QMessageBox.Ok)
        self.robotSettings = self.config['robot']
        self.appSettings = self.config['app']

        # robot settings
        self.upgradeTrigger = self.robotSettings['upgradeTrigger']
        self.upgradeMode = self.robotSettings['upgradeMode']
        self.minPowerToMove = self.robotSettings['minPowerToMove']
        self.maxPowerToMove = self.robotSettings['maxPowerToMove']

        # app settings
        self.showReferenceCreator = int(self.appSettings.get('showReferenceCreator', '1'))
        self.timeLimitMultiplier = float(self.appSettings.get('time_limit_multiplier', '1'))
        self.levelToUnlock = int(self.appSettings.get('level_to_unlock', '0'))

    def writeConfig(self):
        self.robotSettings['upgradeTrigger'] = self.upgradeTrigger
        self.robotSettings['upgradeMode'] = self.upgradeMode
        self.robotSettings['minPowerToMove'] = self.minPowerToMove
        self.robotSettings['maxPowerToMove'] = self.maxPowerToMove

        self.appSettings['level_to_unlock'] = self.levelToUnlock
        with open('config.ini', 'w') as configFile:
            self.config.write(configFile)

    def openSettings(self):
        try:
            SettingsIn = {
                'upgradeTrigger': 'hotspot',
                'upgradeMode': 'left',
                'minPowerToMove': '80'}
            self.settingsWindow = Settings(self.robotSettings)
            self.settingsWindow.Closing.connect(self.settingsClosed)
            self.settingsWindow.show()
            self.setDisabled(True)
        except:
            print('ERROR - Setting.py Load Failed!')

    def settingsClosed(self, message):
        if(message == 'Abort'):
            print('Settigns Aborted!')
        elif(message == 'Closed'):
            print('Settings Closed!')
            # Set New Settings
            newSettings = self.settingsWindow.getSettings()
            self.upgradeTrigger = newSettings['upgradeTrigger']
            self.upgradeMode = newSettings['upgradeMode']
            self.minPowerToMove = newSettings['minPowerToMove']
            self.maxPowerToMove = newSettings['maxPowerToMove']
            self.writeConfig()
        else:
            print('ERROR - Unknown message returned from Settings.py Window!')
        self.setDisabled(False)

    def bringToFront(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()

    def refreshPorts(self):
        if(self.connected):
            for baseStation in self.robot:
                baseStation.close()
        comPorts = self.findPorts()
        if(comPorts):
            self.robot = []
            self.portDisplayText = ''
            for i, port in enumerate(comPorts):
                self.robot.append(serial.Serial(port))
                self.robot[i].baudrate = 115200
                self.robot[i].timeout = 0.05
                self.portDisplayText += (port + '  ')
            self.portDisplay.setText(self.portDisplayText)
            self.connected = True
        else:
            self.robot = []
            self.connected = False

    def folderButtonClicked(self):
        # get folder with content in it from user
        self.folderName = QFileDialog.getExistingDirectory(self, "Select Folder Location for Recorded Content")
        print(self.folderName)
        if os.path.isdir(self.folderName):  # If it is a valid folder
            self.numLevels = 0
            self.numTotalImages = 0
            self.listOfFilesInSelectedFolder = os.listdir(self.folderName)
            self.folderList = []
            self.folderListNameOnly = []
            for name in self.listOfFilesInSelectedFolder:
                fullFileName = os.path.join(self.folderName, name)
                if os.path.isdir(fullFileName):
                    result = self.loadLevel(fullFileName)  # load each level to make sure it is valid
                    if(result < 0):  # if the folder is not a valid level, quit this function
                        return
                    self.folderList.append(fullFileName)
                    self.folderListNameOnly.append(name)
                    self.numLevels += 1
                    self.numTotalImages += result
            self.folderListNameOnly = sorted(self.folderListNameOnly)  # sort the resulting list of level folders (they should be named in order they will be played in)
            if(self.numLevels > 0):
                # multiLevel game selected
                self.loadLevel(self.folderList[0])  # load the first level
                self.numLevelsDisplay.setText(str(self.numLevels))  # display the number of levels in the selected folder
            else:
                # single level selected
                result = self.loadLevel(self.folderName)  # try to load the single level selected
                if(result < 0):  # if level is invalid, quit this function
                    return
                self.numTotalImages = result
                self.numLevelsDisplay.setText('1')
            if(self.levelToUnlock>self.numLevels):
                if(self.numLevels == 0):
                    self.levelToUnlock = 0
                else:
                    self.levelToUnlock = self.numLevels-1
            self.currentLevel = 0
            self.numImagesDisplay.setText(str(self.numTotalImages))
            self.startButton.setEnabled(True)
            if self.showReferenceCreator:
                self.referenceCreator.setEnabled(True)
            self.selectedFolder.setText(self.folderName)
        else:
            QMessageBox.warning(self, 'Folder Error!', 'The folder does not exist!\nPlease select a valid folder', QMessageBox.Ok)

    def loadLevel(self, levelToLoad):
        try:
            print('Trying to load '+levelToLoad)
            self.hotSpotFile = open(levelToLoad+os.path.sep+self.hotSpotFilename, 'r')
            self.hotSpotDict = json.load(self.hotSpotFile)
            self.numHotSpotRecords = len(self.hotSpotDict)
            # self.hotSpotCsv = csv.reader(self.hotSpotFile)
            # next(self.hotSpotCsv)
            # self.numHotSpotRecords = sum(1 for row in self.hotSpotCsv)
            # self.hotSpotFile.seek(0)
            # next(self.hotSpotCsv) #skip column labels on first line
            self.hotSpotFile.close()
        except IOError:
            QMessageBox.critical(self, 'Error: No hotspots.json', 'hotspots.json does not exist\nA Hot Spot file is required to play the game. Please select a complete and valid content folder', QMessageBox.Ok)
            self.selectedFolder.setText('Error: No hotspots.json')
            return -1
        self.imageList = []
        try:
            for imageFile in os.listdir(levelToLoad):
                if(imageFile.endswith('.png')):
                    self.imageList.append(QImage(levelToLoad+os.path.sep+imageFile))
        except IOError:
            QMessageBox.critical(self, 'Error: images reading', 'Images could not be read\nPlease select a complete and valid content folder', QMessageBox.Ok)
            return -1
        self.numImages = len(self.imageList) - 1  # ??? why is this -1;  Starting image does not have a hotspot maybe? or ending image?
        if(self.numImages != self.numHotSpotRecords):
            QMessageBox.critical(self, 'Error: number of images in level "'+str(levelToLoad)+'" do not match the number of hot spot records', QMessageBox.Ok)
            return -1
        return self.numImages

    def startButtonClicked(self):
        print('start')
        self.stackedLayout.setCurrentIndex(1)
        self.paintImageIndex(0)
        self.showMaximized()

        if(self.upgradeTrigger == 'level'):
            self.setPower((int(self.minPowerToMove)*100)//255)

        self.startTime = time.time()

    def paintImageIndex(self, imageNumber):
        if(self.upgradeTrigger == 'hotspot'):
            powerLevel = (self.currentTotalImageNumber/(self.numTotalImages-1))*100
            print('power:', powerLevel, '  currentTotalImageNum:', self.currentTotalImageNumber, '  numTotalImages:', self.numTotalImages)
            self.setPower(powerLevel)
        self.scene.clear()
        print('current image number:', imageNumber)
        self.nextHotSpotInput = self.hotSpotDict[str(self.currentImageNumber).zfill(6)]
        print('nextHotSpotInput', self.nextHotSpotInput)
        self.currentPixmap = QPixmap.fromImage(self.imageList[imageNumber]).copy(QRect(0, 0, 1920, 1020)).scaled(self.screen.width(), self.screen.height(), aspectRatioMode=Qt.IgnoreAspectRatio)

        self.scene.addPixmap(self.currentPixmap)

        self.currentInputModifiers = self.simplifyModifierList(self.nextHotSpotInput['modifiers'])

        if(self.nextHotSpotInput['type'] == 'mouse'):
            commandString = ''
            if self.currentInputModifiers != []:
                commandString += 'Press '
            for mod in self.currentInputModifiers:
                commandString += mod + ' + '
            commandString += 'Click '
            self.currentMouseButton = self.nextHotSpotInput['button']
            if(self.currentMouseButton == 'right'):
                pen = QPen(QColor(0, 0, 255, 128))
                commandString += 'right mouse button'
            elif(self.currentMouseButton == 'left'):
                pen = QPen(QColor(255, 0, 0, 128))
                commandString += 'left mouse button'
            elif(self.currentMouseButton == 'middle'):
                pen = QPen(QColor(0, 255, 0, 128))
                commandString += 'scroll wheel (middle mouse button)'
            else:
                pen = QPen(QColor(0, 0, 0, 128))
            xScale = self.screen.width()/1920
            yScale = self.screen.height()/1020
            if(xScale > yScale):
                minScale = yScale
            else:
                minScale = xScale
            scaledHotSpotSize = self.hotSpotSize*minScale
            xPosition = self.nextHotSpotInput['position'][0]*xScale
            yPosition = self.nextHotSpotInput['position'][1]*yScale
            # adjust yPosition
            yPosition += 30
            brush = QBrush(QColor(180, 180, 180, 100))
            self.currentHotSpot = QGraphicsEllipseItem()
            self.currentHotSpot.setRect(xPosition-scaledHotSpotSize/2, yPosition-scaledHotSpotSize/2, scaledHotSpotSize, scaledHotSpotSize)
            self.currentHotSpot.setBrush(brush)
            self.currentHotSpot.setPen(pen)
            self.scene.addItem(self.currentHotSpot)
            self.currentInputKey = -1
        elif(self.nextHotSpotInput['type'] == 'key'):
            # print('key')
            self.currentInputKey = self.nextHotSpotInput['scancode']
            commandString = 'Press '
            for mod in self.currentInputModifiers:
                commandString += mod
                commandString += ' + '
            commandString += self.nextHotSpotInput['name']
            self.currentHotSpot = 'not a hotspot'
        else:
            QMessageBox.critical(self, 'Error: hotSpotInput type is incorrect. got: "'+self.nextHotSpotInput['type']+'"  expected: "key" or "mouse"', QMessageBox.Ok)

        self.setWindowTitle(self.title + '       ' + commandString)

    def playSound(self):

        class SoundThread(QThread):
            signal = pyqtSignal('PyQt_PyObject')

            def __init__(self, parent, soundFilename):
                super().__init__(parent)

                self.soundFilename = soundFilename

            def run(self):

                # define stream chunk
                chunk = 1024

                # open a wav format music
                f = wave.open(self.soundFilename, "rb")
                # instantiate PyAudio
                p = pyaudio.PyAudio()
                # open stream
                stream = p.open(format=p.get_format_from_width(f.getsampwidth()),
                                channels=f.getnchannels(),
                                rate=f.getframerate(),
                                output=True)
                # read data
                data = f.readframes(chunk)

                # play stream
                while data:
                    stream.write(data)
                    data = f.readframes(chunk)

                # stop stream
                stream.stop_stream()
                stream.close()

                # close PyAudio
                p.terminate()
                self.signal.emit(soundFilename)

        subFolder = ''
        if self.folderListNameOnly:
            subFolder = '%s%s' % (self.folderListNameOnly[self.currentLevel], os.path.sep)
        soundFilename = '%s%s%ssound%s.wav' % (self.folderName, os.path.sep, subFolder, self.currentImageNumber)

        if not os.path.isfile(soundFilename):
            return

        try:
            self.soundThread = SoundThread(self, soundFilename)
            self.soundThread.signal.connect(self.soundFinished)
            self.soundThread.start()
        except:
            print('something when wrong with the sound thread')
    def soundFinished(self, soundFile):
        # print(f'Finished playing {soundFile}')
        pass

    def hotSpotClickedHandler(self, itemClicked, modifiers, mouseButton):
        if itemClicked is self.currentHotSpot:
            if self.checkModifierMatch(modifiers):
                if self.checkButtonMatch(mouseButton):
                    # print('clicked on hot spot!')
                    self.playSound()
                    self.currentImageNumber += 1
                    self.currentTotalImageNumber += 1
                    if self.currentImageNumber >= self.numImages:
                        self.levelCompleted()
                    else:
                        self.paintImageIndex(self.currentImageNumber)
                else:
                    # print('wrong mouse button clicked')
                    pass
            else:
                # print("modifiers don't match")
                pass
        else:
            # print('wrong spot clicked')
            pass

    def checkButtonMatch(self, pressedMouseButton):
        if pressedMouseButton == Qt.LeftButton:
            pressedMouseButtonString = 'left'
        if pressedMouseButton == Qt.RightButton:
            pressedMouseButtonString = 'right'
        if pressedMouseButton == Qt.MiddleButton:
            pressedMouseButtonString = 'middle'

        return self.currentMouseButton == pressedMouseButtonString


    def keyPressedHandler(self, nativeScanCode, keyText, modifiers):
        if(nativeScanCode == self.currentInputKey) and self.checkModifierMatch(modifiers):
            # print('pressed correct key (or key combination)')
            self.playSound()
            self.currentImageNumber += 1
            self.currentTotalImageNumber += 1
            if self.currentImageNumber >= self.numImages:
                self.levelCompleted()
            else:
                self.paintImageIndex(self.currentImageNumber)
        else:
            # print('wrong key or key combination pressed')
            pass

    def checkModifierMatch(self, pressedModifiers):
        modifierTextList = []
        if(pressedModifiers & Qt.ShiftModifier):
            modifierTextList.append('shift')
        if(pressedModifiers & Qt.AltModifier):
            modifierTextList.append('alt')
        if(pressedModifiers & Qt.ControlModifier):
            modifierTextList.append('ctrl')
        if(pressedModifiers & Qt.MetaModifier):
            modifierTextList.append('win')

        return set(modifierTextList) == set(self.currentInputModifiers)

    def simplifyModifierList(self, modifierList):
        tempSet = set()
        for item in modifierList:
            if item == 'left shift':
                tempSet.add('shift')
            elif item == 'right shift':
                tempSet.add('shift')
            elif item == 'left ctrl':
                tempSet.add('ctrl')
            elif item == 'right ctrl':
                tempSet.add('ctrl')
            elif item == 'left alt':
                tempSet.add('alt')
            elif item == 'right alt':
                tempSet.add('alt')
            else:
                tempSet.add(item)
        return list(tempSet)

    def levelCompleted(self):
        self.levelTime = time.time()-self.startTime
        print('completed level: ', self.currentLevel+1)

        if(self.upgradeTrigger == 'level'):
            powerLevel = (self.currentLevel/(self.numLevels-1))*100
            self.setPower(powerLevel)

        timeToBeat = (self.currentTotalImageNumber)*self.timeLimitMultiplier
        if(self.currentLevel == self.levelToUnlock):
            print('unlockLevel?')
            # if the level was completed fast enough to move on
            if(self.levelTime <= timeToBeat):
                print('levelUnlocked')
                # (next level is all levels compounded...)
                # if the level completed was the last level
                if(self.currentLevel >= self.numLevels-1):
                    self.gameCompleted()
                else:
                    # move level to unlock up to next level
                    self.levelToUnlock += 1
                    # otherwise ask the user if they want to play the next
                    # level or quit
                    buttonReply = QMessageBox.question(
                        self,
                        'You Beat Level ' + str(self.currentLevel+1),
                        'You Beat the level!\nYou completed the level in ' + "%.2f" % self.levelTime + ' seconds out of ' + "%.2f" % timeToBeat + '\nPlay next level?',
                        QMessageBox.Yes | QMessageBox.Cancel)
                    if(buttonReply == QMessageBox.Cancel):
                        # quit game and go back to home screen
                        self.returnToHomeScreen()
                    else:
                        # restart (but with next level unlocked)
                        self.currentLevel = 0
                        self.currentImageNumber = 0
                        self.currentTotalImageNumber = 0
                        self.loadLevel(self.folderList[self.currentLevel])
                        self.paintImageIndex(0)
            else:
                print('levelFailed')
                # display dialog; complete in X time to advance to next level.  Replay?  Quit?
                buttonReply = QMessageBox.information(self, 'Too Slow...', 'You were not fast enough.\nYou completed the level in ' + "%.2f" % (self.levelTime) + ' seconds\nFinish in ' + "%.2f" % timeToBeat + ' seconds or less to move on.', QMessageBox.Ok | QMessageBox.Cancel)
                if(buttonReply == QMessageBox.Cancel):
                    # quit game and go back to home screen
                    self.returnToHomeScreen()
                else:
                    # restart
                    self.currentLevel = 0
                    self.currentImageNumber = 0
                    self.currentTotalImageNumber = 0
                    self.loadLevel(self.folderList[self.currentLevel])
                    self.paintImageIndex(0)
            self.startTime = time.time()
        else:
            # play next level
            self.currentLevel += 1
            self.currentImageNumber = 0
            self.loadLevel(self.folderList[self.currentLevel])
            self.paintImageIndex(0)

    def returnToHomeScreen(self):
        print('returning to home screen')
        self.setWindowTitle(self.title)
        self.scene.clear()
        self.currentHotSpot = None
        self.currentImageNumber = 0
        self.currentTotalImageNumber = 0
        self.stackedLayout.setCurrentIndex(0)
        self.showNormal()
        if(self.numLevels > 0):
            self.loadLevel(self.folderList[0])
        else:
            self.loadLevel(self.folderName)
        self.currentLevel = 0

    def gameCompleted(self):
        self.endTime = time.time()
        timeToBeat = (self.currentTotalImageNumber)*self.timeLimitMultiplier
        self.scene.clear()
        self.currentHotSpot = None
        self.currentImageNumber = 0
        self.currentTotalImageNumber = 0
        self.currentPixmap = None
        self.currentPixmap = QPixmap.fromImage(self.imageList[self.numImages]).copy(QRect(0, 0, 1920, 1020)).scaled(self.screen.width(), self.screen.height(), aspectRatioMode=Qt.IgnoreAspectRatio)
        self.scene.addPixmap(self.currentPixmap)
        buttonReply = QMessageBox.information(self, 'You Win!', 'Congradulations, You Won!\nYou completed the game in ' + "%.2f" % (self.endTime-self.startTime) + ' seconds out of ' "%.2f" % timeToBeat, QMessageBox.Ok)
        if buttonReply == QMessageBox.Ok:
            self.setWindowTitle(self.title)
            self.stackedLayout.setCurrentIndex(0)
            self.showNormal()
            if(self.numLevels > 0):
                self.loadLevel(self.folderList[0])
            else:
                self.loadLevel(self.folderName)
            self.currentLevel = 0

    def findPorts(self):
        ports = list(serial.tools.list_ports.comports())
        comPortsList = []
        # microcontrollerPort = None
        for port in ports:
            if 'Silicon Labs' in str(port[1]):
                comPortsList.append(port[0])
        return comPortsList

    def setPower(self, powerLevel):
        if(powerLevel > 100):
            raise ValueError('powerLevel cannot be set above 100')
        if(powerLevel < 0):
            raise ValueError('powerLevel cannot be set below 0')

        minPower = int(self.minPowerToMove)
        mode = self.upgradeMode
        leftPower = minPower
        rightPower = minPower
        maxPower = int(self.maxPowerToMove)
        if(mode == "left"):
            if(powerLevel <= 50):
                leftPower = self.interpolate(powerLevel, 0, 100, minPower, maxPower)
                rightPower = self.interpolate(powerLevel, 0, 50, minPower, maxPower)
            else:
                leftPower = self.interpolate(powerLevel, 0, 100, minPower, maxPower)
                rightPower = self.interpolate(powerLevel, 50, 100, minPower, maxPower)
        elif(mode == "right"):
            if(powerLevel <= 50):
                rightPower = self.interpolate(powerLevel, 0, 100, minPower, maxPower)
                leftPower = self.interpolate(powerLevel, 0, 50, minPower, maxPower)
            else:
                rightPower = self.interpolate(powerLevel, 0, 100, minPower, maxPower)
                leftPower = self.interpolate(powerLevel, 50, 100, minPower, maxPower)
        elif(mode == "both"):
            leftPower = self.interpolate(powerLevel, 0, 100, minPower, maxPower)
            rightPower = leftPower
        elif(mode == "distance"):
            # add fuel to the robot "tank"
            pass

        else:
            raise ValueError('upgradeMode in config.ini does not match any accepted value')

        iLP = int(leftPower)
        iRP = int(rightPower)

        # desiredPowerLevel -= 45
        if self.robot:
            print('connected to BaseStation, attempting to set power to', powerLevel, '   L:', leftPower, 'R:', rightPower)
            for baseStation in self.robot:
                baseStation.write(bytes([0, 0, iLP, iRP])+b'\n')
                baseStation.write(bytes([0, 0, iLP, iRP])+b'\n')
        else:
            print('BaseStation not connected, cannot change power level')

    def interpolate(self, inputValue, inputMin, inputMax, outputMin, outputMax):
        ratio = (inputValue - inputMin)/(inputMax - inputMin)
        outputValue = (outputMax - outputMin) * ratio + outputMin
        return outputValue

    def closeEvent(self, event):
        print('emitting cleanup event')
        try:
            self.settingsWindow.Abort()
        except:
            print('ERROR - Could not properly close settings window!')
        self.cleanupEvent.emit()

    def cleanupStuff(self):
        if self.robot:
            for baseStation in self.robot:
                baseStation.close()
        print('closing')

    def createReferenceFile(self):
        referenceFolder = QFileDialog.getExistingDirectory(self, "Select Folder Location for Reference")
        self.startTime = time.time()
        if os.path.isdir(referenceFolder):

            if(self.numLevels > 0):
                # multiLevel game selected
                print('multiLevelGame Reference started')
                for i in range(0, self.numLevels):
                    # create folder to hold level in reference file
                    levelFolderName = referenceFolder+os.path.sep+self.folderListNameOnly[i]
                    os.mkdir(levelFolderName)

                    self.loadLevel(self.folderList[i])
                    
                    # start msmd level
                    self.stackedLayout.setCurrentIndex(1)
                    self.showMaximized()
                    time.sleep(0.2)
                    
                    for j in range(0, self.numImages):
                        print('next image: '+str(j))
                        self.paintImageIndex(j)
                        QApplication.processEvents()
                        
                        time.sleep(0.05)
                        imageName = str(self.currentImageNumber).zfill(6)
                        pyautogui.screenshot(levelFolderName+os.path.sep+imageName+'.png')
                        
                        self.currentImageNumber += 1
                        self.currentTotalImageNumber += 1
                    
                    self.currentImageNumber = 0
            else:
                print('singleLevelGame Reference Started')
                self.loadLevel(self.folderName)
                self.stackedLayout.setCurrentIndex(1)
                self.showMaximized()
                
                for j in range(0, self.numImages):
                    print('next image: '+str(j))
                    self.paintImageIndex(j)
                    QApplication.processEvents()
                    
                    time.sleep(0.05)
                    imageName = str(self.currentImageNumber).zfill(6)
                    pyautogui.screenshot(levelFolderName+os.path.sep+imageName+'.png')
                    
                    self.currentImageNumber += 1
                    self.currentTotalImageNumber += 1
                    
                self.currentImageNumber = 0
            
            self.gameCompleted()
            

if __name__ == '__main__':
    app = 0
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
