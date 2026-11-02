"""
LANTERN KEEPER - 2D top-down survival game (Pygame)
You carry a lantern in a dark haunted ruin. Collect fireflies, avoid ghosts.

Customization (unique rule): LIGHT = OIL.
  * Your visible radius is tied to your lantern oil. Oil drains constantly.
  * Fireflies give +10 score and +8 oil. Oil flasks give +35 oil.
  * Ghosts are only visible inside your light (only their red eyes show outside).
  * Game ends if oil reaches 0 OR you lose all 3 lives.
Difficulty: level = 1 + fireflies // 5 -> more ghosts, faster ghosts, faster oil drain.

Controls: Arrows / WASD = move | P = pause | ENTER = start/restart | ESC = quit
"""
import math
import random
import sys
from array import array

import pygame

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()
W = H = 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Lantern Keeper")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("georgia", 22, bold=True)
BIG = pygame.font.SysFont("georgia", 54, bold=True)
SMALL = pygame.font.SysFont("georgia", 17)
AMBER, CREAM, RED, BLUE = (255, 190, 80), (240, 232, 210), (255, 70, 80), (120, 190, 255)
PR, FR, GR_, FLR = 12, 8, 14, 10     # radii: player, firefly, ghost, flask


# ---------------- Sound (generated in code) ----------------
def make_sound(notes, vol=0.25, wave="sine"):
    data, rate = array("h"), 44100
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            s = math.sin(2 * math.pi * freq * i / rate)
            if wave == "square":
                s = 1 if s >= 0 else -1
            data.append(int(32767 * vol * s * (1 - i / n)))
    return pygame.mixer.Sound(buffer=data.tobytes())


try:
    SND = {"fly": make_sound([(880, .07), (1170, .09)]), "flask": make_sound([(300, .1), (500, .15)]),
           "hit": make_sound([(120, .35)], 0.4, "square"), "over": make_sound([(260, .25), (160, .5)], 0.3, "square")}
except pygame.error:
    SND = {}


def play(n):
    if n in SND:
        SND[n].play()


# ---------------- Graphics helpers ----------------
FLOOR = pygame.Surface((W, H))
FLOOR.fill((30, 36, 50))
for _i in range(0, W, 40):
    pygame.draw.line(FLOOR, (37, 44, 62), (_i, 0), (_i, H))
    pygame.draw.line(FLOOR, (37, 44, 62), (0, _i), (W, _i))


def glow(pos, r, color):
    g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for i in range(4, 0, -1):
        pygame.draw.circle(g, (*color, 35), (r, r), int(r * i / 4))
    screen.blit(g, (pos[0] - r, pos[1] - r))


def text(s, font, color, center=None, topleft=None):
    img = font.render(s, True, color)
    r = img.get_rect()
    if center:
        r.center = center
    else:
        r.topleft = topleft
    screen.blit(img, r)


def make_walls():
    walls = []
    while len(walls) < 7:
        r = pygame.Rect(random.randint(40, W - 150), random.randint(40, H - 150),
                        random.choice([30, 90, 130]), random.choice([30, 90, 130]))
        if not r.inflate(120, 120).collidepoint(W // 2, H // 2):
            walls.append(r)
    return walls


# ---------------- Game ----------------
class Game:
    def __init__(self):
        self.state = "start"       # start | playing | paused | over
        self.hi = 0
        self.reset()

    def reset(self):
        self.walls = make_walls()
        self.x = self.y = W / 2
        self.score, self.lives, self.oil, self.collected = 0, 3, 100.0, 0
        self.inv, self.t, self.flask = 0.0, 0.0, None
        self.flies = [self.free_pos(100) for _ in range(6)]
        self.ghosts = [self.free_pos(250)]

    def level(self):
        return 1 + self.collected // 5

    def free_pos(self, far):
        while True:
            p = [random.randint(30, W - 30), random.randint(30, H - 30)]
            if (pygame.Rect(p[0] - 14, p[1] - 14, 28, 28).collidelist(self.walls) == -1
                    and math.hypot(p[0] - self.x, p[1] - self.y) > far):
                return p

    def update(self, dt):
        k = pygame.key.get_pressed()
        dx = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (k[pygame.K_LEFT] or k[pygame.K_a])
        dy = (k[pygame.K_DOWN] or k[pygame.K_s]) - (k[pygame.K_UP] or k[pygame.K_w])
        if dx and dy:
            dx, dy = dx * 0.707, dy * 0.707
        nx = min(W - PR, max(PR, self.x + dx * 200 * dt))      # move per axis so you slide along walls
        if pygame.Rect(int(nx) - PR, int(self.y) - PR, 2 * PR, 2 * PR).collidelist(self.walls) == -1:
            self.x = nx
        ny = min(H - PR, max(PR, self.y + dy * 200 * dt))
        if pygame.Rect(int(self.x) - PR, int(ny) - PR, 2 * PR, 2 * PR).collidelist(self.walls) == -1:
            self.y = ny

        self.oil -= (4 + self.level() * 0.6) * dt
        self.inv = max(0, self.inv - dt)
        self.t += dt

        for f in self.flies[:]:                                  # circle-circle collision
            if math.hypot(f[0] - self.x, f[1] - self.y) < PR + FR:
                self.flies.remove(f)
                self.flies.append(self.free_pos(100))
                self.score += 10
                self.collected += 1
                self.oil = min(100, self.oil + 8)
                play("fly")
        if self.flask is None and random.random() < dt * 0.15:
            self.flask = self.free_pos(100)
        if self.flask and math.hypot(self.flask[0] - self.x, self.flask[1] - self.y) < PR + FLR:
            self.oil = min(100, self.oil + 35)
            self.flask = None
            play("flask")

        while len(self.ghosts) < min(7, 1 + self.level()):
            self.ghosts.append(self.free_pos(250))
        for g in self.ghosts:
            a = math.atan2(self.y - g[1], self.x - g[0])
            sp = 55 + self.level() * 12
            g[0] += math.cos(a) * sp * dt
            g[1] += math.sin(a) * sp * dt
            if self.inv <= 0 and math.hypot(g[0] - self.x, g[1] - self.y) < PR + GR_:
                self.lives -= 1
                self.inv = 1.5
                g[:] = self.free_pos(250)
                play("hit")
        if self.lives <= 0 or self.oil <= 0:
            self.state = "over"
            self.hi = max(self.hi, self.score)
            play("over")

    # --- drawing ---
    def darkness(self):
        r = 70 + self.oil * 1.4 + random.uniform(-2, 2)         # LIGHT RADIUS = OIL
        d = pygame.Surface((W, H), pygame.SRCALPHA)
        d.fill((4, 3, 12, 242))
        steps = 14
        for i in range(steps, 0, -1):
            pygame.draw.circle(d, (4, 3, 12, int(242 * (i / steps) ** 2)),
                               (int(self.x), int(self.y)), int(r * i / steps))
        screen.blit(d, (0, 0))

    def draw_play(self):
        screen.blit(FLOOR, (0, 0))
        for w in self.walls:
            pygame.draw.rect(screen, (70, 66, 86), w)
            pygame.draw.rect(screen, (110, 104, 130), w, 3)
        for g in self.ghosts:                                   # ghost bodies (hidden by darkness)
            gx, gy = int(g[0]), int(g[1])
            pygame.draw.circle(screen, (190, 205, 240), (gx, gy), GR_)
            pygame.draw.rect(screen, (190, 205, 240), (gx - GR_, gy, 2 * GR_, GR_))
        if self.inv <= 0 or int(self.t * 10) % 2:               # player blinks when invulnerable
            pygame.draw.circle(screen, CREAM, (int(self.x), int(self.y)), PR)
            pygame.draw.circle(screen, AMBER, (int(self.x) + 9, int(self.y) - 4), 5)
        self.darkness()
        for g in self.ghosts:                                   # red eyes always visible
            for ox in (-5, 5):
                pygame.draw.circle(screen, RED, (int(g[0]) + ox, int(g[1]) - 3), 3)
        pulse = 1 + 0.25 * math.sin(self.t * 6)
        for f in self.flies:
            glow(f, int(18 * pulse), (200, 255, 120))
            pygame.draw.circle(screen, (235, 255, 160), (int(f[0]), int(f[1])), 4)
        if self.flask:
            glow(self.flask, 22, BLUE)
            pygame.draw.rect(screen, BLUE, (self.flask[0] - 6, self.flask[1] - 8, 12, 16), border_radius=4)
        # HUD
        text(f"SCORE {self.score}", FONT, CREAM, topleft=(14, 10))
        text(f"LEVEL {self.level()}", FONT, AMBER, center=(W // 2, 24))
        for i in range(max(0, self.lives)):
            pygame.draw.circle(screen, RED, (W - 24 - i * 24, 24), 9)
        pygame.draw.rect(screen, (50, 50, 70), (14, 44, 160, 14), border_radius=6)
        pygame.draw.rect(screen, AMBER if self.oil > 25 else RED,
                         (14, 44, int(160 * max(0, self.oil) / 100), 14), border_radius=6)
        text("OIL", SMALL, CREAM, topleft=(182, 41))

    def overlay(self, lines):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((4, 3, 12, 225))
        screen.blit(dim, (0, 0))
        y = 170
        for s, f, c in lines:
            text(s, f, c, center=(W // 2, y))
            y += 64 if f is BIG else 34


def main():
    g = Game()
    while True:
        dt = min(0.05, clock.tick(60) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_p:
                    g.state = "paused" if g.state == "playing" else "playing" if g.state == "paused" else g.state
                if e.key in (pygame.K_RETURN, pygame.K_SPACE) and g.state in ("start", "over"):
                    g.reset()
                    g.state = "playing"
        if g.state == "playing":
            g.update(dt)
        if g.state == "start":
            screen.blit(FLOOR, (0, 0))
            g.overlay([("LANTERN KEEPER", BIG, AMBER), ("Your light is your life.", FONT, CREAM),
                       ("Collect fireflies: +10 score, +8 oil", SMALL, (200, 255, 120)),
                       ("Blue flask: +35 oil", SMALL, BLUE),
                       ("Less oil = smaller light. Ghosts hide in the dark!", SMALL, RED),
                       ("Arrows / WASD to move   P = pause", SMALL, CREAM),
                       ("PRESS ENTER TO BEGIN", FONT, AMBER)])
        else:
            g.draw_play()
            if g.state == "paused":
                g.overlay([("PAUSED", BIG, AMBER), ("Press P to resume", FONT, CREAM)])
            elif g.state == "over":
                why = "Your lantern went out..." if g.oil <= 0 else "The ghosts got you..."
                g.overlay([("GAME OVER", BIG, RED), (why, FONT, CREAM),
                           (f"Score {g.score}   Level {g.level()}   Best {g.hi}", FONT, AMBER),
                           ("PRESS ENTER TO PLAY AGAIN", FONT, BLUE)])
        pygame.display.flip()


if __name__ == "__main__":
    main()
