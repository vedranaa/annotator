"""Minimal test for cursor movement behavior on macOS.

Controls:
- C: warp cursor to image center
- Arrow keys: move cursor relatively by 10 pixels
- Shift + Arrow keys: move cursor relatively by 40 pixels
- V: warp cursor to image center via macOS CoreGraphics
- B: move cursor relatively by +10 px in X via macOS CoreGraphics
- N: move cursor to center via CGEventPost
- M: move cursor relatively by +10 px in X via CGEventPost
- P: open Accessibility settings and print trust status
"""

import ctypes
import subprocess
import sys
import numpy as np
import PyQt5.QtCore
import PyQt5.QtGui
import PyQt5.QtWidgets


class TestWindow(PyQt5.QtWidgets.QLabel):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("C=center warp, arrows=relative move")
        self.setFixedSize(400, 400)
        self.setFocusPolicy(PyQt5.QtCore.Qt.StrongFocus)

        self._cg = None
        self._cg_point_type = None
        self._k_cg_event_mouse_moved = None
        self._k_cg_hid_event_tap = None
        self._setup_core_graphics()

        # Random grayscale image as pixmap
        data = np.random.randint(0, 255, (400, 400), dtype=np.uint8)
        qimg = PyQt5.QtGui.QImage(data.tobytes(), 400, 400,
                                  400, PyQt5.QtGui.QImage.Format_Grayscale8)
        self.setPixmap(PyQt5.QtGui.QPixmap.fromImage(qimg))

    def _setup_core_graphics(self):
        try:
            cg = ctypes.CDLL(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )

            class CGPoint(ctypes.Structure):
                _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

            cg.CGWarpMouseCursorPosition.argtypes = [CGPoint]
            cg.CGWarpMouseCursorPosition.restype = ctypes.c_int32
            cg.AXIsProcessTrusted.argtypes = []
            cg.AXIsProcessTrusted.restype = ctypes.c_bool
            cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
            cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
            cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
            cg.CGEventPost.restype = None
            cg.CFRelease.argtypes = [ctypes.c_void_p]
            cg.CFRelease.restype = None

            self._k_cg_event_mouse_moved = 5
            self._k_cg_hid_event_tap = 0

            self._cg = cg
            self._cg_point_type = CGPoint
            trusted = bool(self._cg.AXIsProcessTrusted())
            print(f"CoreGraphics cursor API loaded, AX trusted={trusted}")
        except Exception as exc:
            print(f"CoreGraphics unavailable: {exc}")

    def _open_accessibility_settings(self):
        url = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        try:
            subprocess.Popen(["open", url])
            print("Opened macOS Accessibility settings")
        except Exception as exc:
            print(f"Failed to open Accessibility settings: {exc}")

        print(f"Interpreter path: {sys.executable}")

    def _print_ax_trust(self):
        if self._cg is None:
            print("CoreGraphics unavailable")
            return
        trusted = bool(self._cg.AXIsProcessTrusted())
        print(f"AX trusted now={trusted}")

    def _move_cursor_via_core_graphics(self, global_point):
        if self._cg is None or self._cg_point_type is None:
            print("CoreGraphics cursor warp unavailable")
            return
        cg_point = self._cg_point_type(float(global_point.x()), float(global_point.y()))
        err = self._cg.CGWarpMouseCursorPosition(cg_point)
        print(f"CGWarpMouseCursorPosition err={err}")

    def _move_cursor_via_cgevent_post(self, global_point):
        if self._cg is None or self._cg_point_type is None:
            print("CoreGraphics cursor event unavailable")
            return
        cg_point = self._cg_point_type(float(global_point.x()), float(global_point.y()))
        event = self._cg.CGEventCreateMouseEvent(
            None,
            self._k_cg_event_mouse_moved,
            cg_point,
            0,
        )
        if not event:
            print("CGEventCreateMouseEvent failed")
            return
        self._cg.CGEventPost(self._k_cg_hid_event_tap, event)
        self._cg.CFRelease(event)
        print("CGEventPost mouse move sent")

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()

    def _print_positions(self, label):
        global_pos = PyQt5.QtGui.QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        print(f"{label} global: {global_pos.x()}, {global_pos.y()}")
        print(f"{label} local:  {local_pos.x()}, {local_pos.y()}")

    def _move_cursor_by(self, dx, dy):
        before = PyQt5.QtGui.QCursor.pos()
        requested = PyQt5.QtCore.QPoint(before.x() + dx, before.y() + dy)
        PyQt5.QtGui.QCursor.setPos(requested)
        after = PyQt5.QtGui.QCursor.pos()
        print(f"Relative request: dx={dx}, dy={dy}")
        print(f"Before global:    {before.x()}, {before.y()}")
        print(f"Requested global: {requested.x()}, {requested.y()}")
        print(f"After global:     {after.x()}, {after.y()}")
        after_local = self.mapFromGlobal(after)
        print(f"After local:      {after_local.x()}, {after_local.y()}")

    def keyPressEvent(self, event):
        step = 40 if (event.modifiers() & PyQt5.QtCore.Qt.ShiftModifier) else 10

        if event.key() == PyQt5.QtCore.Qt.Key_C:
            center = self.rect().center()
            global_center = self.mapToGlobal(center)
            print(f"Widget center (local):  {center.x()}, {center.y()}")
            print(f"Widget center (global): {global_center.x()}, {global_center.y()}")
            self._print_positions("Before warp")
            PyQt5.QtGui.QCursor.setPos(global_center)
            # Read back immediately to verify
            actual = self.mapFromGlobal(PyQt5.QtGui.QCursor.pos())
            print(f"Cursor pos after warp:  {actual.x()}, {actual.y()}")
            self._print_positions("After warp")
        elif event.key() == PyQt5.QtCore.Qt.Key_V:
            center = self.rect().center()
            global_center = self.mapToGlobal(center)
            print(f"Widget center (local):  {center.x()}, {center.y()}")
            print(f"Widget center (global): {global_center.x()}, {global_center.y()}")
            self._print_positions("Before CG warp")
            self._move_cursor_via_core_graphics(global_center)
            self._print_positions("After CG warp")
        elif event.key() == PyQt5.QtCore.Qt.Key_B:
            before = PyQt5.QtGui.QCursor.pos()
            requested = PyQt5.QtCore.QPoint(before.x() + 10, before.y())
            print("CG relative request: dx=10, dy=0")
            print(f"Before global:       {before.x()}, {before.y()}")
            print(f"Requested global:    {requested.x()}, {requested.y()}")
            self._move_cursor_via_core_graphics(requested)
            self._print_positions("After CG relative")
        elif event.key() == PyQt5.QtCore.Qt.Key_N:
            center = self.rect().center()
            global_center = self.mapToGlobal(center)
            print(f"Widget center (local):  {center.x()}, {center.y()}")
            print(f"Widget center (global): {global_center.x()}, {global_center.y()}")
            self._print_positions("Before CGEventPost warp")
            self._move_cursor_via_cgevent_post(global_center)
            self._print_positions("After CGEventPost warp")
        elif event.key() == PyQt5.QtCore.Qt.Key_M:
            before = PyQt5.QtGui.QCursor.pos()
            requested = PyQt5.QtCore.QPoint(before.x() + 10, before.y())
            print("CGEventPost relative request: dx=10, dy=0")
            print(f"Before global:                {before.x()}, {before.y()}")
            print(f"Requested global:             {requested.x()}, {requested.y()}")
            self._move_cursor_via_cgevent_post(requested)
            self._print_positions("After CGEventPost relative")
        elif event.key() == PyQt5.QtCore.Qt.Key_P:
            self._open_accessibility_settings()
            self._print_ax_trust()
        elif event.key() == PyQt5.QtCore.Qt.Key_Left:
            self._move_cursor_by(-step, 0)
        elif event.key() == PyQt5.QtCore.Qt.Key_Right:
            self._move_cursor_by(step, 0)
        elif event.key() == PyQt5.QtCore.Qt.Key_Up:
            self._move_cursor_by(0, -step)
        elif event.key() == PyQt5.QtCore.Qt.Key_Down:
            self._move_cursor_by(0, step)
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = PyQt5.QtWidgets.QApplication([])
    w = TestWindow()
    w.show()
    app.exec_()
