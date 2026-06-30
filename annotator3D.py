#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Simple 3D volume annotator.

This module contains the Annotator3D class. Annotator3D is a widget that
allows the user to place annotations on top of slices of a 3D numpy array.

Use:
    from annotator3D import annotate_volume
    annotations = annotate_volume(volume)
    annotations = annotate_volume(volume, save_address='annotations3d.npy')

When a volume is loaded, an annotation volume of the same shape is created with
dtype uint8 unless an existing annotation_volume is supplied.

By default, annotate_volume returns the 3D annotation array and does not save
anything. If save_address is given, the annotation volume is also written to
that .npy file when the annotator closes or when S is pressed.

Controls are similar to the 2D annotator:
- Left / Right arrow: previous / next slice in volume[n]
- D: change slicing direction
- Mouse drag: draw annotation on current slice
- 1..9: pen label
- 0: eraser
- Up / Down: pen width
- O: overlay mode
- Z: zoom mode
- S: save annotation volume (.npy) when save_address is set
"""

import numpy as np

import PyQt5.QtCore
import PyQt5.QtWidgets
import PyQt5.QtGui


class Annotator3D(PyQt5.QtWidgets.QWidget):

    colors = [
        [0, 0, 0],
        [255, 0, 0],
        [0, 191, 0],
        [0, 0, 255],
        [255, 127, 0],
        [0, 255, 191],
        [127, 0, 255],
        [191, 255, 0],
        [0, 127, 255],
        [255, 64, 191],
    ]

    sliceAxisFrameColors = {
        0: PyQt5.QtGui.QColor(255, 0, 0),
        1: PyQt5.QtGui.QColor(0, 191, 0),
        2: PyQt5.QtGui.QColor(0, 0, 255),
    }
    frameWidthPx = 5

    helpText = (
        '<i>Help for annotator3D</i> <br>'
        '<b>KEYBOARD COMMANDS:</b> <br>'
        '&nbsp; &nbsp; <b>1</b> to <b>9</b> changes pen label (L) <br>'
        '&nbsp; &nbsp; <b>0</b> eraser mode <br>'
        '&nbsp; &nbsp; <b>&uarr;</b> and <b>&darr;</b> changes pen width (W) <br>'
        '&nbsp; &nbsp; <b>&larr;</b> and <b>&rarr;</b> changes slice index <br>'
        '&nbsp; &nbsp; <b>D</b> held changes slicing direction, picks slice at cursor <br>'
        '&nbsp; &nbsp; <b>O</b> changes overlay <br>'
        '&nbsp; &nbsp; <b>Z</b> held down enables zoom <br>'
        '&nbsp; &nbsp; <b>Z</b> pressed resets zoom <br>'
        '&nbsp; &nbsp; <b>S</b> saves annotation volume <br>'
        '&nbsp; &nbsp; <b>H</b> shows this help <br>'
        '<b>MOUSE DRAG:</b> <br>'
        '&nbsp; &nbsp; Draws annotation <br>'
        '&nbsp; &nbsp; Zooms when zoom enabled'
    )

    cursorWarpBlockedText = (
        '<i>Cursor movement permission required</i> <br>'
        'annotator3D could not move the system cursor programmatically. <br>'
        '<b>To fix this on macOS:</b> <br>'
        '&nbsp; &nbsp; 1. Open System Settings &#8594; Privacy &amp; Security &#8594; Accessibility <br>'
        '&nbsp; &nbsp; 2. Enable permission for the app launching Python (Terminal, Spyder, or VS Code) <br>'
        '&nbsp; &nbsp; 3. Restart that app and relaunch annotator3D <br>'
        '<b>Press X to dismiss this message.</b>'
    )

    @classmethod
    def introText(cls, rich=True):
        if rich:
            return '<i>Starting annotator3D</i> <br> For help, hit <b>H</b>'
        return "Starting annotator3D. For help, hit 'H'."

    def __init__(self, size=None):
        super().__init__()

        if size is None:
            size = PyQt5.QtCore.QSize(256, 256)
        elif type(size) is tuple:
            size = PyQt5.QtCore.QSize(size[0], size[1])

        # Pixmap layers
        self.imagePix = PyQt5.QtGui.QPixmap(size.width(), size.height())
        self.imagePix.fill(self.color_picker(label=0, opacity=0))
        self.annotationPix = PyQt5.QtGui.QPixmap(self.imagePix.width(), self.imagePix.height())
        self.annotationPix.fill(self.color_picker(label=0, opacity=0))
        self.annotationLabelPix = PyQt5.QtGui.QPixmap(self.imagePix.width(), self.imagePix.height())
        self.annotationLabelPix.fill(self.color_picker(label=0, opacity=0))
        self.cursorPix = PyQt5.QtGui.QPixmap(self.imagePix.width(), self.imagePix.height())
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))

        # Volume state
        self.volume = None
        self.displayVolume = None
        self.annotationVolume = None
        self.sliceAxis = 0
        self.sliceIndex = 0
        self.numSlices = 0
        self.volumeDirty = False

        # Drawing state
        self.label = 1
        self.penWidth = 9
        self.lastDrawPoint = PyQt5.QtCore.QPoint()
        self.lastCursorPoint = PyQt5.QtCore.QPoint()
        self.annotationDirty = False

        # Display state
        self.saveAddress = 'annotations3d.npy'
        self.overlay = 0
        self.overlays = {0: 'both', 1: 'annotation', 2: 'image'}
        self.annotationOpacity = 0.5
        self.cursorOpacity = 0.5
        self.zoomOpacity = 0.5
        self.setTitle()
        self.setCursor(PyQt5.QtGui.QCursor(PyQt5.QtCore.Qt.CrossCursor))
        self.setMouseTracking(True)

        # Coordinate transforms
        self.zoomFactor = 1
        self.padding = PyQt5.QtCore.QPoint(0, 0)
        self.target = PyQt5.QtCore.QRect(0, 0, self.width(), self.height())
        self.source = PyQt5.QtCore.QRect(0, 0, self.imagePix.width(), self.imagePix.height())
        self.offset = PyQt5.QtCore.QPoint(0, 0)

        # Interaction flags
        self.zPressed = False
        self.dPressed = False
        self.directionSelectionActive = False
        self.activelyZooming = False
        self.activelyDrawing = False
        self.newZoomValues = None

        # Overlay text
        self.textField = PyQt5.QtWidgets.QLabel(self)
        self.textField.setStyleSheet("background-color: rgba(191,191,191,191)")
        self.textField.setTextFormat(PyQt5.QtCore.Qt.RichText)
        self.textField.resize(0, 0)
        self.textField.move(10, 10)
        self.hPressed = False
        self.persistentTextVisible = False
        self.cursorWarpTestDone = False
        self.textField.setAttribute(PyQt5.QtCore.Qt.WA_TransparentForMouseEvents)

        self.timer = PyQt5.QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hideTransientText)

        initial_zoom = min(2000 / max(self.imagePix.width(), 4 * self.imagePix.height() / 3), 1)
        self.resize(int(initial_zoom * self.imagePix.width()), int(initial_zoom * self.imagePix.height()))

        self.showInfo(self.introText(), 5000)
        print(self.introText(False))

    def showEvent(self, event):
        super().showEvent(event)
        if not self.cursorWarpTestDone:
            self.cursorWarpTestDone = True
            PyQt5.QtCore.QTimer.singleShot(0, self.runStartupCursorWarpTest)

    @classmethod
    def fromVolume(cls, volume, annotation_volume=None, save_address=None):
        """Create an annotator for a 3D volume with shape (N, H, W)."""
        if not isinstance(volume, np.ndarray):
            raise ValueError('volume must be a numpy array')
        if volume.ndim != 3:
            raise ValueError('volume must be a 3D numpy array with shape (N, H, W)')
        if volume.shape[0] == 0:
            raise ValueError('volume cannot be empty')

        h, w = volume.shape[1], volume.shape[2]
        annotator = Annotator3D((w, h))
        annotator.setVolume(volume, annotation_volume=annotation_volume, save_address=save_address)
        return annotator

    def setVolume(self, volume, annotation_volume=None, save_address=None):
        """Load a 3D volume and initialize the backing annotation volume.

        Parameters
        ----------
        volume : numpy.ndarray
            Input array with shape (N, H, W).
        annotation_volume : numpy.ndarray or None
            Existing uint8-compatible label volume with the same shape as
            volume. If None, a zero-filled uint8 annotation volume is created.
        save_address : str or None
            Optional output path used when the user saves with S or closes the
            annotator.

        """
        self.volume = np.asarray(volume)
        if self.volume.ndim != 3:
            raise ValueError('volume must be 3D')

        self.displayVolume = self.to_uint8(self.volume)
        if annotation_volume is None:
            self.annotationVolume = np.zeros(self.volume.shape, dtype=np.uint8)
        else:
            annotation_volume = np.asarray(annotation_volume)
            if annotation_volume.shape != self.volume.shape:
                raise ValueError('annotation_volume shape must match volume shape')
            self.annotationVolume = annotation_volume.astype(np.uint8).copy()

        self.numSlices = self.volume.shape[0]
        self.sliceAxis = 0
        self.sliceIndex = self.numSlices // 2
        self.volumeDirty = False

        if save_address is not None:
            self.saveAddress = save_address

        self.loadSliceAtIndex(self.sliceIndex, save_current=False)

    def setTitle(self):
        axis_name = ['Z', 'Y', 'X'][self.sliceAxis]
        title = f'L:{self.label}, W:{self.penWidth}, O:{self.overlays[self.overlay]}'
        if self.numSlices > 0:
            title += f', {axis_name}:{self.sliceIndex + 1}/{self.numSlices}'
        self.setWindowTitle(title)

    def volumeSlice(self, vol, axis, index):
        slice_spec = [slice(None)] * vol.ndim
        slice_spec[axis] = slice(index, index + 1)
        return vol[tuple(slice_spec)].squeeze(axis=axis)

    def setVolumeSlice(self, vol, axis, index, values):
        slice_spec = [slice(None)] * vol.ndim
        slice_spec[axis] = slice(index, index + 1)
        vol[tuple(slice_spec)] = np.expand_dims(values, axis=axis)

    def updateSliceCount(self):
        if self.volume is None:
            self.numSlices = 0
            return
        self.numSlices = self.volume.shape[self.sliceAxis]

    def setImage(self, image_pix, preserve_view=False):
        previous_source = PyQt5.QtCore.QRect(self.source)
        previous_offset = PyQt5.QtCore.QPoint(self.offset)
        preserve_view = preserve_view and image_pix.size() == self.imagePix.size()

        self.imagePix = image_pix
        self.annotationPix = PyQt5.QtGui.QPixmap(self.imagePix.size())
        self.annotationPix.fill(self.color_picker(label=0, opacity=0))
        self.annotationLabelPix = PyQt5.QtGui.QPixmap(self.imagePix.size())
        self.annotationLabelPix.fill(self.color_picker(label=0, opacity=0))
        self.cursorPix = PyQt5.QtGui.QPixmap(self.imagePix.size())
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))

        self.lastDrawPoint = PyQt5.QtCore.QPoint()
        self.lastCursorPoint = PyQt5.QtCore.QPoint()
        self.activelyZooming = False
        self.activelyDrawing = False
        self.newZoomValues = None
        self.annotationDirty = False

        if preserve_view:
            self.source = previous_source.intersected(self.imagePix.rect())
            self.offset = previous_offset
        else:
            self.source = PyQt5.QtCore.QRect(0, 0, self.imagePix.width(), self.imagePix.height())
            self.offset = PyQt5.QtCore.QPoint(0, 0)
        self.adjustTarget()

    @classmethod
    def to_uint8(cls, volume):
        arr = np.asarray(volume)
        if arr.dtype == np.uint8:
            return arr.copy()

        if arr.size == 0:
            return arr.astype(np.uint8)

        arr = arr.astype(np.float32)
        vmin = float(np.min(arr))
        vmax = float(np.max(arr))
        if vmax <= vmin:
            return np.zeros(arr.shape, dtype=np.uint8)

        scaled = (arr - vmin) * (255.0 / (vmax - vmin))
        return np.clip(scaled, 0, 255).astype(np.uint8)

    @staticmethod
    def grayscale_to_pixmap(gray2d):
        gray = np.ascontiguousarray(gray2d)
        qimage = PyQt5.QtGui.QImage(
            gray.data,
            gray.shape[1],
            gray.shape[0],
            gray.strides[0],
            PyQt5.QtGui.QImage.Format_Grayscale8,
        ).copy()
        return PyQt5.QtGui.QPixmap.fromImage(qimage)

    def annotation_labels_to_pixmap(self, labels2d):
        labels = np.asarray(labels2d, dtype=np.uint8)
        h, w = labels.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        alpha_value = int(self.annotationOpacity * 255)

        for label in range(1, 10):
            mask = labels == label
            if not np.any(mask):
                continue
            rgba[mask, 0] = self.colors[label][0]
            rgba[mask, 1] = self.colors[label][1]
            rgba[mask, 2] = self.colors[label][2]
            rgba[mask, 3] = alpha_value

        rgba = np.ascontiguousarray(rgba)
        qimage = PyQt5.QtGui.QImage(
            rgba.data,
            rgba.shape[1],
            rgba.shape[0],
            rgba.strides[0],
            PyQt5.QtGui.QImage.Format_RGBA8888,
        ).copy()
        return PyQt5.QtGui.QPixmap.fromImage(qimage)

    def label_values_to_pixmap(self, labels2d):
        labels = np.asarray(labels2d, dtype=np.uint8)
        h, w = labels.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        mask = labels > 0
        rgba[mask, 0] = labels[mask]
        rgba[mask, 1] = labels[mask]
        rgba[mask, 2] = labels[mask]
        rgba[mask, 3] = 255

        rgba = np.ascontiguousarray(rgba)
        qimage = PyQt5.QtGui.QImage(
            rgba.data,
            rgba.shape[1],
            rgba.shape[0],
            rgba.strides[0],
            PyQt5.QtGui.QImage.Format_RGBA8888,
        ).copy()
        return PyQt5.QtGui.QPixmap.fromImage(qimage)

    def labels_from_annotation_pixmap(self):
        image = self.annotationLabelPix.toImage().convertToFormat(PyQt5.QtGui.QImage.Format_RGBA8888)
        h = image.height()
        w = image.width()

        labels = np.zeros((h, w), dtype=np.uint8)
        for y_coord in range(h):
            for x_coord in range(w):
                color = image.pixelColor(x_coord, y_coord)
                if color.alpha() > 0:
                    labels[y_coord, x_coord] = color.red()

        return labels

    def saveCurrentSliceToVolume(self):
        if self.annotationVolume is None or self.numSlices == 0:
            return
        self.setVolumeSlice(
            self.annotationVolume,
            self.sliceAxis,
            self.sliceIndex,
            self.labels_from_annotation_pixmap(),
        )
        self.annotationDirty = False

    def loadSliceAtIndex(self, index, save_current=True):
        if self.displayVolume is None or self.numSlices == 0:
            return
        if not 0 <= index < self.numSlices:
            return

        if save_current:
            self.saveCurrentSliceToVolume()

        self.sliceIndex = index
        image_slice = self.volumeSlice(self.displayVolume, self.sliceAxis, self.sliceIndex)
        image_pix = self.grayscale_to_pixmap(image_slice)
        self.setImage(image_pix, preserve_view=True)

        labels_slice = self.volumeSlice(self.annotationVolume, self.sliceAxis, self.sliceIndex)
        self.annotationPix = self.annotation_labels_to_pixmap(labels_slice)
        self.annotationLabelPix = self.label_values_to_pixmap(labels_slice)

        cursor_point = self.mapFromGlobal(PyQt5.QtGui.QCursor.pos())
        if self.rect().contains(cursor_point):
            self.lastCursorPoint = cursor_point
            self.drawCursorPoint(self.lastCursorPoint)
        else:
            self.cursorPix.fill(self.color_picker(label=0, opacity=0))

        self.setTitle()
        self.update()

    def changeSlice(self, step):
        if self.numSlices == 0:
            return
        new_index = self.sliceIndex + step
        new_index = max(0, min(new_index, self.numSlices - 1))
        if new_index == self.sliceIndex:
            return
        self.loadSliceAtIndex(new_index)

    def changeSliceAxis(self):
        self.changeSliceAxisToIndex((self.sliceAxis + 1) % 3, None)

    def changeSliceAxisToIndex(self, axis, index=None):
        if self.volume is None:
            return
        if self.annotationDirty:
            self.saveCurrentSliceToVolume()

        previous_zoom = self.zoomFactor
        previous_window_size = PyQt5.QtCore.QSize(self.size())
        previous_center_ratio = self.currentSourceCenterRatio()

        self.sliceAxis = int(axis) % 3
        self.updateSliceCount()
        if self.numSlices == 0:
            return
        if index is None:
            self.sliceIndex = self.numSlices // 2
        else:
            self.sliceIndex = max(0, min(int(index), self.numSlices - 1))
        self.loadSliceAtIndex(self.sliceIndex, save_current=False)

        target_center = self.sourcePointFromRatio(previous_center_ratio)
        self.applyZoomLevel(previous_zoom, center_source_point=target_center)
        if self.size() != previous_window_size:
            self.resize(previous_window_size)

    def currentSourceCenterRatio(self):
        if self.imagePix.width() <= 1 or self.imagePix.height() <= 1:
            return 0.5, 0.5

        center_x = self.source.center().x()
        center_y = self.source.center().y()
        ratio_x = center_x / (self.imagePix.width() - 1)
        ratio_y = center_y / (self.imagePix.height() - 1)
        ratio_x = max(0.0, min(1.0, ratio_x))
        ratio_y = max(0.0, min(1.0, ratio_y))
        return ratio_x, ratio_y

    def sourcePointFromRatio(self, ratio):
        ratio_x, ratio_y = ratio
        width = max(1, self.imagePix.width())
        height = max(1, self.imagePix.height())

        x_coord = int(round(ratio_x * (width - 1)))
        y_coord = int(round(ratio_y * (height - 1)))
        x_coord = max(0, min(x_coord, width - 1))
        y_coord = max(0, min(y_coord, height - 1))
        return PyQt5.QtCore.QPoint(x_coord, y_coord)

    def applyZoomLevel(self, zoom_level, center_source_point=None):
        if zoom_level is None or zoom_level <= 0:
            self.adjustTarget()
            return

        frame_margin = max(0, int(np.ceil(self.frameWidthPx)))
        available_width = max(1, self.width() - 2 * frame_margin)
        available_height = max(1, self.height() - 2 * frame_margin)

        desired_width = int(round(available_width / zoom_level))
        desired_height = int(round(available_height / zoom_level))
        desired_width = max(1, min(desired_width, self.imagePix.width()))
        desired_height = max(1, min(desired_height, self.imagePix.height()))

        if center_source_point is None:
            center_source_point = self.imagePix.rect().center()

        left = int(round(center_source_point.x() - desired_width / 2))
        top = int(round(center_source_point.y() - desired_height / 2))
        left = max(0, min(left, self.imagePix.width() - desired_width))
        top = max(0, min(top, self.imagePix.height() - desired_height))

        self.source = PyQt5.QtCore.QRect(left, top, desired_width, desired_height)
        self.offset = self.imagePix.rect().topLeft() - self.source.topLeft()
        self.adjustTarget()

    @staticmethod
    def displayAxesForSliceAxis(axis):
        # Returns (vertical axis, horizontal axis) shown in the current 2D slice view.
        axis_map = {
            0: (1, 2),
            1: (0, 2),
            2: (0, 1),
        }
        return axis_map[int(axis) % 3]

    def clampPointToTarget(self, point):
        if self.target.width() <= 0 or self.target.height() <= 0:
            return None
        clamped_x = max(self.target.left(), min(point.x(), self.target.right()))
        clamped_y = max(self.target.top(), min(point.y(), self.target.bottom()))
        return PyQt5.QtCore.QPoint(clamped_x, clamped_y)

    def widgetPointToSourcePoint(self, point):
        clamped = self.clampPointToTarget(point)
        if clamped is None:
            return None

        target_w = max(1, self.target.width() - 1)
        target_h = max(1, self.target.height() - 1)
        source_w = max(1, self.source.width() - 1)
        source_h = max(1, self.source.height() - 1)

        x_ratio = (clamped.x() - self.target.left()) / target_w
        y_ratio = (clamped.y() - self.target.top()) / target_h

        source_x = self.source.left() + x_ratio * source_w
        source_y = self.source.top() + y_ratio * source_h

        source_x = int(round(source_x))
        source_y = int(round(source_y))
        source_x = max(0, min(source_x, self.imagePix.width() - 1))
        source_y = max(0, min(source_y, self.imagePix.height() - 1))
        return PyQt5.QtCore.QPoint(source_x, source_y)

    def widgetPointToVoxel(self, point):
        if self.volume is None:
            return None
        source_point = self.widgetPointToSourcePoint(point)
        if source_point is None:
            return None

        x_coord = source_point.x()
        y_coord = source_point.y()

        if self.sliceAxis == 0:
            return (self.sliceIndex, y_coord, x_coord)
        if self.sliceAxis == 1:
            return (y_coord, self.sliceIndex, x_coord)
        return (y_coord, x_coord, self.sliceIndex)

    def voxelToSourcePoint(self, voxel, axis):
        if axis == 0:
            return PyQt5.QtCore.QPoint(voxel[2], voxel[1])
        if axis == 1:
            return PyQt5.QtCore.QPoint(voxel[2], voxel[0])
        return PyQt5.QtCore.QPoint(voxel[1], voxel[0])

    def sourcePointToWidgetPoint(self, src_point):
        if self.source.width() <= 0 or self.source.height() <= 0:
            return None
        if self.target.width() <= 0 or self.target.height() <= 0:
            return None
        rel_x = (src_point.x() - self.source.left()) / self.source.width()
        rel_y = (src_point.y() - self.source.top()) / self.source.height()
        widget_x = int(self.target.left() + rel_x * self.target.width())
        widget_y = int(self.target.top() + rel_y * self.target.height())
        widget_x = max(self.target.left(), min(widget_x, self.target.right()))
        widget_y = max(self.target.top(), min(widget_y, self.target.bottom()))
        return PyQt5.QtCore.QPoint(widget_x, widget_y)

    def moveSystemCursorToWidgetPoint(self, widget_point):
        global_point = self.mapToGlobal(widget_point)
        PyQt5.QtGui.QCursor.setPos(global_point)
        # Some platforms may ignore cursor warps during key handling; retry once on next tick.
        PyQt5.QtCore.QTimer.singleShot(0, lambda gp=global_point: PyQt5.QtGui.QCursor.setPos(gp))
        # Redraw using the actual cursor hotspot position to keep cursor and pointer aligned.
        PyQt5.QtCore.QTimer.singleShot(0, lambda wp=widget_point: self.syncPointerToSystemCursor(wp))

    def syncPointerToSystemCursor(self, fallback_point=None):
        cursor_point = self.mapFromGlobal(PyQt5.QtGui.QCursor.pos())
        if self.rect().contains(cursor_point):
            self.lastCursorPoint = cursor_point
            self.drawCursorPoint(self.lastCursorPoint)
        elif fallback_point is not None:
            clamped_point = self.clampPointToTarget(fallback_point) or fallback_point
            self.lastCursorPoint = clamped_point
            self.drawCursorPoint(self.lastCursorPoint)
        else:
            self.cursorPix.fill(self.color_picker(label=0, opacity=0))
        self.update()

    def applyDirectionSelection(self):
        if self.volume is None:
            return

        voxel = self.widgetPointToVoxel(self.lastCursorPoint)
        next_axis = (self.sliceAxis + 1) % 3
        previous_zoom = self.zoomFactor
        previous_window_size = PyQt5.QtCore.QSize(self.size())
        center_widget = self.rect().center()
        if voxel is None:
            self.changeSliceAxisToIndex(next_axis, None)
            if self.size() != previous_window_size:
                self.resize(previous_window_size)
            self.lastCursorPoint = center_widget
            self.drawCursorPoint(center_widget)
            self.moveSystemCursorToWidgetPoint(center_widget)
            return

        self.changeSliceAxisToIndex(next_axis, voxel[next_axis])

        # Prioritize cursor centering by recentering the zoomed view around the selected voxel.
        new_src = self.voxelToSourcePoint(voxel, self.sliceAxis)
        self.applyZoomLevel(previous_zoom, center_source_point=new_src)
        if self.size() != previous_window_size:
            self.resize(previous_window_size)

        self.lastCursorPoint = center_widget
        self.drawCursorPoint(center_widget)
        self.moveSystemCursorToWidgetPoint(center_widget)

    def showHelp(self):
        self.timer.stop()
        if not self.persistentTextVisible:
            self.showText(self.helpText)

    def showInfo(self, text, time=1000):
        if not self.hPressed and not self.persistentTextVisible:
            self.timer.start(time)
            self.showText(text)

    def showText(self, text):
        self.textField.setText(text)
        self.textField.adjustSize()
        self.update()

    def hideText(self):
        self.textField.resize(0, 0)
        self.update()

    def hideTransientText(self):
        if not self.hPressed and not self.persistentTextVisible:
            self.hideText()

    def showPersistentText(self, text):
        self.timer.stop()
        self.persistentTextVisible = True
        self.showText(text)

    def dismissPersistentText(self):
        if self.persistentTextVisible:
            self.persistentTextVisible = False
            self.hideText()

    def _flushCursorPosition(self):
        app = PyQt5.QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents()

    def runStartupCursorWarpTest(self):
        if not self.isVisible():
            return

        original_pos = PyQt5.QtGui.QCursor.pos()
        center_global = self.mapToGlobal(self.rect().center())

        # If cursor starts exactly at center, nudge it first so movement can be verified.
        if original_pos == center_global:
            original_pos = PyQt5.QtCore.QPoint(original_pos.x() + 8, original_pos.y() + 8)
            PyQt5.QtGui.QCursor.setPos(original_pos)
            self._flushCursorPosition()

        PyQt5.QtGui.QCursor.setPos(center_global)
        self._flushCursorPosition()
        pos_after_center = PyQt5.QtGui.QCursor.pos()

        PyQt5.QtGui.QCursor.setPos(original_pos)
        self._flushCursorPosition()
        pos_after_restore = PyQt5.QtGui.QCursor.pos()

        moved_to_center = pos_after_center != original_pos
        moved_back = pos_after_restore != pos_after_center

        if not (moved_to_center and moved_back):
            self.showPersistentText(self.cursorWarpBlockedText)
            print('Cursor warp test failed: enable macOS Accessibility for launcher app.')

    def makePainter(self, pixmap, color):
        painter_scribble = PyQt5.QtGui.QPainter(pixmap)
        painter_scribble.setPen(
            PyQt5.QtGui.QPen(
                color,
                self.penWidth * self.zoomFactor,
                PyQt5.QtCore.Qt.SolidLine,
                PyQt5.QtCore.Qt.RoundCap,
                PyQt5.QtCore.Qt.RoundJoin,
            )
        )
        painter_scribble.translate(-self.offset)
        painter_scribble.translate(-0.25, -0.25)
        painter_scribble.scale(1 / self.zoomFactor, 1 / self.zoomFactor)
        painter_scribble.translate(-self.padding)
        painter_scribble.setCompositionMode(PyQt5.QtGui.QPainter.CompositionMode_Source)
        return painter_scribble

    def paintEvent(self, event):
        painter_display = PyQt5.QtGui.QPainter(self)
        painter_display.setCompositionMode(PyQt5.QtGui.QPainter.CompositionMode_SourceOver)
        if self.overlay != 1:
            painter_display.drawPixmap(self.target, self.imagePix, self.source)
        if self.overlay != 2:
            painter_display.drawPixmap(self.target, self.annotationPix, self.source)
        painter_display.drawPixmap(self.target, self.cursorPix, self.source)

        frame_color = self.sliceAxisFrameColors.get(self.sliceAxis, PyQt5.QtGui.QColor(255, 255, 255))
        half_width = self.frameWidthPx / 2.0
        frame_rect = PyQt5.QtCore.QRectF(self.target)
        frame_rect.adjust(-half_width, -half_width, half_width, half_width)
        if frame_rect.isValid() and frame_rect.width() > 0 and frame_rect.height() > 0:
            frame_pen = PyQt5.QtGui.QPen(
                frame_color,
                self.frameWidthPx,
                PyQt5.QtCore.Qt.SolidLine,
                PyQt5.QtCore.Qt.SquareCap,
                PyQt5.QtCore.Qt.MiterJoin,
            )
            frame_pen.setCosmetic(True)
            painter_display.setPen(frame_pen)
            painter_display.setBrush(PyQt5.QtCore.Qt.NoBrush)
            painter_display.drawRect(frame_rect)

        if self.directionSelectionActive:
            guide_point = self.clampPointToTarget(self.lastCursorPoint)
            if guide_point is not None:
                vertical_axis, horizontal_axis = self.displayAxesForSliceAxis(self.sliceAxis)
                horizontal_color = self.sliceAxisFrameColors.get(vertical_axis, PyQt5.QtGui.QColor(255, 255, 255))
                vertical_color = self.sliceAxisFrameColors.get(horizontal_axis, PyQt5.QtGui.QColor(255, 255, 255))

                line_width = max(2, self.frameWidthPx - 1)

                horizontal_pen = PyQt5.QtGui.QPen(
                    horizontal_color,
                    line_width,
                    PyQt5.QtCore.Qt.SolidLine,
                    PyQt5.QtCore.Qt.SquareCap,
                    PyQt5.QtCore.Qt.MiterJoin,
                )
                horizontal_pen.setCosmetic(True)
                painter_display.setPen(horizontal_pen)
                painter_display.drawLine(
                    self.target.left(),
                    guide_point.y(),
                    self.target.right(),
                    guide_point.y(),
                )

                vertical_pen = PyQt5.QtGui.QPen(
                    vertical_color,
                    line_width,
                    PyQt5.QtCore.Qt.SolidLine,
                    PyQt5.QtCore.Qt.SquareCap,
                    PyQt5.QtCore.Qt.MiterJoin,
                )
                vertical_pen.setCosmetic(True)
                painter_display.setPen(vertical_pen)
                painter_display.drawLine(
                    guide_point.x(),
                    self.target.top(),
                    guide_point.x(),
                    self.target.bottom(),
                )

    def drawCursorPoint(self, point):
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))
        painter_scribble = self.makePainter(self.cursorPix, self.color_picker(self.label, self.cursorOpacity))
        painter_scribble.drawPoint(point)

    def drawAnnotationPoint(self, point):
        visible_painter = self.makePainter(
            self.annotationPix,
            self.color_picker(self.label, (self.label > 0) * self.annotationOpacity),
        )
        visible_painter.drawPoint(point)

        label_painter = self.makePainter(
            self.annotationLabelPix,
            PyQt5.QtGui.QColor(self.label, self.label, self.label, 255 if self.label > 0 else 0),
        )
        label_painter.drawPoint(point)

    def drawAnnotationLine(self, start_point, end_point):
        visible_painter = self.makePainter(
            self.annotationPix,
            self.color_picker(self.label, (self.label > 0) * self.annotationOpacity),
        )
        visible_painter.drawLine(start_point, end_point)

        label_painter = self.makePainter(
            self.annotationLabelPix,
            PyQt5.QtGui.QColor(self.label, self.label, self.label, 255 if self.label > 0 else 0),
        )
        label_painter.drawLine(start_point, end_point)

    def mousePressEvent(self, event):
        if event.button() == PyQt5.QtCore.Qt.LeftButton:
            if self.directionSelectionActive:
                self.lastCursorPoint = self.clampPointToTarget(event.pos()) or event.pos()
            elif self.zPressed:
                self.cursorPix.fill(self.color_picker(label=0, opacity=0))
                self.lastCursorPoint = event.pos()
                self.activelyZooming = True
                self.newZoomValues = None
            else:
                self.drawAnnotationPoint(event.pos())
                self.lastDrawPoint = event.pos()
                self.activelyDrawing = True
                self.annotationDirty = True
                self.volumeDirty = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.activelyZooming:
            self.cursorPix.fill(self.color_picker(label=0, opacity=0))
            painter_scribble = self.makePainter(self.cursorPix, self.color_picker(0, self.zoomOpacity))
            x_coord = min(self.lastCursorPoint.x(), event.x())
            y_coord = min(self.lastCursorPoint.y(), event.y())
            width = abs(self.lastCursorPoint.x() - event.x())
            height = abs(self.lastCursorPoint.y() - event.y())
            painter_scribble.fillRect(x_coord, y_coord, width, height, self.color_picker(0, self.zoomOpacity))
        elif self.directionSelectionActive:
            self.lastCursorPoint = self.clampPointToTarget(event.pos()) or event.pos()
        else:
            if self.activelyDrawing:
                self.drawAnnotationLine(self.lastDrawPoint, event.pos())
                self.lastDrawPoint = event.pos()
                self.annotationDirty = True
                self.volumeDirty = True
            if not self.zPressed:
                self.drawCursorPoint(event.pos())
            self.lastCursorPoint = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.activelyZooming:
            x_coord = min(self.lastCursorPoint.x(), event.x())
            y_coord = min(self.lastCursorPoint.y(), event.y())
            width = abs(self.lastCursorPoint.x() - event.x())
            height = abs(self.lastCursorPoint.y() - event.y())
            if width > 0 and height > 0:
                self.newZoomValues = PyQt5.QtCore.QRect(x_coord, y_coord, width, height)
            self.lastCursorPoint = event.pos()
            self.activelyZooming = False
            if not self.zPressed and self.newZoomValues is not None:
                self.executeZoom()
        elif self.activelyDrawing:
            self.activelyDrawing = False

    def leaveEvent(self, event):
        if not (self.activelyZooming or self.zPressed or self.directionSelectionActive):
            self.cursorPix.fill(self.color_picker(label=0, opacity=0))
            self.update()

    def resizeEvent(self, event):
        self.adjustTarget()

    def adjustTarget(self):
        self.cursorPix.fill(self.color_picker(label=0, opacity=0))
        self.update()

        frame_margin = max(0, int(np.ceil(self.frameWidthPx)))
        available_width = max(1, self.width() - 2 * frame_margin)
        available_height = max(1, self.height() - 2 * frame_margin)

        zoom_width = available_width / self.source.width()
        zoom_height = available_height / self.source.height()

        if zoom_width > zoom_height:
            self.zoomFactor = zoom_height
            self.padding = PyQt5.QtCore.QPoint(
                int((available_width - self.source.width() * self.zoomFactor) / 2) + frame_margin,
                frame_margin,
            )
        else:
            self.zoomFactor = zoom_width
            self.padding = PyQt5.QtCore.QPoint(
                frame_margin,
                int((available_height - self.source.height() * self.zoomFactor) / 2) + frame_margin,
            )

        self.target = PyQt5.QtCore.QRect(
            self.padding,
            PyQt5.QtCore.QPoint(self.width() - 1 - self.padding.x(), self.height() - 1 - self.padding.y()),
        )

    def executeZoom(self):
        self.newZoomValues.translate(-self.padding)
        self.source = PyQt5.QtCore.QRect(
            self.newZoomValues.topLeft() / self.zoomFactor,
            self.newZoomValues.size() / self.zoomFactor,
        )
        self.source.translate(-self.offset)
        self.source = self.source.intersected(self.imagePix.rect())
        self.showInfo('Zooming to ' + self.formatQRect(self.source))
        self.offset = self.imagePix.rect().topLeft() - self.source.topLeft()
        self.adjustTarget()
        self.newZoomValues = None

    def resetZoom(self):
        self.source = PyQt5.QtCore.QRect(0, 0, self.imagePix.width(), self.imagePix.height())
        self.showInfo('Resetting zoom to ' + self.formatQRect(self.source))
        self.offset = PyQt5.QtCore.QPoint(0, 0)
        self.adjustTarget()
        self.newZoomValues = None

    def keyPressEvent(self, event):
        repeatable_keys = {
            PyQt5.QtCore.Qt.Key_Up,
            PyQt5.QtCore.Qt.Key_Down,
            PyQt5.QtCore.Qt.Key_Left,
            PyQt5.QtCore.Qt.Key_Right,
        }
        is_repeat = event.isAutoRepeat()
        if is_repeat and event.key() not in repeatable_keys:
            return
        if self.persistentTextVisible and event.key() == PyQt5.QtCore.Qt.Key_X:
            self.dismissPersistentText()
            return
        if 47 < event.key() < 58:
            self.label = event.key() - 48
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            self.showInfo(f'Changed pen label to {self.label}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Up:
            self.penWidth = min(self.penWidth + 1, 50)
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            if not is_repeat:
                self.showInfo(f'Changed pen width to {self.penWidth}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Down:
            self.penWidth = max(self.penWidth - 1, 1)
            self.drawCursorPoint(self.lastCursorPoint)
            self.update()
            if not is_repeat:
                self.showInfo(f'Changed pen width to {self.penWidth}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Left:
            self.changeSlice(-1)
        elif event.key() == PyQt5.QtCore.Qt.Key_Right:
            self.changeSlice(1)
        elif event.key() == PyQt5.QtCore.Qt.Key_D:
            if not self.dPressed and not self.zPressed and not self.activelyZooming:
                self.dPressed = True
                self.directionSelectionActive = True
                self.lastCursorPoint = self.mapFromGlobal(PyQt5.QtGui.QCursor.pos())
                self.cursorPix.fill(self.color_picker(label=0, opacity=0))
                self.update()
        elif event.key() == PyQt5.QtCore.Qt.Key_S:
            self.saveOutcome()
        elif event.key() == PyQt5.QtCore.Qt.Key_O:
            self.overlay = (self.overlay + 1) % len(self.overlays)
            self.update()
            self.showInfo(f'Changed overlay to {self.overlays[self.overlay]}')
        elif event.key() == PyQt5.QtCore.Qt.Key_Z:
            if not self.zPressed:
                self.showInfo('Zooming enabled')
                self.zPressed = True
                self.cursorPix.fill(self.color_picker(label=0, opacity=0))
                self.update()
        elif event.key() == PyQt5.QtCore.Qt.Key_H:
            if not self.hPressed and not self.persistentTextVisible:
                self.hPressed = True
                self.showHelp()
        elif event.key() in (PyQt5.QtCore.Qt.Key_Q, PyQt5.QtCore.Qt.Key_Escape):
            self.close()
        self.setTitle()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        if event.key() == PyQt5.QtCore.Qt.Key_Z:
            if not self.activelyZooming:
                self.drawCursorPoint(self.lastCursorPoint)
                if self.newZoomValues is None:
                    self.resetZoom()
                else:
                    self.executeZoom()
                self.update()
            self.zPressed = False
        elif event.key() == PyQt5.QtCore.Qt.Key_D:
            self.dPressed = False
            self.directionSelectionActive = False
            self.applyDirectionSelection()
            self.update()
        elif event.key() == PyQt5.QtCore.Qt.Key_H:
            self.hPressed = False
            self.hideTransientText()

    def saveOutcome(self, show_message=True):
        if self.annotationDirty:
            self.saveCurrentSliceToVolume()

        if self.annotationVolume is None:
            return False

        if self.saveAddress is not None:
            np.save(self.saveAddress, self.annotationVolume)
        self.volumeDirty = False
        if show_message:
            if self.saveAddress is None:
                self.showInfo('Annotation volume updated')
            else:
                self.showInfo(f'Saved annotations as {self.saveAddress}')
        return True

    @classmethod
    def color_picker(cls, label, opacity):
        opacity_value = int(opacity * 255)
        color = PyQt5.QtGui.QColor(
            cls.colors[label][0],
            cls.colors[label][1],
            cls.colors[label][2],
            opacity_value,
        )
        return color

    @staticmethod
    def formatQRect(rect):
        coords = rect.getCoords()
        return f'({coords[0]},{coords[1]})--({coords[2]},{coords[3]})'

    def closeEvent(self, event):
        if self.annotationDirty:
            self.saveCurrentSliceToVolume()
        if self.volumeDirty:
            self.saveOutcome(show_message=False)
        event.accept()
        super().closeEvent(event)


def _ensure_qt_app():
    app = PyQt5.QtWidgets.QApplication.instance()
    created_app = False
    if app is None:
        app = PyQt5.QtWidgets.QApplication([])
        created_app = True
    app.setQuitOnLastWindowClosed(True)
    return app, created_app


def _run_annotator(ex, created_app=False):
    app = PyQt5.QtWidgets.QApplication.instance()
    ex.show()
    if created_app and app is not None:
        app.exec()
    return ex


def annotate_volume(volume, annotation_volume=None, save_address=None):
    """Annotate a 3D volume and return the label volume.

    Parameters
    ----------
    volume : numpy.ndarray
        Input array with shape (N, H, W).
    annotation_volume : numpy.ndarray or None
        Optional existing annotation labels with the same shape as volume.
    save_address : str or None
        Optional .npy path. If provided, annotations are also saved there when
        the user presses S or closes the annotator.

    Returns
    -------
    numpy.ndarray
        uint8 annotation volume with the same shape as volume.

    """
    _, created_app = _ensure_qt_app()
    ex = Annotator3D.fromVolume(volume, annotation_volume=annotation_volume, save_address=save_address)
    _run_annotator(ex, created_app)
    return ex.annotationVolume.copy()
