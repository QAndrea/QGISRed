# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGISRedImportDialog
                                 A QGIS plugin
 Some util tools for GISRed
                             -------------------
        begin                : 2019-03-26
        git sha              : $Format:%H$
        copyright            : (C) 2019 by REDHISP (UPV)
        email                : fmartine@hma.upv.es
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.gui import QgsMessageBar
from qgis.core import QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup, QgsCoordinateReferenceSystem
from qgis.PyQt import QtGui, uic

try: #QGis 3.x
    from qgis.gui import QgsProjectionSelectionDialog  as QgsGenericProjectionSelector 
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QAction, QMessageBox, QTableWidgetItem, QFileDialog, QDialog, QApplication
    from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QFileInfo, Qt
    from ..qgisred_utils import QGISRedUtils
except: #QGis 2.x
    from qgis.gui import QgsGenericProjectionSelector
    from PyQt4.QtGui import QAction, QMessageBox, QIcon, QTableWidgetItem, QFileDialog, QDialog, QApplication
    from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QFileInfo, Qt
    from qgis.core import QgsMapLayerRegistry
    from ..qgisred_utils import QGISRedUtils

import os
from ctypes import*
import tempfile

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'qgisred_import_dialog.ui'))


class QGISRedImportDialog(QDialog, FORM_CLASS):
    iface = None
    NewProject = True
    NetworkName = ""
    ProjectDirectory = ""
    InpFile=""
    CRS= None
    ProcessDone= False
    gplFile = ""
    TemporalFolder = "Temporal folder"
    ownMainLayers = ["Pipes", "Valves", "Pumps", "Junctions", "Tanks", "Reservoirs"]
    ownFiles = ["Curves", "Controls", "Patterns", "Rules", "Options", "DefaultValues"]
    def __init__(self, parent=None):
        """Constructor."""
        super(QGISRedImportDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.gplFile = os.path.join(os.path.dirname(os.path.dirname(__file__)) , "qgisredprojectlist.gpl")
        #INP
        self.btImportInp.clicked.connect(self.importInpProject)
        self.btSelectDirectory.clicked.connect(self.selectDirectory)
        self.btSelectCRS.clicked.connect(self.selectCRS)
        self.btSelectInp.clicked.connect(self.selectINP)
        #SHPs
        self.btSelectSHPDirectory.clicked.connect(self.selectSHPDirectory)
        self.cbPipeLayer.currentIndexChanged.connect(self.pipeLayerChanged)
        self.cbValveLayer.currentIndexChanged.connect(self.valveLayerChanged)
        self.cbPumpLayer.currentIndexChanged.connect(self.pumpLayerChanged)
        self.cbTankLayer.currentIndexChanged.connect(self.tankLayerChanged)
        self.cbReservoirLayer.currentIndexChanged.connect(self.reservoirLayerChanged)
        self.cbJunctionLayer.currentIndexChanged.connect(self.junctionLayerChanged)
        self.btImportShps.clicked.connect(self.importShpProject)

    def config(self, ifac, direct, netw):
        self.iface=ifac
        try: #QGis 3.x
            self.CRS = self.iface.mapCanvas().mapSettings().destinationCrs()
        except: #QGis 2.x
            self.CRS = self.iface.mapCanvas().mapRenderer().destinationCrs()
        self.tbCRS.setText(self.CRS.description())
        self.ProcessDone = False
        self.NetworkName = netw
        self.ProjectDirectory = direct
        self.tbNetworkName.setText(netw)
        self.InpFile =""
        self.tbProjectDirectory.setText(direct)
        self.tbProjectDirectory.setCursorPosition(0)
        self.NewProject = self.ProjectDirectory==self.TemporalFolder
        self.btSelectDirectory.setVisible(self.NewProject)
        self.tbNetworkName.setReadOnly(not self.NewProject)
    
    def selectDirectory(self):
        selected_directory = QFileDialog.getExistingDirectory()
        if not selected_directory == "":
            self.tbProjectDirectory.setText(selected_directory)
            self.tbProjectDirectory.setCursorPosition(0)
            self.ProjectDirectory = selected_directory
            self.NetworkName = self.tbNetworkName.text()
        
        dirList = os.listdir(self.ProjectDirectory)
        self.NewProject = True
        for name in self.ownMainLayers:
            if self.NetworkName + "_" + name + ".shp" in dirList:
                self.NewProject = False
                break
        
    def selectCRS(self):
        projSelector = QgsGenericProjectionSelector()
        if projSelector.exec_():
            try: #QGis 3.x
                crsId = projSelector.crs().srsid()
            except: #QGis 2.x
                crsId = projSelector.selectedCrsId()
            if not crsId==0:
                self.CRS = QgsCoordinateReferenceSystem()
                self.CRS.createFromId(crsId, QgsCoordinateReferenceSystem.InternalCrsId)
                self.tbCRS.setText(self.CRS.description())

    def validationsCreateProject(self):
        self.NetworkName = self.tbNetworkName.text()
        if len(self.NetworkName)==0:
            self.iface.messageBar().pushMessage("Validations", "The network's name is not valid", level=1)
            return False
        self.ProjectDirectory = self.tbProjectDirectory.text()
        if len(self.ProjectDirectory)==0 or self.ProjectDirectory==self.TemporalFolder:
            self.ProjectDirectory=tempfile._get_default_tempdir() + "\\" + next(tempfile._get_candidate_names())
        else:
            if not os.path.exists(self.ProjectDirectory):
                self.iface.messageBar().pushMessage("Validations", "The project directory does not exist", level=1)
                return False
        return True

    def createProject(self):
        os.chdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dlls"))

        mydll = WinDLL("GISRed.QGisPlugins.dll")
        mydll.CreateProject.argtypes = (c_char_p, c_char_p, c_char_p)
        mydll.CreateProject.restype = c_char_p
        b = mydll.CreateProject(self.ProjectDirectory.encode('utf-8'), self.NetworkName.encode('utf-8'), "".encode('utf-8'))
        try: #QGis 3.x
            b= "".join(map(chr, b)) #bytes to string
        except:  #QGis 2.x
            b=b
        
        if not b=="True":
            if b=="False":
                self.iface.messageBar().pushMessage("Warning", "Some issues occurred in the process", level=1, duration=10)
            else:
                self.iface.messageBar().pushMessage("Error", b, level=2, duration=10)
            self.close()
            return False
        
        file = open(self.gplFile, "a+")
        QGISRedUtils().writeFile(file, self.NetworkName + ";" + self.ProjectDirectory + '\n')
        file.close()
        return True

#INP SECTION
    def selectINP(self):
        qfd = QFileDialog()
        path = ""
        filter = "inp(*.inp)"
        f = QFileDialog.getOpenFileName(qfd, "Select INP file", path, filter)
        if isinstance(f, tuple): #QGis 3.x
            f = f[0]
        
        if not f=="":
            self.InpFile = f
            self.tbInpFile.setText(str(f))
            self.tbInpFile.setCursorPosition(0)

    def importInpProject(self):
        isValid = self.validationsCreateProject()
        if isValid==True:
            #Validations INP
            self.InpFile = self.tbInpFile.text()
            if len(self.InpFile)==0:
                self.iface.messageBar().pushMessage("Validations", "INP file is not valid", level=1)
                return
            else:
                if not os.path.exists(self.InpFile):
                    self.iface.messageBar().pushMessage("Validations", "INP file does not exist", level=1)
                    return
            
            #Process
            if self.NewProject:
                if not self.createProject():
                    return
            #Remove layers
            utils = QGISRedUtils(self.ProjectDirectory, self.NetworkName, self.iface)
            utils.removeLayers(self.ownMainLayers)
            utils.removeLayers(self.ownFiles, ".csv")
            
            #Method
            QApplication.setOverrideCursor(Qt.WaitCursor)
            os.chdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dlls"))
            mydll = WinDLL("GISRed.QGisPlugins.dll")
            mydll.ImportFromInp.argtypes = (c_char_p, c_char_p, c_char_p)
            mydll.ImportFromInp.restype = c_char_p
            b = mydll.ImportFromInp(self.ProjectDirectory.encode('utf-8'), self.NetworkName.encode('utf-8'), self.InpFile.encode('utf-8'))
            try: #QGis 3.x
                b= "".join(map(chr, b)) #bytes to string
            except:  #QGis 2.x
                b=b
            
            #Group
            dataGroup = QgsProject.instance().layerTreeRoot().findGroup(self.NetworkName + " Inputs")
            if dataGroup is None:
                root = QgsProject.instance().layerTreeRoot()
                dataGroup = root.addGroup(self.NetworkName + " Inputs")
            #Open layers
            utils.openElementsLayers(dataGroup, self.CRS, self.ownMainLayers, self.ownFiles)
            QApplication.restoreOverrideCursor()

            if b=="True":
                self.iface.messageBar().pushMessage("Information", "Process successfully completed", level=3, duration=10)
            elif b=="False":
                self.iface.messageBar().pushMessage("Warning", "Some issues occurred in the process", level=1, duration=10)
            else:
                self.iface.messageBar().pushMessage("Error", b, level=2, duration=10)

            self.close()
            self.ProcessDone = True

#SHPS SECTION
    def selectSHPDirectory(self):
        selected_directory = QFileDialog.getExistingDirectory()
        if selected_directory == "":
            return
        
        self.tbShpDirectory.setText(selected_directory)
        self.tbShpDirectory.setCursorPosition(0)

        dirList = os.listdir(selected_directory)
        self.cbPipeLayer.clear()
        self.cbPipeLayer.addItem("None")
        self.cbValveLayer.clear()
        self.cbValveLayer.addItem("None")
        self.cbPumpLayer.clear()
        self.cbPumpLayer.addItem("None")
        self.cbTankLayer.clear()
        self.cbTankLayer.addItem("None")
        self.cbReservoirLayer.clear()
        self.cbReservoirLayer.addItem("None")
        self.cbJunctionLayer.clear()
        self.cbJunctionLayer.addItem("None")
        for file in dirList:
            if ".shp" in file:
                name= os.path.splitext(os.path.basename(file))[0]
                self.cbPipeLayer.addItem(name)
                self.cbValveLayer.addItem(name)
                self.cbPumpLayer.addItem(name)
                self.cbTankLayer.addItem(name)
                self.cbReservoirLayer.addItem(name)
                self.cbJunctionLayer.addItem(name)

    def selectComboBoxItem(self, combobox, options):
        for i in range(combobox.count()):
            fieldName = combobox.itemText(i).lower()
            if fieldName in options:
                combobox.setCurrentIndex(i)
                return

    def pipeLayerChanged(self):
        newItem = self.cbPipeLayer.currentText()
        self.cbPipe_Id.clear()
        self.cbPipe_Length.clear()
        self.cbPipe_Diameter.clear()
        self.cbPipe_LossCoef.clear()
        self.cbPipe_Tag.clear()
        self.cbPipe_Descr.clear()
        if newItem=="None":
            self.gbPipes.setEnabled(False)
            return
        
        self.gbPipes.setEnabled(True)
        
        pipeLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(pipeLayer, "Pipes layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbPipe_Id.addItems(field_names)
        self.cbPipe_Length.addItems(field_names)
        self.cbPipe_Diameter.addItems(field_names)
        self.cbPipe_LossCoef.addItems(field_names)
        self.cbPipe_Tag.addItems(field_names)
        self.cbPipe_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbPipe_Id, ["id"]) #["one", "two", "THREE"]
        self.selectComboBoxItem(self.cbPipe_Length, ["length"])
        self.selectComboBoxItem(self.cbPipe_Diameter, ["diameter", "diam"])
        self.selectComboBoxItem(self.cbPipe_LossCoef, ["losscoeff"])
        self.selectComboBoxItem(self.cbPipe_Tag, ["tag"])
        self.selectComboBoxItem(self.cbPipe_Descr, ["descrip", "descr", "description"])

    def valveLayerChanged(self):
        newItem = self.cbValveLayer.currentText()
        self.cbValve_Id.clear()
        self.cbValve_Diameter.clear()
        self.cbValve_Type.clear()
        self.cbValve_InitStat.clear()
        self.cbValve_Orient.clear()
        self.cbValve_Tag.clear()
        self.cbValve_Descr.clear()
        if newItem=="None":
            self.gbValves.setEnabled(False)
            return
        
        self.gbValves.setEnabled(True)
        
        valveLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(valveLayer, "Valves layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbValve_Id.addItems(field_names)
        self.cbValve_Diameter.addItems(field_names)
        self.cbValve_Type.addItems(field_names)
        self.cbValve_InitStat.addItems(field_names)
        self.cbValve_Orient.addItems(field_names)
        self.cbValve_Tag.addItems(field_names)
        self.cbValve_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbValve_Id, ["id"])
        self.selectComboBoxItem(self.cbValve_Diameter, ["diameter", "diam"])
        self.selectComboBoxItem(self.cbValve_Type, ["type"])
        self.selectComboBoxItem(self.cbValve_InitStat, ["inistatus"])
        self.selectComboBoxItem(self.cbValve_Orient, ["orientatio"])
        self.selectComboBoxItem(self.cbValve_Tag, ["tag"])
        self.selectComboBoxItem(self.cbValve_Descr, ["descrip", "descr", "description"])

    def pumpLayerChanged(self):
        newItem = self.cbPumpLayer.currentText()
        self.cbPump_Id.clear()
        self.cbPump_Power.clear()
        self.cbPump_InitStat.clear()
        self.cbPump_Orient.clear()
        self.cbPump_Tag.clear()
        self.cbPump_Descr.clear()
        if newItem=="None":
            self.gbPumps.setEnabled(False)
            return
        
        self.gbPumps.setEnabled(True)
        
        valveLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(valveLayer, "Pumps layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbPump_Id.addItems(field_names)
        self.cbPump_Power.addItems(field_names)
        self.cbPump_InitStat.addItems(field_names)
        self.cbPump_Orient.addItems(field_names)
        self.cbPump_Tag.addItems(field_names)
        self.cbPump_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbPump_Id, ["id"])
        self.selectComboBoxItem(self.cbPump_Power, ["power"])
        self.selectComboBoxItem(self.cbPump_InitStat, ["inistatus"])
        self.selectComboBoxItem(self.cbPump_Orient, ["orientatio"])
        self.selectComboBoxItem(self.cbPump_Tag, ["tag"])
        self.selectComboBoxItem(self.cbPump_Descr, ["descrip", "descr", "description"])

    def tankLayerChanged(self):
        newItem = self.cbTankLayer.currentText()
        self.cbTank_Id.clear()
        self.cbTank_Elevat.clear()
        self.cbTank_MinLevel.clear()
        self.cbTank_MaxLevel.clear()
        self.cbTank_Diameter.clear()
        self.cbTank_ReactCoeff.clear()
        self.cbTank_Tag.clear()
        self.cbTank_Descr.clear()
        if newItem=="None":
            self.gbTanks.setEnabled(False)
            return
        
        self.gbTanks.setEnabled(True)
        
        valveLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(valveLayer, "Tanks layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbTank_Id.addItems(field_names)
        self.cbTank_Elevat.addItems(field_names)
        self.cbTank_MinLevel.addItems(field_names)
        self.cbTank_MaxLevel.addItems(field_names)
        self.cbTank_Diameter.addItems(field_names)
        self.cbTank_ReactCoeff.addItems(field_names)
        self.cbTank_Tag.addItems(field_names)
        self.cbTank_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbTank_Id, ["id"])
        self.selectComboBoxItem(self.cbTank_Elevat, ["elevation"])
        self.selectComboBoxItem(self.cbTank_MinLevel, ["minlevel"])
        self.selectComboBoxItem(self.cbTank_MaxLevel, ["maxlevel"])
        self.selectComboBoxItem(self.cbTank_Diameter, ["diameter", "diam"])
        self.selectComboBoxItem(self.cbTank_ReactCoeff, ["reactcoef"])
        self.selectComboBoxItem(self.cbTank_Tag, ["tag"])
        self.selectComboBoxItem(self.cbTank_Descr, ["descrip", "descr", "description"])

    def reservoirLayerChanged(self):
        newItem = self.cbReservoirLayer.currentText()
        self.cbReservoir_Id.clear()
        self.cbReservoir_TotHead.clear()
        self.cbReservoir_Tag.clear()
        self.cbReservoir_Descr.clear()
        if newItem=="None":
            self.gbReservoirs.setEnabled(False)
            return
        
        self.gbReservoirs.setEnabled(True)
        
        valveLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(valveLayer, "Reservoirs layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbReservoir_Id.addItems(field_names)
        self.cbReservoir_TotHead.addItems(field_names)
        self.cbReservoir_Tag.addItems(field_names)
        self.cbReservoir_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbReservoir_Id, ["id"])
        self.selectComboBoxItem(self.cbReservoir_TotHead, ["totalhead"])
        self.selectComboBoxItem(self.cbReservoir_Tag, ["tag"])
        self.selectComboBoxItem(self.cbReservoir_Descr, ["descrip", "descr", "description"])

    def junctionLayerChanged(self):
        newItem = self.cbJunctionLayer.currentText()
        self.cbJunction_Id.clear()
        self.cbJunction_Elevation.clear()
        self.cbJunction_BaseDem.clear()
        self.cbJunction_Tag.clear()
        self.cbJunction_Descr.clear()
        if newItem=="None":
            self.gbJunctions.setEnabled(False)
            return
        
        self.gbJunctions.setEnabled(True)
        
        valveLayer = os.path.join(self.tbShpDirectory.text(), newItem + ".shp")
        vlayer = QgsVectorLayer(valveLayer, "Juntions layer", "ogr")
        if not vlayer.isValid():
            return
        field_names = [field.name() for field in vlayer.fields()]
        field_names.insert(0,"None")
        self.cbJunction_Id.addItems(field_names)
        self.cbJunction_Elevation.addItems(field_names)
        self.cbJunction_BaseDem.addItems(field_names)
        self.cbJunction_Tag.addItems(field_names)
        self.cbJunction_Descr.addItems(field_names)
        
        self.selectComboBoxItem(self.cbJunction_Id, ["id"])
        self.selectComboBoxItem(self.cbJunction_Elevation, ["elevation"])
        self.selectComboBoxItem(self.cbJunction_BaseDem, ["basedem"])
        self.selectComboBoxItem(self.cbJunction_Tag, ["tag"])
        self.selectComboBoxItem(self.cbJunction_Descr, ["descrip", "descr", "description"])

    def createShpsNames(self):
        shpFolder = self.tbShpDirectory.text()
        shpNames =""
        
        name = self.cbPipeLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[PIPES]" + os.path.join(shpFolder, name) + ","
        name = self.cbValveLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[VALVES]" + os.path.join(shpFolder, name) + ","
        name = self.cbPumpLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[PUMPS]" + os.path.join(shpFolder, name) + ","
        name = self.cbTankLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[TANKS]" + os.path.join(shpFolder, name) + ","
        name = self.cbReservoirLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[RESERVOIRS]" + os.path.join(shpFolder, name) + ","
        name = self.cbJunctionLayer.currentText()
        if not name == "None":
            shpNames = shpNames + "[JUNCTIONS]" + os.path.join(shpFolder, name) + ","
        return shpNames

    def createShpFields(self):
        fields = ""
        
        name = self.cbPipeLayer.currentText()
        if not name == "None":
            fields = "[PIPES]"
            name = self.cbPipe_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbPipe_Length.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbPipe_Diameter.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";" 
            fields = fields + ";"#RougCoeff
            name = self.cbPipe_LossCoef.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #InitStat
            fields = fields + ";" #BulkCoef
            fields = fields + ";" #WallCoef
            name = self.cbPipe_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbPipe_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers

        name = self.cbValveLayer.currentText()
        if not name == "None":
            fields = fields + "[VALVES]"
            name = self.cbValve_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbValve_Diameter.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbValve_Type.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #Setting
            fields = fields + ";" #IdHeadLoss
            fields = fields + ";" #LossCoef
            name = self.cbValve_InitStat.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbValve_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbValve_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #Sector
            name = self.cbValve_Orient.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers

        name = self.cbPumpLayer.currentText()
        if not name == "None":
            fields = fields + "[PUMPS]"
            name = self.cbPump_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #IdHFCurve
            name = self.cbPump_Power.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #Speed
            fields = fields + ";" #IdSpeedPat
            name = self.cbPump_InitStat.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #IdEfficCur
            fields = fields + ";" #EnergPrice
            fields = fields + ";" #IdPricePat
            name = self.cbPump_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbPump_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #Sector
            name = self.cbPump_Orient.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers
        
        name = self.cbTankLayer.currentText()
        if not name == "None":
            fields = fields + "[TANKS]"
            name = self.cbTank_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbTank_Elevat.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #IniLevel
            name = self.cbTank_MinLevel.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbTank_MaxLevel.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbTank_Diameter.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #MinVolum
            fields = fields + ";" #IdVolCur
            fields = fields + ";" #MixMod
            fields = fields + ";" #MixFrac
            name = self.cbTank_ReactCoeff.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbTank_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbTank_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers
        
        name = self.cbReservoirLayer.currentText()
        if not name == "None":
            fields = fields + "[RESERVOIRS]"
            name = self.cbReservoir_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbReservoir_TotHead.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #IdHeadPat
            fields = fields + ";" #IniQual
            name = self.cbReservoir_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbReservoir_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers
        
        name = self.cbJunctionLayer.currentText()
        if not name == "None":
            fields = fields + "[JUNCTIONS]"
            name = self.cbJunction_Id.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbJunction_Elevation.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbJunction_BaseDem.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            fields = fields + ";" #IdDemPat
            fields = fields + ";" #EmitCoef
            fields = fields + ";" #IniQual
            name = self.cbJunction_Tag.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            name = self.cbJunction_Descr.currentText()
            if not name == "None":
                fields = fields + name
            fields = fields + ";"
            
            fields = fields + "," #To separate layers
        
        return fields

    def importShpProject(self):
        isValid = self.validationsCreateProject()
        if isValid==True:
            #Validations SHP's
            if not os.path.exists(self.tbShpDirectory.text()):
                self.iface.messageBar().pushMessage("Validations", "The SHPs folder is not valid or does not exist", level=1)
                return
            fields = self.createShpFields()
            if fields == "":
                self.iface.messageBar().pushMessage("Validations", "Any SHP selected for importing", level=1)
                return
            
            #Process
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if self.NewProject:
                if not self.createProject():
                    return
            #Remove layers
            utils = QGISRedUtils(self.ProjectDirectory, self.NetworkName, self.iface)
            utils.removeLayers(self.ownMainLayers)
            utils.removeLayers(self.ownFiles, ".csv")
            
            shapes = self.createShpsNames()
            #Method
            os.chdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dlls"))
            mydll = WinDLL("GISRed.QGisPlugins.dll")
            mydll.ImportFromShps.argtypes = (c_char_p, c_char_p, c_char_p, c_char_p)
            mydll.ImportFromShps.restype = c_char_p
            b = mydll.ImportFromShps(self.ProjectDirectory.encode('utf-8'), self.NetworkName.encode('utf-8'), shapes.encode('utf-8'), fields.encode('utf-8'))
            try: #QGis 3.x
                b= "".join(map(chr, b)) #bytes to string
            except:  #QGis 2.x
                b=b
            
            #Group
            dataGroup = QgsProject.instance().layerTreeRoot().findGroup(self.NetworkName + " Inputs")
            if dataGroup is None:
                root = QgsProject.instance().layerTreeRoot()
                dataGroup = root.addGroup(self.NetworkName + " Inputs")
            #Open layers
            utils.openElementsLayers(dataGroup, self.CRS, self.ownMainLayers, self.ownFiles)
            QApplication.restoreOverrideCursor()

            if b=="True":
                self.iface.messageBar().pushMessage("Information", "Process successfully completed", level=3, duration=10)
            elif b=="False":
                self.iface.messageBar().pushMessage("Warning", "Some issues occurred in the process", level=1, duration=10)
            else:
                self.iface.messageBar().pushMessage("Error", b, level=2, duration=10)

            self.close()
            self.ProcessDone = True