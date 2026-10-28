"""Pure temporal command gate; independent of camera, GUI and keyboard access."""
from dataclasses import dataclass

@dataclass
class GestureGate:
    hold_seconds: float = .7
    cooldown_seconds: float = 1.4
    min_frames: int = 3
    max_gap_seconds: float = 2.

    def __post_init__(self):
        self.reset()

    def reset(self):
        self.candidate = None
        self.since = 0.
        self.frames = 0
        self.latched = None
        self.last_fire = float('-inf')
        self.last_time = float('-inf')

    def update(self, label, score, now, threshold):
        if now - self.last_time > self.max_gap_seconds:
            self.candidate = None
            self.frames = 0
            self.latched = None
        self.last_time = now
        if label == 'no_gesture' or score < threshold:
            self.candidate = None
            self.frames = 0
            self.latched = None
            return None
        if label != self.candidate:
            self.candidate, self.since, self.frames = label, now, 1
        else:
            self.frames += 1
        if (self.latched == label or now-self.since < self.hold_seconds
                or self.frames < self.min_frames or now-self.last_fire < self.cooldown_seconds):
            return None
        self.latched, self.last_fire = label, now
        return label
