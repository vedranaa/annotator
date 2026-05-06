#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Simple image annotator.

This module contains the Annotator class. Annotator is a widget that allows the
user to place annotations on top of an image. All interaction is using mouse
clicks, draws, and keyboard input. Help is accessed by pressing 'H'.

Use:
    Annotate a folder of images:
        from annotator import annotate_folder
        annotate_folder('data')

    Annotate a single image file:
        from annotator import annotate_filename
        annotate_filename('image.png')

    Run from command-line with:
        $ python annotator.py image_filename
        $ python annotator.py folder/

Author: vand@dtu.dk, 2020
"""

import sys 
from pathlib import Path

import PyQt5.QtCore  
import PyQt5.QtWidgets 
import PyQt5.QtGui


IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
  
class Annotator(PyQt5.QtWidgets.QWidget):
    
    def __init__(self, size=None):
        '''
        Initializes an Annotator without the image.

        Parameters
        ----------
        size : two-element tuple for the size of the annotator.

        '''
        
        super().__init__() 
        
        if size is None:
            size = PyQt5.QtCore.QSize(256,256)
        elif type(size) is tuple:
            size = PyQt5.QtCore.QSize(size[0],size[1])
            
        # Pixmap layers
        self.imagePix = PyQt5.QtGui.QPixmap(size.width(), size.height()) 
        self.imagePix.fill(self.color_picker(label=0, opacity=0))
        self.annotationPix = PyQt5.QtGui.QPixmap(self.imagePix.width(), 
                                                 self.imagePix.height())
        self.annotationPix.fill(self.color_picker(label=0, opacity=0))
        self.cursorPix = PyQt5.QtGui.QPixmap(self.imagePix.width(), 
                                             self.imagePix.height())
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))    
        
        # Attributes for drawing
        self.label = 1
        self.penWidth = 9
        self.lastDrawPoint = PyQt5.QtCore.QPoint()

        # State for current image/folder session
        self.saveAddress = 'annotations.png'
        self.currentImagePath = None
        self.imageFiles = []
        self.imageIndex = None
        self.annotationsDir = None
        self.annotationDirty = False

        # Attributes for displaying
        self.overlay = 0
        self.overlays = {0: 'both', 1: 'annotation', 2: 'image'}
        self.annotationOpacity = 0.5
        self.cursorOpacity = 0.5
        self.zoomOpacity = 0.5
        self.setTitle()
        self.setCursor(PyQt5.QtGui.QCursor(PyQt5.QtCore.Qt.CrossCursor))
        self.lastCursorPoint = PyQt5.QtCore.QPoint()
        self.setMouseTracking(True)

        # Attributes relating to the transformation between widget
        # coordinate system and image coordinate system
        self.zoomFactor = 1  # accounts for resizing and zooming
        self.padding = PyQt5.QtCore.QPoint(0, 0)  # padding for aspect ratio mismatch
        self.target = PyQt5.QtCore.QRect(0, 0, self.width(), self.height())  # display area
        self.source = PyQt5.QtCore.QRect(0, 0,
                self.imagePix.width(), self.imagePix.height())  # image area being drawn
        self.offset = PyQt5.QtCore.QPoint(0, 0)  # offset between centers

        # Flags for tracking state
        self.zPressed = False  # zooming mode when z is pressed
        self.activelyZooming = False
        self.activelyDrawing = False
        self.newZoomValues = None
        
        # Label for displaying text overlay
        self.textField = PyQt5.QtWidgets.QLabel(self)
        self.textField.setStyleSheet("background-color: rgba(191,191,191,191)")
        self.textField.setTextFormat(PyQt5.QtCore.Qt.RichText)
        self.textField.resize(0, 0)
        self.textField.move(10, 10)
        self.hPressed = False
        self.textField.setAttribute(PyQt5.QtCore.Qt.WA_TransparentForMouseEvents)

        # Timer for displaying text overlay
        self.timer = PyQt5.QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hideText)

        # Calculate initial zoom to fit screen
        initial_zoom = min(2000 / max(self.imagePix.width(),
                4 * self.imagePix.height() / 3), 1)  # limit to ~2000x1500
        self.resize(int(initial_zoom * self.imagePix.width()),
                    int(initial_zoom * self.imagePix.height()))
        
        self.showInfo(self.introText(),5000)
        print(self.introText(False))
    
    @classmethod
    def fromFilename(cls, filename):
        '''
        Initializes an Annotator with an image loaded from a file.

        Parameters
        ----------
        filename : filename of an image in usual formats (jpg, png, ...).

        '''
        image_path = Path(filename)
        image_pix = PyQt5.QtGui.QPixmap(str(image_path))
        if image_pix.isNull():
            raise ValueError(f'Could not load image: {filename}')
        annotator = Annotator(image_pix.size())
        annotator.setImage(image_pix, image_path=str(image_path),
                           save_address=str(image_path.with_name(
                               image_path.stem + '_annotated.png')))
        return annotator

    @classmethod
    def fromFolder(cls, foldername):
        '''
        Initializes an Annotator in folder mode, loading the first image.

        Annotations are saved to an 'annotations' folder next to the image
        folder. Use left/right arrow keys to navigate between images.

        Parameters
        ----------
        foldername : path to a folder containing images.

        '''
        folder = Path(foldername)
        image_files = sorted(
            path for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        if not image_files:
            raise ValueError(f'No images found in folder: {foldername}')

        first_image_pix = PyQt5.QtGui.QPixmap(str(image_files[0]))
        if first_image_pix.isNull():
            raise ValueError(f'Could not load image: {image_files[0]}')

        annotator = Annotator(first_image_pix.size())
        annotator.imageFiles = [str(path) for path in image_files]
        annotator.annotationsDir = folder.parent / 'annotations'
        annotator.annotationsDir.mkdir(exist_ok=True)
        annotator.loadImageAtIndex(0, save_current=False)
        return annotator
    
    @classmethod
    def fromRgba(cls, rgba):
        '''
        Initializes an Annotator with an image given as an rgba array.

        Parameters
        ----------
        rgba : (..., 4) array with dtype uint8.

        '''
        rgba = rgba.copy()
        qimage = PyQt5.QtGui.QImage(rgba.data, rgba.shape[1], rgba.shape[0],
                                    PyQt5.QtGui.QImage.Format_RGBA8888)
        image_pix = PyQt5.QtGui.QPixmap(qimage)
        annotator = Annotator(image_pix.size())
        annotator.setImage(image_pix,
                   save_address='from_rgba_annotated.png')
        return annotator    
    
    @classmethod
    def fromGrayscale(cls, gray):
        '''
        Initializes an Annotator with an image given as a grayscale array.

        Parameters
        ----------
        gray : 2D array with dtype uint8.

        '''
        gray = gray.copy()

        bytes_per_line = gray.nbytes // gray.shape[0]
        qimage = PyQt5.QtGui.QImage(gray.data, gray.shape[1], gray.shape[0],
                                    bytes_per_line,
                                    PyQt5.QtGui.QImage.Format_Grayscale8)
        image_pix = PyQt5.QtGui.QPixmap(qimage)
        annotator = Annotator(image_pix.size())
        annotator.setImage(image_pix,
                   save_address='from_grayscale_annotated.png')
        return annotator    
     
    helpText = (
        '<i>Help for annotator</i> <br>' 
        '<b>KEYBOARD COMMANDS:</b> <br>' 
        '&nbsp; &nbsp; <b>1</b> to <b>9</b> changes pen label (L) <br>' 
        '&nbsp; &nbsp; <b>0</b> eraser mode <br>' 
        '&nbsp; &nbsp; <b>&uarr;</b> and <b>&darr;</b> changes pen width (W) <br>' 
        '&nbsp; &nbsp; <b>&larr;</b> and <b>&rarr;</b> changes image in folder mode <br>' 
        '&nbsp; &nbsp; <b>O</b> changes overlay <br>' 
        '&nbsp; &nbsp; <b>Z</b> held down enables zoom <br>' 
        '&nbsp; &nbsp; <b>Z</b> pressed resets zoom <br>' 
        '&nbsp; &nbsp; <b>S</b> saves annotation <br>' 
        '&nbsp; &nbsp; <b>H</b> shows this help <br>' 
        '<b>MOUSE DRAG:</b> <br>' 
        '&nbsp; &nbsp; Draws annotation <br>' 
        '&nbsp; &nbsp; Zooms when zoom enabled')
    
    @classmethod
    def introText(cls, rich = True):
        if rich:
            return '<i>Starting annotator</i> <br> For help, hit <b>H</b>'
            #'<hr> ANNOTATOR <br> Copyright (C) 2020 <br> Vedrana A. Dahl'
        else:
            return "Starting annotator. For help, hit 'H'."

        
    def showHelp(self):
        self.timer.stop()
        self.showText(self.helpText)
    
    def showInfo(self, text, time=1000):
        if not self.hPressed:
            self.timer.start(time)
            self.showText(text)
    
    def showText(self, text):
        self.textField.setText(text)
        #self.textField.resize(self.textField.fontMetrics().size(PyQt5.QtCore.Qt.TextExpandTabs, text))
        self.textField.adjustSize()
        self.update()
          
    def hideText(self):
        self.textField.resize(0,0)
        self.update()
        
    def setTitle(self):
        title = f'L:{self.label}, W:{self.penWidth}, O:{self.overlays[self.overlay]}'
        if self.imageIndex is not None and self.imageFiles:
            filename = Path(self.imageFiles[self.imageIndex]).name
            title += f', I:{self.imageIndex + 1}/{len(self.imageFiles)} {filename}'
        self.setWindowTitle(title)

    def setImage(self, image_pix, image_path=None, save_address=None):
        '''
        Replaces the displayed image and resets annotation and drawing state.

        Parameters
        ----------
        image_pix : QPixmap of the new image.
        image_path : optional path string for the loaded image file.
        save_address : optional path string where annotation will be saved.

        '''
        self.imagePix = image_pix
        self.annotationPix = PyQt5.QtGui.QPixmap(self.imagePix.size())
        self.annotationPix.fill(self.color_picker(label=0, opacity=0))
        self.cursorPix = PyQt5.QtGui.QPixmap(self.imagePix.size())
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))
        self.currentImagePath = image_path
        if save_address is not None:
            self.saveAddress = save_address
        self.lastDrawPoint = PyQt5.QtCore.QPoint()
        self.lastCursorPoint = PyQt5.QtCore.QPoint()
        self.activelyZooming = False
        self.activelyDrawing = False
        self.newZoomValues = None
        self.annotationDirty = False
        self.source = PyQt5.QtCore.QRect(0, 0,
                self.imagePix.width(), self.imagePix.height())
        self.offset = PyQt5.QtCore.QPoint(0, 0)
        self.adjustTarget()

    def annotationPathForImage(self, image_path):
        '''
        Returns the save path for the annotation of a given image.

        In folder mode, returns a path inside annotationsDir. Otherwise,
        returns a sibling file with '_annotated' appended to the stem.

        '''
        image_path = Path(image_path)
        if self.annotationsDir is not None:
            return self.annotationsDir / f'{image_path.stem}_annotated.png'
        return image_path.with_name(f'{image_path.stem}_annotated.png')

    def loadAnnotation(self):
        '''
        Loads an existing annotation file for the current image, if one exists
        and matches the image size. Resets annotationDirty to False.

        '''
        annotation_path = Path(self.saveAddress)
        if not annotation_path.exists():
            return

        annotation_pix = PyQt5.QtGui.QPixmap(str(annotation_path))
        if annotation_pix.isNull() or annotation_pix.size() != self.imagePix.size():
            return
        self.annotationPix = annotation_pix
        self.annotationDirty = False

    def hasVisibleAnnotation(self):
        '''
        Returns True if any pixel in the annotation layer has alpha > 0.

        '''
        image = self.annotationPix.toImage()
        for y_coord in range(image.height()):
            for x_coord in range(image.width()):
                if image.pixelColor(x_coord, y_coord).alpha() > 0:
                    return True
        return False

    def loadImageAtIndex(self, index, save_current=True):
        '''
        Loads the image at the given index from imageFiles.

        Parameters
        ----------
        index : index into imageFiles.
        save_current : if True, saves the current annotation before switching.

        '''
        if not self.imageFiles:
            return
        if not 0 <= index < len(self.imageFiles):
            return

        if save_current and self.currentImagePath is not None:
            self.saveOutcome(show_message=False)

        image_path = Path(self.imageFiles[index])
        image_pix = PyQt5.QtGui.QPixmap(str(image_path))
        if image_pix.isNull():
            raise ValueError(f'Could not load image: {image_path}')

        self.imageIndex = index
        self.setImage(image_pix, image_path=str(image_path),
                      save_address=str(self.annotationPathForImage(image_path)))
        self.loadAnnotation()
        self.drawCursorPoint(self.lastCursorPoint)
        self.setTitle()
        self.showInfo(f'Loaded {image_path.name} ({index + 1}/{len(self.imageFiles)})')
        self.update()

    def changeImage(self, step):
        '''
        Navigates forward or backward in the image list with wraparound.

        Parameters
        ----------
        step : +1 for next image, -1 for previous.

        '''
        if not self.imageFiles or self.imageIndex is None:
            return

        new_index = (self.imageIndex + step) % len(self.imageFiles)
        self.loadImageAtIndex(new_index)
            
    def makePainter(self, pixmap, color):
        """" Returns scribble painter operating on a given pixmap. """
        painter_scribble = PyQt5.QtGui.QPainter(pixmap)       
        painter_scribble.setPen(PyQt5.QtGui.QPen(color, 
                    self.penWidth*self.zoomFactor, PyQt5.QtCore.Qt.SolidLine, 
                    PyQt5.QtCore.Qt.RoundCap, PyQt5.QtCore.Qt.RoundJoin))
        painter_scribble.translate(-self.offset)
        painter_scribble.translate(-0.25,-0.25) # a compromise between odd and even pen width
        painter_scribble.scale(1/self.zoomFactor, 1/self.zoomFactor)
        painter_scribble.translate(-self.padding)        
        painter_scribble.setCompositionMode(
                    PyQt5.QtGui.QPainter.CompositionMode_Source)
        return painter_scribble

    def paintEvent(self, event):
        """ Paint event for displaying the content of the widget."""
        painter_display = PyQt5.QtGui.QPainter(self) # this is painter used for display
        painter_display.setCompositionMode(
                    PyQt5.QtGui.QPainter.CompositionMode_SourceOver)
        if self.overlay != 1: # overlay 0 or 2
            painter_display.drawPixmap(self.target, self.imagePix, self.source)
        if self.overlay != 2: # overlay 0 or 1
            painter_display.drawPixmap(self.target, self.annotationPix, 
                                       self.source)
        painter_display.drawPixmap(self.target, self.cursorPix, self.source)
        
    def drawCursorPoint(self, point):
        """Called when cursorPix needs update due to pen change or movement"""
        self.cursorPix.fill(self.color_picker(label=0, opacity=0)) # transparent
        painter_scribble = self.makePainter(self.cursorPix, 
                    self.color_picker(self.label, self.cursorOpacity)) # the painter used for cursor
        painter_scribble.drawPoint(point)   
    
    def mousePressEvent(self, event):
        if event.button() == PyQt5.QtCore.Qt.LeftButton: 
            if self.zPressed: # initiate zooming and not drawing
                self.cursorPix.fill(self.color_picker(label=0, opacity=0)) # clear (fill with transparent)
                self.lastCursorPoint = event.pos()
                self.activelyZooming = True
                self.newZoomValues = None
            else: # initiate drawing
                painter_scribble = self.makePainter(self.annotationPix, 
                        self.color_picker(self.label, 
                            (self.label>0)*self.annotationOpacity)) # the painter used for drawing        
                painter_scribble.drawPoint(event.pos())
                self.lastDrawPoint = event.pos()   
                self.activelyDrawing = True
                self.annotationDirty = True
            self.update()
    
    def mouseMoveEvent(self, event):
        if self.activelyZooming: 
            self.cursorPix.fill(self.color_picker(label=0, opacity=0)) # clear (fill with transparent)
            painter_scribble = self.makePainter(self.cursorPix,
                    self.color_picker(0, self.zoomOpacity))          
            x = min(self.lastCursorPoint.x(), event.x())
            y = min(self.lastCursorPoint.y(), event.y())
            w = abs(self.lastCursorPoint.x() - event.x())
            h = abs(self.lastCursorPoint.y() - event.y())      
            painter_scribble.fillRect(x, y, w, h, 
                            self.color_picker(0, self.zoomOpacity))
        else:     
            if self.activelyDrawing: 
                painter_scribble = self.makePainter(self.annotationPix, 
                        self.color_picker(self.label, 
                                (self.label>0)*self.annotationOpacity)) # the painter used for drawing        
                painter_scribble.drawLine(self.lastDrawPoint, event.pos())
                self.lastDrawPoint = event.pos()
                self.annotationDirty = True
            if not self.zPressed: # just moving around
                self.drawCursorPoint(event.pos())
            self.lastCursorPoint = event.pos()      
        self.update()
    
    def mouseReleaseEvent(self, event):  
        if self.activelyZooming:
            x = min(self.lastCursorPoint.x(), event.x())
            y = min(self.lastCursorPoint.y(), event.y())
            w = abs(self.lastCursorPoint.x() - event.x())
            h = abs(self.lastCursorPoint.y() - event.y())
            if w>0 and h>0:
                self.newZoomValues = PyQt5.QtCore.QRect(x,y,w,h)
            self.lastCursorPoint = event.pos()    
            self.activelyZooming = False
            if not self.zPressed and self.newZoomValues is not None:
                self.executeZoom()
        elif self.activelyDrawing:
            self.activelyDrawing = False
    
    def leaveEvent(self, event):
        """Removes cursor when mouse leaves widget. """
        if not (self.activelyZooming or self.zPressed):
            self.cursorPix.fill(self.color_picker(label=0, opacity=0)) # clear (fill with transparent)
            self.update()
            
    def resizeEvent(self, event):
        """ Triggered by resizing of the widget window. """
        self.adjustTarget()
                
    def adjustTarget(self):
        """ Computes padding needed such that aspect ratio of the image is correct. """
        self.cursorPix.fill(self.color_picker(label=0, opacity=0)) # clear (fill with transparent)
        self.update()   

        zoomWidth = self.width()/self.source.width()
        zoomHeight = self.height()/self.source.height() 
        
        # depending on aspect ratios, either pad up and down, or left and right
        if zoomWidth > zoomHeight:
            self.zoomFactor = zoomHeight
            self.padding = PyQt5.QtCore.QPoint(int((self.width() 
                            - self.source.width()*self.zoomFactor)/2), 0)
        else:
            self.zoomFactor = zoomWidth
            self.padding = PyQt5.QtCore.QPoint(0, int((self.height()
                            - self.source.height()*self.zoomFactor)/2))
            
        self.target = PyQt5.QtCore.QRect(self.padding, 
                            self.rect().bottomRight() - self.padding)
                   
    def executeZoom(self):
        """ Zooms to rectangle given by newZoomValues. """
        self.newZoomValues.translate(-self.padding)
        self.source = PyQt5.QtCore.QRect(self.newZoomValues.topLeft()/self.zoomFactor,
                self.newZoomValues.size()/self.zoomFactor)
        self.source.translate(-self.offset)
        self.source = self.source.intersected(self.imagePix.rect()) 
        self.showInfo('Zooming to ' + self.formatQRect(self.source))     
        self.offset = self.imagePix.rect().topLeft() - self.source.topLeft()
        self.adjustTarget()
        self.newZoomValues = None
    
    def resetZoom(self):
        """ Back to original zoom """
        self.source = PyQt5.QtCore.QRect(0,0,self.imagePix.width(), 
                                         self.imagePix.height())
        self.showInfo('Resetting zoom to ' + self.formatQRect(self.source))        
        self.offset = PyQt5.QtCore.QPoint(0,0)
        self.adjustTarget()        
        self.newZoomValues = None
            
    def keyPressEvent(self, event):
        if 47 < event.key() < 58:  # numbers 0 (48) to 9 (57)
            self.label = event.key() - 48
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            self.showInfo(f'Changed pen label to {self.label}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Up:  # up arrow
            self.penWidth = min(self.penWidth + 1, 50)
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            self.showInfo(f'Changed pen width to {self.penWidth}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Down:  # down arrow
            self.penWidth = max(self.penWidth - 1, 1)
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            self.showInfo(f'Changed pen width to {self.penWidth}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Left:
            self.changeImage(-1)
        elif event.key() == PyQt5.QtCore.Qt.Key_Right:
            self.changeImage(1)
        elif event.key() == PyQt5.QtCore.Qt.Key_S:  # s
            self.saveOutcome()
        elif event.key() == PyQt5.QtCore.Qt.Key_O:  # o
            self.overlay = (self.overlay + 1) % len(self.overlays)
            self.update()
            self.showInfo(f'Changed overlay to {self.overlays[self.overlay]}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Z:  # z
            if not self.zPressed:
                self.showInfo('Zooming enabled')
                self.zPressed = True
                self.cursorPix.fill(self.color_picker(label=0, opacity=0))
                self.update()
        elif event.key() == PyQt5.QtCore.Qt.Key_H:  # h
            if not self.hPressed:
                self.hPressed = True
                self.showHelp()
        elif event.key() in (PyQt5.QtCore.Qt.Key_Q, PyQt5.QtCore.Qt.Key_Escape):
            self.close()
        self.setTitle()
        
    def keyReleaseEvent(self, event):
        if event.key()==PyQt5.QtCore.Qt.Key_Z: # z
            if not self.activelyZooming:
                self.drawCursorPoint(self.lastCursorPoint)
                if self.newZoomValues is None:
                    self.resetZoom()
                else:
                    self.executeZoom()                       
                self.update()
            self.zPressed = False
        elif event.key()==PyQt5.QtCore.Qt.Key_H: # h
            self.hideText()
            self.hPressed = False
            
    def saveOutcome(self, show_message=True):
        '''
        Saves the annotation to saveAddress. If there is no visible annotation,
        any existing file at saveAddress is deleted instead. Returns True if
        a file was saved, False otherwise.

        Parameters
        ----------
        show_message : if True, shows an on-screen confirmation message.

        '''
        if not self.annotationDirty and not self.hasVisibleAnnotation():
            existing_file = Path(self.saveAddress)
            if existing_file.exists():
                existing_file.unlink()
            return False

        if not self.hasVisibleAnnotation():
            existing_file = Path(self.saveAddress)
            if existing_file.exists():
                existing_file.unlink()
            self.annotationDirty = False
            return False

        self.annotationPix.save(self.saveAddress)
        self.annotationDirty = False
        if show_message:
            self.showInfo(f'Saved annotations as {self.saveAddress}')
        return True
        
    # colors associated with different labels
    colors = [
        [0, 0, 0], # background, transparency is always drawn with black
        [255, 0, 0], # label 1
        [0, 191, 0], # label 2
        [0, 0, 255], # etc
        [255, 127, 0],
        [0, 255, 191],
        [127, 0, 255],
        [191, 255, 0],
        [0, 127, 255],
        [255, 64, 191]] 

    @classmethod
    def color_picker(cls, label, opacity):
        """ Pen colors given for a label number. """
        opacity_value = int(opacity*255)
        color = PyQt5.QtGui.QColor(cls.colors[label][0], cls.colors[label][1], 
                cls.colors[label][2], opacity_value)
        return(color)
    
    @staticmethod
    def formatQRect(rect):
        coords =  rect.getCoords()
        s = f'({coords[0]},{coords[1]})--({coords[2]},{coords[3]})'
        return(s)     
    
    def closeEvent(self, event):
        if self.currentImagePath is not None:
            self.saveOutcome(show_message=False)
        event.accept()
        super().closeEvent(event)
 
    
def annotate(image):
    return annotate_grayscale(image)


def _ensure_qt_app():
    app = PyQt5.QtWidgets.QApplication.instance()
    created_app = False
    if app is None:
        app = PyQt5.QtWidgets.QApplication([])
        created_app = True
    # Ensure GUI loops created by this module terminate when the annotator closes.
    app.setQuitOnLastWindowClosed(True)
    return app, created_app


def _run_annotator(ex, created_app=False):
    app = PyQt5.QtWidgets.QApplication.instance()

    ex.show()
    if created_app and app is not None:
        app.exec()
    return ex


def annotate_grayscale(image):
    _, created_app = _ensure_qt_app()
    ex = Annotator.fromGrayscale(image)
    return _run_annotator(ex, created_app)


def annotate_filename(filename):
    _, created_app = _ensure_qt_app()
    ex = Annotator.fromFilename(filename)
    return _run_annotator(ex, created_app)


def annotate_folder(foldername):
    _, created_app = _ensure_qt_app()
    ex = Annotator.fromFolder(foldername)
    return _run_annotator(ex, created_app)


def annotate_rgba(rgba):
    _, created_app = _ensure_qt_app()
    ex = Annotator.fromRgba(rgba)
    return _run_annotator(ex, created_app)

    
if __name__ == '__main__':
    
    '''
    For use from command-line. 
    '''
       
    if len(sys.argv)<2:
        print('Usage: $ python annotator.py image_filename_or_folder')
    else:
        filename = sys.argv[1]
        if Path(filename).is_dir():
            annotate_folder(filename)
        else:
            annotate_filename(filename)
    
        #app.quit(), not needed? exec starts the loop which quits when the last top widget is closed  
        #sys.exit(), not needed?  
    
    
    
    