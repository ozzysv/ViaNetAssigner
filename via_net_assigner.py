"""Via Net Assigner — KiCad 10 IPC plugin (kicad-python 0.8)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import wx
from kipy import KiCad
from kipy.board_types import ArcTrack, Pad, Track, Via

APP_NAME = "Via Net Assigner"
APP_VERSION = "1.0.6"
POLL_MS = 170
SETTINGS_FILE = Path(__file__).with_name("settings.json")


def load_position():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        x, y = data["x"], data["y"]
        if type(x) is int and type(y) is int and abs(x) < 100000 and abs(y) < 100000:
            return x, y
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None


def save_position(position):
    # Atomic replace: concurrent KiCad editor instances cannot write a partial file.
    tmp = SETTINGS_FILE.with_name(f".settings.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps({"x": position.x, "y": position.y}) + "\n", encoding="utf-8")
        os.replace(tmp, SETTINGS_FILE)
    except OSError as exc:
        print(f"{APP_NAME}: cannot save window position: {exc}", file=sys.stderr)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def restore_position(frame):
    saved = load_position()
    if saved is None:
        frame.CentreOnScreen()
        return

    x, y = saved
    size = frame.GetSize()
    bounds = wx.Rect(x, y, size.width, size.height)
    for index in range(wx.Display.GetCount()):
        area = wx.Display(index).GetClientArea()
        if bounds.Intersects(area):
            frame.SetPosition(wx.Point(
                max(area.GetLeft(), min(x, area.GetRight() - size.width + 1)),
                max(area.GetTop(), min(y, area.GetBottom() - size.height + 1)),
            ))
            return
    frame.CentreOnScreen()


class InstanceLock:
    """Allow one instance per IPC session, but independent PCB Editors."""

    def __init__(self, socket, token):
        key = hashlib.sha256(f"{socket}\0{token}".encode()).hexdigest()[:24]
        self.path = Path(tempfile.gettempdir()) / f"via-net-assigner-{key}.lock"
        self.handle = None

    def acquire(self):
        self.handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.release()
            return False

    def release(self):
        if self.handle is not None:
            # Closing a file descriptor also releases its OS-level file lock.
            self.handle.close()
            self.handle = None


class ViaNetWindow(wx.Frame):
    def __init__(self, board):
        style = wx.CAPTION | wx.CLOSE_BOX | wx.SYSTEM_MENU | wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR
        super().__init__(None, title=f"{APP_NAME} v{APP_VERSION}", style=style)
        self.board = board
        self.source_net = None
        self.assigned_count = 0
        self.last_selected_id = None

        icon = Path(__file__).with_name("icon.png")
        if icon.is_file():
            try:
                self.SetIcon(wx.Icon(str(icon), wx.BITMAP_TYPE_PNG))
            except Exception:
                pass  # Optional icon must never prevent startup.

        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        name = Path(str(getattr(board, "name", "") or "PCB Editor")).name
        if len(name) > 42:
            name = name[:19] + "…" + name[-20:]
        board_label = wx.StaticText(panel, label=name)
        board_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        layout.Add(board_label, 0, wx.EXPAND | wx.BOTTOM, 4)

        net_row = wx.BoxSizer(wx.HORIZONTAL)
        net_row.Add(wx.StaticText(panel, label="Net:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.net_label = wx.StaticText(panel, label="— Select pad/track —", style=wx.ST_ELLIPSIZE_END)
        self.net_label.SetMinSize((215, -1))
        self.net_label.SetFont(self.net_label.GetFont().Bold())
        net_row.Add(self.net_label, 1, wx.ALIGN_CENTER_VERTICAL)
        layout.Add(net_row, 0, wx.EXPAND | wx.BOTTOM, 5)

        options = wx.BoxSizer(wx.HORIZONTAL)
        self.overwrite = wx.CheckBox(panel, label="Overwrite via with net")
        options.Add(self.overwrite, 0, wx.ALIGN_CENTER_VERTICAL)
        options.AddStretchSpacer()
        self.count_label = wx.StaticText(panel, label="Changed: 0")
        options.Add(self.count_label, 0, wx.ALIGN_CENTER_VERTICAL)
        layout.Add(options, 0, wx.EXPAND | wx.BOTTOM, 5)

        footer = wx.BoxSizer(wx.HORIZONTAL)
        self.status = wx.StaticText(panel, label="Select a pad or track", style=wx.ST_ELLIPSIZE_END)
        self.status.SetMinSize((205, -1))
        self.status.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        footer.Add(self.status, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 7)
        close_button = wx.Button(panel, label="Close", size=(66, 25))
        footer.Add(close_button, 0, wx.ALIGN_CENTER_VERTICAL)
        layout.Add(footer, 0, wx.EXPAND)

        panel.SetSizer(layout)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND | wx.ALL, 7)
        self.SetSizerAndFit(outer)
        restore_position(self)

        close_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        try:
            self.board.clear_selection()  # Ignore objects selected before launch.
        except Exception:
            pass
        self.timer.Start(POLL_MS)

    def set_status(self, message):
        self.status.SetLabel(message)
        self.status.SetToolTip(message)

    def set_source(self, net):
        # A pad/track without a net must clear the previous source.
        self.source_net = net if net and net.name else None
        name = self.source_net.name if self.source_net else "— Select pad/track —"
        self.net_label.SetLabel(name)
        self.net_label.SetToolTip(name)
        self.set_status("Click via to assign net" if self.source_net else "Source has no net")

    def process_item(self, item):
        if isinstance(item, (Pad, Track, ArcTrack)):
            self.set_source(item.net)
            return
        if not isinstance(item, Via):
            self.set_status("Select pad, track or via")
            return
        if self.source_net is None:
            self.set_status("First select pad or track")
            return

        # Fetch the current via before editing it, to avoid stale snapshots.
        matches = self.board.get_items_by_id(item.id)
        via = next((obj for obj in matches if isinstance(obj, Via)), None)
        if via is None:
            self.set_status("Via no longer exists")
            return
        if via.locked:
            self.set_status("Via is locked; skipped")
            return
        old_net = via.net.name
        new_net = self.source_net.name
        if old_net == new_net:
            self.set_status("Via already has this net")
            return
        if old_net and not self.overwrite.GetValue():
            self.set_status("Enable Overwrite to change net")
            return

        via.net = self.source_net
        result = self.board.update_items([via])
        if not result or not isinstance(result[0], Via) or result[0].net.name != new_net:
            raise RuntimeError("KiCad did not confirm via net update")
        self.assigned_count += 1
        self.count_label.SetLabel(f"Changed: {self.assigned_count}")
        self.set_status(f"Assigned: {new_net}")

    def on_timer(self, event):
        try:
            selected = self.board.get_selection()
            if not selected:
                self.last_selected_id = None
            elif len(selected) == 1:
                item = selected[0]
                identifier = str(item.id)
                if identifier != self.last_selected_id:
                    self.last_selected_id = identifier
                    try:
                        self.process_item(item)
                    finally:
                        self.board.clear_selection()
            else:
                self.last_selected_id = None
                self.set_status("Select just one item")
        except Exception as exc:
            self.set_status(f"IPC error: {str(exc)[:100]}")

    def on_close(self, event):
        self.timer.Stop()
        if not self.IsIconized():
            save_position(self.GetPosition())
        self.Destroy()


def show_error(message):
    if wx.GetApp() is None:
        wx.App(False)
    wx.MessageBox(message, APP_NAME, wx.OK | wx.ICON_ERROR)


def main():
    socket = os.environ.get("KICAD_API_SOCKET")
    token = os.environ.get("KICAD_API_TOKEN")
    if not socket or not token:
        show_error("Launch the plugin from KiCad PCB Editor (IPC session not found).")
        return 1

    lock = InstanceLock(socket, token)
    if not lock.acquire():
        show_error("Via Net Assigner is already running for this PCB Editor.")
        return 0
    try:
        try:
            client = KiCad(socket_path=socket, kicad_token=token, timeout_ms=1800)
            board = client.get_board()
            if board is None:
                raise RuntimeError("No PCB document open")
            app = wx.App(False)
            window = ViaNetWindow(board)
            window.Show()
            app.MainLoop()
        except Exception as exc:
            show_error(f"Plugin error:\n{exc}")
            return 1
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
