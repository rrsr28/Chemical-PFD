import os
import sys
import os
from PyQt5.QtSvg import QSvgGenerator
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QSize, QPoint, QRectF
from PyQt5.QtGui import QBrush, QColor, QImage, QPainter, QPalette, QPen, QKeySequence
from PyQt5.QtWidgets import (QComboBox, QMessageBox, QFileDialog, QFormLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QMainWindow, QMenu,
                             QPushButton, QWidget, QMdiArea, QSplitter, QGraphicsItem)

from utils.canvas import canvas
from utils.fileWindow import FileWindow
from utils.data import ppiList, sheetDimensionList
from utils import dialogs
from utils.toolbar import toolbar
from utils.app import app, settings, load

import shapes

class appWindow(QMainWindow):
    """
    Application entry point, subclasses QMainWindow and implements the main widget,
    sets necessary window behaviour etc.
    """
    def __init__(self, parent=None):
        super(appWindow, self).__init__(parent)
        
        #create the menu bar
        self.createMenuBar()

        #used for file name
        self.counterr = 0

        self.mdi = QMdiArea(self) #create area for files to be displayed
        self.mdi.setObjectName('mdi area')
        
        #create toolbar and add the toolbar plus mdi to layout
        self.createToolbar()
        
        #set flags so that window doesnt look weird
        self.mdi.setOption(QMdiArea.DontMaximizeSubWindowOnActivation, True) 
        self.mdi.setTabsClosable(True)
        self.mdi.setTabsMovable(True)
        self.mdi.setDocumentMode(False)
        
        #declare main window layout
        self.setCentralWidget(self.mdi)
        # self.resize(1280, 720) #set collapse dim
        self.mdi.subWindowActivated.connect(self.tabSwitched)
        self.readSettings()
    
    def createMenuBar(self):
        # Fetches a reference to the menu bar in the main window, and adds actions to it.

        titleMenu = self.menuBar() #fetch reference to current menu bar
        
        self.menuFile = titleMenu.addMenu('File') #File Menu
        newAction = self.menuFile.addAction("New", self.newProject)
        openAction = self.menuFile.addAction("Open", self.openProject)
        saveAction = self.menuFile.addAction("Save", self.saveProject)
        
        newAction.setShortcut(QKeySequence.New)
        openAction.setShortcut(QKeySequence.Open)
        saveAction.setShortcut(QKeySequence.Save)
        
        self.menuEdit = titleMenu.addMenu('Edit')
        undoAction = self.undo = self.menuEdit.addAction("Undo", lambda x=self: x.activeScene.painter.undoAction.trigger())
        redoAction = self.redo = self.menuEdit.addAction("Redo", lambda x=self: x.activeScene.painter.redoAction.trigger())
        
        undoAction.setShortcut(QKeySequence.Undo)
        redoAction.setShortcut(QKeySequence.Redo)
        
        self.menuEdit.addAction("Show Undo Stack", lambda x=self: x.activeScene.painter.createUndoView(self) )
        self.menuEdit.addSeparator()
        self.menuEdit.addAction("Add new symbols", self.addSymbolWindow)
        
        self.menuGenerate = titleMenu.addMenu('Export') #Export menu
        imageAction = self.menuGenerate.addAction("Image", self.saveImage)
        reportAction = self.menuGenerate.addAction("Report", self.generateReport)
        
        imageAction.setShortcut(QKeySequence("Ctrl+P"))
        reportAction.setShortcut(QKeySequence("Ctrl+R"))
            
    def createToolbar(self):
        #place holder for toolbar with fixed width, layout may change
        self.toolbar = toolbar(self)
        self.toolbar.setObjectName("Toolbar")
        # self.addToolBar(Qt.LeftToolBarArea, self.toolbar)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbar)
        self.toolbar.toolbuttonClicked.connect(self.toolButtonClicked)
        self.toolbar.populateToolbar()
        
    def toolButtonClicked(self, object):
        # To add the corresponding symbol for the clicked button to active scene.
        if self.mdi.currentSubWindow():
            currentDiagram = self.mdi.currentSubWindow().tabber.currentWidget().painter
            if currentDiagram:
                graphic = getattr(shapes, object['object'])(*map(lambda x: int(x) if x.isdigit() else x, object['args']))
                graphic.setPos(50, 50)
                currentDiagram.addItemPlus(graphic) 
    
    def addSymbolWindow(self):
        # Opens the add symbol window when requested
        from utils.custom import ShapeDialog
        ShapeDialog(self).exec()
        
    def newProject(self):
        #call to create a new file inside mdi area
        project = FileWindow(self.mdi)
        project.setObjectName("New Project")
        project.setWindowFlags(Qt.FramelessWindowHint)
        self.mdi.addSubWindow(project)
        if not project.tabList: # important when unpickling a file instead
            project.newDiagram() #create a new tab in the new file
        project.fileCloseEvent.connect(self.fileClosed) #closed file signal to switch to sub window view
        self.mdi.setViewMode(QMdiArea.TabbedView)
        project.show()
                
    def openProject(self):
        #show the open file dialog to open a saved file, then unpickle it.
        document_path = os.path.join(os.path.expanduser('~/Documents'),'PFDs')
        if(not os.path.exists(document_path)):
           document_path = os.path.expanduser('~/Documents')
        name = QFileDialog.getOpenFileNames(self, 'Open File(s)', f'{document_path}', 'Process Flow Diagram (*pfd)')
        if name:
            for files in name[0]:
                with open(files,'r') as file:
                    projectData = load(file)
                    project = FileWindow(self.mdi)
                    self.mdi.addSubWindow(project)
                    #create blank window and set its state
                    project.__setstate__(projectData)
                    project.resizeHandler()
                    project.fileCloseEvent.connect(self.fileClosed)
                    project.show()
        self.mdi.setViewMode(QMdiArea.TabbedView)
            
    def saveProject(self):
        #serialize all files in mdi area
        document_path = os.path.join(os.path.expanduser('~/Documents'),'PFDs')
        if(not os.path.exists(document_path)):
           os.mkdir(document_path)
        for j, i in enumerate(self.activeFiles): #get list of all windows with atleast one tab
            if i.tabCount:
                name = QFileDialog.getSaveFileName(self, 'Save File', f'{document_path}/Flow_Diagram_{j}.pfd', 'Process Flow Diagram (*.pfd)')
                i.saveProject(name)
            else:
                return False
        return True

    def saveImage(self):
        if self.mdi.currentSubWindow():
            currentDiagram = self.mdi.currentSubWindow().tabber.currentWidget().painter
            if currentDiagram:
                fileName = self.mdi.activeSubWindow().tabber.currentWidget().objectName()
                defaultPath = os.path.expanduser("~/Pictures")

                msg_box = QMessageBox()
                msg_box.setText("Choose the file format:")
                msg_box.addButton("PNG", QMessageBox.YesRole)
                msg_box.addButton("JPEG", QMessageBox.NoRole)
                msg_box.addButton("SVG", QMessageBox.NoRole)

                choice = msg_box.exec_()

                if choice == 0:
                    fileExtension = ".png"
                elif choice == 1:
                    fileExtension = ".jpg"
                else:
                    fileExtension = ".svg"

                options = QFileDialog.Options()
                options |= QFileDialog.ReadOnly  # Disable the ability to change the file filter
                file_dialog = QFileDialog(self, 'Save File', os.path.join(defaultPath, fileName + fileExtension),
                                          "Images (*.png *.jpg *.svg)", options=options)
                file_dialog.setAcceptMode(QFileDialog.AcceptSave)

                if file_dialog.exec_():
                    name = file_dialog.selectedFiles()[0]
                    if fileExtension == ".svg":
                        currentDiagram.clearSelection()

                        image = QImage(currentDiagram.sceneRect().size().toSize(), QImage.Format_ARGB32)
                        image.fill(Qt.transparent)

                        with QPainter(image) as painter:
                            currentDiagram.render(painter)

                        bounding_box = currentDiagram.itemsBoundingRect().toRect()
                        cropped_image = image.copy(bounding_box)

                        svgGenerator = QSvgGenerator()
                        svgGenerator.setFileName(name)
                        svgGenerator.setSize(QSize(int(bounding_box.width()), int(bounding_box.height())))
                        svgGenerator.setViewBox(QRectF(bounding_box))
                        svgGenerator.setTitle(fileName)
                        svgGenerator.setDescription("Generated by Process Flow Diagram Editor")

                        with QPainter(svgGenerator) as svgPainter:
                            svgPainter.drawImage(QPoint(bounding_box.x(), bounding_box.y()), cropped_image)

                    else:
                        image = QImage(currentDiagram.sceneRect().size().toSize(), QImage.Format_ARGB32)
                        image.fill(Qt.transparent)
                        painter = QPainter(image)
                        currentDiagram.render(painter)
                        bounding_box = currentDiagram.itemsBoundingRect().toRect()
                        cropped_image = image.copy(bounding_box)
                        cropped_image.save(name)
                        self.counterr += 1
                        painter.end()
    
    def generateReport(self):
        #place holder for future implementaion        
        pass
    
    def tabSwitched(self, window):
        #handle window switched edge case
        if window and window.tabCount:
            window.resizeHandler()
                
    def resizeEvent(self, event):
        #overload resize to also handle resize on file windows inside
        for i in self.mdi.subWindowList():
            i.resizeHandler()
        self.toolbar.resize()
        super(appWindow, self).resizeEvent(event)
        
    def closeEvent(self, event):
        #save alert on window close
        if len(self.activeFiles) and not dialogs.saveEvent(self):
            event.ignore()
        else:
            event.accept()
        self.writeSettings()  
    
    def fileClosed(self, index):
        pass
        #checks if the file tab menu needs to be removed
        # if self.count <= 1 :
        #     self.mdi.setViewMode(QMdiArea.SubWindowView)
    
    def writeSettings(self):
        # write window state on window close
        settings.beginGroup("MainWindow")
        settings.setValue("maximized", self.isMaximized())
        if not self.isMaximized():
            settings.setValue("size", self.size())
            settings.setValue("pos", self.pos())
        settings.endGroup()
    
    def readSettings(self):
        # read window state when app launches
        settings.beginGroup("MainWindow")
        self.resize(settings.value("size", QSize(1280, 720)))
        self.move(settings.value("pos", QPoint(320, 124)))
        if settings.value("maximized", False, type=bool):
            self.showMaximized()
        settings.endGroup()
      
    #useful one liner properties for getting data
    @property   
    def activeFiles(self):
        return [i for i in self.mdi.subWindowList() if i.tabCount]
    
    @property
    def count(self):
        return len(self.mdi.subWindowList())
    
    @property
    def activeScene(self):
        return self.mdi.currentSubWindow().tabber.currentWidget()

    #Key input handler
    def keyPressEvent(self, event):
        #overload key press event for custom keyboard shortcuts
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                #todo implement selectAll
                for item in self.mdi.activeSubWindow().tabber.currentWidget().items:
                    item.setSelected(True)
            
            #todo copy, paste, undo redo
            else:
                return
            event.accept()
        elif event.key() == Qt.Key_Q:
            if self.mdi.activeSubWindow() and self.mdi.activeSubWindow().tabber.currentWidget():
                for item in self.mdi.activeSubWindow().tabber.currentWidget().painter.selectedItems():
                    item.rotation -= 1
                    
        elif event.key() == Qt.Key_E:
            if self.mdi.activeSubWindow() and self.mdi.activeSubWindow().tabber.currentWidget():
                for item in self.mdi.activeSubWindow().tabber.currentWidget().painter.selectedItems():
                    item.rotation += 1
                        
if __name__ == '__main__':      # 1. Instantiate ApplicationContext
    main = appWindow()
    main.show()
    exit_code = app.app.exec_()      # 2. Invoke app.app.exec_()
    sys.exit(exit_code)
