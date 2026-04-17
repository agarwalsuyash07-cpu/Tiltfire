import math, random, sys, collections
import pygame
from pygame.math import Vector2

# ---------- Tunable parameters ----------
SCREEN_W, SCREEN_H = 1000, 700
FPS = 60
CENTER_Y = SCREEN_H // 2.5  # horizontal wall at CENTER_Y

# Movement / "tilt" feel (player)
ACCEL_STRENGTH = 700.0
MAX_SPEED = 1000.0
DRAG = 6.0
INPUT_RAMP_TIME = 0.08

# Charge shooting (player)
CHARGE_DURATION = 1.2
MIN_PROJ_SPEED = 350.0
MAX_PROJ_SPEED = 1000.0
MIN_PROJ_RADIUS = 4
MAX_PROJ_RADIUS = 28
MIN_DAMAGE = 6
MAX_DAMAGE = 50
PROJECTILE_LIFETIME = 3.0

# Player visuals / physics
PLAYER_RADIUS = 18
PLAYER_SHAPE = "triangle"
PLAYER_COLOR = (230, 230, 230)
CHARGE_COLOR = (200, 120, 255)
HIT_FLASH_TIME = 0.08
PLAYER_STARTING_HEALTH = 100

# Reload / ammo
PLAYER_MAX_AMMO = 7
PLAYER_RELOAD_PER_BULLET = 0.66  # seconds to reload one bullet
PLAYER_RELOAD_TIME = PLAYER_RELOAD_PER_BULLET * PLAYER_MAX_AMMO  # derived total

# Boss params (including ammo)
BOSS_RADIUS = 36
BOSS_COLOR = (80, 200, 220)
BOSS_MAX_HEALTH_BASE = 300
BOSS_MOVE_SPEED_BASE = 180.0
BOSS_ACCEL_BASE = 900.0
BOSS_DRAG = 6.0
BOSS_CHARGE_DURATION = 1.1
BOSS_MIN_PROJ_SPEED = 260.0
BOSS_MAX_PROJ_SPEED = 720.0
BOSS_MIN_PROJECTILE_RADIUS = 6
BOSS_MAX_PROJECTILE_RADIUS = 30
BOSS_FIRE_COOLDOWN_BASE = 1.0
BOSS_LEARN_WINDOW = 40
BOSS_VIBRATE_TIME = 0.14
BOSS_VIBRATE_MAG = 8.0
# -------- Boss AI States --------
BOSS_STATE_APPROACH = "approach"
BOSS_STATE_STRAFE = "strafe"
BOSS_STATE_RETREAT = "retreat"
BOSS_STATE_CHARGE = "charge"
BOSS_STATE_POKE = "poke"


# Boss magazine uses same size by default; per-bullet reload same as player
BOSS_MAX_AMMO = PLAYER_MAX_AMMO
BOSS_RELOAD_PER_BULLET = PLAYER_RELOAD_PER_BULLET

# Auto reload delay (start reloading if no shot fired for this many seconds)
AUTO_RELOAD_DELAY = 2.5

# Particles
PARTICLE_COUNT_HIT = 12
PARTICLE_LIFE_MIN = 0.35
PARTICLE_LIFE_MAX = 0.85

# UI / visuals
BACKGROUND_COLOR = (0, 0, 0)
HUD_COLOR = (200, 200, 200)
PROJECTILE_GLOW = (180, 160, 255)
PLAYER_HIT_TINT = (255, 180, 180)
FONT_NAME = "Arial"

# Middle divider flash
DIVIDER_FLASH_DURATION = 1.5   # seconds
DIVIDER_FLASH_FREQ = 6.0       # flashes per second
DIVIDER_COLOR = (180, 180, 180)
DIVIDER_THICKNESS = 4
divider_flash_timer = 0.0



pygame.init()
# initialize mixer separately (failure shouldn't crash game)
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2)
except Exception:
    print("Warning: audio mixer initialization failed — sounds disabled")

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
clock = pygame.time.Clock()
font = pygame.font.SysFont(FONT_NAME, 18)
big_font = pygame.font.SysFont(FONT_NAME, 36)
title_font = pygame.font.SysFont(FONT_NAME, 48)

# Globals for UI
last_frame_surface = None
restart_btn = None
quit_btn = None

# Optional: numpy for sound generation
try:
    import numpy as np
except Exception:
    np = None

# Simple sound generation helper (uses numpy if available). If numpy not installed, sounds will be None.
def make_sine_sound(freq=440.0, duration=0.08, volume=0.28, sample_rate=44100):
    if np is None:
        return None
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(2 * np.pi * freq * t)
    env = np.ones_like(wave)
    atk = int(0.01 * sample_rate)
    rel = int(0.02 * sample_rate)
    if atk > 0:
        env[:atk] = np.linspace(0.0, 1.0, atk)
    if rel > 0:
        env[-rel:] = np.linspace(1.0, 0.0, rel)
    wave *= env
    audio = (wave * (32767 * volume)).astype(np.int16)
    stereo = np.column_stack((audio, audio))
    try:
        snd = pygame.sndarray.make_sound(stereo.copy())
        return snd
    except Exception:
        return None

# create some sounds (may be None if numpy isn't installed)
player_shot_sound = make_sine_sound(900.0, 0.07, 0.28)
boss_shot_sound = make_sine_sound(520.0, 0.10, 0.26)
hit_sound = make_sine_sound(1400.0, 0.06, 0.36)
reload_sound = make_sine_sound(220.0, 0.10, 0.22)
empty_click_sound = make_sine_sound(160.0, 0.05, 0.12)


def clamp(x, a, b):
    return max(a, min(b, x))


def blur_surface(surf, amt=6):
    if amt <= 0:
        return surf.copy()
    scale = 1.0 / max(1, amt)
    surf_small = pygame.transform.smoothscale(surf, (max(1, int(surf.get_width() * scale)),
                                                    max(1, int(surf.get_height() * scale))))
    surf_blur = pygame.transform.smoothscale(surf_small, (surf.get_width(), surf.get_height()))
    return surf_blur

class Particle:
    def __init__(self, pos: Vector2, vel: Vector2, life: float, color: tuple, size: float):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size

    def update(self, dt):
        self.pos += self.vel * dt
        self.vel *= clamp(1 - 3.0 * dt, 0.0, 1.0)
        self.life -= dt

    def draw(self, surf):
        if self.life <= 0:
            return
        frac = clamp(self.life / self.max_life, 0.0, 1.0)
        alpha = int(255 * frac)
        r, g, b = self.color
        size = max(1, int(self.size * (0.6 + 0.4 * frac)))
        s = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (r, g, b, alpha), (size, size), size)
        surf.blit(s, (int(self.pos.x - size), int(self.pos.y - size)))

class Projectile:
    def __init__(self, pos: Vector2, vel: Vector2, radius: float, damage: float, owner_tag: str):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.radius = float(radius)
        self.damage = float(damage)
        self.life = PROJECTILE_LIFETIME
        self.hit = False
        self.owner = owner_tag

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surf):
        outer = int(self.radius * 2.4)
        pygame.draw.circle(surf, PROJECTILE_GLOW, (int(self.pos.x), int(self.pos.y)), outer)
        pygame.draw.circle(surf, (255, 255, 255), (int(self.pos.x), int(self.pos.y)), int(self.radius))

    def is_dead(self):
        if self.life <= 0 or self.hit:
            return True
        if self.pos.x < -100 or self.pos.x > SCREEN_W + 100 or self.pos.y < -100 or self.pos.y > SCREEN_H + 100:
            return True
        return False

class Player:
    def __init__(self, pos: Vector2, side="bottom"):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.input_mag = 0.0
        self.charging = False
        self.charge_start_time = 0.0
        self.charge = 0.0
        self.hit_timer = 0.0
        self.health = PLAYER_STARTING_HEALTH
        self.radius = PLAYER_RADIUS
        self.side = side
        # ammo / reload
        self.max_ammo = PLAYER_MAX_AMMO
        self.ammo = self.max_ammo
        self.reloading = False
        self.reload_timer = 0.0
        # timing for auto-reload: if no shot for this many seconds, start reload
        self.last_shot_time = 0.0
        self.auto_reload_delay = AUTO_RELOAD_DELAY

    def start_charge(self, now):
        # allow charging while reloading; you may use bullets that have already reloaded
        if not self.charging and self.health > 0:
            self.charging = True
            self.charge_start_time = now

    def end_charge(self, now):
        if not self.charging:
            return 0.0
        self.charging = False
        charge = clamp((now - self.charge_start_time) / CHARGE_DURATION, 0.0, 1.0)
        self.charge = 0.0
        return charge

    def apply_hit(self, damage):
        self.health -= damage
        self.hit_timer = HIT_FLASH_TIME
        self.health = max(self.health, 0)

    def update(self, dt, raw_input_dir: Vector2):
        # reload handling (per-bullet). bullets become available immediately when loaded.
        if self.reloading:
            self.reload_timer -= dt
            while self.reloading and self.reload_timer <= 0:
                if self.ammo < self.max_ammo:
                    self.ammo += 1
                    if reload_sound:
                        reload_sound.play()
                    # schedule next bullet
                    if self.ammo < self.max_ammo:
                        self.reload_timer += PLAYER_RELOAD_PER_BULLET
                    else:
                        self.reloading = False
                else:
                    self.reloading = False

        # auto-start reload if player hasn't shot recently or if magazine is empty
        if not self.reloading and self.ammo < self.max_ammo:
            if (pygame.time.get_ticks() / 1000.0 - self.last_shot_time) >= self.auto_reload_delay or self.ammo == 0:
                self.start_reload()

        target_mag = 1.0 if raw_input_dir.length_squared() > 0.0001 else 0.0
        if INPUT_RAMP_TIME > 0:
            alpha = clamp(dt / INPUT_RAMP_TIME, 0.0, 1.0)
            self.input_mag = (1 - alpha) * self.input_mag + alpha * target_mag
        else:
            self.input_mag = target_mag

        dir_vec = raw_input_dir.normalize() if raw_input_dir.length_squared() > 0.0001 else Vector2(0, 0)
        accel = dir_vec * (ACCEL_STRENGTH * self.input_mag)
        self.vel += accel * dt
        self.vel = self.vel.lerp(Vector2(0, 0), clamp(DRAG * dt, 0, 1))

        if self.vel.length() > MAX_SPEED:
            self.vel = self.vel.normalize() * MAX_SPEED

        self.pos += self.vel * dt

        # clamp to halves (horizontal wall): bottom or top
        if self.side == "bottom":
            self.pos.y = clamp(self.pos.y, max(self.radius, CENTER_Y + 1), SCREEN_H - self.radius)
            self.pos.x = clamp(self.pos.x, self.radius, SCREEN_W - self.radius)
        else:
            self.pos.y = clamp(self.pos.y, self.radius, min(SCREEN_H - self.radius, CENTER_Y - 1))
            self.pos.x = clamp(self.pos.x, self.radius, SCREEN_W - self.radius)

        if self.hit_timer > 0:
            self.hit_timer -= dt

    def start_reload(self):
        if not self.reloading and self.ammo < self.max_ammo:
            self.reloading = True
            # start with first bullet timer
            self.reload_timer = PLAYER_RELOAD_PER_BULLET

    def record_shot(self, now):
        self.last_shot_time = now

    def draw(self, surf, aim_dir: Vector2, charge_frac: float):
        base_col = PLAYER_COLOR
        if self.hit_timer > 0:
            base_col = (255, 255, 255)
        px, py = int(self.pos.x), int(self.pos.y)

        if charge_frac > 0:
            ring_r = int(self.radius + 6 + charge_frac * 20)
            s = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (CHARGE_COLOR[0], CHARGE_COLOR[1], CHARGE_COLOR[2], 90),
                               (ring_r + 2, ring_r + 2), ring_r, width=6)
            surf.blit(s, (px - ring_r - 2, py - ring_r - 2))

        if PLAYER_SHAPE == "triangle":
            if aim_dir.length_squared() < 1e-4:
                forward = self.vel.normalize() if self.vel.length_squared() > 1e-6 else Vector2(0, -1)
            else:
                forward = aim_dir.normalize()
            size = self.radius
            perp = Vector2(-forward.y, forward.x)
            p1 = self.pos + forward * (size * 1.2)
            p2 = self.pos - forward * (size * 0.7) + perp * (size * 0.7)
            p3 = self.pos - forward * (size * 0.7) - perp * (size * 0.7)
            pygame.draw.polygon(surf, base_col, [(p1.x, p1.y), (p2.x, p2.y), (p3.x, p3.y)])
            pygame.draw.polygon(surf, (20, 20, 20), [(p1.x, p1.y), (p2.x, p2.y), (p3.x, p3.y)], width=2)
        else:
            half = self.radius
            angle = math.atan2(aim_dir.y, aim_dir.x) if aim_dir.length_squared() > 1e-4 else 0
            rect = pygame.Surface((half * 2, half * 2), pygame.SRCALPHA)
            pygame.draw.rect(rect, base_col, rect.get_rect())
            rs = pygame.transform.rotate(rect, -math.degrees(angle))
            rrect = rs.get_rect(center=(px, py))
            surf.blit(rs, rrect.topleft)
            pygame.draw.rect(surf, (20, 20, 20), rrect, width=2)

class Boss:
    def __init__(self, pos: Vector2, difficulty="Normal"):
        self.pos = Vector2(pos)
        self.last_player_pos = None
        self.player_velocity = Vector2(0, 0)
        self.vel = Vector2(0, 0)
        self.target_vel = Vector2(0, 0)
        self.fake_charge_chance = 0.25
        self.is_fake_charging = False
        self.panic_mode = False
        self.visual_charge = 0.0
        self.radius = BOSS_RADIUS
        self.preferred_dist = 260




        # ---------------- Difficulty ----------------
        if difficulty == "Easy":
            self.max_health = int(BOSS_MAX_HEALTH_BASE * 0.8)
            self.move_speed = BOSS_MOVE_SPEED_BASE * 0.9
            self.aggression = 0.85
        elif difficulty == "Hard":
            self.max_health = int(BOSS_MAX_HEALTH_BASE * 1.4)
            self.move_speed = BOSS_MOVE_SPEED_BASE * 1.2
            self.aggression = 1.2
        else:
            self.max_health = BOSS_MAX_HEALTH_BASE
            self.move_speed = BOSS_MOVE_SPEED_BASE
            self.aggression = 1.0

        self.health = self.max_health

        # ---------------- Personality ----------------
        self.personality = random.choice(["Sniper", "Brawler", "Trickster", "Adaptive"])

        if self.personality == "Sniper":
            self.preferred_dist = 340
            self.retreat_bias = 0.55
        elif self.personality == "Brawler":
            self.preferred_dist = 220
            self.retreat_bias = 0.25
        elif self.personality == "Trickster":
            self.preferred_dist = 280
            self.retreat_bias = 0.45
        else:
            self.preferred_dist = 260
            self.retreat_bias = 0.4

        # Distance comfort band (CRITICAL FIX)
        self.comfort_min = self.preferred_dist - 45
        self.comfort_max = self.preferred_dist + 45

        # -------- Firing personality --------
        if self.personality == "Sniper":
            self.fire_bias = 0.45
        elif self.personality == "Brawler":
            self.fire_bias = 0.85
        elif self.personality == "Trickster":
            self.fire_bias = 0.65
        else:  # Adaptive
            self.fire_bias = 0.7


        # ---------------- Movement commitment ----------------
        self.move_commit_timer = random.uniform(0.4, 0.9)
        self.committed_dir = Vector2(0, 0)

        # ---------------- Proactive disengage ----------------
        self.reset_timer = random.uniform(2.5, 4.5)
        self.reset_duration = 0.0

        # ---------------- Combat ----------------
        self.state = BOSS_STATE_STRAFE
        self.state_timer = random.uniform(0.8, 1.6)

        self.max_ammo = BOSS_MAX_AMMO
        self.ammo = self.max_ammo
        self.reloading = False
        self.reload_timer = 0.0
        self.last_shot_time = 0.0
        self.auto_reload_delay = AUTO_RELOAD_DELAY

        self.charging = False
        self.charge_start = None
        self.time_since_last_shot = 0.0

        # ---------------- Learning ----------------
        self.player_shot_count = 0
        self.player_hit_count = 0
        self.player_positions = collections.deque(maxlen=BOSS_LEARN_WINDOW)

        # ---------------- FX ----------------
        self.hit_timer = 0.0
        self.vibrate_timer = 0.0
        self.vibrate_offset = Vector2(0, 0)

    # ======================================================
    # ---------------- UPDATE -------------------------------
    # ======================================================

    def update(self, dt, player, projectiles_out, now):
        if self.health <= 0:
            return
        
        self._track_player_velocity(player, dt)
        self._update_reload(dt, now)
        self._update_learning()
        self._update_proactive_retreat(dt)
        self._update_state(dt, player)
        self._update_movement(dt, player)
        self._update_velocity(dt)
        self._update_position(dt)
        self._update_shooting(dt, player, projectiles_out, now)
        self._update_fx(dt)


    def _track_player_velocity(self, player, dt):
        if self.last_player_pos is not None:
            self.player_velocity = (player.pos - self.last_player_pos) / max(dt, 1e-5)
        self.last_player_pos = Vector2(player.pos)

    def _get_predicted_aim(self, player, projectile_speed):
        lead_time = clamp((player.pos - self.pos).length() / projectile_speed, 0.05, 0.6)
        predicted_pos = player.pos + self.player_velocity * lead_time
        aim = predicted_pos - self.pos
        return aim.normalize() if aim.length_squared() > 1e-6 else Vector2(0, 1)



    # ======================================================
    # ---------------- MOVEMENT -----------------------------
    # ======================================================

    def _update_movement(self, dt, player):
        to_player = player.pos - self.pos
        dist = to_player.length()
        dir_to_player = to_player.normalize() if dist > 1e-4 else Vector2(0, 1)
        perp = Vector2(-dir_to_player.y, dir_to_player.x)

        self.move_commit_timer -= dt

        if self.move_commit_timer <= 0:
            self.move_commit_timer = random.uniform(0.45, 0.95)

            move = Vector2(0, 0)

            # ---- Distance band logic (MAIN FIX) ----
            if dist < self.comfort_min:
                move = -dir_to_player
            elif dist > self.comfort_max:
                move = dir_to_player
            else:
                # Inside comfort → lateral drift or idle
                if random.random() < 0.7:
                    move = perp * random.choice([-1, 1])
                else:
                    move = Vector2(0, 0)

            # ---- Proactive retreat (human hesitation) ----
            if self.reset_duration > 0:
                move = -dir_to_player

            self.committed_dir = move.normalize() if move.length() > 0 else Vector2(0, 0)

        # Desired velocity (NOT raw acceleration)
        self.target_vel = self.committed_dir * self.move_speed * clamp(self.aggression, 0.7, 1.4)

    def _update_velocity(self, dt):
        # Smooth velocity (kills jitter)
        self.vel = self.vel.lerp(self.target_vel, 0.12)

        # Soft wall avoidance (no bouncing)
        wall_dist = abs(self.pos.y - CENTER_Y)
        if wall_dist < 60:
            push = 220 * (1 - wall_dist / 60)
            self.vel.y += push * dt * (1 if self.pos.y < CENTER_Y else -1)

    def _update_position(self, dt):
        self.pos += self.vel * dt
        self.pos.x = clamp(self.pos.x, self.radius, SCREEN_W - self.radius)
        self.pos.y = clamp(self.pos.y, self.radius, CENTER_Y - 1)

    # ======================================================
    # ---------------- STATE & AI ---------------------------
    # ======================================================

    def _update_state(self, dt, player):
        self.state_timer -= dt
        if self.state_timer <= 0:
            self.state = random.choice([BOSS_STATE_STRAFE, BOSS_STATE_POKE])
            self.state_timer = random.uniform(0.8, 1.6)

    def _update_proactive_retreat(self, dt):
        self.reset_timer -= dt
        if self.reset_timer <= 0:
            if random.random() < self.retreat_bias:
                self.reset_duration = random.uniform(0.6, 1.2)
            self.reset_timer = random.uniform(2.5, 4.5)

        if self.reset_duration > 0:
            self.reset_duration -= dt

    # ======================================================
    # ---------------- LEARNING -----------------------------
    # ======================================================
    def record_player(self, player_pos: Vector2, now: float, player_fired=False):
        """
        Records player position and firing events for boss learning.
        Called from run_game() when the player shoots.
        """
        self.player_positions.append((now, Vector2(player_pos)))

        if player_fired:
            self.player_shot_count += 1

    def _update_learning(self):
        if self.player_shot_count >= 10:
            acc = self.player_hit_count / max(1, self.player_shot_count)
            self.aggression *= 0.97 if acc > 0.5 else 1.03
            self.aggression = clamp(self.aggression, 0.6, 1.6)

    # ======================================================
    # ---------------- RELOAD -------------------------------
    # ======================================================

    def _update_reload(self, dt, now):
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0 and self.ammo < self.max_ammo:
                self.ammo += 1
                self.reload_timer = BOSS_RELOAD_PER_BULLET
                if self.ammo >= self.max_ammo:
                    self.reloading = False

        if not self.reloading and self.ammo < self.max_ammo:
            if now - self.last_shot_time >= self.auto_reload_delay:
                self.reloading = True
                self.reload_timer = BOSS_RELOAD_PER_BULLET

    # ======================================================
    # ---------------- DAMAGE & FX --------------------------
    # ======================================================

    def apply_hit(self, damage):
        self.health = max(0, self.health - damage)
        self.hit_timer = 0.06
        self.vibrate_timer = BOSS_VIBRATE_TIME
        self.player_hit_count += 1

    def _update_fx(self, dt):
        if self.hit_timer > 0:
            self.hit_timer -= dt

        if self.vibrate_timer > 0:
            self.vibrate_timer -= dt
            mag = BOSS_VIBRATE_MAG * (self.vibrate_timer / BOSS_VIBRATE_TIME)
            self.vibrate_offset = Vector2(random.uniform(-mag, mag), random.uniform(-mag, mag))
        else:
            self.vibrate_offset = Vector2(0, 0)

    # ======================================================
    # ---------------- DRAW --------------------------------
    # ======================================================

    def draw(self, surf):
        pos = self.pos + self.vibrate_offset
        pygame.draw.circle(surf, BOSS_COLOR, pos, self.radius)
        pygame.draw.circle(surf, (20, 20, 20), pos, self.radius, 3)
        if self.visual_charge > 0:
            ring_r = int(self.radius + 12 + self.visual_charge * 28)
            ring_alpha = int(120 + 100 * self.visual_charge)
            ring = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                ring,
                (255, 80, 80, ring_alpha),
                (ring_r, ring_r),
                ring_r,
                width=6
            )
            surf.blit(ring, (pos.x - ring_r, pos.y - ring_r))

    def draw_health_bar(self, surf):
        w = 420
        h = 18
        x = (SCREEN_W - w) // 2
        y = 14

        pygame.draw.rect(surf, (40, 40, 40), (x, y, w, h), border_radius=6)

        frac = clamp(self.health / self.max_health, 0.0, 1.0)
        fill_w = int(frac * (w - 6))

        if frac > 0.6:
            color = (80, 220, 120)
        elif frac > 0.3:
            color = (240, 200, 60)
        else:
            color = (240, 80, 80)

        pygame.draw.rect(
            surf,
            color,
            (x + 3, y + 3, fill_w, h - 6),
            border_radius=5
        )

        pygame.draw.rect(
            surf,
            (10, 10, 10),
            (x, y, w, h),
            width=2,
            border_radius=6
        )
        
    def _update_shooting(self, dt, player, projectiles_out, now):
        self.time_since_last_shot += dt

        cooldown = BOSS_FIRE_COOLDOWN_BASE / clamp(self.aggression, 0.7, 1.4)

        self.panic_mode = self.ammo <= max(1, self.max_ammo // 3)
        if self.panic_mode:
            cooldown *= 0.45

        # No shooting while reloading or retreating
        if self.reloading or self.ammo <= 0 or self.reset_duration > 0:
            return

        # Fake charge
        if (
            not self.is_fake_charging
            and self.time_since_last_shot >= cooldown
            and random.random() < self.fake_charge_chance
        ):
            self.is_fake_charging = True
            self.charge_start = now
            return

        if self.is_fake_charging:
            if now - self.charge_start > random.uniform(0.25, 0.5):
                self.is_fake_charging = False
                self.time_since_last_shot = 0.0
            return

        if self.time_since_last_shot < cooldown:
            return

        if random.random() > self.fire_bias:
            return

        # ---- REAL SHOT ----
        charge = 0.25 if self.panic_mode else random.uniform(0.25, 0.85)
        bullets_used = max(1, int(math.ceil(charge * self.max_ammo)))
        bullets_used = min(bullets_used, self.ammo)

        effective_charge = bullets_used / self.max_ammo
        speed = BOSS_MIN_PROJ_SPEED + (BOSS_MAX_PROJ_SPEED - BOSS_MIN_PROJ_SPEED) * effective_charge

        aim_dir = self._get_predicted_aim(player, speed)

        radius = BOSS_MIN_PROJECTILE_RADIUS + (BOSS_MAX_PROJECTILE_RADIUS - BOSS_MIN_PROJECTILE_RADIUS) * effective_charge
        damage = MIN_DAMAGE + (MAX_DAMAGE - MIN_DAMAGE) * effective_charge

        spawn_pos = self.pos + aim_dir * (self.radius + radius + 4)
        proj = Projectile(spawn_pos, aim_dir * speed, radius, damage, owner_tag="boss")
        projectiles_out.append(proj)

        if boss_shot_sound:
            boss_shot_sound.play()

        self.ammo -= bullets_used
        self.last_shot_time = now
        self.time_since_last_shot = 0.0
        self.visual_charge = 0.0


def circle_collide(a_pos, a_rad, b_pos, b_rad):
    return (a_pos - b_pos).length_squared() <= (a_rad + b_rad) ** 2


def draw_button(surf, rect, text, highlight=False):
    color = (70, 70, 70) if not highlight else (120, 120, 120)
    pygame.draw.rect(surf, color, rect, border_radius=8)
    pygame.draw.rect(surf, (20, 20, 20), rect, width=2, border_radius=8)
    txt = font.render(text, True, (230, 230, 230))
    tw, th = txt.get_size()
    surf.blit(txt, (rect.x + (rect.w - tw) // 2, rect.y + (rect.h - th) // 2))


def start_screen_loop():
    difficulties = ["Easy", "Normal", "Hard"]
    selected_idx = 1
    running = True
    rules_x = 80
    rules_y = 140
    rules_spacing = 30
    diff_panel_x = SCREEN_W - 440
    diff_panel_y = 220
    diff_rects = [pygame.Rect(diff_panel_x, diff_panel_y + i * 64, 360, 52) for i in range(len(difficulties))]
    start_btn = pygame.Rect(SCREEN_W // 2 - 96, SCREEN_H - 120, 192, 58)

    while running:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(diff_rects):
                    if r.collidepoint(mouse):
                        selected_idx = i
                if start_btn.collidepoint(mouse):
                    return difficulties[selected_idx]

        screen.fill(BACKGROUND_COLOR)
        title = title_font.render("TILTFIRE — BOSS TRAINING", True, (230, 230, 230))
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 40))

        rules = [
            "Rules:",
            "You (bottom half) and Boss (top half) are separated "
            "by an invisible horizontal wall.",
            "Neither you nor the Boss can cross the middle — movement and aim matter.",
            "Move with WASD (tilt-like momentum). Aim with mouse.",
            "Hold Space or Left Mouse to charge; release to fire.",
            "Charge affects projectile size / speed / damage and eats more ammo.",
            "Defeat the Boss by reducing its HP to 0. If your HP reaches 0, you lose.",
        ]
        for i, line in enumerate(rules):
            color = (220, 220, 220) if i == 0 else (180, 180, 180)
            txt = font.render(line, True, color)
            screen.blit(txt, (rules_x, rules_y + i * rules_spacing))

        health_txt = font.render(f"Player starting health: {PLAYER_STARTING_HEALTH}", True, (200,200,200))
        screen.blit(health_txt, (rules_x, rules_y + len(rules) * rules_spacing + 8))

        diff_title = big_font.render("Select Difficulty", True, (200, 200, 200))
        screen.blit(diff_title, (diff_panel_x, diff_panel_y - 54))
        for i, diff in enumerate(difficulties):
            draw_button(screen, diff_rects[i], diff, highlight=(i == selected_idx))

        draw_button(screen, start_btn, "Start Game", highlight=False)

        footer = font.render("Press Esc to quit at any time", True, (120, 120, 120))
        screen.blit(footer, (SCREEN_W // 2 - footer.get_width() // 2, SCREEN_H - 40))

        pygame.display.flip()
        clock.tick(FPS)
    return None


def end_screen_return(result_text, frame_surface):
    global last_frame_surface, restart_btn, quit_btn
    last_frame_surface = frame_surface.copy()
    box_w, box_h = 640, 240
    bx = SCREEN_W // 2 - box_w // 2
    by = SCREEN_H // 2 - box_h // 2
    restart_btn = pygame.Rect(bx + 78, by + box_h - 86, 200, 56)
    quit_btn = pygame.Rect(bx + box_w - 78 - 200, by + box_h - 86, 200, 56)

    while True:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if restart_btn.collidepoint(mouse):
                    return "restart"
                if quit_btn.collidepoint(mouse):
                    return "quit"

        blurred = blur_surface(last_frame_surface, amt=8)
        screen.blit(blurred, (0, 0))
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 8, 8, 160))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, (28, 28, 28), (bx, by, box_w, box_h), border_radius=12)
        pygame.draw.rect(screen, (20, 20, 20), (bx, by, box_w, box_h), width=2, border_radius=12)

        rt = title_font.render(result_text, True, (220, 220, 220))
        screen.blit(rt, (SCREEN_W // 2 - rt.get_width() // 2, by + 28))

        draw_button(screen, restart_btn, "Restart", highlight=False)
        draw_button(screen, quit_btn, "Quit", highlight=False)

        pygame.display.flip()
        clock.tick(FPS)


def run_game():
    global last_frame_surface
    STATE_START = "START"
    STATE_PLAYING = "PLAYING"
    state = STATE_START
    chosen_difficulty = "Normal"

    particles = []

    def spawn_particles(pos, base_color, count=PARTICLE_COUNT_HIT):
        for i in range(count):
            dirv = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
            if dirv.length_squared() < 1e-6:
                dirv = Vector2(0, -1)
            else:
                dirv = dirv.normalize()
            speed = random.uniform(80, 280)
            vel = dirv * speed
            life = random.uniform(PARTICLE_LIFE_MIN, PARTICLE_LIFE_MAX)
            size = random.uniform(2, 6)
            color = (
                clamp(base_color[0] + random.randint(-30, 30), 80, 255),
                clamp(base_color[1] + random.randint(-30, 30), 80, 255),
                clamp(base_color[2] + random.randint(-30, 30), 80, 255),
            )
            particles.append(Particle(Vector2(pos), vel, life, color, size))

    while True:
        if state == STATE_START:
            diff = start_screen_loop()
            if diff is None:
                pygame.quit()
                sys.exit()
            chosen_difficulty = diff
            player = Player(Vector2(SCREEN_W // 2, CENTER_Y + (SCREEN_H - CENTER_Y) * 0.5), side="bottom")
            boss = Boss(Vector2(SCREEN_W // 2, CENTER_Y * 0.5), difficulty=chosen_difficulty)
            projectiles = []
            divider_flash_timer = DIVIDER_FLASH_DURATION
            state = STATE_PLAYING

        elif state == STATE_PLAYING:
            playing = True
            while playing:
                dt = clock.tick(FPS) / 1000.0
                now = pygame.time.get_ticks() / 1000.0
                if divider_flash_timer > 0:
                    divider_flash_timer -= dt


                raw_dir = Vector2(0, 0)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            player.start_charge(now)
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            charge_val = player.end_charge(now)
                            if charge_val > 0.001 and player.health > 0:
                                # determine how many bullets this charge wants to consume
                                desired_slots = max(1, int(math.ceil(charge_val * player.max_ammo)))
                                if desired_slots >= player.max_ammo:
                                    desired_slots = player.max_ammo
                                if player.ammo <= 0:
                                    if empty_click_sound:
                                        empty_click_sound.play()
                                else:
                                    # if not enough ammo, scale down the effective charge
                                    bullets_used = min(desired_slots, player.ammo)
                                    effective_charge = bullets_used / float(player.max_ammo)
                                    mpos = Vector2(pygame.mouse.get_pos())
                                    aim = (mpos - player.pos)
                                    # spawn projectile and record shot immediately
                                    proj = None
                                    if effective_charge > 0:
                                        proj = Projectile(player.pos + aim.normalize() * (player.radius + (MIN_PROJ_RADIUS + (MAX_PROJ_RADIUS - MIN_PROJ_RADIUS) * effective_charge) + 4),
                                                          aim.normalize() * (MIN_PROJ_SPEED + (MAX_PROJ_SPEED - MIN_PROJ_SPEED) * effective_charge),
                                                          MIN_PROJ_RADIUS + (MAX_PROJ_RADIUS - MIN_PROJ_RADIUS) * effective_charge,
                                                          MIN_DAMAGE + (MAX_DAMAGE - MIN_DAMAGE) * effective_charge,
                                                          owner_tag="player")
                                    if proj:
                                        projectiles.append(proj)
                                        boss.record_player(player.pos, now, player_fired=True)
                                        player.ammo -= bullets_used
                                        player.record_shot(now)
                                        if player_shot_sound:
                                            player_shot_sound.play()
                                        # start per-bullet reload if magazine empty
                                        if player.ammo <= 0 and not player.reloading:
                                            player.reloading = True
                                            player.reload_timer = PLAYER_RELOAD_PER_BULLET
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            player.start_charge(now)
                        if event.key == pygame.K_r:
                            if player.ammo < player.max_ammo and not player.reloading:
                                player.start_reload()
                    elif event.type == pygame.KEYUP:
                        if event.key == pygame.K_SPACE:
                            charge_val = player.end_charge(now)
                            if charge_val > 0.001 and player.health > 0:
                                desired_slots = max(1, int(math.ceil(charge_val * player.max_ammo)))
                                if desired_slots >= player.max_ammo:
                                    desired_slots = player.max_ammo
                                if player.ammo <= 0:
                                    if empty_click_sound:
                                        empty_click_sound.play()
                                else:
                                    bullets_used = min(desired_slots, player.ammo)
                                    effective_charge = bullets_used / float(player.max_ammo)
                                    mpos = Vector2(pygame.mouse.get_pos())
                                    aim = (mpos - player.pos)
                                    proj = None
                                    if effective_charge > 0:
                                        proj = Projectile(player.pos + aim.normalize() * (player.radius + (MIN_PROJ_RADIUS + (MAX_PROJ_RADIUS - MIN_PROJ_RADIUS) * effective_charge) + 4),
                                                          aim.normalize() * (MIN_PROJ_SPEED + (MAX_PROJ_SPEED - MIN_PROJ_SPEED) * effective_charge),
                                                          MIN_PROJ_RADIUS + (MAX_PROJ_RADIUS - MIN_PROJ_RADIUS) * effective_charge,
                                                          MIN_DAMAGE + (MAX_DAMAGE - MIN_DAMAGE) * effective_charge,
                                                          owner_tag="player")
                                    if proj:
                                        projectiles.append(proj)
                                        boss.record_player(player.pos, now, player_fired=True)
                                        player.ammo -= bullets_used
                                        player.record_shot(now)
                                        if player_shot_sound:
                                            player_shot_sound.play()
                                        if player.ammo <= 0 and not player.reloading:
                                            player.reloading = True
                                            player.reload_timer = PLAYER_RELOAD_PER_BULLET

                keys = pygame.key.get_pressed()
                if keys[pygame.K_w]:
                    raw_dir.y -= 1
                if keys[pygame.K_s]:
                    raw_dir.y += 1
                if keys[pygame.K_a]:
                    raw_dir.x -= 1
                if keys[pygame.K_d]:
                    raw_dir.x += 1

                if player.charging:
                    player.charge = clamp((now - player.charge_start_time) / CHARGE_DURATION, 0.0, 1.0)
                else:
                    player.charge = 0.0

                player.update(dt, raw_dir)
                boss.update(dt, player, projectiles, now)

                for p in projectiles:
                    p.update(dt)

                # update particles
                for part in particles:
                    part.update(dt)
                particles = [pt for pt in particles if pt.life > 0]

                # collisions
                for p in projectiles:
                    if p.is_dead():
                        continue
                    if p.owner == "player":
                        if circle_collide(p.pos, p.radius, boss.pos, boss.radius):
                            p.hit = True
                            boss.apply_hit(p.damage)
                            spawn_particles(p.pos, (200, 120, 255), count=PARTICLE_COUNT_HIT)
                            if hit_sound:
                                hit_sound.play()
                    elif p.owner == "boss":
                        if circle_collide(p.pos, p.radius, player.pos, player.radius):
                            p.hit = True
                            player.apply_hit(p.damage)
                            spawn_particles(p.pos, (255, 120, 80), count=PARTICLE_COUNT_HIT)
                            if hit_sound:
                                hit_sound.play()

                projectiles = [p for p in projectiles if not p.is_dead()]

                screen.fill(BACKGROUND_COLOR)
                if divider_flash_timer > 0:
                    phase = int(divider_flash_timer * DIVIDER_FLASH_FREQ) % 2
                    if phase == 0:
                        pygame.draw.line(
                            screen,
                            DIVIDER_COLOR,
                            (0, CENTER_Y),
                            (SCREEN_W, CENTER_Y),
                            DIVIDER_THICKNESS
                        )

                for p in projectiles:
                    p.draw(screen)

                boss.draw(screen)
                boss.draw_health_bar(screen)

                mpos = Vector2(pygame.mouse.get_pos())
                aim_dir = mpos - player.pos
                player.draw(screen, aim_dir, player.charge)

                # draw particles (above player/boss for nice effect)
                for part in particles:
                    part.draw(screen)

                if player.hit_timer > 0:
                    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    alpha = int(180 * (player.hit_timer / HIT_FLASH_TIME))
                    s.fill((PLAYER_HIT_TINT[0], PLAYER_HIT_TINT[1], PLAYER_HIT_TINT[2], alpha))
                    screen.blit(s, (0, 0))

                # HUD: show player health clearly
                text = font.render(f"Player HP: {int(player.health)}", True, HUD_COLOR)
                screen.blit(text, (12, 12))
                boss_text = font.render(f"Boss HP: {int(boss.health)} / {boss.max_health}", True, HUD_COLOR)
                screen.blit(boss_text, (SCREEN_W - 320, 12))

                # Ammo / reload HUD - show per-bullet reload progress for player and boss
                if player.reloading:
                    frac = clamp(1.0 - (player.reload_timer / PLAYER_RELOAD_PER_BULLET), 0.0, 1.0)
                    ammo_txt = f"Player reload: {player.ammo} / {player.max_ammo} ({frac*100:.0f}%)"
                else:
                    ammo_txt = f"Ammo: {player.ammo} / {player.max_ammo}"
                ammo_surface = font.render(ammo_txt, True, HUD_COLOR)
                screen.blit(ammo_surface, (12, 36))

                # show boss ammo as well
                if boss.reloading:
                    bfrac = clamp(1.0 - (boss.reload_timer / BOSS_RELOAD_PER_BULLET), 0.0, 1.0)
                    boss_ammo_txt = f"Boss reload: {boss.ammo} / {boss.max_ammo} ({bfrac*100:.0f}%)"
                else:
                    boss_ammo_txt = f"Boss Ammo: {boss.ammo} / {boss.max_ammo}"
                boss_ammo_surface = font.render(boss_ammo_txt, True, HUD_COLOR)
                screen.blit(boss_ammo_surface, (12, 58))

                if player.charging:
                    cp = int(player.charge * 100)
                    t = font.render(f"Charge: {cp}%", True, (210, 210, 210))
                    screen.blit(t, (SCREEN_W - 120, 36))

                hint = font.render("Press R to reload (manual). Shots consume more ammo when charged.", True, (120, 120, 120))
                screen.blit(hint, (12, SCREEN_H - 28))

                pygame.display.flip()

                if boss.health <= 0:
                    result = "Victory! You defeated the Boss."
                    last_frame_surface = screen.copy()
                    res = end_screen_return(result, last_frame_surface)
                    if res == "restart":
                        state = "START"
                    else:
                        pygame.quit()
                        sys.exit()
                    playing = False
                elif player.health <= 0:
                    result = "Defeat — You were defeated by the Boss."
                    last_frame_surface = screen.copy()
                    res = end_screen_return(result, last_frame_surface)
                    if res == "restart":
                        state = "START"
                    else:
                        pygame.quit()
                        sys.exit()
                    playing = False

if __name__ == "__main__":
    run_game()
