"""
Tetris Effect: Connected — Single-file Python implementation
Controls:
  Arrow Left/Right  — Move piece
  Arrow Up / X      — Rotate clockwise
  Z                 — Rotate counter-clockwise
  Arrow Down        — Soft drop
  Space             — Hard drop
  C                 — Hold piece
  Tab / F           — Activate ZONE (when meter is full)
  Escape / P        — Pause
  R                 — Restart (game over screen)
"""

import pygame
import random
import math
import sys
import time
from collections import deque

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COLS, ROWS = 10, 20
CELL = 34
BOARD_X = 260
BOARD_Y = 40
SCREEN_W = 900
SCREEN_H = 760

FPS = 60

# Tetromino definitions (shape, base color)
TETROMINOES = {
    'I': {'cells': [(0,1),(1,1),(2,1),(3,1)], 'color': (0, 240, 240)},
    'O': {'cells': [(0,0),(1,0),(0,1),(1,1)], 'color': (240, 240, 0)},
    'T': {'cells': [(1,0),(0,1),(1,1),(2,1)], 'color': (160, 0, 240)},
    'S': {'cells': [(1,0),(2,0),(0,1),(1,1)], 'color': (0, 240, 0)},
    'Z': {'cells': [(0,0),(1,0),(1,1),(2,1)], 'color': (240, 0, 0)},
    'J': {'cells': [(0,0),(0,1),(1,1),(2,1)], 'color': (0, 0, 240)},
    'L': {'cells': [(2,0),(0,1),(1,1),(2,1)], 'color': (240, 160, 0)},
}
PIECE_KEYS = list(TETROMINOES.keys())

# Wall-kick data (SRS)
WALL_KICKS = {
    'normal': {
        (0,1):  [(-1,0),(-1,1),(0,-2),(-1,-2)],
        (1,0):  [(1,0),(1,-1),(0,2),(1,2)],
        (1,2):  [(1,0),(1,-1),(0,2),(1,2)],
        (2,1):  [(-1,0),(-1,1),(0,-2),(-1,-2)],
        (2,3):  [(1,0),(1,1),(0,-2),(1,-2)],
        (3,2):  [(-1,0),(-1,-1),(0,2),(-1,2)],
        (3,0):  [(-1,0),(-1,-1),(0,2),(-1,2)],
        (0,3):  [(1,0),(1,1),(0,-2),(1,2)],
    },
    'I': {
        (0,1):  [(-2,0),(1,0),(-2,-1),(1,2)],
        (1,0):  [(2,0),(-1,0),(2,1),(-1,-2)],
        (1,2):  [(-1,0),(2,0),(-1,2),(2,-1)],
        (2,1):  [(1,0),(-2,0),(1,-2),(-2,1)],
        (2,3):  [(2,0),(-1,0),(2,1),(-1,-2)],
        (3,2):  [(-2,0),(1,0),(-2,-1),(1,2)],
        (3,0):  [(1,0),(-2,0),(1,-2),(-2,1)],
        (0,3):  [(-1,0),(2,0),(-1,2),(2,-1)],
    },
}

# Scoring
LINE_SCORES   = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
ZONE_BONUSES  = {1:100,2:300,3:500,4:800,5:1200,6:1600,7:2000,8:2500,
                 9:3000,10:3600,11:4200,12:4800,13:5600,14:6400,15:7400,16:8400}

ZONE_FILL_PER_LINE = 0.12   # how much the zone meter fills per cleared line
ZONE_FILL_PER_DROP = 0.003  # small fill per hard drop
ZONE_DRAIN_RATE    = 0.004  # per frame while zone active

# Gravity (frames per cell) per level
GRAVITY = [48,43,38,33,28,23,18,13,8,6,5,5,5,4,4,4,3,3,3,2,
           2,2,2,2,2,2,2,2,2,1]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def add_alpha(color, alpha):
    return (*color[:3], alpha)

def hsv_to_rgb(h, s, v):
    h = h % 360
    s /= 100; v /= 100
    c = v * s; x = c*(1-abs((h/60)%2-1)); m = v-c
    if   h < 60:  r,g,b = c,x,0
    elif h < 120: r,g,b = x,c,0
    elif h < 180: r,g,b = 0,c,x
    elif h < 240: r,g,b = 0,x,c
    elif h < 300: r,g,b = x,0,c
    else:         r,g,b = c,0,x
    return (int((r+m)*255), int((g+m)*255), int((b+m)*255))

# ---------------------------------------------------------------------------
# Piece
# ---------------------------------------------------------------------------
class Piece:
    def __init__(self, key=None):
        self.key = key or random.choice(PIECE_KEYS)
        data = TETROMINOES[self.key]
        self.cells = [list(c) for c in data['cells']]
        self.color = data['color']
        self.rotation = 0
        # Spawn centred at top
        self.x = COLS//2 - 2
        self.y = -1 if self.key != 'I' else -1

    def rotated_cells(self, rot):
        """Return cells rotated to given rotation state."""
        cells = [list(c) for c in TETROMINOES[self.key]['cells']]
        times = rot % 4
        for _ in range(times):
            cells = [[-c[1], c[0]] for c in cells]
        # Normalise so min x/y == 0
        min_x = min(c[0] for c in cells)
        min_y = min(c[1] for c in cells)
        return [[c[0]-min_x, c[1]-min_y] for c in cells]

    def world_cells(self, dx=0, dy=0, rot=None):
        cells = self.rotated_cells(rot if rot is not None else self.rotation)
        return [[self.x + dx + c[0], self.y + dy + c[1]] for c in cells]

    def kick_type(self):
        return 'I' if self.key == 'I' else 'normal'

# ---------------------------------------------------------------------------
# Bag (7-bag randomiser)
# ---------------------------------------------------------------------------
class Bag:
    def __init__(self):
        self._bag = []

    def next(self):
        if not self._bag:
            self._bag = PIECE_KEYS[:]
            random.shuffle(self._bag)
        return self._bag.pop()

# ---------------------------------------------------------------------------
# Particles
# ---------------------------------------------------------------------------
class Particle:
    __slots__ = ('x','y','vx','vy','life','max_life','color','size','glow')
    def __init__(self, x, y, vx, vy, life, color, size=3, glow=False):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.glow = glow

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.08   # gravity
        self.vx *= 0.98
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        t = self.life / self.max_life
        alpha = int(255 * t)
        s = max(1, int(self.size * t))
        color = (*self.color[:3], alpha)
        if self.glow:
            gsurf = pygame.Surface((s*6, s*6), pygame.SRCALPHA)
            for r, a in [(s*3, 30), (s*2, 60), (s, alpha)]:
                pygame.draw.circle(gsurf, (*self.color[:3], a), (s*3, s*3), r)
            surf.blit(gsurf, (int(self.x)-s*3, int(self.y)-s*3))
        else:
            psurf = pygame.Surface((s*2+1, s*2+1), pygame.SRCALPHA)
            pygame.draw.circle(psurf, color, (s, s), s)
            surf.blit(psurf, (int(self.x)-s, int(self.y)-s))


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit_line_clear(self, row_y, color, count=40):
        for _ in range(count):
            x = BOARD_X + random.randint(0, COLS*CELL)
            vx = random.uniform(-4, 4)
            vy = random.uniform(-6, 0)
            life = random.randint(30, 70)
            size = random.randint(2, 6)
            self.particles.append(Particle(x, row_y, vx, vy, life, color, size, glow=True))

    def emit_lock(self, cells, color):
        for cx, cy in cells:
            px = BOARD_X + cx*CELL + CELL//2
            py = BOARD_Y + cy*CELL + CELL//2
            for _ in range(4):
                vx = random.uniform(-2, 2)
                vy = random.uniform(-3, 0)
                self.particles.append(Particle(px, py, vx, vy, random.randint(15,35), color, 2))

    def emit_zone_enter(self):
        for _ in range(120):
            x = BOARD_X + random.randint(0, COLS*CELL)
            y = BOARD_Y + random.randint(0, ROWS*CELL)
            vx = random.uniform(-5, 5)
            vy = random.uniform(-8, -1)
            life = random.randint(40, 90)
            color = hsv_to_rgb(random.randint(180,260), 80, 100)
            self.particles.append(Particle(x, y, vx, vy, life, color, random.randint(3,8), glow=True))

    def emit_zone_clear(self, count):
        for _ in range(count * 60):
            x = BOARD_X + random.randint(-20, COLS*CELL+20)
            y = random.randint(-50, SCREEN_H)
            vx = random.uniform(-6, 6)
            vy = random.uniform(-10, -2)
            life = random.randint(50, 120)
            color = hsv_to_rgb(random.randint(160, 280), 90, 100)
            self.particles.append(Particle(x, y, vx, vy, life, color, random.randint(4, 10), glow=True))

    def update_and_draw(self, surf):
        self.particles = [p for p in self.particles if p.update()]
        for p in self.particles:
            p.draw(surf)


# ---------------------------------------------------------------------------
# Star field background
# ---------------------------------------------------------------------------
class Starfield:
    def __init__(self, count=200):
        self.stars = []
        for _ in range(count):
            self.stars.append({
                'x': random.uniform(0, SCREEN_W),
                'y': random.uniform(0, SCREEN_H),
                'z': random.uniform(0.5, 3.0),
                'hue': random.randint(0, 360),
                'blink': random.uniform(0, math.pi*2),
            })
        self.pulse = 0.0

    def update(self, pulse_amount=0.0):
        self.pulse = pulse_amount
        for s in self.stars:
            s['blink'] += 0.03 + s['z']*0.01
            s['x'] -= s['z'] * 0.3 * (1 + pulse_amount*2)
            if s['x'] < 0:
                s['x'] = SCREEN_W
                s['y'] = random.uniform(0, SCREEN_H)

    def draw(self, surf):
        for s in self.stars:
            bright = int(100 + 80*math.sin(s['blink']) + self.pulse*75)
            r = max(1, int(s['z'] * (0.8 + self.pulse)))
            color = hsv_to_rgb(s['hue'], 60, min(100, bright//2.55))
            pygame.draw.circle(surf, color, (int(s['x']), int(s['y'])), r)


# ---------------------------------------------------------------------------
# Background ring / aurora effects
# ---------------------------------------------------------------------------
class AuroraLayer:
    def __init__(self):
        self.t = 0.0
        self.base_hue = random.randint(0, 360)

    def update(self, in_zone=False):
        self.t += 0.008 if not in_zone else 0.02
        self.base_hue = (self.base_hue + (0.3 if not in_zone else 1.5)) % 360

    def draw(self, surf, in_zone=False):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        bands = 6
        for i in range(bands):
            hue = (self.base_hue + i*(360//bands)) % 360
            sat = 80 if not in_zone else 100
            col = hsv_to_rgb(hue, sat, 50)
            alpha = int(18 + 12*math.sin(self.t + i))
            if in_zone:
                alpha = int(35 + 20*math.sin(self.t*2 + i))
            amp = 120 + 60*math.sin(self.t*0.7 + i*0.9)
            cx = SCREEN_W//2 + int(amp*math.cos(self.t*0.5 + i*1.1))
            cy = SCREEN_H//2 + int(amp*math.sin(self.t*0.4 + i*1.3))
            rad = int(180 + 100*math.sin(self.t*0.3 + i))
            pygame.draw.circle(s, (*col, alpha), (cx, cy), rad)
        surf.blit(s, (0,0))


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
class Board:
    def __init__(self):
        self.grid = [[None]*COLS for _ in range(ROWS)]

    def valid(self, cells):
        for x, y in cells:
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock(self, piece):
        for x, y in piece.world_cells():
            if 0 <= y < ROWS and 0 <= x < COLS:
                self.grid[y][x] = piece.color

    def clear_lines(self):
        cleared = []
        new_grid = []
        for r in range(ROWS):
            if all(self.grid[r][c] is not None for c in range(COLS)):
                cleared.append(r)
            else:
                new_grid.append(self.grid[r])
        for _ in cleared:
            new_grid.insert(0, [None]*COLS)
        self.grid = new_grid
        return cleared

    def collect_zone_lines(self):
        """In zone mode, collect lines without dropping them yet."""
        lines = []
        for r in range(ROWS):
            if all(self.grid[r][c] is not None for c in range(COLS)):
                lines.append(r)
        return lines

    def clear_zone_lines(self, lines):
        """Clear all collected zone lines at once."""
        new_grid = [row for i, row in enumerate(self.grid) if i not in lines]
        for _ in lines:
            new_grid.insert(0, [None]*COLS)
        self.grid = new_grid
        return len(lines)

    def draw(self, surf, flash_rows=None, zone_active=False):
        flash_rows = flash_rows or []
        # Board background
        board_rect = pygame.Rect(BOARD_X, BOARD_Y, COLS*CELL, ROWS*CELL)
        bg = pygame.Surface((COLS*CELL, ROWS*CELL), pygame.SRCALPHA)
        bg.fill((0,0,0,160))
        surf.blit(bg, (BOARD_X, BOARD_Y))

        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                rect = pygame.Rect(BOARD_X + c*CELL, BOARD_Y + r*CELL, CELL-1, CELL-1)
                if cell:
                    if r in flash_rows:
                        col = (255,255,255)
                    elif zone_active:
                        col = lerp_color(cell, (100, 200, 255), 0.5)
                    else:
                        col = cell
                    pygame.draw.rect(surf, col, rect)
                    # Shine
                    shine = pygame.Surface((CELL-1, CELL//3), pygame.SRCALPHA)
                    shine.fill((255,255,255,40))
                    surf.blit(shine, rect.topleft)
                else:
                    pygame.draw.rect(surf, (20,20,35,80), rect)

        # Grid lines
        gl = pygame.Surface((COLS*CELL, ROWS*CELL), pygame.SRCALPHA)
        for r in range(ROWS+1):
            pygame.draw.line(gl, (80,80,120,40), (0,r*CELL), (COLS*CELL,r*CELL))
        for c in range(COLS+1):
            pygame.draw.line(gl, (80,80,120,40), (c*CELL,0), (c*CELL,ROWS*CELL))
        surf.blit(gl, (BOARD_X, BOARD_Y))

        # Border
        border_color = (100,220,255) if zone_active else (80,80,160)
        if zone_active:
            # Glowing border
            for i in range(4, 0, -1):
                bc = (*border_color, 60//i)
                bs = pygame.Surface((COLS*CELL+i*4, ROWS*CELL+i*4), pygame.SRCALPHA)
                pygame.draw.rect(bs, bc, (0,0,COLS*CELL+i*4,ROWS*CELL+i*4), 2)
                surf.blit(bs, (BOARD_X-i*2, BOARD_Y-i*2))
        pygame.draw.rect(surf, border_color, board_rect, 2)


# ---------------------------------------------------------------------------
# Ghost piece helper
# ---------------------------------------------------------------------------
def ghost_y(board, piece):
    dy = 0
    while board.valid(piece.world_cells(dy=dy+1)):
        dy += 1
    return dy


# ---------------------------------------------------------------------------
# HUD drawing helpers
# ---------------------------------------------------------------------------
def draw_piece_preview(surf, key, ox, oy, scale=1.0, alpha=255, zone=False):
    if key is None:
        return
    data = TETROMINOES[key]
    cells = data['cells']
    color = data['color']
    if zone:
        color = lerp_color(color, (100,200,255), 0.6)
    sz = int(CELL * scale)
    for cx, cy in cells:
        r = pygame.Rect(ox + cx*sz, oy + cy*sz, sz-2, sz-2)
        s = pygame.Surface((sz-2, sz-2), pygame.SRCALPHA)
        s.fill((*color, alpha))
        surf.blit(s, r.topleft)
        shine = pygame.Surface((sz-2, (sz-2)//3), pygame.SRCALPHA)
        shine.fill((255,255,255,60))
        surf.blit(shine, r.topleft)


def draw_text(surf, text, x, y, size, color, center=False, alpha=255):
    font = pygame.font.SysFont('Arial', size, bold=True)
    img = font.render(text, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    if center:
        x -= img.get_width()//2
    surf.blit(img, (x, y))


def draw_zone_meter(surf, zone_pct, zone_active, t):
    mx, my = 20, 200
    mw, mh = 24, 300
    # Background
    pygame.draw.rect(surf, (20,20,40), (mx, my, mw, mh))
    pygame.draw.rect(surf, (60,60,120), (mx, my, mw, mh), 2)

    fill_h = int(mh * min(1.0, zone_pct))
    if fill_h > 0:
        if zone_active:
            col = hsv_to_rgb((t*3) % 360, 80, 100)
        else:
            pct = zone_pct
            col = lerp_color((0,100,200), (100,220,255), pct)
        pygame.draw.rect(surf, col, (mx+2, my+mh-fill_h, mw-4, fill_h-2))

        if not zone_active:
            # Glow
            gs = pygame.Surface((mw+20, fill_h), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*col, 40), (0, 0, mw+20, fill_h))
            surf.blit(gs, (mx-10, my+mh-fill_h))

    label = "ZONE" if not zone_active else "●ZONE●"
    col = (100,220,255) if zone_active else ((200,200,255) if zone_pct >= 1.0 else (80,80,160))
    draw_text(surf, label, mx + mw//2, my-22, 12, col, center=True)
    if zone_pct >= 1.0 and not zone_active:
        pulse = abs(math.sin(t*0.1))
        a = int(180 + 75*pulse)
        draw_text(surf, "TAB", mx+mw//2, my+mh+6, 11, (100,220,255,a), center=True, alpha=a)


# ---------------------------------------------------------------------------
# Flash / screen-shake helper
# ---------------------------------------------------------------------------
class ScreenShake:
    def __init__(self):
        self.intensity = 0

    def trigger(self, amount):
        self.intensity = max(self.intensity, amount)

    def update(self):
        if self.intensity > 0:
            self.intensity = max(0, self.intensity - 1)
        ox = random.randint(-self.intensity, self.intensity) if self.intensity else 0
        oy = random.randint(-self.intensity//2, self.intensity//2) if self.intensity else 0
        return ox, oy


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.bag = Bag()
        self.board = Board()
        self.particles = ParticleSystem()
        self.shake = ScreenShake()

        self.current = self._spawn()
        self.hold = None
        self.held_this_turn = False
        self.next_queue = deque([self.bag.next() for _ in range(5)])

        self.score = 0
        self.level = 1
        self.lines = 0
        self.combo = -1

        # Zone
        self.zone_meter = 0.0
        self.zone_active = False
        self.zone_lines_held = []
        self.zone_timer = 0

        # Gravity
        self.gravity_counter = 0
        self.lock_delay = 0
        self.max_lock_delay = 30
        self.lock_resets = 0
        self.max_lock_resets = 15

        # Line clear flash
        self.flash_rows = []
        self.flash_timer = 0

        # DAS / ARR
        self.das_dir = 0
        self.das_timer = 0
        self.arr_timer = 0
        DAS = 10  # frames
        ARR = 2

        self._das = DAS
        self._arr = ARR

        self.game_over = False
        self.paused = False
        self.t = 0   # frame counter

        self.last_action_spin = False
        self.back_to_back = False

        # Score popup
        self.score_popups = []   # (text, x, y, life, max_life, color)

        # Level-up flash
        self.level_flash = 0

    def _spawn(self):
        key = self.bag.next()
        return Piece(key)

    def _next_piece(self):
        key = self.next_queue.popleft()
        self.next_queue.append(self.bag.next())
        p = Piece(key)
        return p

    def _gravity_frames(self):
        idx = min(self.level - 1, len(GRAVITY)-1)
        return GRAVITY[idx]

    def hold_piece(self):
        if self.held_this_turn:
            return
        if self.hold is None:
            self.hold = self.current.key
            self.current = self._next_piece()
        else:
            self.hold, old_key = self.current.key, self.hold
            self.current = Piece(old_key)
        self.held_this_turn = True
        self.lock_delay = 0
        self.lock_resets = 0

    def try_move(self, dx, dy):
        if self.board.valid(self.current.world_cells(dx=dx, dy=dy)):
            self.current.x += dx
            self.current.y += dy
            if dx != 0:
                self.lock_delay = 0
                self.lock_resets += 1
            return True
        return False

    def try_rotate(self, cw=True):
        old_rot = self.current.rotation
        new_rot = (old_rot + (1 if cw else -1)) % 4
        # Test base position
        test_cells = self.current.rotated_cells(new_rot)
        world = [[self.current.x + c[0], self.current.y + c[1]] for c in test_cells]
        if self.board.valid(world):
            self.current.rotation = new_rot
            self.lock_delay = 0
            self.lock_resets += 1
            self.last_action_spin = True
            return True
        # Wall kicks
        kicks = WALL_KICKS[self.current.kick_type()].get((old_rot, new_rot), [])
        for kx, ky in kicks:
            world = [[self.current.x + kx + c[0], self.current.y + ky + c[1]] for c in test_cells]
            if self.board.valid(world):
                self.current.x += kx
                self.current.y += ky
                self.current.rotation = new_rot
                self.lock_delay = 0
                self.lock_resets += 1
                self.last_action_spin = True
                return True
        return False

    def hard_drop(self):
        dy = ghost_y(self.board, self.current)
        self.score += dy * 2
        self.current.y += dy
        self.zone_meter = min(1.0, self.zone_meter + ZONE_FILL_PER_DROP)
        self._lock_piece()

    def soft_drop(self):
        if self.try_move(0, 1):
            self.score += 1

    def _lock_piece(self):
        wc = self.current.world_cells()
        self.particles.emit_lock(wc, self.current.color)
        self.board.lock(self.current)

        if self.zone_active:
            zone_lines = self.board.collect_zone_lines()
            self.zone_lines_held.extend(zone_lines)
        else:
            cleared = self.board.clear_lines()
            if cleared:
                self._process_clears(cleared)

        self.current = self._next_piece()
        self.held_this_turn = False
        self.lock_delay = 0
        self.lock_resets = 0
        self.last_action_spin = False

        # Check game over
        if not self.board.valid(self.current.world_cells()):
            if self.zone_active:
                self._end_zone()
            else:
                self.game_over = True

    def _process_clears(self, cleared):
        n = len(cleared)
        self.combo += 1
        self.lines += n
        old_level = self.level
        self.level = self.lines // 10 + 1
        if self.level > old_level:
            self.level_flash = 60

        # B2B
        difficult = (n == 4) or (self.last_action_spin and n > 0)
        b2b_mult = 1.5 if (self.back_to_back and difficult) else 1.0
        self.back_to_back = difficult

        base = LINE_SCORES.get(n, 0) * self.level
        combo_bonus = 50 * self.combo * self.level if self.combo > 0 else 0
        pts = int(base * b2b_mult) + combo_bonus
        self.score += pts

        # Zone meter fill
        self.zone_meter = min(1.0, self.zone_meter + ZONE_FILL_PER_LINE * n)

        # Flash + particles
        self.flash_rows = list(cleared)
        self.flash_timer = 20
        self.shake.trigger(4 * n)
        for r in cleared:
            cy = BOARD_Y + r*CELL + CELL//2
            col = (200, 220, 255) if n == 4 else (180,180,255)
            self.particles.emit_line_clear(cy, col, count=20+10*n)

        # Score popup
        labels = {1:'SINGLE',2:'DOUBLE',3:'TRIPLE',4:'TETRIS!'}
        label = labels.get(n,'')
        if n == 4: label = '✦ TETRIS! ✦'
        if self.last_action_spin and n > 0: label = f'T-SPIN {label}'
        if b2b_mult > 1: label = 'BACK-TO-BACK ' + label
        px = BOARD_X + COLS*CELL//2
        py = BOARD_Y + cleared[0]*CELL
        color = (255,220,80) if n == 4 else (180,220,255)
        self.score_popups.append([label, px, py, 90, 90, color])

    def activate_zone(self):
        if self.zone_meter < 1.0 or self.zone_active:
            return
        self.zone_active = True
        self.zone_timer = 600   # 10 seconds at 60fps
        self.zone_lines_held = []
        self.zone_meter = 1.0
        self.particles.emit_zone_enter()
        self.shake.trigger(8)

    def _end_zone(self):
        n = len(self.zone_lines_held)
        if n > 0:
            self.board.clear_zone_lines(self.zone_lines_held)
            bonus = ZONE_BONUSES.get(n, n*600)
            self.score += bonus * self.level
            self.particles.emit_zone_clear(n)
            self.shake.trigger(12)
            label = f'ZONE CLEAR! ×{n} lines!'
            self.score_popups.append([label, BOARD_X+COLS*CELL//2, BOARD_Y+ROWS*CELL//2-30, 120, 120, (100,220,255)])
            self.lines += n
            old_level = self.level
            self.level = self.lines // 10 + 1
            if self.level > old_level:
                self.level_flash = 60

        self.zone_active = False
        self.zone_meter = 0.0
        self.zone_lines_held = []

    def update(self, keys_held):
        if self.game_over or self.paused:
            return

        self.t += 1

        # DAS/ARR handling
        if self.das_dir != 0:
            self.das_timer += 1
            if self.das_timer >= self._das:
                self.arr_timer += 1
                if self.arr_timer >= self._arr:
                    self.arr_timer = 0
                    self.try_move(self.das_dir, 0)
        else:
            self.das_timer = 0

        # Zone timer
        if self.zone_active:
            self.zone_timer -= 1
            self.zone_meter = max(0.0, self.zone_meter - ZONE_DRAIN_RATE)
            if self.zone_timer <= 0 or self.zone_meter <= 0:
                self._end_zone()

        # Gravity
        if not self.zone_active:
            gf = self._gravity_frames()
        else:
            gf = max(8, self._gravity_frames() * 3)  # slow in zone

        self.gravity_counter += 1
        if self.gravity_counter >= gf:
            self.gravity_counter = 0
            if not self.try_move(0, 1):
                # Can't fall: lock delay
                self.lock_delay += 1
                if self.lock_delay >= self.max_lock_delay:
                    self._lock_piece()
            else:
                self.lock_delay = 0

        # Flash
        if self.flash_timer > 0:
            self.flash_timer -= 1
            if self.flash_timer == 0:
                self.flash_rows = []

        # Score popups
        new_popups = []
        for p in self.score_popups:
            p[2] -= 1.0   # float up
            p[3] -= 1
            if p[3] > 0:
                new_popups.append(p)
        self.score_popups = new_popups

        if self.level_flash > 0:
            self.level_flash -= 1

    def start_das(self, direction):
        if self.das_dir != direction:
            self.das_dir = direction
            self.das_timer = 0
            self.arr_timer = 0
            self.try_move(direction, 0)

    def stop_das(self, direction):
        if self.das_dir == direction:
            self.das_dir = 0


# ---------------------------------------------------------------------------
# Main renderer / game loop
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption('Tetris Effect: Connected')
    clock = pygame.time.Clock()

    # Synthesise simple sound effects using pygame mixer
    def make_beep(freq, dur_ms, vol=0.3, wave='sine'):
        sample_rate = 44100
        n = int(sample_rate * dur_ms / 1000)
        buf = []
        for i in range(n):
            t_s = i / sample_rate
            if wave == 'sine':
                v = math.sin(2*math.pi*freq*t_s)
            elif wave == 'square':
                v = 1.0 if math.sin(2*math.pi*freq*t_s) >= 0 else -1.0
            else:
                v = math.sin(2*math.pi*freq*t_s)
            env = min(1.0, (n-i)/(n*0.1))   # fade out
            buf.append(int(v * env * vol * 32767))
        import array as arr
        stereo = arr.array('h')
        for s in buf:
            stereo.append(s); stereo.append(s)
        sound = pygame.sndarray.make_sound(stereo)
        return sound

    try:
        snd_move   = make_beep(220, 40, 0.12, 'sine')
        snd_rotate = make_beep(330, 50, 0.15, 'sine')
        snd_lock   = make_beep(180, 80, 0.2,  'square')
        snd_line1  = make_beep(440, 120, 0.3, 'sine')
        snd_line4  = make_beep(880, 200, 0.5, 'sine')
        snd_zone   = make_beep(660, 300, 0.6, 'sine')
        snd_hold   = make_beep(280, 60, 0.15, 'sine')
    except Exception:
        snd_move = snd_rotate = snd_lock = snd_line1 = snd_line4 = snd_zone = snd_hold = None

    def play(snd):
        if snd:
            try: snd.play()
            except Exception: pass

    starfield = Starfield(220)
    aurora = AuroraLayer()
    game = Game()

    # Particle surface (reused)
    particle_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    font_big   = pygame.font.SysFont('Arial', 48, bold=True)
    font_med   = pygame.font.SysFont('Arial', 26, bold=True)
    font_small = pygame.font.SysFont('Arial', 16, bold=True)
    font_tiny  = pygame.font.SysFont('Arial', 13)

    def render_text_glow(surf, text, font, color, x, y, center=False, glow_color=None, glow_radius=6):
        img = font.render(text, True, color)
        if glow_color:
            glow = font.render(text, True, glow_color)
            for dx in range(-glow_radius, glow_radius+1, 2):
                for dy in range(-glow_radius, glow_radius+1, 2):
                    if dx*dx+dy*dy <= glow_radius*glow_radius:
                        g2 = glow.copy(); g2.set_alpha(40)
                        bx = x - img.get_width()//2 + dx if center else x + dx
                        surf.blit(g2, (bx, y+dy))
        bx = x - img.get_width()//2 if center else x
        surf.blit(img, (bx, y))

    running = True
    while running:
        dt = clock.tick(FPS)

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key

                if game.game_over:
                    if k == pygame.K_r:
                        game = Game()
                    continue

                if k == pygame.K_ESCAPE or k == pygame.K_p:
                    game.paused = not game.paused

                if game.paused:
                    continue

                if k == pygame.K_LEFT:
                    game.start_das(-1)
                    play(snd_move)
                elif k == pygame.K_RIGHT:
                    game.start_das(1)
                    play(snd_move)
                elif k == pygame.K_DOWN:
                    game.soft_drop()
                elif k == pygame.K_UP or k == pygame.K_x:
                    if game.try_rotate(cw=True): play(snd_rotate)
                elif k == pygame.K_z:
                    if game.try_rotate(cw=False): play(snd_rotate)
                elif k == pygame.K_SPACE:
                    game.hard_drop(); play(snd_lock)
                elif k == pygame.K_c:
                    game.hold_piece(); play(snd_hold)
                elif k == pygame.K_TAB or k == pygame.K_f:
                    if game.zone_meter >= 1.0:
                        game.activate_zone(); play(snd_zone)

            elif event.type == pygame.KEYUP:
                k = event.key
                if k == pygame.K_LEFT:  game.stop_das(-1)
                if k == pygame.K_RIGHT: game.stop_das(1)

        # Soft-drop held
        if not game.paused and not game.game_over:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_DOWN]:
                game.gravity_counter += 3

        # --- Update ---
        game.update(pygame.key.get_pressed())

        pulse = 0.0
        if game.zone_active:
            pulse = 0.6 + 0.4*math.sin(game.t * 0.15)
        elif game.flash_timer > 0:
            pulse = game.flash_timer / 20.0 * 0.4

        starfield.update(pulse_amount=pulse)
        aurora.update(in_zone=game.zone_active)

        # --- Render ---
        ox, oy = game.shake.update()

        # Background
        screen.fill((4, 4, 18))
        starfield.draw(screen)
        aurora.draw(screen, in_zone=game.zone_active)

        # Zone vignette
        if game.zone_active:
            vsurf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pulse_a = int(30 + 20*math.sin(game.t * 0.12))
            for i in range(5):
                margin = i * 18
                rect = pygame.Rect(BOARD_X - margin, BOARD_Y - margin,
                                   COLS*CELL + margin*2, ROWS*CELL + margin*2)
                col = (*hsv_to_rgb((game.t*2)%360, 70, 90), pulse_a//(i+1))
                pygame.draw.rect(vsurf, col, rect, 2)
            screen.blit(vsurf, (ox, oy))

        # Board
        game.board.draw(screen, flash_rows=game.flash_rows if game.flash_timer > 0 else [],
                        zone_active=game.zone_active)

        # Ghost piece
        if not game.game_over:
            dy = ghost_y(game.board, game.current)
            ghost_cells = game.current.world_cells(dy=dy)
            gsurf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for cx, cy in ghost_cells:
                if cy >= 0:
                    r = pygame.Rect(BOARD_X + cx*CELL + ox, BOARD_Y + cy*CELL + oy, CELL-1, CELL-1)
                    gcol = lerp_color(game.current.color, (40,40,60), 0.6)
                    pygame.draw.rect(gsurf, (*gcol, 120), r)
                    pygame.draw.rect(gsurf, (*game.current.color, 60), r, 1)
            screen.blit(gsurf, (0, 0))

            # Current piece
            for cx, cy in game.current.world_cells():
                if cy >= 0:
                    col = game.current.color
                    if game.zone_active:
                        col = lerp_color(col, (120, 210, 255), 0.4)
                    r = pygame.Rect(BOARD_X + cx*CELL + ox, BOARD_Y + cy*CELL + oy, CELL-1, CELL-1)
                    pygame.draw.rect(screen, col, r)
                    shine = pygame.Surface((CELL-1, (CELL-1)//3), pygame.SRCALPHA)
                    shine.fill((255,255,255,60))
                    screen.blit(shine, r.topleft)

        # Particles
        particle_surf.fill((0,0,0,0))
        game.particles.update_and_draw(particle_surf)
        screen.blit(particle_surf, (ox, oy))

        # --- HUD ---
        # Zone meter
        draw_zone_meter(screen, game.zone_meter, game.zone_active, game.t)

        # HOLD box
        hold_x, hold_y = 60, 50
        pygame.draw.rect(screen, (20,20,40), (hold_x-5, hold_y-5, 110, 90))
        pygame.draw.rect(screen, (60,60,120), (hold_x-5, hold_y-5, 110, 90), 2)
        draw_text(screen, 'HOLD', hold_x+45, hold_y-22, 14, (150,150,220), center=True)
        if game.hold:
            halpha = 140 if game.held_this_turn else 255
            draw_piece_preview(screen, game.hold, hold_x, hold_y, scale=0.85, alpha=halpha, zone=game.zone_active)

        # NEXT queue
        next_x = BOARD_X + COLS*CELL + 22
        draw_text(screen, 'NEXT', next_x + 50, BOARD_Y, 14, (150,150,220), center=True)
        for i, key in enumerate(game.next_queue):
            sc = 0.85 if i == 0 else 0.65
            alpha = 255 if i == 0 else int(255 - i*35)
            draw_piece_preview(screen, key, next_x + 5, BOARD_Y + 20 + i*68, scale=sc, alpha=alpha, zone=game.zone_active)

        # Score / Level / Lines
        info_x = next_x
        info_y = BOARD_Y + 20 + 5*68 + 10
        pygame.draw.rect(screen, (20,20,40), (info_x-2, info_y, 130, 140))
        pygame.draw.rect(screen, (60,60,120), (info_x-2, info_y, 130, 140), 1)

        lfc = (200,255,100) if game.level_flash > 0 else (200,200,255)
        draw_text(screen, 'SCORE',  info_x+4, info_y+6,  13, (130,130,200))
        draw_text(screen, str(game.score), info_x+4, info_y+22, 18, (255,255,255))
        draw_text(screen, 'LEVEL',  info_x+4, info_y+52, 13, (130,130,200))
        draw_text(screen, str(game.level), info_x+4, info_y+68, 22, lfc)
        draw_text(screen, 'LINES',  info_x+4, info_y+96, 13, (130,130,200))
        draw_text(screen, str(game.lines), info_x+4, info_y+112, 18, (255,255,255))

        # Zone active HUD
        if game.zone_active:
            zt_secs = game.zone_timer // FPS
            zt_frac = (game.zone_timer % FPS) / FPS
            zp = min(1.0, game.zone_meter)
            zcol = hsv_to_rgb((game.t*3)%360, 80, 100)
            render_text_glow(screen, 'Z O N E', font_big, zcol,
                             SCREEN_W//2, 8, center=True, glow_color=(50,150,255), glow_radius=8)
            # Zone line counter
            zl = len(game.zone_lines_held)
            if zl:
                render_text_glow(screen, f'+{zl} lines', font_med, (180,255,255),
                                 SCREEN_W//2, 65, center=True, glow_color=(50,150,255))

            # Zone timer bar
            bar_w = COLS*CELL
            bar_h = 6
            bx = BOARD_X
            by = BOARD_Y + ROWS*CELL + 8
            pygame.draw.rect(screen, (20,20,60), (bx, by, bar_w, bar_h))
            fill = int(bar_w * zp)
            pygame.draw.rect(screen, zcol, (bx, by, fill, bar_h))

        # Score popups
        for pop in game.score_popups:
            label, px, py, life, max_life, color = pop
            t_fade = life / max_life
            alpha = int(255 * min(1.0, t_fade * 2))
            fs = 20 if 'TETRIS' in label or 'ZONE' in label else 16
            font_p = pygame.font.SysFont('Arial', fs, bold=True)
            img = font_p.render(label, True, color)
            img.set_alpha(alpha)
            screen.blit(img, (int(px) - img.get_width()//2, int(py)))

        # Combo indicator
        if game.combo > 0:
            c_col = lerp_color((200,200,255), (255,160,0), min(1.0, game.combo/8))
            draw_text(screen, f'COMBO ×{game.combo+1}',
                      BOARD_X - 10, BOARD_Y + ROWS*CELL + 20, 16, c_col)

        # Controls hint
        draw_text(screen, '←→ Move  ↑/X Rotate CW  Z Rotate CCW',
                  BOARD_X, SCREEN_H-38, 12, (80,80,120))
        draw_text(screen, 'Space Hard Drop  C Hold  Tab ZONE  P Pause',
                  BOARD_X, SCREEN_H-22, 12, (80,80,120))

        # Pause overlay
        if game.paused:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0,0,0,160))
            screen.blit(ov, (0,0))
            render_text_glow(screen, 'PAUSED', font_big, (200,220,255),
                             SCREEN_W//2, SCREEN_H//2-40, center=True,
                             glow_color=(80,100,255), glow_radius=10)
            draw_text(screen, 'Press P or Esc to resume', SCREEN_W//2, SCREEN_H//2+30,
                      18, (150,150,200), center=True)

        # Game over overlay
        if game.game_over:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0,0,0,190))
            screen.blit(ov, (0,0))
            render_text_glow(screen, 'GAME OVER', font_big, (255,100,100),
                             SCREEN_W//2, SCREEN_H//2-80, center=True,
                             glow_color=(200,0,0), glow_radius=12)
            draw_text(screen, f'Score: {game.score}', SCREEN_W//2, SCREEN_H//2,
                      28, (255,255,255), center=True)
            draw_text(screen, f'Level: {game.level}   Lines: {game.lines}',
                      SCREEN_W//2, SCREEN_H//2+40, 20, (180,180,200), center=True)
            t_blink = int(time.time()*2) % 2
            if t_blink:
                draw_text(screen, 'Press R to restart', SCREEN_W//2, SCREEN_H//2+90,
                          22, (200,200,255), center=True)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
