# controller.py
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class TimerController(QObject):
    tick             = pyqtSignal(int)
    phase_changed    = pyqtSignal(str)
    session_done     = pyqtSignal(int)
    session_recorded = pyqtSignal(int, str) 

    def __init__(self):
        super().__init__()
        self.work_secs          = 25 * 60
        self.short_break_secs   = 5  * 60
        self.long_break_secs    = 15 * 60
        self.sessions_per_cycle = 4
        self.break_flow         = "auto"

        self.phase          = "Work"
        self.remaining_secs = self.work_secs
        self.total_secs     = self.work_secs
        self.is_running     = False
        self.work_sessions  = 0

        self._qtimer = QTimer()
        self._qtimer.timeout.connect(self._on_tick)

        self._skip_in_progress = False
        self._skip_cooldown = QTimer()
        self._skip_cooldown.setSingleShot(True)
        self._skip_cooldown.setInterval(400)
        self._skip_cooldown.timeout.connect(self._clear_skip_cooldown)

    def _clear_skip_cooldown(self):
        self._skip_in_progress = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._qtimer.start(1000)

    def pause(self):
        self.is_running = False
        self._qtimer.stop()

    def reset(self):
        self.pause()
        self._skip_in_progress = False
        self._skip_cooldown.stop()
        self.work_sessions = 0
        self.set_phase("Work")

    def skip(self):
        if self._skip_in_progress: return
        self._skip_in_progress = True
        self._skip_cooldown.start()

        was_running = self.is_running
        self._qtimer.stop()
        self.is_running = False

        if self.phase == "Work":
            self.work_sessions += 1
            self.session_done.emit(self.work_sessions)
            completed_duration = self.work_secs - self.remaining_secs
            self.session_recorded.emit(completed_duration, "Work")
            self.set_phase(self._decide_break())
        else:
            self.set_phase("Work")

        if was_running:
            self.is_running = True
            self._qtimer.start(1000)

    def _decide_break(self) -> str:
        if self.break_flow == "always_short": return "Short Break"
        elif self.break_flow == "always_long": return "Long Break"
        else:
            if self.work_sessions % self.sessions_per_cycle == 0: return "Long Break"
            return "Short Break"

    def set_phase(self, phase: str):
        self.phase = phase
        durations = {
            "Work": self.work_secs,
            "Short Break": self.short_break_secs,
            "Long Break": self.long_break_secs,
        }
        secs = durations.get(phase, self.work_secs)
        self.remaining_secs = self.total_secs = secs
        self.phase_changed.emit(self.phase)
        self.tick.emit(self.remaining_secs)

    def update_settings(self, work_s: int, short_s: int, long_s: int, flow: str):
        changed = (self.work_secs != work_s or self.short_break_secs != short_s or
                   self.long_break_secs != long_s or self.break_flow != flow)
        if not changed: return
        self.work_secs        = work_s
        self.short_break_secs = short_s
        self.long_break_secs  = long_s
        self.break_flow       = flow
        self.reset()

    def progress(self) -> float:
        if self.total_secs == 0: return 0.0
        return 1.0 - (self.remaining_secs / self.total_secs)

    def _on_tick(self):
        self.remaining_secs -= 1
        self.tick.emit(self.remaining_secs)
        if self.remaining_secs <= 0:
            self.skip()