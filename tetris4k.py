#!/usr/bin/env python3
# Kondo's Tetris 0.1
# Single-file Pygame implementation
# FILES_OFF = True
# 60 FPS / Famicom-style game timing

import math
import random
import sys
import pygame

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
TITLE = "Kondo's Tetris 0.1"
FILES_OFF = True
FPS = 60
SPEED_MODE = "FAMICOM"

SCREEN_W = 900
SCREEN_H = 720

BOARD_W = 10
BOARD_H = 20
CELL = 30
BOARD_X = 300
BOARD_Y = 70

BG = (12, 15, 24)
PANEL = (24, 29, 44)
GRID = (45, 52, 72)
TEXT = (235, 240, 255)
MUTED = (150, 160, 190)
ACCENT = (120, 210, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

COLORS = {
    "I": (70, 220, 235),
    "O": (245, 215, 70),
    "T": (180, 90, 220),
    "S": (90, 210, 110),
    "Z": (235, 75, 75),
    "J": (75, 110, 235),
    "L": (240, 150, 70),
}

# Tetromino spawn orientations in SRS-like local coordinates.
SHAPES = {
    "I": [
        [(0,1),(1,1),(2,1),(3,1)],
        [(2,0),(2,1),(2,2),(2,3)],
        [(0,2),(1,2),(2,2),(3,2)],
        [(1,0),(1,1),(1,2),(1,3)],
    ],
    "O": [
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
    ],
    "T": [
        [(1,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(2,1),(1,2)],
        [(0,1),(1,1),(2,1),(1,2)],
        [(1,0),(0,1),(1,1),(1,2)],
    ],
    "S": [
        [(1,0),(2,0),(0,1),(1,1)],
        [(1,0),(1,1),(2,1),(2,2)],
        [(1,1),(2,1),(0,2),(1,2)],
        [(0,0),(0,1),(1,1),(1,2)],
    ],
    "Z": [
        [(0,0),(1,0),(1,1),(2,1)],
        [(2,0),(1,1),(2,1),(1,2)],
        [(0,1),(1,1),(1,2),(2,2)],
        [(1,0),(0,1),(1,1),(0,2)],
    ],
    "J": [
        [(0,0),(0,1),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(1,2)],
        [(0,1),(1,1),(2,1),(2,2)],
        [(1,0),(1,1),(0,2),(1,2)],
    ],
    "L": [
        [(2,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(1,2),(2,2)],
        [(0,1),(1,1),(2,1),(0,2)],
        [(0,0),(1,0),(1,1),(1,2)],
    ],
}

# Practical SRS-style kick checks.
KICKS_NORMAL = [(0,0),(-1,0),(1,0),(0,-1),(-2,0),(2,0),(0,-2)]
KICKS_I = [(0,0),(-2,0),(2,0),(-1,0),(1,0),(0,-1),(0,-2)]

# NES/Famicom-inspired gravity table, measured in frames per row.
# Classic NES Tetris is NTSC ~60 Hz. Values approximate classic level speed.
FAMICOM_GRAVITY_FRAMES = [
    48,43,38,33,28,23,18,13,8,6,
    5,5,5,4,4,4,3,3,3,2,
    2,2,2,2,2,2,2,2,2,1
]

LINE_POINTS = {1: 40, 2: 100, 3: 300, 4: 1200}

# ------------------------------------------------------------
# AUDIO - generated in memory, no files
# ------------------------------------------------------------
def make_tone(freq, duration_ms, volume=0.18, sample_rate=44100):
    """Generate a square-ish chiptune tone in memory."""
    count = max(1, int(sample_rate * duration_ms / 1000.0))
    buf = bytearray()
    for i in range(count):
        t = i / sample_rate
        # Slightly softened square wave using sine + 3rd harmonic.
        v = math.sin(2 * math.pi * freq * t)
        v += 0.28 * math.sin(2 * math.pi * freq * 3 * t)
        v /= 1.28
        sample = int(max(-1, min(1, v)) * 32767 * volume)
        buf += int(sample).to_bytes(2, "little", signed=True)
        buf += int(sample).to_bytes(2, "little", signed=True)
    return pygame.mixer.Sound(buffer=bytes(buf))

NOTE_FREQ = {
    "E5":659.25, "B4":493.88, "C5":523.25, "D5":587.33,
    "A4":440.00, "C4":261.63, "E4":329.63, "G4":392.00,
    "F4":349.23, "D4":293.66, "B3":246.94, "A3":220.00,
}

# A short public-domain Korobeiniki-inspired phrase, synthesized at runtime.
# Not sampled from any ROM or commercial recording.
MELODY = [
    ("E5",180),("B4",120),("C5",120),("D5",180),("C5",120),("B4",120),
    ("A4",180),("A4",120),("C5",120),("E5",180),("D5",120),("C5",120),
    ("B4",240),("C5",120),("D5",180),("E5",180),("C5",180),("A4",180),
    ("A4",240),
]

class MusicEngine:
    def __init__(self):
        self.enabled = True
        self.ready = False
        self.index = 0
        self.deadline = 0
        self.channel = None
        self.sounds = {}
        try:
            if pygame.mixer.get_init():
                self.channel = pygame.mixer.Channel(0)
                for note, dur in MELODY:
                    key = (note, dur)
                    if key not in self.sounds:
                        self.sounds[key] = make_tone(NOTE_FREQ[note], dur)
                self.ready = True
        except pygame.error:
            self.ready = False

    def update(self):
        if not self.enabled or not self.ready:
            return
        now = pygame.time.get_ticks()
        if self.channel and (not self.channel.get_busy()) and now >= self.deadline:
            note, dur = MELODY[self.index]
            self.channel.play(self.sounds[(note, dur)])
            self.deadline = now + dur + 18
            self.index = (self.index + 1) % len(MELODY)

    def stop(self):
        if self.channel:
            self.channel.stop()

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()

# ------------------------------------------------------------
# GAME OBJECTS
# ------------------------------------------------------------
class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.rot = 0
        self.x = 3
        self.y = -1 if kind != "I" else -2

    def cells(self, x=None, y=None, rot=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        pr = self.rot if rot is None else rot
        return [(px + dx, py + dy) for dx, dy in SHAPES[self.kind][pr % 4]]

class Bag:
    def __init__(self):
        self.queue = []

    def refill(self):
        bag = list(SHAPES.keys())
        random.shuffle(bag)
        self.queue.extend(bag)

    def next(self):
        if len(self.queue) < 7:
            self.refill()
        return self.queue.pop(0)

    def peek(self, n=5):
        while len(self.queue) < n:
            self.refill()
        return self.queue[:n]

class TetrisGame:
    def __init__(self):
        self.bag = Bag()
        self.reset()

    def reset(self):
        self.board = [[None for _ in range(BOARD_W)] for _ in range(BOARD_H)]
        self.bag = Bag()
        self.current = Piece(self.bag.next())
        self.hold_kind = None
        self.can_hold = True
        self.score = 0
        self.lines = 0
        self.level = 0
        self.combo = -1
        self.b2b = False
        self.game_over = False
        self.paused = False
        self.gravity_counter = 0
        self.lock_counter = 0
        self.lock_delay = 30
        self.last_move_was_rotation = False

    def gravity_frames(self):
        idx = min(self.level, len(FAMICOM_GRAVITY_FRAMES)-1)
        return FAMICOM_GRAVITY_FRAMES[idx]

    def valid(self, piece, x=None, y=None, rot=None):
        for cx, cy in piece.cells(x, y, rot):
            if cx < 0 or cx >= BOARD_W or cy >= BOARD_H:
                return False
            if cy >= 0 and self.board[cy][cx] is not None:
                return False
        return True

    def grounded(self):
        return not self.valid(self.current, y=self.current.y + 1)

    def spawn(self):
        self.current = Piece(self.bag.next())
        self.can_hold = True
        self.lock_counter = 0
        self.gravity_counter = 0
        if not self.valid(self.current):
            self.game_over = True

    def move(self, dx, dy):
        if self.game_over or self.paused:
            return False
        if self.valid(self.current, x=self.current.x + dx, y=self.current.y + dy):
            self.current.x += dx
            self.current.y += dy
            self.last_move_was_rotation = False
            if dx != 0:
                self.lock_counter = 0
            return True
        return False

    def rotate(self, direction):
        if self.game_over or self.paused:
            return
        old = self.current.rot
        new = (old + direction) % 4
        kicks = KICKS_I if self.current.kind == "I" else KICKS_NORMAL
        for kx, ky in kicks:
            if self.valid(self.current,
                          x=self.current.x + kx,
                          y=self.current.y + ky,
                          rot=new):
                self.current.x += kx
                self.current.y += ky
                self.current.rot = new
                self.lock_counter = 0
                self.last_move_was_rotation = True
                return

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        dist = 0
        while self.move(0, 1):
            dist += 1
        self.score += dist * 2
        self.lock()

    def soft_drop(self):
        if self.move(0, 1):
            self.score += 1
            return True
        return False

    def hold(self):
        if not self.can_hold or self.game_over or self.paused:
            return
        self.can_hold = False
        old = self.current.kind
        if self.hold_kind is None:
            self.hold_kind = old
            self.current = Piece(self.bag.next())
        else:
            self.current = Piece(self.hold_kind)
            self.hold_kind = old
        self.lock_counter = 0
        self.gravity_counter = 0
        if not self.valid(self.current):
            self.game_over = True

    def ghost_y(self):
        gy = self.current.y
        while self.valid(self.current, y=gy + 1):
            gy += 1
        return gy

    def lock(self):
        if self.game_over:
            return
        top_out = False
        for x, y in self.current.cells():
            if y < 0:
                top_out = True
            elif 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                self.board[y][x] = self.current.kind
        if top_out:
            self.game_over = True
            return

        cleared = self.clear_lines()
        if cleared:
            self.combo += 1
            base = LINE_POINTS.get(cleared, 0) * (self.level + 1)
            if cleared == 4:
                if self.b2b:
                    base = int(base * 1.5)
                self.b2b = True
            else:
                self.b2b = False
            if self.combo > 0:
                base += 50 * self.combo * (self.level + 1)
            self.score += base
            self.lines += cleared
            self.level = self.lines // 10
        else:
            self.combo = -1

        self.spawn()

    def clear_lines(self):
        kept = [row for row in self.board if any(cell is None for cell in row)]
        cleared = BOARD_H - len(kept)
        while len(kept) < BOARD_H:
            kept.insert(0, [None for _ in range(BOARD_W)])
        self.board = kept
        return cleared

    def update(self):
        if self.game_over or self.paused:
            return

        self.gravity_counter += 1
        frames = self.gravity_frames()

        # At max speed, move each frame.
        if self.gravity_counter >= frames:
            self.gravity_counter = 0
            self.move(0, 1)

        if self.grounded():
            self.lock_counter += 1
            if self.lock_counter >= self.lock_delay:
                self.lock()
        else:
            self.lock_counter = 0

# ------------------------------------------------------------
# DRAWING
# ------------------------------------------------------------
def draw_text(screen, font, text, x, y, color=TEXT, center=False):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surf, rect)

def draw_block(screen, gx, gy, color, alpha=255, ox=BOARD_X, oy=BOARD_Y, scale=1.0):
    size = int(CELL * scale)
    px = ox + gx * size
    py = oy + gy * size
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (*color, alpha)
    pygame.draw.rect(s, c, (1, 1, size-2, size-2), border_radius=4)
    hi = tuple(min(255, v + 50) for v in color)
    pygame.draw.line(s, (*hi, alpha), (3, 3), (size-5, 3), 2)
    pygame.draw.line(s, (*hi, alpha), (3, 3), (3, size-5), 2)
    screen.blit(s, (px, py))

def draw_mini_piece(screen, kind, x, y):
    if not kind:
        return
    shape = SHAPES[kind][0]
    mini = 18
    for dx, dy in shape:
        r = pygame.Rect(x + dx*mini, y + dy*mini, mini-2, mini-2)
        pygame.draw.rect(screen, COLORS[kind], r, border_radius=3)

def draw_game(screen, game, fonts):
    font, small, big = fonts

    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (BOARD_X-10, BOARD_Y-10, BOARD_W*CELL+20, BOARD_H*CELL+20), border_radius=10)

    # Board grid
    for y in range(BOARD_H):
        for x in range(BOARD_W):
            pygame.draw.rect(screen, GRID,
                             (BOARD_X+x*CELL, BOARD_Y+y*CELL, CELL, CELL), 1)
            kind = game.board[y][x]
            if kind:
                draw_block(screen, x, y, COLORS[kind])

    # Ghost
    if not game.game_over:
        gy = game.ghost_y()
        for x, y in game.current.cells(y=gy):
            if y >= 0:
                draw_block(screen, x, y, COLORS[game.current.kind], alpha=65)

        # Current piece
        for x, y in game.current.cells():
            if y >= 0:
                draw_block(screen, x, y, COLORS[game.current.kind])

    # Left info panel
    draw_text(screen, big, TITLE, 28, 28, ACCENT)
    draw_text(screen, small, "60 FPS / FAMICOM SPEED", 30, 78, MUTED)

    draw_text(screen, font, "HOLD", 58, 145)
    pygame.draw.rect(screen, PANEL, (32, 180, 185, 105), border_radius=8)
    draw_mini_piece(screen, game.hold_kind, 80, 200)

    draw_text(screen, font, "SCORE", 40, 330)
    draw_text(screen, big, f"{game.score:08d}", 40, 365, WHITE)
    draw_text(screen, font, f"LINES  {game.lines}", 40, 435)
    draw_text(screen, font, f"LEVEL  {game.level}", 40, 470)

    # Right panel
    draw_text(screen, font, "NEXT", 665, 100)
    pygame.draw.rect(screen, PANEL, (650, 135, 210, 330), border_radius=8)
    for i, kind in enumerate(game.bag.peek(5)):
        draw_mini_piece(screen, kind, 695, 155 + i*58)

    controls = [
        "← →   Move",
        "↓     Soft drop",
        "SPACE Hard drop",
        "Z / X Rotate",
        "C     Hold",
        "P     Pause",
        "M     Music",
        "ESC   Menu",
    ]
    draw_text(screen, small, "CONTROLS", 665, 500, ACCENT)
    for i, line in enumerate(controls):
        draw_text(screen, small, line, 665, 530+i*22, MUTED)

    if game.paused:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))
        draw_text(screen, big, "PAUSED", SCREEN_W//2, SCREEN_H//2-20, WHITE, True)
        draw_text(screen, small, "Press P to resume", SCREEN_W//2, SCREEN_H//2+25, MUTED, True)

    if game.game_over:
        overlay = pygame.Surface((BOARD_W*CELL, 160), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (BOARD_X, SCREEN_H//2-80))
        draw_text(screen, big, "GAME OVER", BOARD_X+BOARD_W*CELL//2, SCREEN_H//2-30, WHITE, True)
        draw_text(screen, small, "ENTER: retry   ESC: menu", BOARD_X+BOARD_W*CELL//2, SCREEN_H//2+20, MUTED, True)

def draw_menu(screen, fonts, selected):
    font, small, big = fonts
    screen.fill(BG)

    # Animated falling mini blocks
    t = pygame.time.get_ticks() / 1000.0
    for i, kind in enumerate(SHAPES.keys()):
        x = 70 + i*115
        y = 65 + int((math.sin(t*1.4 + i) + 1) * 12)
        draw_mini_piece(screen, kind, x, y)

    draw_text(screen, big, "KONDO'S TETRIS 0.1", SCREEN_W//2, 205, ACCENT, True)
    draw_text(screen, font, "60 FPS  •  SPEED = FAMICOM  •  FILES_OFF", SCREEN_W//2, 250, MUTED, True)

    items = ["PLAY GAME", "HELP", "MUSIC: ON", "EXIT"]
    for i, item in enumerate(items):
        y = 335 + i*62
        color = WHITE if i == selected else MUTED
        prefix = "▶ " if i == selected else "  "
        draw_text(screen, font, prefix + item, SCREEN_W//2, y, color, True)

    draw_text(screen, small, "Arrow keys / Enter", SCREEN_W//2, 625, MUTED, True)
    draw_text(screen, small, "Pure Pygame • no ROM • no external assets", SCREEN_W//2, 655, MUTED, True)

def draw_help(screen, fonts):
    font, small, big = fonts
    screen.fill(BG)
    draw_text(screen, big, "HELP", SCREEN_W//2, 80, ACCENT, True)

    lines = [
        "LEFT / RIGHT  Move piece",
        "DOWN          Soft drop (+1 per cell)",
        "SPACE         Hard drop (+2 per cell)",
        "Z / X         Rotate counter-clockwise / clockwise",
        "C             Hold piece",
        "P             Pause / resume",
        "M             Toggle synthesized music",
        "ESC           Return to main menu",
        "",
        "Features:",
        "• 10×20 board, seven tetrominoes, 7-bag queue",
        "• Hold, five-piece preview, ghost piece",
        "• line clears, combos, back-to-back Tetris bonus",
        "• score, levels, progressively faster gravity",
        "• 60 FPS loop with Famicom/NES-style gravity timing",
        "• lock delay and basic wall-kick rotation",
        "• generated chiptune Korobeiniki-style melody",
        "• FILES_OFF: no images, fonts, music, or ROM files",
    ]
    for i, line in enumerate(lines):
        color = WHITE if line.endswith(":") else TEXT
        draw_text(screen, small, line, 130, 145+i*27, color)

    draw_text(screen, small, "Press ESC or ENTER to return", SCREEN_W//2, 665, MUTED, True)

# ------------------------------------------------------------
# INPUT / MAIN LOOP
# ------------------------------------------------------------
def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 34)
    small = pygame.font.Font(None, 24)
    big = pygame.font.Font(None, 48)
    fonts = (font, small, big)

    music = MusicEngine()
    game = TetrisGame()

    state = "menu"
    prev_state = state
    menu_selected = 0
    running = True

    # DAS / ARR for horizontal movement.
    das_frames = 10
    arr_frames = 2
    left_held = False
    right_held = False
    left_frames = 0
    right_frames = 0

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if state == "menu":
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = (menu_selected - 1) % 4
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = (menu_selected + 1) % 4
                    elif event.key == pygame.K_RETURN:
                        if menu_selected == 0:
                            game.reset()
                            state = "game"
                        elif menu_selected == 1:
                            state = "help"
                        elif menu_selected == 2:
                            music.toggle()
                        elif menu_selected == 3:
                            running = False
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_m:
                        music.toggle()

                elif state == "help":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                        state = "menu"

                elif state == "game":
                    if game.game_over:
                        if event.key == pygame.K_RETURN:
                            game.reset()
                        elif event.key == pygame.K_ESCAPE:
                            state = "menu"
                        elif event.key == pygame.K_m:
                            music.toggle()
                    else:
                        if event.key == pygame.K_ESCAPE:
                            state = "menu"
                        elif event.key == pygame.K_p:
                            game.paused = not game.paused
                        elif event.key == pygame.K_m:
                            music.toggle()
                        elif not game.paused:
                            if event.key == pygame.K_LEFT:
                                left_held = True
                                left_frames = 0
                                game.move(-1, 0)
                            elif event.key == pygame.K_RIGHT:
                                right_held = True
                                right_frames = 0
                                game.move(1, 0)
                            elif event.key == pygame.K_DOWN:
                                game.soft_drop()
                            elif event.key == pygame.K_SPACE:
                                game.hard_drop()
                            elif event.key == pygame.K_z:
                                game.rotate(-1)
                            elif event.key in (pygame.K_x, pygame.K_UP):
                                game.rotate(1)
                            elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                                game.hold()

            elif event.type == pygame.KEYUP and state == "game":
                if event.key == pygame.K_LEFT:
                    left_held = False
                    left_frames = 0
                elif event.key == pygame.K_RIGHT:
                    right_held = False
                    right_frames = 0

        # Held-key movement / soft drop.
        if state == "game" and not game.paused and not game.game_over:
            keys = pygame.key.get_pressed()

            if left_held and not right_held:
                left_frames += 1
                if left_frames >= das_frames and (left_frames - das_frames) % arr_frames == 0:
                    game.move(-1, 0)

            if right_held and not left_held:
                right_frames += 1
                if right_frames >= das_frames and (right_frames - das_frames) % arr_frames == 0:
                    game.move(1, 0)

            if keys[pygame.K_DOWN]:
                # Extra repeat while held.
                if pygame.time.get_ticks() % 3 == 0:
                    game.soft_drop()

            game.update()

        # OST only plays while actually in the game screen.
        if state != prev_state:
            if state != "game":
                music.stop()
            prev_state = state

        if state == "game":
            music.update()

        if state == "menu":
            draw_menu(screen, fonts, menu_selected)
            # Keep displayed music state accurate.
            label = "MUSIC: ON" if music.enabled else "MUSIC: OFF"
            y = 335 + 2*62
            pygame.draw.rect(screen, BG, (300, y-24, 300, 48))
            prefix = "▶ " if menu_selected == 2 else "  "
            draw_text(screen, font, prefix + label, SCREEN_W//2, y,
                      WHITE if menu_selected == 2 else MUTED, True)
        elif state == "help":
            draw_help(screen, fonts)
        elif state == "game":
            draw_game(screen, game, fonts)

        pygame.display.flip()

    music.stop()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
