# -*- coding: utf-8 -*-
import pygame
import math # for mathematical calculations (circles, angles)
import random
import asyncio


width=1200  
height=600

ground=540

# pygame.init() and screen setup moved inside main() for better stability in web environment
screen = None


# --- Game State Definitions ---
STATE_TITLE = "title"         # Title screen (defined but not implemented)
STATE_LOBBY = "lobby"         # Lobby state before character selection
STATE_PLAYING = "playing"     # Main combat/exploration state
STATE_PAUSED = "paused"       # Pause menu active
STATE_GAMEOVER = "gameover"   # Game over screen
STATE_SELECT_CHAR = "select_char" # Character selection active (including Reincarnator mode toggle)
STATE_CHOOSE_WEAPON = "choose_weapon" # Weapon selection
STATE_UPGRADE = "upgrade"     # Skill/Status upgrade after wave clear
STATE_SETTINGS = "settings"   # Key configuration settings
STATE_REPLACE_SKILL = "replace_skill" # Skill replacement screen when limit reached
STATE_BOSS_REWARD = "boss_reward"    # Special reward selection after boss defeat


# --- Key Configuration ---

key_config = {
    'move_left': pygame.K_LEFT,
    'move_right': pygame.K_RIGHT,
    'jump': pygame.K_UP,
    'attack': pygame.K_SPACE,
    'skill_1': pygame.K_j,
    'skill_2': pygame.K_k,
    'skill_3': pygame.K_l,
    'skill_4': pygame.K_n,
    'skill_5': pygame.K_m,
    'pause': pygame.K_q,
}
settings_selecting = None

KEY_ACTION_NAMES = {
    'move_left': 'Move Left', 'move_right': 'Move Right',
    'jump': 'Jump', 'attack': 'Attack',
    'skill_1': 'Skill 1 (J)', 'skill_2': 'Skill 2 (K)',
    'skill_3': 'Skill 3 (L)', 'skill_4': 'Skill 4 (N)',
    'skill_5': 'Skill 5 (M)', 'pause': 'Pause',
}

game_state = STATE_LOBBY

# --- Smartphone / Touch Control Settings ---
smartphone_mode = 0 # 0: OFF, 1: Mode 1, 2: Mode 2
active_fingers = {} # finger_id -> (last_x, last_y)
touch_keys = {
    'left': False, 'right': False, 'up': False, 'attack': False, 'pause': False
}
# Virtual Pad Layouts (1200x600 resolution)
V_PAD_1 = {
    'left': pygame.Rect(30, 450, 120, 120),
    'right': pygame.Rect(170, 450, 120, 120),
    'up': pygame.Rect(100, 330, 120, 120),
    'attack': pygame.Rect(950, 400, 200, 160),
    'pause': pygame.Rect(1100, 20, 80, 80)
}
V_PAD_2 = {
    'left': pygame.Rect(30, 390, 150, 150),
    'right': pygame.Rect(210, 390, 150, 150),
    'up': pygame.Rect(760, 340, 140, 140),
    'attack': pygame.Rect(950, 400, 200, 160),
    'pause': pygame.Rect(1100, 20, 80, 80)
}
V_PAD = V_PAD_1


# Push factor (for collision separation)
PUSH_FORCE = 0.5 

def separate_actors(actors):
    """Resolve overlap between actors"""
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            a, b = actors[i], actors[j]
            if not a or not b or a == b: continue
            # Enemies allow overlap, so exclude them from separation
            if isinstance(a, Enemy) or isinstance(b, Enemy): continue

            
            w_a = getattr(a, 'width', 40)
            h_a = getattr(a, 'height', 40)
            w_b = getattr(b, 'width', 40)
            h_b = getattr(b, 'height', 40)
            
            rect_a = pygame.Rect(a.x, a.y, w_a, h_a)
            rect_b = pygame.Rect(b.x, b.y, w_b, h_b)
            
            if rect_a.colliderect(rect_b):
                overlap_x = min(rect_a.right, rect_b.right) - max(rect_a.left, rect_b.left)
                direction = 1 if a.x < b.x else -1
                a.x -= overlap_x * PUSH_FORCE * direction
                b.x += overlap_x * PUSH_FORCE * direction
wave_number = 0
is_combat_mode = False
wave_clear_timer = 0 # Wait timer between waves
wave_start_wait_timer = 0 # Wait timer at wave start


# --- Platforms ---

PLATFORM_X = 450
PLATFORM_Y = 380
PLATFORM_W = 300
PLATFORM_H = 12

# --- Skill Class Definitions ---

class Skill:
    """
    Base class for skills.
    Handles cooldown management, activation, and basic drawing logic.
    """

    def __init__(self, x, y, max_cool, color_ready, color_charge):
        self.x = x                          # X coordinate for UI
        self.y = y                          # Y coordinate for UI
        self.cool = 0                       # Current cooldown remaining (0 for ready)
        self.max_cool = max_cool            # Max cooldown for the skill
        self.color_ready = color_ready      # Icon color when ready
        self.color_charge = color_charge    # Icon color when charging
        self.damage_bonus = 0               # Additional damage from evolution, etc.


    def update(self, enemies=None, cooldown_speed=1, player=None):
        """Decrease cooldown per frame"""
        if self.cool > 0:
            cs = cooldown_speed
            # Apply limit to cooldown reduction for buff skills (1.3x rule)

            if hasattr(self, 'active_timer') and hasattr(self, 'max_cool'):
                duration = getattr(self, 'initial_duration', 0)
                if duration > 0:
                    min_cool_time = duration * 1.3
                    # Limit actual cooling speed (current / target time)
                    cs = min(cs, self.max_cool / min_cool_time)

            
            self.cool -= cs
            if self.cool < 0: self.cool = 0

    def activate(self, player, enemies=None):
        """Attempt to activate skill. Returns False if on cooldown."""

        if self.cool == 0:
            self.cool = self.max_cool
            return True
        return False

    def draw_effect(self, screen):
        pass

    def draw(self, screen):
        icon_rect = pygame.Rect(self.x, self.y, 50, 50)
        icon_center = icon_rect.center
        
        if self.cool > 0:
            pygame.draw.rect(screen, (80, 80, 80), icon_rect)
            screen.set_clip(icon_rect)
            draw_radius = 40
            angle_limit = (self.cool / self.max_cool) * 360
            points = [icon_center]
            for deg in range(0, int(angle_limit) + 1, 5):
                rad = math.radians(-deg)
                px = icon_center[0] + draw_radius * math.sin(rad)
                py = icon_center[1] - draw_radius * math.cos(rad)
                points.append((px, py))
            rad_end = math.radians(-angle_limit)
            points.append((icon_center[0] + draw_radius * math.sin(rad_end),
                           icon_center[1] - draw_radius * math.cos(rad_end)))
            if len(points) >= 3:
                pygame.draw.polygon(screen, self.color_charge, points)
            screen.set_clip(None)
            pygame.draw.rect(screen, (200, 200, 200), icon_rect, 2)
        else:
            pygame.draw.rect(screen, self.color_ready, icon_rect)
            pygame.draw.rect(screen, (255, 255, 255), icon_rect, 2)

class MirrorSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 180, (0, 255, 0), (255, 200, 0))
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.x = width - player.x
            player.vx = -player.vx
            player.ax = -player.ax

class GravitySkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 300, (0, 255, 0), (100, 100, 255))
        self.range = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 300
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0: self.range -= 1

class IceSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (0, 255, 0), (100, 200, 255))
        self.range = 0
        self.place = 0
        self.width = 400
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 400
            self.place = player.x - self.width / 2
            # Freeze grounded enemies within range
            if enemies:

                for e in enemies:
                    if e.hp > 0 and self.place < e.x + e.width and e.x < self.place + self.width and e.y + e.height >= ground - 5:
                        if hasattr(e, 'frozen_timer'):
                            e.frozen_timer = 120 # 2 seconds

            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0: self.range -= 1
    def draw_effect(self, screen):
        if self.range > 0:
            pygame.draw.rect(screen, (10, 10, 250), (self.place, ground, self.width, 100))

class DashSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 180, (0, 255, 0), (255, 255, 0))
        self.range = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 10
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0: self.range -= 1

class LavaSkill(Skill):
    def __init__(self, x, y):
        # Red/Orange theme for lava (color_charge: bright red, color_ready: fiery orange)
        super().__init__(x, y, 300, (255, 69, 0), (255, 0, 0))

        self.range = 0
        self.place = 0
        self.width = 400
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 400
            self.place = player.x - self.width / 2
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0:
            self.range -= 1
            if self.range % 30 == 0 and enemies is not None:
                for e in enemies:
                    if e.hp > 0 and self.place < e.x + e.width and e.x < self.place + self.width and e.y + e.height >= ground - 5:
                        e.burn_timer = 180
                        e.take_damage(1 + self.damage_bonus, status_effect=True, element='fire')

    def draw_effect(self, screen):
        if self.range > 0:
            # Draw ground in slightly dark red for fake transparency
            pygame.draw.rect(screen, (200, 0, 0), (self.place, ground, self.width, 100))


class FireSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 40, (255, 100, 100), (255, 0, 0))
        self.bullets = [] # list of [x, y, vx, timer]
        self.width = 40
        self.height = 20
        self.speed = 18
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            # Factor in player's speed when launched
            vx = (self.speed + abs(player.vx)) * player.facing
            # Launch from near player center [x, y, vx, timer, hit_enemies]
            self.bullets.append([player.x + 20, player.y + 10, vx, 80, []])
            return True

        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        new_bullets = []
        for b in self.bullets:
            b[0] += b[2] # x movement
            b[3] -= 1 # lifetime
            # Collision detection
            bx, by = b[0], b[1]

            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x <= bx <= e.x + e.width and e.y <= by <= e.y + e.height:
                        # Pierce: Deal damage if enemy hasn't been hit by this bullet yet
                        if e not in b[4]:
                            if e.take_damage(1 + self.damage_bonus, 1 if b[2] > 0 else -1, element='fire', ignore_iframes=True):
                                b[4].append(e)

            
            # Expiration check: lifetime expired or out of bounds
            if b[3] > 0 and -100 < b[0] < width + 100:
                new_bullets.append(b)

        self.bullets = new_bullets
    def draw_effect(self, screen):
        for b in self.bullets:
            pygame.draw.rect(screen, (255, 0, 0), (int(b[0]), int(b[1]), self.width, self.height))

class ThunderSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 200, (255, 255, 0), (200, 200, 0)) # Increased cooldown by 5x (40->200)

        self.range = 0
        self.points = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 30 # Display duration
            # List living enemies

            alive_enemies = []
            if enemies:
                alive_enemies = [e for e in enemies if e.hp > 0]
            
            if alive_enemies:
                # Select a random enemy
                target_enemy = random.choice(alive_enemies)
                tx = target_enemy.x + target_enemy.width / 2
                target_enemy.take_damage(2 + self.damage_bonus)
            else:
                # If no enemies, pick a random position
                tx = random.randint(50, width - 50)

                
            self.points = [(tx, 0)]
            curr_y = 0
            while curr_y < ground + 100:
                curr_y += random.randint(30, 60)
                next_x = tx + random.randint(-40, 40)
                self.points.append((next_x, curr_y))
            
            # Collision detection (based on lightning strike location tx)
            for e in enemies:
                if e.hp > 0:
                    # Check distance from lightning center Y-axis
                    if abs((e.x + e.width/2) - tx) < 40:
                        # Lightning comes from above, so source_facing is arbitrary
                        sf = 1 if e.x < tx else -1
                        e.take_damage(3 + self.damage_bonus, sf)
            return True

        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0: self.range -= 1
    def draw_effect(self, screen):
        if self.range > 0:
            # Draw thick white lightning with slight offsets for glow effect
            for i in range(2):
                offset_x = random.randint(-3, 3)
                p_list = [(p[0] + offset_x, p[1]) for p in self.points]
                pygame.draw.lines(screen, (255, 255, 255), False, p_list, 5 - i*2)


class DashStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 60, (255, 255, 255), (100, 100, 255))
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.vx = 30 * player.facing
            player.swording = 20
            player.hit_timer = max(player.hit_timer, 25)
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)

class BraveChargeSkill(Skill):
    def __init__(self, x, y):
        # Cooldown 900, Duration 600
        super().__init__(x, y, 900, (255, 200, 0), (200, 100, 0))
        self.active_timer = 0
        self.initial_duration = 600
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 600 # 10 seconds (at 60fps)

            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.rect(screen, (255, 150, 0), (int(self.player_ref.x) - 4, int(self.player_ref.y) - 4, 48, 48), 2)

class MagicSwordSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 480, (0, 150, 255), (100, 200, 255))
        self.active_timer = 0
        self.waves = [] # [x, y, vx, timer, hit_enemies]
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 999  # Large value for infinite duration (limit based on swings_left)
            self.swings_left = 6   # Up to 6 times
            player.swording = 15
            return True

        return False
    def launch_wave(self, player):
        if hasattr(self, 'swings_left') and self.swings_left > 0:
            vx = 20 * player.facing
            # [x, y, vx, timer, hit_enemies]
            self.waves.append([player.x + 20, player.y + 10, vx, 40, []])
            self.swings_left -= 1
            if self.swings_left <= 0:
                self.active_timer = 0 # Finish

        
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        # Removed automatic timer decrease (lasts until swings_left is 0)
        
        new_waves = []
        for w in self.waves:
            w[0] += w[2] # Movement
            w[3] -= 1 # Lifetime

            if enemies:
                # Collision detection adjusted to crescent size (100x180)
                wave_rect = pygame.Rect(w[0] - 50, w[1] - 90, 100, 180)
                for e in enemies:
                    if e.hp > 0 and wave_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        if e not in w[4]:

                            if e.take_damage(2 + self.damage_bonus, 1 if w[2] > 0 else -1, ignore_iframes=True):
                                w[4].append(e)
            if w[3] > 0: new_waves.append(w)
        self.waves = new_waves
    
    def draw_effect(self, screen):
        for w in self.waves:
            # Crescent shape: thick center, thin ends
            points = []

            direction = 1 if w[2] > 0 else -1
            
            base_r = 100
            max_thickness = 40
            angle_range = 75
            
            # Outer arc
            for i in range(-angle_range, angle_range + 1, 5):
                rad = math.radians(i)
                px = w[0] + math.cos(rad) * base_r * direction
                py = w[1] + math.sin(rad) * base_r
                points.append((px, py))
            
            # Inner arc (use cosine to thicken center and taper ends)
            for i in range(angle_range, -angle_range - 1, -5):
                rad = math.radians(i)
                # Adjust thickness: max at center (i=0), near zero at ends (i=angle_range)
                t = max_thickness * math.cos(math.radians(i * 90 / angle_range))
                px = w[0] + (math.cos(rad) * base_r - t) * direction
                py = w[1] + math.sin(rad) * base_r
                points.append((px, py))

            
            if len(points) > 2:
                pygame.draw.polygon(screen, (100, 200, 255), points)

class RisingStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 45, (255, 100, 50), (150, 50, 0))
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.swording = 18
            player.vy = -25
            player.hit_timer = max(player.hit_timer, 30)
            player.y -= 10
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)



class PiercingArrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 180, (200, 200, 200), (100, 100, 100))
        self.aiming = False
        self.aim_angle = 45 # Initial angle
        self.arrows = [] # [x, y, vx, vy, hit_enemies]

    def activate(self, player, enemies=None):
        if self.cool == 0 and not self.aiming:
            self.aiming = True
            self.player_ref = player
            self.aim_angle = 0 if player.facing == 1 else 180
            player.vx = 0 # Stop while aiming
            return True

        elif self.aiming:
            self.aiming = False
            self.cool = self.max_cool
            rad = math.radians(self.aim_angle)
            vx = 25 * math.cos(rad)
            vy = 25 * math.sin(rad)
            self.arrows.append([player.x + 20, player.y + 20, vx, vy, []])
            return True

        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        if not self.aiming:
            super().update(enemies, cooldown_speed)
        new_arrows = []
        for a in self.arrows:
            a[0] += a[2]; a[1] += a[3]
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e not in a[4] and e.x < a[0] < e.x + e.width and e.y < a[1] < e.y + e.height:
                        if e.take_damage(2 + self.damage_bonus, 1 if a[2] > 0 else -1, ignore_iframes=True):
                            a[4].append(e) # Piercing

            if -100 < a[0] < width + 100 and -100 < a[1] < height + 100 and a[1] < ground + 20:
                new_arrows.append(a)
        self.arrows = new_arrows
    def draw_effect(self, screen):
        if self.aiming and hasattr(self, 'player_ref') and self.player_ref:
            p_center = (self.player_ref.x + 20, self.player_ref.y + 20)
            rad = math.radians(self.aim_angle)
            end_p = (p_center[0] + 100 * math.cos(rad), p_center[1] + 100 * math.sin(rad))
            pygame.draw.line(screen, (255, 0, 0), p_center, end_p, 2)
        for a in self.arrows:
            pygame.draw.circle(screen, (255, 255, 255), (int(a[0]), int(a[1])), 8)

class WarpArrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 420, (255, 100, 255), (150, 0, 150))
        self.arrow = None # [x, y, vx, vy]
        self.player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.player_ref = player
            self.arrow = [player.x+20, player.y+20, 20*player.facing, -5]
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.arrow:
            a = self.arrow; a[0] += a[2]; a[1] += a[3]; a[3] += 0.5
            hit = False
            if a[1] >= ground: a[1] = ground; hit = True
            if not hit and enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < a[0] < e.x + e.width and e.y < a[1] < e.y + e.height:
                        e.take_damage(1, 1 if a[2] > 0 else -1); hit = True; break
            if hit:
                if self.player_ref:
                    self.player_ref.x = a[0]-20; self.player_ref.y = a[1]-40
                    self.player_ref.vy = 0
                self.arrow = None
            elif not (-100 < a[0] < width + 100): self.arrow = None
    def draw_effect(self, screen):
        if self.arrow: pygame.draw.circle(screen, (255, 100, 255), (int(self.arrow[0]), int(self.arrow[1])), 5)

class ArrowRainSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 480, (100, 200, 255), (0, 100, 255))
        self.arrows = [] 
        self.spawn_count = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.spawn_x_base = player.x + 150*player.facing
            self.spawn_count = 40; return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.spawn_count > 0:
            ax = self.spawn_x_base + random.randint(-200, 200)
            self.arrows.append([ax, -50, random.uniform(18, 30)])
            self.spawn_count -= 1
        new_arrows = []
        for a in self.arrows:
            a[1] += a[2]
            hit = False
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < a[0] < e.x + e.width and e.y < a[1] < e.y + e.height:
                        e.take_damage(2, 1 if a[0] > self.spawn_x_base else -1, ignore_iframes=True); hit = True; break
            if not hit and a[1] < ground + 20: new_arrows.append(a)
        self.arrows = new_arrows
    def draw_effect(self, screen):
        for a in self.arrows: pygame.draw.line(screen, (150, 200, 255), (int(a[0]), int(a[1])-15), (int(a[0]), int(a[1])+15), 3)

class PinningArrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 360, (100, 255, 255), (0, 150, 150))
        self.arrows = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.arrows.append([player.x+20, player.y+20, 30*player.facing])
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        for a in self.arrows[:]:
            a[0] += a[2]
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < a[0] < e.x + e.width and e.y < a[1] < e.y + e.height:
                        if e.take_damage(1, 1 if a[2] > 0 else -1, ignore_iframes=True):
                            e.frozen_timer = 180; self.arrows.remove(a); break
            if a in self.arrows and not (-100 < a[0] < width + 100): self.arrows.remove(a)
    def draw_effect(self, screen):
        for a in self.arrows: pygame.draw.circle(screen, (100, 255, 255), (int(a[0]), int(a[1])), 6)

class IceEnchantSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (150, 200, 255), (50, 100, 255))
        self.active_timer = 0
        self.initial_duration = 420
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 420
            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0: self.active_timer -= 1
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (150, 200, 255), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 35, 2)

class FireEnchantSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (255, 100, 50), (255, 0, 0))
        self.active_timer = 0
        self.initial_duration = 420
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 420
            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0: self.active_timer -= 1
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (255, 100, 50), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 40, 2)

class HammerThrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 300, (200, 100, 50), (150, 50, 0))
        self.hammer = None
        self.player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.player_ref = player
            # [x, y, vx, vy, timer, facing, hit_enemies]
            self.hammer = [player.x+20, player.y+20, 25*player.facing, -5, 60, player.facing, []]
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.hammer:
            h = self.hammer; h[0] += h[2]; h[1] += h[3]; h[4] -= 1
            if h[4] < 30 and self.player_ref:
                # [Translated/Cleaned Comment]
                dx = self.player_ref.x + 20 - h[0]
                dy = self.player_ref.y + 20 - h[1]
                dist = max(1, math.hypot(dx, dy))
                h[2] += (dx / dist) * 2.5
                h[3] += (dy / dist) * 2.5
                if dist < 40: # [Translated/Cleaned Comment]
                    self.hammer = None
                    return
            
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e not in h[6] and e.x < h[0]+30 and h[0]-30 < e.x+e.width and e.y < h[1]+30 and h[1]-30 < e.y+e.height:
                        e.take_damage(4, 1 if h[2]>0 else -1, knockback_x=8, knockback_y=-5, element='heavy', ignore_iframes=True)
                        h[6].append(e)
                        
            if h[4] <= -100: self.hammer = None
    def draw_effect(self, screen):
        if self.hammer:
            angle = pygame.time.get_ticks() % 360
            surf = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.rect(surf, (150, 100, 50), (25, 5, 10, 50))       # [Translated/Cleaned Comment]
            pygame.draw.rect(surf, (100, 100, 100), (10, 5, 40, 20))      # [Translated/Cleaned Comment]
            rot_surf = pygame.transform.rotate(surf, angle)
            rect = rot_surf.get_rect(center=(int(self.hammer[0]), int(self.hammer[1])))
            screen.blit(rot_surf, rect)

class SuperArmorSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 900, (200, 200, 255), (100, 100, 255))
        self.active_timer = 0
        self.initial_duration = 420
        self.player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 420
            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0: 
            self.active_timer -= 1
            if player: player.invincible_timer = 2
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.rect(screen, (200, 255, 255), (int(self.player_ref.x)-10, int(self.player_ref.y)-10, 60, 60), 2)

class EarthquakeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 480, (150, 100, 50), (100, 50, 0))
        self.active_timer = 0; self.falling = False
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.vy = -30; self.player_ref = player; self.falling = True; return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0: self.active_timer -= 1
        if self.falling and self.player_ref:
            if self.player_ref.vy > 10:
                self.player_ref.vy = 25
                if self.player_ref.y >= ground:
                    self.falling = False; self.active_timer = 15
                    if enemies:
                        for e in enemies:
                            # [Translated/Cleaned Comment]
                            if e.hp > 0 and e.y + e.height >= ground - 5:
                                e.take_damage(6, 1 if e.x > self.player_ref.x else -1, knockback_y=-10, element='heavy')
    def draw_effect(self, screen):
        if self.active_timer > 0: pygame.draw.rect(screen, (255, 200, 100), (0, ground - 10, width, 20))

class WarCrySkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 720, (255, 50, 50), (150, 0, 0))
        self.active_timer = 0
        self.initial_duration = 480
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 480
            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0: self.active_timer -= 1
        if self.active_timer == 479 and enemies and player:
            for e in enemies:
                if e.hp > 0 and math.hypot(e.x - player.x, e.y - player.y) < 300: e.frozen_timer = 60
    def draw_effect(self, screen):
        if self.active_timer > 465 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (255, 100, 100), (int(self.player_ref.x+20), int(self.player_ref.y+20)), (480-self.active_timer)*20, 5)

# [Translated/Cleaned Comment]
class Character:
    """
                       
                                               
    """
    def __init__(self, player):
        self.player = player
        self.skills = []                 # [Translated/Cleaned Comment]
        self.is_reincarnator_mode = False # [Translated/Cleaned Comment]
        self.max_skills = 5              # [Translated/Cleaned Comment]
        self.upgrade_slots = 3           # [Translated/Cleaned Comment]
        self.current_upgrades = []       # [Translated/Cleaned Comment]
        self.queued_skill = None         # [Translated/Cleaned Comment]

    def handle_event(self, event, enemies):
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack']:
                self.attack(enemies)

            # [Translated/Cleaned Comment]
            keys = [key_config['skill_1'], key_config['skill_2'], key_config['skill_3'], 
                    key_config['skill_4'], key_config['skill_5']]
            for i, k in enumerate(keys):
                if event.key == k and i < len(self.skills):
                    # [Translated/Cleaned Comment]
                    self.skills[i].activate(self.player, enemies)

    def on_sword_hit(self, enemy, source_facing):
        """                               """
        for s in self.skills:
            # [Translated/Cleaned Comment]
            if type(s).__name__ == "IceEnchantSkill" and getattr(s, 'active_timer', 0) > 0:
                enemy.frozen_timer = 120
            # [Translated/Cleaned Comment]
            if type(s).__name__ == "FireEnchantSkill" and getattr(s, 'active_timer', 0) > 0:
                enemy.burn_timer = 180
                enemy.take_damage(1, source_facing, status_effect=True, element='fire')

    def update(self, keys, enemies, cooldown_speed):
        """
        Update character state. Processes skill cooldowns and status changes.
        """

        # Reset status to default values each frame (before applying buffs)
        self.player.damage_multiplier = 1.0
        self.player.move_speed = self.get_speed()
        self.player.jump_power = self.get_jump_power()


        # Global buff calculations (e.g. haste skills)
        cs = cooldown_speed
        for s in self.skills:
            if type(s).__name__ == "BraveChargeSkill" and getattr(s, 'active_timer', 0) > 0:
                cs *= 2 # Double cooldown reduction speed

        
        # [Translated/Cleaned Comment]
        for s in self.skills: 
            s.update(enemies, cs, player=self.player)
            
        # Dynamic status modification based on active skills
        for s in self.skills:
            # Brave Charge (Rampage) state
            if type(s).__name__ == "BraveChargeSkill" and getattr(s, 'active_timer', 0) > 0:
                self.player.damage_multiplier = max(self.player.damage_multiplier, 2.0)
                self.player.move_speed = max(self.player.move_speed, 2.0)
                # Boost jump power
                self.player.jump_power = min(self.player.jump_power, -20)
            
            # War Cry (Motivation) state
            if type(s).__name__ == "WarCrySkill" and getattr(s, 'active_timer', 0) > 0:
                self.player.damage_multiplier = max(self.player.damage_multiplier, 1.5)

            
            # Reduce fall speed due to Gravity skill
            if type(s).__name__ == "GravitySkill" and getattr(s, 'range', 0) > 0:
                self.player.vy += 0.3


    def draw_effects(self, screen):
        for s in self.skills:
            s.draw_effect(screen)
    def draw_ui(self, screen):
        SKILL_NAMES = {
            'MagicSwordSkill': 'Magic Sword', 'ThunderSkill': 'Lightning', 'IceEnchantSkill': 'Ice Enchant',
            'FireEnchantSkill': 'Fire Enchant', 'BraveChargeSkill': 'Charge', 'HammerThrowSkill': 'Hammer Throw',
            'SuperArmorSkill': 'Super Armor', 'EarthquakeSkill': 'Earthquake',
            'WarCrySkill': 'War Cry', 'LavaSkill': 'Lava', 'EruptionSkill': 'Eruption',
            'FlameDashSkill': 'Flame Dash', 'MeteorSkill': 'Meteor', 'PiercingArrowSkill': 'Pierce Arrow',
            'MirrorSkill': 'Mirror', 'WarpArrowSkill': 'Warp Arrow', 'ArrowRainSkill': 'Arrow Rain',
            'PinningArrowSkill': 'Pinning Arrow', 'JavelinThrowSkill': 'Javelin',
            'VaultingStrikeSkill': 'Vault Strike', 'RapidThrustsSkill': 'Rapid Thrusts',
            'SweepingStrikeSkill': 'Sweep', 'DragonDiveSkill': 'Dragon Dive',
            'RisingStrikeSkill': 'Rising Strike', 'DashStrikeSkill': 'Dash Strike',
            'EnhancedFireSkill': 'Spread Fire', 'FireSkill': 'Fireball', 'IceSkill': 'Frost',
            'DashSkill': 'Dash', 'GravitySkill': 'Gravity',
            'PounceSkill': 'Pounce', 'ScaleProjectileSkill': 'Scale Blade',
            'RoarSkill': 'Roar', 'AmpuleSkill': 'Ampule', 'RampageSkill': 'Rampage',
        }

        skill_keys = ['J', 'K', 'L', 'N', 'M']
        if not hasattr(Character, '_font_sm') or Character._font_sm is None:
            jp_fonts = ['msgothic', 'yugothic', 'meiryo', 'msuigothic', 'arial']
            Character._font_sm = None
            for f in jp_fonts:
                try:
                    Character._font_sm = pygame.font.SysFont(f, 14)
                    if Character._font_sm: break
                except: continue
            if not Character._font_sm: Character._font_sm = pygame.font.SysFont(None, 14)
        font_sm = Character._font_sm
        for i, s in enumerate(self.skills):
            s.x = 15 + i * 60
            s.y = 15
            s.draw(screen)
            if i < len(skill_keys):
                ks = font_sm.render(skill_keys[i], True, (255, 255, 0))
                screen.blit(ks, (s.x + 2, s.y - 14))
            cls_name = type(s).__name__
            disp_name = SKILL_NAMES.get(cls_name, cls_name.replace('Skill', ''))
            ns = font_sm.render(disp_name, True, (255, 255, 255))
            screen.blit(ns, (s.x, s.y + 52))

    def attack(self, enemies):
        """Execute basic attack (common for smartphone/keyboard)"""
        self.player.swording = 12

    # Duplicate handle_event removed


    def update_timers(self): pass
    def get_max_hp(self): return 10
    def get_speed(self): return 1.2
    def get_jump_power(self): return -15

    def generate_upgrades(self):
        """Generates 3 rewards (status up or new skill) after wave clear"""
        # Pool for status upgrade items

        pool = [
            {"type": "heal", "name": "HP Recovery", "desc": "Restore 5 HP"},
            {"type": "maxhp", "name": "Max HP Increase", "desc": "Max HP +3, Restore 3 HP"},
            {"type": "jump", "name": "Extra Jump", "desc": "Gain +1 extra jump in the air"},
            {"type": "attack", "name": "Attack Power UP", "desc": "Increase base damage by +1"},
            {"type": "defense", "name": "Defense Power UP", "desc": "Reduce incoming damage by 1"},
            {"type": "speed", "name": "Movement Speed UP", "desc": "Increase move speed by 20%"},
            {"type": "cd", "name": "Cooldown Reduction", "desc": "Increase skill cooldown speed by 20%"}
        ]
        
        # All skill classes defined in main.py

        all_skills_classes = [MagicSwordSkill, ThunderSkill, IceEnchantSkill, FireEnchantSkill, BraveChargeSkill,
                              HammerThrowSkill, SuperArmorSkill, EarthquakeSkill, WarCrySkill,
                              LavaSkill, EruptionSkill, FlameDashSkill, MeteorSkill,
                              PiercingArrowSkill, MirrorSkill, WarpArrowSkill, ArrowRainSkill, PinningArrowSkill,
                              JavelinThrowSkill, VaultingStrikeSkill, RapidThrustsSkill, SweepingStrikeSkill, DragonDiveSkill,
                              RisingStrikeSkill, DashStrikeSkill, EnhancedFireSkill]
                              
        # List of candidate skills excluding already owned ones

        my_skill_types = [type(s) for s in self.skills]
        unacquired = [s for s in all_skills_classes if s not in my_skill_types]
        random.shuffle(unacquired)
        
        # [Translated/Cleaned Comment]
        for i in range(min(2, len(unacquired))): 
            name = unacquired[i].__name__.replace("Skill", "")
            pool.append({"type": "skill", "name": "[New Skill]", "desc": f"Learn the skill '{name}'", "skill_class": unacquired[i]})
            
        # Randomly select from pool and store
        self.current_upgrades = random.sample(pool, min(self.upgrade_slots, len(pool)))


    def apply_upgrade(self, upgrade):
        """Applies the selected reward to the player. Transitions to replacement screen if slots are full."""
        global game_state

        if upgrade["type"] == "heal":
            self.player.hp = min(self.player.max_hp, self.player.hp + 5)
        elif upgrade["type"] == "maxhp":
            self.player.max_hp += 3
            self.player.hp += 3
        elif upgrade["type"] == "jump":
            self.player.jump_count_max += 1
        elif upgrade["type"] == "attack":
            self.player.bonus_damage += 1
        elif upgrade["type"] == "defense":
            self.player.defense += 1
        elif upgrade["type"] == "speed":
            self.player.move_speed += 0.2
        elif upgrade["type"] == "cd":
            self.player.cooldown_speed_mult += 0.2
        elif upgrade["type"] == "skill":
            # Create a new skill instance
            new_skill = upgrade["skill_class"](0, 15)
            if len(self.skills) < self.max_skills:
                # If below skill limit, learn immediately
                self.skills.append(new_skill)
            else:
                # If 5 slots are full, set to queued skill and enter replacement state
                self.queued_skill = new_skill
                game_state = STATE_REPLACE_SKILL
                return False # Do not proceed to next wave until replacement is handled
        return True




class EnhancedFireSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 120, (255, 150, 50), (255, 50, 0))
        self.bullets = [] # [x, y, vx, vy, timer]
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            vx = 15 * player.facing
            self.bullets.append([player.x+20, player.y+20, vx, 0, 60])
            self.bullets.append([player.x+20, player.y+20, vx, -3, 60])
            self.bullets.append([player.x+20, player.y+20, vx, 3, 60])
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        for b in self.bullets[:]:
            b[0] += b[2]
            b[1] += b[3]
            b[4] -= 1
            hit = False
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < b[0] < e.x + e.width and e.y < b[1] < e.y + e.height:
                        if e.take_damage(2 + self.damage_bonus, 1 if b[2] > 0 else -1, element='fire'):
                            hit = True
                            break
            if hit or b[4] <= 0:
                self.bullets.remove(b)
    def draw_effect(self, screen):
        for b in self.bullets:
            pygame.draw.circle(screen, (255, 100, 0), (int(b[0]), int(b[1])), 8)

class EruptionSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 360, (255, 80, 20), (200, 0, 0))
        self.active_timer = 0
        self.pillar_x = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 90 # Lasts 1.5 seconds (at 60fps)
            self.pillar_x = player.x + (150 * player.facing)
            self.source_facing = player.facing
            return True
        return False

    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if enemies:
                er_rect = pygame.Rect(self.pillar_x - 40, ground - 300, 80, 300)
                for e in enemies:
                    if e.hp > 0 and er_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        e.take_damage(1 + self.damage_bonus, self.source_facing, element='fire') # Low damage (hits every frame)
    def draw_effect(self, screen):
        if self.active_timer > 0:
            # Flickering pillar of fire

            for _ in range(15):
                rw = random.randint(40, 100)
                rh = random.randint(150, 400)
                rx = self.pillar_x - rw // 2 + random.randint(-10, 10)
                ry = ground - rh
                rc = (255, random.randint(50, 200), 0)
                surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
                pygame.draw.rect(surf, (*rc, 150), (0, 0, rw, rh), border_radius=10)
                screen.blit(surf, (rx, ry))

class FlameDashSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 240, (255, 120, 50), (200, 50, 0))
        self.flames = [] # [x, y, timer, facing, hit_enemies]
        self.active_timer = 0
        self.player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 40 # Lasts 40 frames
            self.player_ref = player
            player.vy = -5
            return True
        return False

    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        
        p = player if player else self.player_ref
        if self.active_timer > 0 and p:
            self.active_timer -= 1
            # Fix speed and grant invincibility
            p.vx = 20 * p.facing
            p.invincible_timer = max(p.invincible_timer, 2)
            # Drop fire every 3 frames
            if self.active_timer % 3 == 0:
                self.flames.append([p.x, p.y, 75, p.facing, []])

                
        for f in self.flames[:]:
            f[2] -= 1
            if enemies:
                f_rect = pygame.Rect(f[0], f[1], 40, 40)
                hit_list = f[4] if len(f) > 4 else []
                for e in enemies:
                    if e.hp > 0 and e not in hit_list and f_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        e.burn_timer = 180
                        if e.take_damage(1 + self.damage_bonus, f[3] if len(f)>3 else 1, status_effect=True, element='fire'):
                            hit_list.append(e)
            if f[2] <= 0:
                self.flames.remove(f)
    def draw_effect(self, screen):
        for f in self.flames:
            c = min(255, max(0, int(f[2] / 75 * 255)))
            pygame.draw.rect(screen, (255, c, 0), (int(f[0]), int(f[1]) + 20, 40, 20))


class MeteorSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (255, 60, 60), (150, 0, 0))
        self.meteor = None # [x, y, vy]
        self.target_x = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.target_x = player.x + (250 * player.facing)
            self.meteor = [self.target_x, -100, 15]
            return True
        return False

    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.meteor:
            m = self.meteor
            m[1] += m[2]
            if m[1] >= ground: # Impact
                if enemies:
                    # Double attack range (300 -> 600)
                    blast_rect = pygame.Rect(m[0] - 300, ground - 100, 600, 100)
                    for e in enemies:
                        if e.hp > 0 and blast_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            # Shockwave direction
                            sf = 1 if e.x > m[0] else -1
                            e.take_damage(12 + self.damage_bonus, sf, element='fire')
                            e.burn_timer = 180 # Inflict burn
                self.meteor = None

    def draw_effect(self, screen):
        if self.meteor:
            m = self.meteor
            pygame.draw.circle(screen, (255, 100, 0), (int(m[0]), int(m[1])), 80) # Slightly larger
            pygame.draw.circle(screen, (255, 200, 50), (int(m[0]), int(m[1])), 50) # Slightly larger
            # Range display set to 600 width
            pygame.draw.ellipse(screen, (255, 0, 0), (int(m[0]) - 300, ground - 20, 600, 40), 2)

        
class Warrior(Character):
    def __init__(self, player):
        super().__init__(player)
        self.skill_throw = HammerThrowSkill(15, 15)
        self.skill_armor = SuperArmorSkill(75, 15)
        self.skill_brave_charge = BraveChargeSkill(135, 15)
        self.skill_earthquake = EarthquakeSkill(195, 15)
        self.skill_warcry = WarCrySkill(255, 15)
        self.skills = [self.skill_throw, self.skill_armor, self.skill_brave_charge, self.skill_earthquake, self.skill_warcry]
        self.hammering = 0
        self.hit_enemies = []

    def get_max_hp(self):
        return 15 # High HP
    def get_speed(self):
        return 0.8 # Slow move speed
    def get_jump_power(self):
        return -12 # Low jump power


    def attack(self, enemies):
        if self.hammering == 0:
            self.hammering = 20 # Swing duration frames (fastened from 15 to 10)
            self.hit_enemies = []


    def handle_event(self, event, enemies):
        """Warrior input handling (basic attack and skills)"""
        super().handle_event(event, enemies)

        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            # Individual skill activation (from key config) - Normal mode only
            if not self.is_reincarnator_mode:

                if event.key == key_config['skill_1']: self.skill_throw.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_armor.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_brave_charge.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_earthquake.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_warcry.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        
        # Hammer collision detection
        if self.hammering > 0:
            self.hammering -= 1
            if self.hammering < 6: # Collison active in the last 6 frames of attack
                hx = self.player.x + (60 * self.player.facing)

                hy = self.player.y + 20
                if enemies:
                    hammer_rect = pygame.Rect(hx - 50, hy - 50, 100, 100)
                    for e in enemies:
                        if e.hp > 0 and e not in self.hit_enemies and hammer_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            if e.take_damage(4 * self.player.damage_multiplier, self.player.facing, knockback_x=12, knockback_y=-8, element='heavy'): # High damage, large knockback
                                self.hit_enemies.append(e)


    def draw_effects(self, screen):
        super().draw_effects(screen)
        
        # Hammer rendering (stylized)
        if self.hammering > 0:

            p_center_x = self.player.x + 20
            p_center_y = self.player.y + 20
            progress = (20 - self.hammering) / 20.0
            base_angle = 0 if self.player.facing == 1 else 180
            current_angle = base_angle + (-110 + 130 * progress) * self.player.facing
            rad = math.radians(current_angle)
            dist = 70
            end_x = p_center_x + dist * math.cos(rad)
            end_y = p_center_y + dist * math.sin(rad)
            
            # Afterimage
            for i in range(3):

                alpha_progress = max(0, progress - i * 0.05)
                alpha_angle = base_angle + (-110 + 180 * alpha_progress) * self.player.facing
                a_rad = math.radians(alpha_angle)
                ax = p_center_x + dist * math.cos(a_rad)
                ay = p_center_y + dist * math.sin(a_rad)
                pygame.draw.line(screen, (100, 100, 100), (p_center_x, p_center_y), (ax, ay), 4)

            pygame.draw.line(screen, (150, 100, 50), (p_center_x, p_center_y), (end_x, end_y), 10)
            pygame.draw.rect(screen, (80, 80, 80), (end_x - 25, end_y - 25, 50, 50), border_radius=5)
            pygame.draw.rect(screen, (120, 120, 120), (end_x - 25, end_y - 25, 50, 50), 3, border_radius=5)





class Pyromancer(Character):
    """Fire Mage: Specializes in long-range fireballs and wide-area fire skills"""
    def __init__(self, player):

        super().__init__(player)
        self.skill_lava = LavaSkill(15, 15)
        self.skill_enhanced = EnhancedFireSkill(75, 15)
        self.skill_eruption = EruptionSkill(135, 15)
        self.skill_flamedash = FlameDashSkill(195, 15)
        self.skill_meteor = MeteorSkill(255, 15)
        self.skills = [self.skill_lava, self.skill_enhanced, self.skill_eruption, self.skill_flamedash, self.skill_meteor]
        self.fireballs = [] # [Translated/Cleaned Comment]

    def get_max_hp(self):
        return 7 # Low durability

    def get_speed(self):
        return 1.1
    def get_jump_power(self):
        return -14

    def attack(self, enemies):
        # Basic attack: Fireball
        vx = 20 * self.player.facing

        self.fireballs.append([self.player.x + 20, self.player.y + 20, vx, 40, self.player.facing]) # Add player.facing

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_lava.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_enhanced.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_eruption.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_flamedash.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_meteor.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        # Update fireballs
        for fb in self.fireballs[:]:

            fb[0] += fb[2]
            fb[3] -= 1
            hit = False
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < fb[0] < e.x + e.width and e.y < fb[1] < e.y + e.height:
                        if e.take_damage(1, fb[4], element='fire', ignore_iframes=True): # Use fireball's facing
                            hit = True
                            break

            if hit or fb[3] <= 0:
                self.fireballs.remove(fb)
                
        # [Translated/Cleaned Comment]
        if self.skill_flamedash.flames and len(self.skill_flamedash.flames) > 0:
            if abs(self.player.vx) > 5 and self.player.invincible_timer > 0:
                if random.random() < 0.5:
                    self.skill_flamedash.flames.append([self.player.x, self.player.y, 60, self.player.facing])

    def draw_effects(self, screen):
        super().draw_effects(screen)
        for fb in self.fireballs:
            pygame.draw.circle(screen, (255, 50, 0), (int(fb[0]), int(fb[1])), 10)
            pygame.draw.circle(screen, (255, 200, 0), (int(fb[0]), int(fb[1])), 5)

class JavelinThrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 180, (200, 200, 255), (100, 100, 255))
        self.javelins = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            vx = 35 * player.facing # High speed

            self.javelins.append([player.x + 20, player.y + 20, vx, 40, [], player.facing])
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        for j in self.javelins[:]:
            j[0] += j[2]
            j[3] -= 1
            if enemies:
                er_rect = pygame.Rect(j[0], j[1] - 5, 40, 10)
                for e in enemies:
                    if e.hp > 0 and e not in j[4] and er_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        if e.take_damage(4 + self.damage_bonus, j[5]): # Piercing

                            j[4].append(e)
            if j[3] <= 0:
                self.javelins.remove(j)
    def draw_effect(self, screen):
        for j in self.javelins:
            pygame.draw.line(screen, (200, 255, 255), (j[0], j[1]), (j[0] + 40 * (1 if j[2]>0 else -1), j[1]), 4)

class VaultingStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 300, (150, 255, 150), (50, 200, 50))
        self.active_timer = 0
        self.player_ref = None
        self.source_facing = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.player_ref = player
            self.source_facing = player.facing
            player.vy = -20 # Diagonal jump
            player.invincible_timer = 20
            self.active_timer = 30 # Air active time
            self.player_ref = player
            self.source_facing = player.facing

            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if self.player_ref.y >= ground - 10: # On landing

                self.active_timer = 0
                if enemies: # Shockwave

                    blast = pygame.Rect(self.player_ref.x - 40, self.player_ref.y, 120, 40)
                    for e in enemies:
                        if e.hp > 0 and blast.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(3 + self.damage_bonus, self.source_facing)
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (150, 255, 150), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 30, 2)

class RapidThrustsSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 420, (255, 255, 150), (200, 200, 50))
        self.active_timer = 0
        self.player_ref = None
        self.source_facing = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 60 # 1 second multi-thrust

            self.player_ref = player
            self.source_facing = player.facing
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if self.player_ref:
                self.player_ref.vx = 0 
            if self.active_timer % 6 == 0: # Shortened hit interval (10->6)

                if enemies and self.player_ref:
                    hx = self.player_ref.x + (20 if self.player_ref.facing == 1 else -160)
                    hitbox = pygame.Rect(hx, self.player_ref.y + 10, 180, 30) # Expanded hitbox

                    for e in enemies:
                        if e.hp > 0 and hitbox.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(1 + self.damage_bonus, self.source_facing)
                            # Pulling effect

                            pull_x = self.player_ref.x + 60 * self.player_ref.facing
                            e.x += (pull_x - e.x) * 0.2
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            for _ in range(3):
                lx = self.player_ref.x + 20 + random.randint(0, 100) * self.player_ref.facing
                ly = self.player_ref.y + 20 + random.randint(-10, 10)
                pygame.draw.line(screen, (255, 255, 150), (self.player_ref.x+20, self.player_ref.y+20), (lx, ly), 2)

class SweepingStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 360, (255, 150, 255), (150, 50, 150))
        self.active_timer = 0
        self.player_ref = None
        self.hit_enemies = []
        self.source_facing = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 20
            self.player_ref = player
            self.hit_enemies = []
            self.source_facing = player.facing
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if enemies and self.player_ref:
                hitbox = pygame.Rect(self.player_ref.x - 60, self.player_ref.y - 40, 160, 120)
                for e in enemies:
                    if e.hp > 0 and e not in self.hit_enemies and hitbox.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        if e.take_damage(4 + self.damage_bonus, self.source_facing, knockback_x=15):
                            self.hit_enemies.append(e)
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            radius = int((20 - self.active_timer) / 20 * 80)
            pygame.draw.circle(screen, (255, 150, 255), (int(self.player_ref.x+20), int(self.player_ref.y+20)), radius, 3)

class DragonDiveSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 720, (100, 255, 255), (0, 150, 150))
        self.phase = 0 # 0: none, 1: rising, 2: diving
        self.player_ref = None
        self.source_facing = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.phase = 1
            player.vy = -35
            player.invincible_timer = 60
            self.player_ref = player
            self.source_facing = player.facing
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.phase == 1:
            self.player_ref.vx = 0 # Rising straight up

            if self.player_ref.vy > -5: # Near end of ascent

                self.phase = 2
                self.player_ref.vy = 50 # Dive speed

        elif self.phase == 2:
            # Left/right control during dive

            keys = pygame.key.get_pressed()
            move_speed = 10
            if keys[key_config['move_left']]:
                self.player_ref.x -= move_speed
            if keys[key_config['move_right']]:
                self.player_ref.x += move_speed
                
            if self.player_ref.y >= ground:
                self.phase = 0
                if enemies:
                    # Damage surrounding area on ground impact

                    blast = pygame.Rect(self.player_ref.x - 120, self.player_ref.y - 60, 280, 110)
                    for e in enemies:
                        if e.hp > 0 and blast.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(10 + self.damage_bonus, self.source_facing, knockback_y=-15, element='heavy')
    def draw_effect(self, screen):
        if (self.phase == 1 or self.phase == 2) and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (100, 255, 255), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 25)
            pygame.draw.polygon(screen, (50, 200, 200), [(self.player_ref.x+20, self.player_ref.y-20), (self.player_ref.x+50, self.player_ref.y+50), (self.player_ref.x-10, self.player_ref.y+50)])

class Lancer(Character):
    """Lancer: Mid-range powerful thrust attacks and mobility-focused skills"""
    def __init__(self, player):

        super().__init__(player)
        self.skill_javelin = JavelinThrowSkill(15, 15)
        self.skill_vault = VaultingStrikeSkill(75, 15)
        self.skill_rapid = RapidThrustsSkill(135, 15)
        self.skill_sweep = SweepingStrikeSkill(195, 15)
        self.skill_dragondive = DragonDiveSkill(255, 15)
        self.skills = [self.skill_javelin, self.skill_vault, self.skill_rapid, self.skill_sweep, self.skill_dragondive]
        self.thrusting = 0 # Thrust duration timer
        self.hit_enemies = []


    def get_max_hp(self):
        return 12
    def get_speed(self):
        return 1.3
    def get_jump_power(self):
        return -18

    def attack(self, enemies):
        if self.thrusting == 0:
            self.thrusting = 15 # High-speed thrust
            self.hit_enemies = []


    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_javelin.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_vault.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_rapid.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_sweep.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_dragondive.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        
        # Spear thrust collision
        if self.thrusting > 0:
            self.thrusting -= 1
            if self.thrusting == 10: # Active frame

                hx = self.player.x + (20 if self.player.facing == 1 else -140)
                hy = self.player.y + 20
                if enemies:
                    spear_rect = pygame.Rect(hx, hy - 5, 160, 10) # Very long hitbox
                    for e in enemies:
                        if e.hp > 0 and e not in self.hit_enemies and spear_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            if e.take_damage(2, self.player.facing, knockback_x=4): # Light knockback
                                self.hit_enemies.append(e)


    def draw_effects(self, screen):
        super().draw_effects(screen)
        
        # Spear attack rendering (stylized)
        if self.thrusting > 0:

            px = self.player.x + 20
            py = self.player.y + 20
            progress = (15 - self.thrusting) / 15.0
            reach = 180 * math.sin(progress * math.pi) # [Translated/Cleaned Comment]
            
            # [Translated/Cleaned Comment]
            pygame.draw.line(screen, (255, 255, 255), (px, py), (px + (reach + 20) * self.player.facing, py), 6)
            pygame.draw.line(screen, (100, 200, 255), (px, py), (px + reach * self.player.facing, py), 12)
            
            # Tip flash

            if 5 < self.thrusting < 12:
                flash_surf = pygame.Surface((60, 20), pygame.SRCALPHA)
                pygame.draw.ellipse(flash_surf, (255, 255, 255, 180), (0, 0, 60, 20))
                screen.blit(flash_surf, (px + (reach - 30) * self.player.facing if self.player.facing == 1 else px - reach - 30, py - 10))

class Swordsman(Character):
    """Swordsman: Standard character. Good balance of melee and mobility skills."""
    def __init__(self, player):

        super().__init__(player)
        self.skill_dash_strike = DashStrikeSkill(15, 15)
        self.skill_rising_strike = RisingStrikeSkill(75, 15)
        self.skill_fire = FireSkill(135, 15)
        self.skill_brave_charge = BraveChargeSkill(195, 15)
        self.skill_gravity = GravitySkill(255, 15)
        self.skills = [self.skill_dash_strike, self.skill_rising_strike, self.skill_fire, self.skill_brave_charge, self.skill_gravity]

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_dash_strike.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_rising_strike.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_fire.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_brave_charge.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_gravity.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
            
        # Update unique skills (global effects like gravity)
        if self.skill_gravity in self.skills and self.skill_gravity.range > 0:
            # Gravity reduction is handled in Player.update, but can be supplemented here
            pass


    def draw_effects(self, screen):
        super().draw_effects(screen)

class Archer(Character):
    """Archer: Long-range specialist. Uses bombs and trajectory-altering arrow skills."""
    def __init__(self, player):

        super().__init__(player)
        self.skill_pierce = PiercingArrowSkill(15, 15)
        self.skill_mirror = MirrorSkill(75, 15)
        self.skill_warp = WarpArrowSkill(135, 15)
        self.skill_rain = ArrowRainSkill(195, 15)
        self.skill_pin = PinningArrowSkill(255, 15)
        self.skills = [self.skill_pierce, self.skill_mirror, self.skill_warp, self.skill_rain, self.skill_pin]
        self.bombs = [] # List of active bombs


    def get_max_hp(self):
        return 10
    def get_speed(self):
        return 1.2
    def get_jump_power(self):
        return -15

    def attack(self, enemies):
        # Bomb attack (no cooldown, but can be limited by number of active bombs)
        bx = self.player.x + 60 * self.player.facing
        by = self.player.y + 20
        self.bombs.append([bx, by, 15, self.player.facing]) # 15 frame explosion


    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            # Handling PiercingArrow aim (if owned)
            pierce_skill = next((s for s in self.skills if isinstance(s, PiercingArrowSkill)), None)

            if pierce_skill and pierce_skill.aiming:
                if event.key == key_config['skill_1']: 
                    pierce_skill.activate(self.player, enemies) # Fire

                elif event.key == key_config['jump']:
                    pierce_skill.aim_angle -= 15 * self.player.facing
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    pierce_skill.aim_angle += 15 * self.player.facing
            else:
                if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                    self.player.vy = self.player.jump_power
                    self.player.jumpcount -= 1
                if not self.is_reincarnator_mode:
                    if event.key == key_config['skill_1']: self.skill_pierce.activate(self.player, enemies)
                    if event.key == key_config['skill_2']: self.skill_mirror.activate(self.player, enemies)
                    if event.key == key_config['skill_3']: self.skill_warp.activate(self.player, enemies)
                    if event.key == key_config['skill_4']: self.skill_rain.activate(self.player, enemies)
                    if event.key == key_config['skill_5']: self.skill_pin.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        
        # Update bombs and check for explosions
        for b in self.bombs[:]:
            b[2] -= 1 # Countdown timer
            if b[2] <= 0:
                # Explosion
                if enemies:
                    blast_rect = pygame.Rect(b[0] - 60, b[1] - 40, 120, 80)
                    for e in enemies:
                        if e.hp > 0 and blast_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(4, b[3], element='fire') # Damage adjustment
                self.bombs.remove(b)


    def draw_effects(self, screen):
        super().draw_effects(screen)
        # Render bombs and explosions
        for b in self.bombs:
            if b[2] > 5: # Placed
                pygame.draw.circle(screen, (30, 30, 30), (int(b[0]), int(b[1])), 10) # Darken color
                pygame.draw.circle(screen, (255, 50, 50), (int(b[0]), int(b[1])), 5)
            else: # Explosion
                # Fancy explosion effect
                radius = 60 - b[2]*4
                alpha = 150 + b[2]*10
                surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (255, 150, 50, alpha), (radius, radius), radius)
                screen.blit(surf, (int(b[0]-radius), int(b[1]-radius)))


class MagicSwordsman(Character):
    def __init__(self, player):
        super().__init__(player)
        self.skill_magic_sword = MagicSwordSkill(15, 15)
        self.skill_thunder = ThunderSkill(75, 15)
        self.skill_ice_enchant = IceEnchantSkill(135, 15)
        self.skill_fire_enchant = FireEnchantSkill(195, 15)
        self.skill_brave_charge = BraveChargeSkill(255, 15)
        self.skills = [self.skill_magic_sword, self.skill_thunder, self.skill_ice_enchant, self.skill_fire_enchant, self.skill_brave_charge]

    def attack(self, enemies):
        self.player.swording = 12
        # Launch wave if MagicSword is active
        ms_skill = next((s for s in self.skills if isinstance(s, MagicSwordSkill)), None)
        if ms_skill and ms_skill.active_timer > 0:
            ms_skill.launch_wave(self.player)


    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_magic_sword.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_thunder.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_ice_enchant.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_fire_enchant.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_brave_charge.activate(self.player, enemies)


    def on_sword_hit(self, enemy, source_facing):
        # [Translated/Cleaned Comment]
        super().on_sword_hit(enemy, source_facing)
            
    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)

    def draw_effects(self, screen):
        super().draw_effects(screen)


# [Translated/Cleaned Comment]
class PounceSkill(Skill):
    """     :            HP  """
    def __init__(self, x, y):
        super().__init__(x, y, 90, (200, 50, 50), (100, 25, 25))
        self.dashing = 0
        self.dash_dir = 1
        self.hit_enemies = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.dashing = 15
            self.dash_dir = player.facing
            self.hit_enemies = []
            player.vy = -8
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.dashing > 0 and player:
            self.dashing -= 1
            player.x += 12 * self.dash_dir
            player.invincible_timer = max(player.invincible_timer, 2)
            if enemies:
                hit_rect = pygame.Rect(player.x - 10, player.y - 10, 60, 60)
                for e in enemies:
                    if e.hp > 0 and e not in self.hit_enemies:
                        if hit_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            dmg = 3 * getattr(player, 'damage_multiplier', 1)
                            if e.take_damage(int(dmg), self.dash_dir, knockback_x=8, knockback_y=-5):
                                self.hit_enemies.append(e)
                                if getattr(player, '_monster_rampage', 0) > 0:
                                    # [Translated/Cleaned Comment]
                                    heal_amount = 1
                                    player.hp = min(player.max_hp, player.hp + heal_amount)
    def draw_effect(self, screen):
        pass

class ScaleProjectileSkill(Skill):
    """  :            """
    def __init__(self, x, y):
        super().__init__(x, y, 45, (150, 80, 80), (75, 40, 40))
        self.projectiles = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            vx = 15 * player.facing
            pierce = getattr(player, '_monster_rampage', 0) > 0
            self.projectiles.append({
                'x': player.x + 20, 'y': player.y + 15,
                'vx': vx, 'timer': 60, 'facing': player.facing,
                'pierce': pierce, 'hit': []
            })
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        dmg_mult = getattr(player, 'damage_multiplier', 1) if player else 1
        for p in self.projectiles[:]:
            p['x'] += p['vx']
            p['timer'] -= 1
            if p['timer'] <= 0 or p['x'] < -50 or p['x'] > width + 50:
                self.projectiles.remove(p)
                continue
            if enemies:
                proj_rect = pygame.Rect(p['x'] - 10, p['y'] - 5, 20, 10)
                for e in enemies:
                    if e.hp > 0 and e not in p['hit']:
                        if proj_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(int(2 * dmg_mult), p['facing'])
                            p['hit'].append(e)
                            if not p['pierce']:
                                if p in self.projectiles: self.projectiles.remove(p)
                                break
    def draw_effect(self, screen):
        for p in self.projectiles:
            color = (200, 100, 100) if not p['pierce'] else (255, 50, 50)
            px, py = int(p['x']), int(p['y'])
            d = 1 if p['vx'] > 0 else -1
            pygame.draw.polygon(screen, color, [
                (px + 12 * d, py), (px - 8 * d, py - 6), (px - 8 * d, py + 6)
            ])

class RoarSkill(Skill):
    """  :        +      """
    def __init__(self, x, y):
        super().__init__(x, y, 180, (180, 130, 50), (90, 65, 25))
        self.roar_effect = 0
        self._player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.roar_effect = 15
            self._player_ref = player
            if enemies:
                cx = player.x + 20
                cy = player.y + 20
                for e in enemies:
                    if e.hp > 0:
                        dist = math.hypot(e.x + e.width//2 - cx, e.y + e.height//2 - cy)
                        if dist < 200:
                            e.frozen_timer = max(e.frozen_timer, 60)
                            e.take_damage(1, 1 if e.x > cx else -1, knockback_x=3, knockback_y=-2, status_effect=True)
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.roar_effect > 0: self.roar_effect -= 1
    def draw_effect(self, screen):
        if self.roar_effect > 0 and self._player_ref:
            px = self._player_ref.x + 20
            py = self._player_ref.y + 20
            r = int((15 - self.roar_effect) / 15 * 200)
            alpha = int(self.roar_effect / 15 * 150)
            if r >= 4:
                surf = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (255, 200, 50, alpha), (r+1, r+1), r, 4)
                screen.blit(surf, (int(px)-r-1, int(py)-r-1))

class AmpuleSkill(Skill):
    """      :    +       """
    def __init__(self, x, y):
        super().__init__(x, y, 120, (100, 200, 100), (50, 100, 50))
    def activate(self, player, enemies=None):
        # [Translated/Cleaned Comment]
        if player.hp <= 1:
            return False
            
        if super().activate(player, enemies):
            # [Translated/Cleaned Comment]
            self_dmg = max(1, player.max_hp // 10)
            
            player.hp -= self_dmg
            if player.hp < 1: player.hp = 1
            player._ampule_count = getattr(player, '_ampule_count', 0) + 1
            return True
        return False

class RampageSkill(Skill):
    """  :               """
    def __init__(self, x, y):
        super().__init__(x, y, 300, (200, 30, 30), (100, 15, 15))
        self.active_timer = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            amps = getattr(player, '_ampule_count', 0)
            
            # [Translated/Cleaned Comment]
            base_duration = 180
            duration_per_ampule = 30
            self.active_timer = base_duration + amps * duration_per_ampule
            self.initial_duration = self.active_timer
            
            player._monster_rampage = self.active_timer
            
            # [Translated/Cleaned Comment]
            player._ampule_count = amps // 2
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if player:
                player._monster_rampage = self.active_timer
    def draw_effect(self, screen):
        pass

class MonsterBeta(Character):
    """
       :                                         
    """
    def __init__(self, player):
        super().__init__(player)
        # [Translated/Cleaned Comment]
        self.skill_pounce = PounceSkill(15, 15)
        self.skill_scale = ScaleProjectileSkill(75, 15)
        self.skill_roar = RoarSkill(135, 15)
        self.skill_ampule = AmpuleSkill(195, 15)
        self.skill_rampage = RampageSkill(255, 15)
        # [Translated/Cleaned Comment]
        self.skills = [self.skill_pounce, self.skill_scale, self.skill_roar, self.skill_ampule, self.skill_rampage]
        self.scratch_timer = 0  # [Translated/Cleaned Comment]
        self.hit_enemies = []   # [Translated/Cleaned Comment]
        player._ampule_count = 0     # [Translated/Cleaned Comment]
        player._monster_rampage = 0  # [Translated/Cleaned Comment]

    def get_max_hp(self): return 12
    def get_speed(self): return 1.5
    def get_jump_power(self): return -16

    def attack(self, enemies):
        if self.scratch_timer == 0:
            self.scratch_timer = 8
            self.hit_enemies = []

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']:
                    self.skill_pounce.activate(self.player, enemies)
                if event.key == key_config['skill_2']:
                    self.skill_scale.activate(self.player, enemies)
                if event.key == key_config['skill_3']:
                    self.skill_roar.activate(self.player, enemies)
                if event.key == key_config['skill_4']:
                    self.skill_ampule.activate(self.player, enemies)
                if event.key == key_config['skill_5']:
                    self.skill_rampage.activate(self.player, enemies)


    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        amps = getattr(self.player, '_ampule_count', 0)
        rampage = getattr(self.player, '_monster_rampage', 0)
        
        self.player.damage_multiplier = 1.0 + amps * 1.1
        if rampage > 0:
            amp_bonus = amps * 0.3
            self.player.damage_multiplier += 1.0 + amp_bonus
            self.player.move_speed = 1.5 + 0.3 * min(amps, 5)
            self.player.jump_power = -16 - min(amps, 5)
        else:
            self.player.move_speed = 1.5
            self.player.jump_power = -16
        
        if self.scratch_timer > 0:
            self.scratch_timer -= 1
            if self.scratch_timer < 5:
                hx = self.player.x + (50 * self.player.facing)
                hy = self.player.y + 15
                if enemies:
                    claw_rect = pygame.Rect(hx - 25, hy - 20, 50, 40)
                    for e in enemies:
                        if e.hp > 0 and e not in self.hit_enemies:
                            if claw_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                                dmg = int(2 * self.player.damage_multiplier)
                                if e.take_damage(dmg, self.player.facing, knockback_x=4, knockback_y=-2):
                                    self.hit_enemies.append(e)

    def draw_effects(self, screen):
        super().draw_effects(screen)
        p = self.player
        rampage = getattr(p, '_monster_rampage', 0)
        amps = getattr(p, '_ampule_count', 0)
        
        if self.scratch_timer > 0 and self.scratch_timer < 5:
            cx = int(p.x + 50 * p.facing)
            cy = int(p.y + 15)
            for i in range(3):
                offset = (i - 1) * 8
                pygame.draw.line(screen, (255, 200, 200),
                    (cx - 15 * p.facing, cy + offset - 10),
                    (cx + 15 * p.facing, cy + offset + 10), 3)
        
        if rampage > 0:
            # [Translated/Cleaned Comment]
            shade = pygame.Surface((p.width, p.height), pygame.SRCALPHA)
            shade.fill((200, 0, 0, 120))
            screen.blit(shade, (int(p.x), int(p.y)))
            
            # [Translated/Cleaned Comment]
            eye_y = int(p.y + 12)
            eye_x = int(p.x + p.width/2 + 10 * p.facing)
            pygame.draw.circle(screen, (255, 0, 0), (eye_x, eye_y), 5)
            pygame.draw.circle(screen, (255, 255, 100), (eye_x, eye_y), 2)
            
            # [Translated/Cleaned Comment]
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.015)) * 50
            aura_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            aura_color = (200 + int(pulse), 20, 20, 60 + int(pulse))
            pygame.draw.ellipse(aura_surf, aura_color, (0, 0, 100, 100))
            screen.blit(aura_surf, (int(p.x - 30), int(p.y - 30)))
        
        if amps > 0:
            # [Translated/Cleaned Comment]
            icon_w = 4
            icon_h = 10
            spacing = 2
            max_per_row = 10
            for i in range(amps):
                row = i // max_per_row
                col = i % max_per_row
                num_in_this_row = min(amps - row * max_per_row, max_per_row)
                total_w = num_in_this_row * icon_w + (num_in_this_row - 1) * spacing
                start_x = int(p.x + p.width/2 - total_w/2)
                start_y = int(p.y - 15 - row * (icon_h + 3))
                
                ix = start_x + col * (icon_w + spacing)
                # Green ampule
                pygame.draw.rect(screen, (50, 220, 50), (ix, start_y, icon_w, icon_h))
                # Ampule cap (white)
                pygame.draw.rect(screen, (255, 255, 255), (ix, start_y, icon_w, 2))

class AlHumaSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (150, 255, 255), (100, 200, 255))
        self.blocks = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            for _ in range(12):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(30, 60)
                bx = player.x + 20 + math.cos(angle) * dist
                by = player.y + 20 + math.sin(angle) * dist
                self.blocks.append([bx, by, 0, 0, 0, 60, None])
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        new_blocks = []
        for b in self.blocks:
            if b[4] == 0:
                b[5] -= 1
                b[1] += math.sin(pygame.time.get_ticks() * 0.005 + b[0]) * 0.5
                if b[5] <= 0:
                    b[4] = 1 # homing
                    alive = [e for e in enemies if e.hp > 0] if enemies else []
                    if alive: b[6] = random.choice(alive)
                    else:
                        b[2] = random.choice([-15, 15])
                        b[3] = random.uniform(-5, 5)
            elif b[4] == 1:
                # homing
                if b[6] and b[6].hp > 0:
                    dx = b[6].x + b[6].width/2 - b[0]
                    dy = b[6].y + b[6].height/2 - b[1]
                    d = max(1, math.hypot(dx, dy))
                    b[2] = (dx / d) * 25
                    b[3] = (dy / d) * 25
                b[0] += b[2]
                b[1] += b[3]
                
            hit = False
            if enemies and b[4] == 1:
                for e in enemies:
                    if e.hp > 0 and e.x < b[0] < e.x + e.width and e.y < b[1] < e.y + e.height:
                        e.take_damage(2 + self.damage_bonus, 1 if b[2] > 0 else -1, element='ice', ignore_iframes=True)
                        hit = True
                        break
            if not hit and -100 < b[0] < width + 100 and -100 < b[1] < height + 100:
                new_blocks.append(b)
        self.blocks = new_blocks
    def draw_effect(self, screen):
        for b in self.blocks:
            pygame.draw.rect(screen, (150, 255, 255), (int(b[0])-6, int(b[1])-6, 12, 12))

class IceBrandArtsSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 1200, (100, 200, 255), (0, 150, 255))
        self.active_timer = 0
        self.initial_duration = 600
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 600
            self.player_ref = player
            player._ice_brand_timer = 600
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if self.player_ref:
                self.player_ref._ice_brand_timer = self.active_timer
    def draw_effect(self, screen):
        if self.active_timer > 0 and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (100, 200, 255), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 35, 2)

class BlizzardLanceSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 480, (200, 255, 255), (100, 255, 255))
        self.lance = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.lance = [player.x + 20, player.y + 10, 30 * player.facing, 0, []]
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.lance:
            l = self.lance
            l[0] += l[2]
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e not in l[4] and e.x < l[0] + 60 and l[0] - 60 < e.x + e.width and e.y < l[1] + 15 and l[1] - 15 < e.y + e.height:
                        e.take_damage(10 + self.damage_bonus, 1 if l[2] > 0 else -1, knockback_x=5, element='ice', ignore_iframes=True)
                        l[4].append(e)
            if not (-200 < l[0] < width + 200):
                self.lance = None
    def draw_effect(self, screen):
        if self.lance:
            l = self.lance
            points = []
            direction = 1 if l[2] > 0 else -1
            points.append((l[0] + 80 * direction, l[1]))
            points.append((l[0] - 40 * direction, l[1] - 15))
            points.append((l[0] - 40 * direction, l[1] + 15))
            pygame.draw.polygon(screen, (150, 255, 255), points)

class IceShieldSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 600, (50, 150, 255), (0, 100, 255))
        self.active_timer = 0
        self.initial_duration = 300
        self.shield_rect = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 300
            self.player_ref = player
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if self.player_ref:
                sp_x = self.player_ref.x + 50 * self.player_ref.facing
                if self.player_ref.facing < 0:
                    sp_x -= 20
                self.shield_rect = pygame.Rect(sp_x, self.player_ref.y - 10, 20, 60)
                if enemies:
                    for e in enemies:
                        if e.hp > 0 and self.shield_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.frozen_timer = max(e.frozen_timer if hasattr(e, 'frozen_timer') else 0, 60)
        else:
            self.shield_rect = None
    def draw_effect(self, screen):
        if self.shield_rect:
            pygame.draw.rect(screen, (150, 255, 255), self.shield_rect)

class CocytusSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 1200, (200, 255, 255), (255, 255, 255))
        self.active_timer = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 30
            if enemies:
                for e in enemies:
                    if e.hp > 0:
                        e.frozen_timer = 10
                        e.take_damage(5 + self.damage_bonus, 0, element='ice')
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
    def draw_effect(self, screen):
        if self.active_timer > 0:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((200, 255, 255, 100))
            screen.blit(overlay, (0, 0))

class IceMage(Character):
    """Ice Mage: Uses various ice-based skills and freezing effects."""
    def __init__(self, player):
        super().__init__(player)
        self.skill_alhuma = AlHumaSkill(15, 15)
        self.skill_icebrand = IceBrandArtsSkill(75, 15)
        self.skill_lance = BlizzardLanceSkill(135, 15)
        self.skill_shield = IceShieldSkill(195, 15)
        self.skill_cocytus = CocytusSkill(255, 15)
        self.skills = [self.skill_alhuma, self.skill_icebrand, self.skill_lance, self.skill_shield, self.skill_cocytus]
        
        self.ice_blocks = []
        self.player._ice_brand_timer = 0
        
    def get_max_hp(self): return 8
    def get_speed(self): return 1.2
    def get_jump_power(self): return -14

    def attack(self, enemies):
        if getattr(self.player, '_ice_brand_timer', 0) > 0:
            self.player.swording = 15
            self.player.hit_timer = max(self.player.hit_timer, 20)
            hx = self.player.x + (60 * self.player.facing)
            hy = self.player.y + 20
            if enemies:
                sword_rect = pygame.Rect(hx - 40, hy - 40, 80, 80)
                for e in enemies:
                    if e.hp > 0:
                        if sword_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(int(2 + self.player.damage_multiplier), self.player.facing, element='ice')
                            e.frozen_timer = max(e.frozen_timer if hasattr(e, 'frozen_timer') else 0, 30)
        else:
            vx = 20 * self.player.facing
            self.ice_blocks.append([self.player.x + 20, self.player.y + 20, vx, 40, self.player.facing])

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_alhuma.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_icebrand.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_lance.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_shield.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_cocytus.activate(self.player, enemies)

    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        new_blocks = []
        for b in self.ice_blocks:
            b[0] += b[2]
            b[3] -= 1
            hit = False
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < b[0] < e.x + e.width and e.y < b[1] < e.y + e.height:
                        if e.take_damage(1, b[4], element='ice', ignore_iframes=True):
                            hit = True
                            break
            if hit or b[3] <= 0:
                pass
            else:
                new_blocks.append(b)
        self.ice_blocks = new_blocks
        
        if getattr(self.player, '_ice_brand_timer', 0) > 0:
            self.player.move_speed = 1.6
        else:
            self.player.move_speed = 1.2

    def draw_effects(self, screen):
        super().draw_effects(screen)
        for b in self.ice_blocks:
            pygame.draw.rect(screen, (200, 255, 255), (int(b[0]), int(b[1]), 15, 15))
        
        if getattr(self.player, '_ice_brand_timer', 0) > 0 and self.player.swording > 0:
            p = self.player
            cx = int(p.x + 20)
            cy = int(p.y + 20)
            # Two swords swinging in crossing arcs based on swing progress
            max_swing = 15  # matches swording duration
            progress = (max_swing - p.swording) / max_swing
            base_angle = 0 if p.facing == 1 else 180
            sword_len = 55
            # Sword 1: swings from upper-back to lower-front
            angle1 = base_angle + (-80 + 160 * progress) * p.facing
            rad1 = math.radians(angle1)
            ex1 = cx + sword_len * math.cos(rad1)
            ey1 = cy + sword_len * math.sin(rad1)
            # Sword 2: swings from lower-back to upper-front (delayed)
            angle2 = base_angle + (80 - 160 * min(1.0, progress * 1.3)) * p.facing
            rad2 = math.radians(angle2)
            ex2 = cx + sword_len * math.cos(rad2)
            ey2 = cy + sword_len * math.sin(rad2)
            # Afterimage trails
            for i in range(3):
                trail_p = max(0, progress - i * 0.06)
                ta1 = base_angle + (-80 + 160 * trail_p) * p.facing
                tr1 = math.radians(ta1)
                tx1 = cx + sword_len * math.cos(tr1)
                ty1 = cy + sword_len * math.sin(tr1)
                pygame.draw.line(screen, (100, 200, 255), (cx, cy), (int(tx1), int(ty1)), 2)
                trail_p2 = max(0, min(1.0, progress * 1.3) - i * 0.06)
                ta2 = base_angle + (80 - 160 * trail_p2) * p.facing
                tr2 = math.radians(ta2)
                tx2 = cx + sword_len * math.cos(tr2)
                ty2 = cy + sword_len * math.sin(tr2)
                pygame.draw.line(screen, (100, 200, 255), (cx, cy), (int(tx2), int(ty2)), 2)
            # Main swords
            pygame.draw.line(screen, (150, 255, 255), (cx, cy), (int(ex1), int(ey1)), 5)
            pygame.draw.line(screen, (200, 255, 255), (cx, cy), (int(ex2), int(ey2)), 5)
            # Sword tips glow
            pygame.draw.circle(screen, (220, 255, 255), (int(ex1), int(ey1)), 4)
            pygame.draw.circle(screen, (220, 255, 255), (int(ex2), int(ey2)), 4)

# --- Player Class Definition ---
class Player:
    """
    Manages player physics, rendering, and character class instance.
    """

    def __init__(self):
        self.x, self.y = 400, 350
        self.width, self.height = 40, 40
        self.vx, self.vy = 0, 0
        self.ax, self.ay = 0, 0.8
        self.friction = 0.9
        self.move_speed = 1.2
        self.jump_power = -15
        self.jump_count_max = 2
        self.jumpcount = 2
        self.facing = 1
        self.swording = 0             # Melee attack (sword) duration timer
        self.sword_length = 120
        self.hp = 10
        self.max_hp = 10
        self.defense = 0
        self.bonus_damage = 0         # Additional damage from upgrades
        self.cooldown_speed_mult = 1.0 # Cooldown reduction multiplier
        self.hit_timer = 0            # Hit knockback/flashing timer
        self.prev_touch_up = False    # Jump input tracking for smartphone mode
        self.attack_cooldown = 0      # Minimum cooldown between attacks (smartphone anti-spam)



        self.character = None         # Active character class instance
        self.invincible_timer = 0     # Invincibility timer
        self.reincarnator_mode = False # Stores Reincarnator mode setting

        self.skill_m = MirrorSkill(15, 15)
        self.skill_g = GravitySkill(75, 15)
        self.skill_i = IceSkill(135, 15)
        self.skill_d = DashSkill(195, 15)
        self.skill_l = LavaSkill(255, 15)
        self.skill_f = FireSkill(315, 15)
        self.skill_t = ThunderSkill(375, 15)
        self.skills = [self.skill_m, self.skill_g, self.skill_i, self.skill_d, self.skill_l, self.skill_f, self.skill_t]

    def handle_event(self, event, enemies):
        if self.character:
            self.character.handle_event(event, enemies)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack']:
                self.swording = 12
            if (event.key == key_config['jump']) and (self.y >= ground or self.jumpcount > 0):
                self.vy = self.jump_power
                self.jumpcount -= 1
            if event.key == pygame.K_m: self.skill_m.activate(self)
            if event.key == pygame.K_g: self.skill_g.activate(self)
            if event.key == pygame.K_i: self.skill_i.activate(self, enemies)
            if event.key == pygame.K_d: self.skill_d.activate(self)
            if event.key == pygame.K_l: self.skill_l.activate(self, enemies)
            if event.key == pygame.K_f: self.skill_f.activate(self)
            if event.key == pygame.K_t: self.skill_t.activate(self, enemies)

    def set_character(self, character_class):
        self.character = character_class(self)
        self.hp = self.character.get_max_hp()
        self.max_hp = self.hp
        self.move_speed = self.character.get_speed()
        self.jump_power = self.character.get_jump_power()
        self.skills = self.character.skills

    def reset(self):
        self.x, self.y = 400, 350
        self.vx, self.vy = 0, 0
        self.hp = 10
        self.max_hp = 10
        self.defense = 0
        self.bonus_damage = 0
        self.cooldown_speed_mult = 1.0
        self.jump_count_max = 2
        self.character = None
        self.reincarnator_mode = False
        self.skills = [self.skill_m, self.skill_g, self.skill_i, self.skill_d, self.skill_l, self.skill_f, self.skill_t]

    def update(self, keys, enemies):
        global hit_stop_timer, game_state
        if self.hit_timer > 0: self.hit_timer -= 1

        self.ax = 0
        if keys[key_config['move_left']] or (smartphone_mode and touch_keys['left']):
            self.ax = -self.move_speed
            self.facing = -1
        if keys[key_config['move_right']] or (smartphone_mode and touch_keys['right']):
            self.ax = self.move_speed
            self.facing = 1

        self.vx += self.ax
        self.vx *= self.friction
        
        # Gravity skill check

        gravity_active = False
        if self.character:
            for s in self.character.skills:
                if type(s).__name__ == "GravitySkill" and getattr(s, 'range', 0) > 0:
                    gravity_active = True
                    break
        elif self.skill_g.range > 0:
            gravity_active = True

        current_ay = 0.3 if gravity_active else 0.8
        
        # Jump input detection (keys or smartphone button)

        jump_input = keys[key_config['jump']] or (smartphone_mode and touch_keys['up'])
        
        # Discrete jump detection for smartphone

        touch_jump_triggered = False
        if smartphone_mode:
            if touch_keys['up'] and not self.prev_touch_up:
                touch_jump_triggered = True
            self.prev_touch_up = touch_keys['up']

        # Jump behavior

        if touch_jump_triggered and (self.y >= ground - 45 or self.jumpcount > 0):
            self.vy = self.jump_power
            self.jumpcount -= 1

        
        self.vy += current_ay

        self.x += self.vx
        self.y += self.vy

        # Skill updates

        cooldown_speed = 1.0 * self.cooldown_speed_mult
        if self.character:
            self.character.update(keys, enemies, cooldown_speed)
        
        if game_state == STATE_LOBBY:
            for s in self.skills: s.update(enemies)

        # Dash skill check

        dash_active = False
        if self.character:
            for s in self.character.skills:
                if type(s).__name__ == "DashSkill" and getattr(s, 'range', 0) > 0:
                    dash_active = True
                    break
        elif game_state == STATE_LOBBY and self.skill_d.range > 0:
            dash_active = True

        if dash_active:
            self.vx = self.facing * 50

        if self.y > ground - 40:
            self.y = ground - 40
            self.vy = 0
            self.jumpcount = self.jump_count_max

        # One-way platform detection (passable from below)
        if self.vy > 0:  # Only while falling

            foot_y = self.y + self.height
            prev_foot_y = foot_y - self.vy
            if prev_foot_y <= PLATFORM_Y and foot_y >= PLATFORM_Y:
                if PLATFORM_X <= self.x + self.width and self.x <= PLATFORM_X + PLATFORM_W:
                    self.y = PLATFORM_Y - self.height
                    self.vy = 0
                    self.jumpcount = self.jump_count_max

        if self.x <= 10 or self.x >= width - 40:
            self.vx = -self.vx
            if self.x <= 10: self.x = 10
            if self.x >= width - 40: self.x = width - 40

        # Smartphone attack detection (with 3-frame minimum cooldown)

        if smartphone_mode and touch_keys['attack'] and self.swording <= 0 and self.attack_cooldown <= 0:
            self.attack_cooldown = 3  # Minimum 3-frame interval between attacks
            if self.character:
                self.character.attack(enemies)
            else:
                self.swording = 12


        if self.swording > 0:
            is_critical = abs(self.vx) > 10
            damage = (2 if is_critical else 1) + self.bonus_damage
            p_center_x = self.x + 20 * self.facing + 20
            p_center_y = self.y + 20
            swing_progress = (12 - self.swording) / 12.0
            base_angle = 0 if self.facing == 1 else 180
            current_center_angle = base_angle + (-75 + 90 * swing_progress) * self.facing
            rad = math.radians(current_center_angle)
            end_x = p_center_x + self.sword_length * math.cos(rad)
            end_y = p_center_y + self.sword_length * math.sin(rad)
            
            for i in range(1, 6):
                ratio = i / 5.0
                sx = p_center_x + (end_x - p_center_x) * ratio
                sy = p_center_y + (end_y - p_center_y) * ratio
                hit_any = False
                for e in enemies:
                    if e.hp > 0 and e.x <= sx <= e.x+e.width and e.y <= sy <= e.y+e.height:
                        if e.take_damage(damage, self.facing):
                            hit_any = True
                            hit_stop_timer = 8 if is_critical else 4
                            if self.character: self.character.on_sword_hit(e, self.facing)
                            break
                if hit_any: break
        
        if self.hp <= 0:
            game_state = STATE_GAMEOVER

    def draw(self, screen):
        color = (30, 100, 30)
        if self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0:
            color = (255, 255, 255)
        pygame.draw.rect(screen, color, (int(self.x), int(self.y), 40, 40))
        
        if self.character:
            self.character.draw_effects(screen)
            self.character.draw_ui(screen)
        
        if game_state == STATE_LOBBY:
            for s in self.skills:
                s.draw_effect(screen)
                s.draw(screen)
        
        if self.swording > 0:
            p_center_x = self.x + 20 * self.facing + 20
            p_center_y = self.y + 20
            swing_progress = (12 - self.swording) / 12.0
            base_angle = 0 if self.facing == 1 else 180
            current_center_angle = base_angle + (-75 + 90 * swing_progress) * self.facing
            rad = math.radians(current_center_angle)
            end_x = p_center_x + self.sword_length * math.cos(rad)
            end_y = p_center_y + self.sword_length * math.sin(rad)
            pygame.draw.line(screen, (255, 255, 255), (p_center_x, p_center_y), (end_x, end_y), 10)

    def update_timers(self):
        if self.swording > 0: self.swording -= 1
        if self.hit_timer > 0: self.hit_timer -= 1
        if self.invincible_timer > 0: self.invincible_timer -= 1
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if self.character: self.character.update_timers()

    def take_damage(self, amount, source_facing=1):
        if self.invincible_timer > 0: return False
        if self.hit_timer == 0:
            amount = max(0, amount - self.defense) # Reduce by defense (0 damage allowed)
            if amount <= 0:
                self.hit_timer = 10 # Short invincibility prevents multiple hits
                return False # 0 damage so no damage
            self.hp -= amount
            self.hit_timer = 40
            self.vx = source_facing * 10 # Knockback
            return True
        return False

class EnemyBullet:
    def __init__(self, x, y, angle, damage=1):
        self.x = x
        self.y = y
        self.speed = 7
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed
        self.width = 15
        self.height = 15
        self.timer = 180 # Expires in 3 seconds
        self.damage = damage

    def update(self, player):
        self.x += self.vx
        self.y += self.vy
        self.timer -= 1
        
        # Collision detection

        if player.x <= self.x <= player.x + 40 and player.y <= self.y <= player.y + 40:
            if player.take_damage(self.damage, 1 if self.vx > 0 else -1):
                return True # Hit

        return False

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 100, 255), (int(self.x), int(self.y), self.width, self.height))

class Enemy:
    def __init__(self, x, y, hp=3, color=(255, 0, 0), enemy_type='ground', attack_damage=1):
        self.x, self.y = x, y
        self.width, self.height = 40, 40
        self.hp, self.max_hp = hp, hp
        self.attack_damage = attack_damage
        self.speed = random.uniform(2, 4)
        self.color = color
        self.hit_timer = 0
        self.vy, self.vx = 0, 0
        self.enemy_type = enemy_type
        self.facing = -1
        self.attack_cooldown = random.randint(60, 180)
        self.frozen_timer = 0
        self.burn_timer = 0
        self.spawn_timer = 0
        self.debris_particles = []

    def update(self, player):
        if self.spawn_timer > 0:
            self.spawn_timer -= 1
            if self.spawn_timer == 0 and self.enemy_type != 'pink':
                self.y = ground - self.height # Align to ground
            return
            
        if self.hit_timer > 0: self.hit_timer -= 1
        
        # Status effect updates

        if self.frozen_timer > 0:
            self.frozen_timer -= 1
            # Skip physics and behavior while frozen

            if self.y < ground - self.height: self.vy += 1
            self.y += self.vy
            self.x += self.vx
            self.vx *= 0.9
            if self.y > ground - self.height: self.y = ground - self.height; self.vy = 0
            # Prevent screen escape

            if self.x < 0:
                self.x = 0
                self.vx *= -0.5
            elif self.x > width - self.width:
                self.x = width - self.width
                self.vx *= -0.5
            return

        if self.burn_timer > 0:
            self.burn_timer -= 1
            if self.burn_timer % 60 == 0: # Damage every second

                self.take_damage(1, status_effect=True)

        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        # Do not move or deal damage during READY state

        if wave_start_wait_timer > 0:
            return

        self._update_physics()
        if self.hp > 0: self._update_behavior(player)
        
        # Prevent screen escape (common)

        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5
        
        if self.y < 0:
            self.y = 0
        elif self.y > ground - self.height:
            self.y = ground - self.height
            self.vy = 0

    def _update_physics(self):
        if self.y < ground - self.height: 
            self.vy += 1
        elif self.vy > 0: # Align to ground when falling

            self.vy = 0
            self.y = ground - self.height
        
        self.y += self.vy
        self.x += self.vx
        self.vx *= 0.9
        
        # One-way platform detection (ground enemies only)

        if self.enemy_type != 'pink' and self.vy > 0:
            foot_y = self.y + self.height
            prev_foot_y = foot_y - self.vy
            if prev_foot_y <= PLATFORM_Y and foot_y >= PLATFORM_Y:
                if PLATFORM_X <= self.x + self.width and self.x <= PLATFORM_X + PLATFORM_W:
                    self.y = PLATFORM_Y - self.height
                    self.vy = 0

    def _update_behavior(self, player):
        pass

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None, ignore_iframes=False):
        if self.hp <= 0: return False
        if self.spawn_timer > 0: return False  # Invulnerable during spawn animation
        
        # Elemental synergy

        if self.frozen_timer > 0:
            if element == 'fire':
                self.frozen_timer = 0
                damage += 5 # Melt bonus
            elif element == 'heavy':
                self.frozen_timer = 0
                damage += 8 # Shatter bonus
                knockback_x *= 2
                knockback_y -= 5
                
        if status_effect:
            self.hp -= damage
            if self.hp <= 0: self._spawn_debris()
            return True
            
        if self.hit_timer > 0 and not ignore_iframes: return False
        
        if self.frozen_timer > 0:
            # Skip knockback while frozen

            knockback_x = 0
            knockback_y = 0
            
        self.hp -= damage
        self.hit_timer = 15
        self.vx = source_facing * knockback_x
        self.vy = knockback_y
        
        if self.hp <= 0:
            self._spawn_debris()
            
        return True

    def _spawn_debris(self):
        for _ in range(12):
            self.debris_particles.append({
                'x': self.x + random.randint(0, self.width),
                'y': self.y + random.randint(0, self.height),
                'vx': random.uniform(-8, 8),
                'vy': random.uniform(-15, -5),
                'timer': random.randint(60, 120),
                'color': self.color
            })

    def update_debris(self): 
        new_debris = []
        for p in self.debris_particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.8 # gravity
            if p['y'] > ground:
                p['y'] = ground
                p['vy'] *= -0.5
                p['vx'] *= 0.8
            p['timer'] -= 1
            if p['timer'] > 0:
                new_debris.append(p)
        self.debris_particles = new_debris

    def draw(self, screen):
        if self.hp <= 0:
            for p in self.debris_particles:
                alpha = min(255, p['timer'] * 4) # Fade out
                surf = pygame.Surface((8, 8), pygame.SRCALPHA)
                surf.fill((*p['color'], alpha))
                screen.blit(surf, (int(p['x']), int(p['y'])))
            return
            
        if self.spawn_timer > 0:
            # Summoning effect

            radius = int((60 - self.spawn_timer % 60) * 0.5)
            pygame.draw.ellipse(screen, (255, 255, 100), (self.x - 20, ground - 10, self.width + 40, 20), 2)
            if radius >= 1:
                pygame.draw.circle(screen, (255, 255, 200), (int(self.x + self.width//2), ground), radius, 1)
            pygame.draw.line(screen, (255, 255, 100), (self.x + self.width//2, ground), (self.x + self.width//2, self.y - 100 + self.spawn_timer), 2)
            return
        draw_color = self.color
        if self.hit_timer > 0:
            draw_color = (255, 255, 255)
        elif self.frozen_timer > 0:
            draw_color = (150, 200, 255) # Pale blue while frozen

        elif self.burn_timer > 0:
            if (self.burn_timer // 10) % 2 == 0:
                draw_color = (255, 100, 0)
        
        pygame.draw.rect(screen, draw_color, (int(self.x), int(self.y), self.width, self.height))
        
        # Flame effect

        if self.burn_timer > 0:
            for _ in range(3):
                fx = self.x + random.randint(0, self.width)
                fy = self.y + self.height - random.randint(0, self.height)
                radius = random.randint(3, 8)
                color = (255, random.randint(50, 150), 0)
                pygame.draw.circle(screen, color, (int(fx), int(fy)), radius)

class RedEnemy(Enemy):
    def __init__(self, x, y, hp=3, attack_damage=1):
        super().__init__(x, y, hp, (255, 0, 0), 'red', attack_damage)

    def _update_physics(self):
        # Align to ground
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.92 # User-adjusted

        
        # Prevent screen escaping
        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5

    def _update_behavior(self, player):
        # Left/right patrol (flip at screen edge)
        if self.x <= 0:
            self.facing = 1
        elif self.x >= width - self.width:
            self.facing = -1

        
        # Check distance to player
        dist = math.hypot(player.x - self.x, player.y - self.y)

        
        # Dash on approach (only when cooldown is off)
        if dist < 300 and self.attack_cooldown <= 0:
            dash_dir = 1 if player.x > self.x else -1
            self.vx = dash_dir * 35 # 28 -> 35
            self.attack_cooldown = random.randint(120, 240)
            self.facing = dash_dir # Face the dash direction

        
        # Normal movement (if vx is small, otherwise let dash handle it)
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing

        
        # Contact damage
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)


class PinkEnemy(Enemy):
    def __init__(self, x, y, hp=2, attack_damage=1):
        super().__init__(x, y, hp, (255, 100, 200), 'pink', attack_damage)
        self.float_y = y

    def _update_physics(self):
        self.x += self.vx
        self.vx *= 0.92 # User-adjusted

        
        # Prevent screen escaping
        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5

        
        if self.y < 0:
            self.y = 0
        elif self.y > ground - self.height:
            self.y = ground - self.height

    def _update_behavior(self, player):
        # Left/right patrol (flip at screen edge)
        if self.x <= 0:
            self.facing = 1
        elif self.x >= width - self.width:
            self.facing = -1


        # Check distance to player
        dist = math.hypot(player.x - self.x, player.y - self.y)


        if self.attack_cooldown <= 0:
            if dist < 400 and random.random() < 0.3: # Low-chance dash when close
                dash_dir = 1 if player.x > self.x else -1
                self.vx = dash_dir * 30 # 22 -> 30
                self.facing = dash_dir
            else: # Otherwise, shoot from distance in the air
                angle = math.atan2(player.y - self.y, player.x - self.x)
                enemy_bullets.append(EnemyBullet(self.x + 12, self.y + 12, angle, self.attack_damage))
            self.attack_cooldown = random.randint(90, 160) # Shorten interval further

        
        # Normal movement at constant speed
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing

        
        # Contact damage
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

class GreenEnemy(Enemy):
    def __init__(self, x, y, hp=4, attack_damage=1):
        super().__init__(x, y, hp, (0, 200, 0), 'green', attack_damage)
        self.jump_power = -18
        self.is_jumping = False

    def _update_physics(self):
        # Apply gravity
        if self.y < ground - self.height:
            self.vy += 0.8
            self.is_jumping = True

        elif self.vy > 0: # Only while falling
            self.vy = 0
            self.y = ground - self.height
            if self.is_jumping:
                self.vx = 0 # Stop horizontal movement on landing
                self.is_jumping = False

        
        self.y += self.vy
        self.x += self.vx
        
        # Prevent screen escaping
        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5


    def _update_behavior(self, player):
        # Jump toward player if on ground and ready to attack
        if not self.is_jumping and self.attack_cooldown <= 0:
            dx = player.x - self.x
            self.vy = self.jump_power
            # Adjust horizontal speed based on distance (aim slightly short)
            self.vx = dx * 0.05
            self.attack_cooldown = random.randint(120, 180)
            self.is_jumping = True

        
        # Normal patrol (only when not jumping)

        if not self.is_jumping:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            self.x += self.speed * 0.5 * self.facing

        # Contact damage

        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

class ShieldEnemy(Enemy):
    """Shield Bearer: Reduces front-facing damage by 50%"""

    def __init__(self, x, y, hp=5, attack_damage=1):
        super().__init__(x, y, hp, (150, 50, 150), 'shield', attack_damage)
        self.speed = random.uniform(1.5, 2.5)

    def _update_physics(self):
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.92
        if self.x < 0: self.x = 0; self.vx *= -0.5
        elif self.x > width - self.width: self.x = width - self.width; self.vx *= -0.5

    def _update_behavior(self, player):
        # Always face the player

        self.facing = 1 if player.x > self.x else -1
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing
        # Contact damage

        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None, ignore_iframes=False):
        # Halve damage if attacking from the front (facing direction)
        if not status_effect and source_facing == self.facing:

            damage = max(1, damage // 2)
            knockback_x = max(1, knockback_x // 2)
        return super().take_damage(damage, source_facing, knockback_x, knockback_y, status_effect, element, ignore_iframes)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # Render shield

        shield_x = self.x + (self.width if self.facing == 1 else -10)
        shield_color = (200, 100, 200) if self.frozen_timer <= 0 else (150, 200, 255)
        pygame.draw.rect(screen, shield_color, (int(shield_x), int(self.y + 5), 10, 30))

class HealerEnemy(Enemy):
    """Healer: Periodically heals surrounding enemies"""

    def __init__(self, x, y, hp=4, attack_damage=1):
        super().__init__(x, y, hp, (50, 200, 50), 'healer', attack_damage)
        self.heal_cooldown = 0
        self.heal_range = 200
        self.heal_effect_timer = 0
        self.speed = random.uniform(1, 2)

    def _update_physics(self):
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.92
        if self.x < 0: self.x = 0; self.vx *= -0.5
        elif self.x > width - self.width: self.x = width - self.width; self.vx *= -0.5

    def _update_behavior(self, player):
        if self.heal_effect_timer > 0: self.heal_effect_timer -= 1
        dist = math.hypot(player.x - self.x, player.y - self.y)
        # Keep distance from player

        if dist < 200:
            flee_dir = -1 if player.x > self.x else 1
            if abs(self.vx) < 3: self.x += self.speed * 2 * flee_dir
            self.facing = flee_dir
        else:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            if abs(self.vx) < 3: self.x += self.speed * self.facing
        # Healing action

        if self.heal_cooldown <= 0:
            healed = False
            for e in enemies:
                if e is not self and e.hp > 0 and e.hp < e.max_hp:
                    if math.hypot(e.x - self.x, e.y - self.y) < self.heal_range:
                        e.hp = min(e.max_hp, e.hp + 1)
                        healed = True
            if healed:
                self.heal_cooldown = 180
                self.heal_effect_timer = 30
        else:
            self.heal_cooldown -= 1
        # Contact damage

        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # Render cross mark

        cx, cy = int(self.x + self.width // 2), int(self.y + self.height // 2)
        pygame.draw.line(screen, (255, 255, 255), (cx - 8, cy), (cx + 8, cy), 3)
        pygame.draw.line(screen, (255, 255, 255), (cx, cy - 8), (cx, cy + 8), 3)
        # Healing effect

        if self.heal_effect_timer > 0:
            radius = int((30 - self.heal_effect_timer) * 7)
            if radius > 0:
                surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
                alpha = int(self.heal_effect_timer / 30 * 150)
                pygame.draw.circle(surf, (100, 255, 100, alpha), (radius + 1, radius + 1), radius, 3)
                screen.blit(surf, (cx - radius - 1, cy - radius - 1))

class BomberEnemy(Enemy):
    """Bomber: Explodes and deals area damage when defeated"""
    def __init__(self, x, y, hp=2, attack_damage=1):
        super().__init__(x, y, hp, (255, 150, 0), 'bomber', attack_damage)
        self.speed = random.uniform(4, 6)
        self.exploded = False
        self.explosion_timer = 0
        self.explosion_radius = 100
        self.explosion_damage = 3

    def _update_physics(self):
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.95
        if self.x < 0: self.x = 0; self.vx *= -0.5
        elif self.x > width - self.width: self.x = width - self.width; self.vx *= -0.5

    def _update_behavior(self, player):
        # Dash toward player at high speed

        self.facing = 1 if player.x > self.x else -1
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing
        # Contact damage

        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def _spawn_debris(self):
        super()._spawn_debris()
        self.exploded = True
        self.explosion_timer = 20

    def explode(self, target_player):
        """Explosion process: Damage player and nearby enemies"""

        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        # Damage to player

        pdist = math.hypot(target_player.x + 20 - cx, target_player.y + 20 - cy)
        if pdist < self.explosion_radius:
            sf = 1 if target_player.x > cx else -1
            target_player.take_damage(self.explosion_damage, sf)
        # Damage to nearby enemies

        for e in enemies:
            if e is self or e.hp <= 0: continue
            edist = math.hypot(e.x + e.width // 2 - cx, e.y + e.height // 2 - cy)
            if edist < self.explosion_radius:
                sf = 1 if e.x > cx else -1
                e.take_damage(self.explosion_damage, sf, status_effect=True, element='fire')
        # Massive amount of debris

        for _ in range(20):
            self.debris_particles.append({
                'x': cx + random.randint(-20, 20), 'y': cy + random.randint(-20, 20),
                'vx': random.uniform(-12, 12), 'vy': random.uniform(-20, -5),
                'timer': random.randint(60, 120), 'color': (255, random.randint(100, 200), 0)
            })

    def draw(self, screen):
        if self.explosion_timer > 0:
            # Explosion effect

            cx, cy = int(self.x + self.width // 2), int(self.y + self.height // 2)
            r = int((20 - self.explosion_timer) / 20 * self.explosion_radius)
            alpha = int(self.explosion_timer / 20 * 200)
            surf = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 200, 0, alpha), (r + 5, r + 5), max(1, r))
            pygame.draw.circle(surf, (255, 100, 0, min(255, alpha + 50)), (r + 5, r + 5), max(1, r // 2))
            screen.blit(surf, (cx - r - 5, cy - r - 5))
            for p in self.debris_particles:
                a = min(255, p['timer'] * 4)
                s = pygame.Surface((8, 8), pygame.SRCALPHA)
                s.fill((*p['color'], a))
                screen.blit(s, (int(p['x']), int(p['y'])))
            return
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # Blinking warning mark

        if (pygame.time.get_ticks() // 300) % 2 == 0:
            cx = int(self.x + self.width // 2)
            cy = int(self.y + 5)
            pygame.draw.polygon(screen, (255, 255, 0), [(cx, cy - 5), (cx - 4, cy + 5), (cx + 4, cy + 5)])

class SniperEnemy(Enemy):
    """Sniper: High-damage bullets with a warning line from long distance"""

    def __init__(self, x, y, hp=2, attack_damage=2):
        super().__init__(x, y, hp, (200, 200, 50), 'sniper', attack_damage)
        self.speed = random.uniform(1, 2)
        self.aim_timer = 0
        self.aim_angle = 0
        self.shoot_cooldown = 240

    def _update_physics(self):
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.92
        if self.x < 0: self.x = 0; self.vx *= -0.5
        elif self.x > width - self.width: self.x = width - self.width; self.vx *= -0.5

    def _update_behavior(self, player):
        dist = math.hypot(player.x - self.x, player.y - self.y)
        self.facing = 1 if player.x > self.x else -1
        # Keep distance from player
        if dist < 300:
            flee_dir = -1 if player.x > self.x else 1
            if abs(self.vx) < 3: self.x += self.speed * 2 * flee_dir
        elif abs(self.vx) < 3:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            self.x += self.speed * 0.5 * self.facing
        # Snipe: Warning -> Shoot stages

        if self.aim_timer > 0:
            self.aim_timer -= 1
            self.aim_angle = math.atan2(player.y + 20 - (self.y + 20), player.x + 20 - (self.x + 20))
            if self.aim_timer == 0:
                enemy_bullets.append(EnemyBullet(self.x + 20, self.y + 20, self.aim_angle, self.attack_damage))
                self.shoot_cooldown = 240
        elif self.shoot_cooldown <= 0:
            self.aim_timer = 60
        else:
            self.shoot_cooldown -= 1
        # Contact damage

        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # Warning line (laser sight)
        if self.aim_timer > 0:

            sx, sy = int(self.x + 20), int(self.y + 20)
            ex = sx + int(math.cos(self.aim_angle) * 600)
            ey = sy + int(math.sin(self.aim_angle) * 600)
            blink = self.aim_timer % 6 < 3
            color = (255, 0, 0) if blink else (200, 50, 50)
            pygame.draw.line(screen, color, (sx, sy), (ex, ey), 2)
        # Aim mark

        cx = int(self.x + self.width // 2)
        cy = int(self.y + self.height // 2)
        pygame.draw.circle(screen, (255, 255, 100), (cx, cy), 4)

class BlockGolemBoss(Enemy):
    """
    Giant boss that appears every 5 waves.
    High HP, uses jump press, spread shots, and defense shield.
    """

    def __init__(self, x, y, hp=100, attack_damage=2):
        super().__init__(x, y, hp, (218, 165, 32), 'boss', attack_damage) # Goldenrod color
        self.width, self.height = 100, 100
        self.max_hp = hp
        self.speed = 1.5
        self.shield_timer = 0
        self.action_timer = 0
        self.current_action = None # 'jump', 'shoot', 'shield'
        self.shockwave_timer = 0

    def _update_physics(self):
        # Apply gravity
        if self.y < ground - self.height:

            self.vy += 0.8
        elif self.vy > 0:
            self.vy = 0
            self.y = ground - self.height
            # Shockwave detection on landing
            if self.current_action == 'jump':
                self.shockwave_timer = 30
                self.current_action = None

        self.y += self.vy
        self.x += self.vx
        self.vx *= 0.95

    def _update_behavior(self, player):
        if self.shield_timer > 0: self.shield_timer -= 1
        if self.shockwave_timer > 0:
            self.shockwave_timer -= 1
            # Shockwave damage (only if player on ground)
            if player.y + player.height >= ground - 5:
                dist = abs((self.x + self.width // 2) - (player.x + player.width // 2))
                if dist < 300:
                    sf = 1 if player.x > self.x else -1
                    player.take_damage(self.attack_damage, sf)

        if self.action_timer > 0:
            self.action_timer -= 1
            if self.current_action == 'shoot' and self.action_timer % 20 == 0:
                # Spread shot
                for angle in [-0.2, 0, 0.2]:
                    base_angle = math.atan2(player.y - self.y, player.x - self.x)
                    enemy_bullets.append(EnemyBullet(self.x + 50, self.y + 50, base_angle + angle, self.attack_damage))
            return

        # Choose next action
        r = random.random()
        if r < 0.3: # Jump

            self.current_action = 'jump'
            self.vy = -25
            self.vx = (1 if player.x > self.x else -1) * 10
            self.action_timer = 120
        elif r < 0.6: # Shoot

            self.current_action = 'shoot'
            self.action_timer = 60
        elif r < 0.8: # Shield

            self.current_action = 'shield'
            self.shield_timer = 120
            self.action_timer = 150
        else: # Move

            self.facing = 1 if player.x > self.x else -1
            self.vx = self.facing * 5
            self.action_timer = 60

        # Contact damage
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None, ignore_iframes=False):
        if self.shield_timer > 0:
            damage = max(1, damage // 5) # [Translated/Cleaned Comment]
        # Boss is resistant to knockback
        return super().take_damage(damage, source_facing, knockback_x * 0.2, knockback_y * 0.2, status_effect, element, ignore_iframes)

    def draw(self, screen):
        if self.hp <= 0:
            super().draw(screen)
            return
        
        # Boss body
        color = self.color
        if self.hit_timer > 0: color = (255, 255, 255)
        elif self.shield_timer > 0: color = (200, 200, 255) # Glows pale blue
        
        pygame.draw.rect(screen, color, (int(self.x), int(self.y), self.width, self.height))
        # Patterns
        pygame.draw.rect(screen, (0, 0, 0), (int(self.x), int(self.y), self.width, self.height), 2)
        pygame.draw.rect(screen, (0, 0, 0), (int(self.x + 20), int(self.y + 20), 60, 60), 1)
        
        # HP Bar
        bar_w = 400
        bar_h = 20
        pygame.draw.rect(screen, (50, 50, 50), (width // 2 - bar_w // 2, 20, bar_w, bar_h))
        hp_ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(screen, (255, 0, 0), (width // 2 - bar_w // 2, 20, int(bar_w * hp_ratio), bar_h))
        pygame.draw.rect(screen, (255, 255, 255), (width // 2 - bar_w // 2, 20, bar_w, bar_h), 2)
        
        # Shockwave effect
        if self.shockwave_timer > 0:
            r = int((30 - self.shockwave_timer) * 10)
            pygame.draw.ellipse(screen, (255, 255, 200), (self.x + 50 - r, ground - 20, r * 2, 40), 2)

player = Player()
enemies = []
enemy_bullets = []
hit_stop_timer = 0

def start_next_wave():
    global wave_number, enemies, enemy_bullets, wave_start_wait_timer
    wave_number += 1
    wave_start_wait_timer = 60
    enemies = []
    enemy_bullets = [] # Clear previous wave bullets
    
    # Boss spawn restricted to Reincarnator mode
    is_reincarnMode = getattr(player.character, 'is_reincarnator_mode', False)
    
    # Boss Wave Check
    if is_reincarnMode and wave_number > 0 and wave_number % 5 == 0:
        boss_hp = 60 + (wave_number // 5 - 1) * 40 # 100+80n -> 60+40n
        boss_atk = 2 + (wave_number // 5 - 1)
        enemies.append(BlockGolemBoss(width // 2 - 50, ground - 100, hp=boss_hp, attack_damage=boss_atk))
        return

    # Wave 1: 2 enemies. Increases by 1 every 2 waves, max 8
    num_enemies = min(2 + wave_number // 2, 8)
    
    # Non-Reincarnator modes scale half as fast
    
    # Enemy scaling: every 2 waves after W20, every wave after W40
    if wave_number < 20:
        hp_bonus = wave_number // 3
        atk_bonus = wave_number // 4
    elif wave_number < 40:
        hp_bonus = (20 // 3) + (wave_number - 20) // 2
        atk_bonus = (20 // 4) + (wave_number - 20) // 2
    else:
        hp_bonus = (20 // 3) + (20 // 2) + (wave_number - 40)
        atk_bonus = (20 // 4) + (20 // 2) + (wave_number - 40)
    
    if not is_reincarnMode:
        hp_bonus = hp_bonus // 2
        atk_bonus = atk_bonus // 2
    
    enemy_hp = 3 + hp_bonus
    enemy_atk = 1 + atk_bonus
    
    for i in range(num_enemies):
        rx = random.randint(100, width - 100)
        r = random.random()
        enemy = None
        
        # Add new species as waves progress
        if wave_number >= 7 and r < 0.10:
            enemy = SniperEnemy(rx, ground - 40, hp=max(2, enemy_hp - 1), attack_damage=enemy_atk)
        elif wave_number >= 5 and r < 0.25:
            enemy = BomberEnemy(rx, ground - 40, hp=max(2, enemy_hp - 1), attack_damage=enemy_atk)
        elif wave_number >= 4 and r < 0.35:
            enemy = HealerEnemy(rx, ground - 40, hp=max(3, enemy_hp), attack_damage=enemy_atk)
        elif wave_number >= 3 and r < 0.50:
            enemy = ShieldEnemy(rx, ground - 40, hp=enemy_hp + 2, attack_damage=enemy_atk)
        elif r < 0.50:
            enemy = RedEnemy(rx, ground - 40, hp=enemy_hp, attack_damage=enemy_atk)
        elif r < 0.75:
            ry = random.randint(100, 400)
            enemy = PinkEnemy(rx, ry, hp=max(2, enemy_hp - 1), attack_damage=enemy_atk)
        else:
            enemy = GreenEnemy(rx, ground - 40, hp=enemy_hp + 1, attack_damage=enemy_atk)
            
        enemy.spawn_timer = 30 + i * 75 # stagger spawns ( wider interval )
        enemies.append(enemy)


async def main():
    global game_state, settings_selecting, player, wave_number, enemies, enemy_bullets
    global is_combat_mode, wave_start_wait_timer, wave_clear_timer, hit_stop_timer
    global screen, smartphone_mode, V_PAD


    pygame.init()
    screen = pygame.display.set_mode((width, height))
    clock = pygame.time.Clock()

    # Pre-define fonts to avoid creating them every frame (major performance bottleneck)
    font_main = pygame.font.SysFont(None, 48)
    font_title = pygame.font.SysFont(None, 60)
    font_settings_hint = pygame.font.SysFont(None, 36)
    font_settings_title = pygame.font.SysFont(None, 50)
    font_settings_row = pygame.font.SysFont(None, 32)
    font_settings_footer = pygame.font.SysFont(None, 28)
    font_card_name = pygame.font.SysFont(None, 30)
    font_card_skill = pygame.font.SysFont(None, 18)
    font_weapon_name = pygame.font.SysFont(None, 40)
    font_weapon_desc = pygame.font.SysFont(None, 24)
    font_upgrade_name = pygame.font.SysFont(None, 34)
    font_upgrade_desc = pygame.font.SysFont(None, 24)
    font_gameover = pygame.font.SysFont(None, 100)

    running = True
    is_fullscreen = False

    while running:
        # Update virtual key states for smartphone ---
        if smartphone_mode:
            touch_keys['left'] = any(V_PAD['left'].collidepoint(pos) for pos in active_fingers.values())
            touch_keys['right'] = any(V_PAD['right'].collidepoint(pos) for pos in active_fingers.values())
            touch_keys['up'] = any(V_PAD['up'].collidepoint(pos) for pos in active_fingers.values())
            touch_keys['attack'] = any(V_PAD['attack'].collidepoint(pos) for pos in active_fingers.values())
            touch_keys['pause'] = any(V_PAD['pause'].collidepoint(pos) for pos in active_fingers.values())

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                is_fullscreen = not is_fullscreen
            
            # --- Smartphone touch processing ---
            if event.type == pygame.FINGERDOWN or event.type == pygame.FINGERMOTION:
                px, py = event.x * width, event.y * height
                active_fingers[event.finger_id] = (px, py)
                
                if event.type == pygame.FINGERDOWN and game_state == STATE_PLAYING:
                    if smartphone_mode and 'pause' in V_PAD and V_PAD['pause'].collidepoint(px, py):
                        game_state = STATE_PAUSED
                
                # Skill icon touch detection (FINGERDOWN only)
                if event.type == pygame.FINGERDOWN and player.character:
                    for s in player.character.skills:
                        # Detection area (60x60) wider than icon (40x40)
                        s_touch_rect = pygame.Rect(s.x - 10, s.y - 10, 60, 60)
                        if s_touch_rect.collidepoint(px, py):
                            s.activate(player, enemies if 'enemies' in locals() else [])
            
            if event.type == pygame.FINGERUP:
                if event.finger_id in active_fingers:
                    del active_fingers[event.finger_id]
            
            if game_state == STATE_LOBBY:
                player.handle_event(event, [])
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_state = STATE_SELECT_CHAR
                    elif event.key == pygame.K_s:
                        game_state = STATE_SETTINGS
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # "Character Select" area
                    if width // 2 - 300 <= mx <= width // 2 + 300 and 45 <= my <= 105:
                        game_state = STATE_SELECT_CHAR
                    # "Smartphone Mode" toggle button
                    if width // 2 - 150 <= mx <= width // 2 + 150 and 130 <= my <= 180:
                        smartphone_mode = (smartphone_mode + 1) % 3
                        V_PAD = V_PAD_1 if smartphone_mode == 1 else V_PAD_2

                
            elif game_state == STATE_SETTINGS:
                if event.type == pygame.KEYDOWN:
                    if settings_selecting is not None:
                        if event.key != pygame.K_ESCAPE:
                            key_config[settings_selecting] = event.key
                        settings_selecting = None
                    elif event.key == pygame.K_ESCAPE:
                        game_state = STATE_LOBBY
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    actions = list(key_config.keys())
                    for idx, action in enumerate(actions):
                        row_y = 130 + idx * 45
                        if 350 <= mx <= 850 and row_y <= my <= row_y + 38:
                            settings_selecting = action
                            break

            elif game_state == STATE_SELECT_CHAR:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    scale = 0.52
                    card_w_s_base, card_h_s_base = int(280 * scale), int(420 * scale)
                    spacing_x = 30
                    spacing_y = 30
                    columns = 4
                    total_w = columns * card_w_s_base + (columns - 1) * spacing_x
                    start_x = (width - total_w) // 2
                    start_y = 50
                
                    for i in range(8):
                        row = i // columns
                        col = i % columns
                        cx = start_x + col * (card_w_s_base + spacing_x)
                        cy = start_y + row * (card_h_s_base + spacing_y)
                        rect = pygame.Rect(cx, cy, card_w_s_base, card_h_s_base)
                    
                        if rect.collidepoint(mx, my):
                            if i == 0: player.set_character(Swordsman)
                            elif i == 1: player.set_character(Archer)
                            elif i == 2: player.set_character(MagicSwordsman)
                            elif i == 3: player.set_character(Warrior)
                            elif i == 4: player.set_character(Pyromancer)
                            elif i == 5: player.set_character(Lancer)
                            elif i == 6: player.set_character(MonsterBeta)
                            elif i == 7: player.set_character(IceMage)
                        
                            # Apply reincarnator mode flag to the new character
                            if player.character:
                                player.character.is_reincarnator_mode = player.reincarnator_mode

                            # Reset player position and start battle
                            player.x, player.y = 400, 350
                            player.vx, player.vy = 0, 0
                            player.hp = player.max_hp
                            wave_number = 0
                            enemies = []
                            enemy_bullets = []
                            is_combat_mode = True
                            start_next_wave()
                            wave_start_wait_timer = 60
                            game_state = STATE_PLAYING
                            break
                    
                    # Mode toggle areas
                    if height - 120 <= my <= height - 50:
                        if 300 < mx < width // 2 - 10:
                            player.reincarnator_mode = not player.reincarnator_mode
                        elif width // 2 + 10 < mx < 900:
                            smartphone_mode = (smartphone_mode + 1) % 3
                            V_PAD = V_PAD_1 if smartphone_mode == 1 else V_PAD_2

                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        player.reincarnator_mode = not player.reincarnator_mode
                    if event.key == pygame.K_t:
                        smartphone_mode = (smartphone_mode + 1) % 3
                        V_PAD = V_PAD_1 if smartphone_mode == 1 else V_PAD_2
                    elif event.key == pygame.K_ESCAPE:
                        game_state = STATE_LOBBY

            elif game_state == STATE_CHOOSE_WEAPON:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    scale = 0.6
                    card_w, card_h = int(280 * scale), int(420 * scale)
                    spacing = 50
                    total_w = 3 * card_w + 2 * spacing
                    start_x = (width - total_w) // 2
                    start_y = height // 2 - card_h // 2
                
                    for i in range(3):
                        rect = pygame.Rect(start_x + i * (card_w + spacing), start_y, card_w, card_h)
                        if rect.collidepoint(mx, my):
                            if i == 0: player.character.weapon_type = "sword"
                            elif i == 1: player.character.weapon_type = "hammer"
                            elif i == 2: player.character.weapon_type = "spear"
                        
                            player.x, player.y = 400, 350
                            player.vx, player.vy = 0, 0
                            player.hp = player.max_hp
                            wave_number = 0
                            enemies = []
                            enemy_bullets = []
                            is_combat_mode = True
                            start_next_wave()
                            wave_start_wait_timer = 60
                            game_state = STATE_PLAYING
                            break
            elif game_state == STATE_UPGRADE:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    scale = 0.6
                    card_w, card_h = int(280 * scale), int(420 * scale)
                    spacing = 50
                    num_upgrades = len(player.character.current_upgrades) if hasattr(player.character, 'current_upgrades') else 3
                    total_w = num_upgrades * card_w + (num_upgrades - 1) * spacing
                    start_x = (width - total_w) // 2
                    start_y = height // 2 - card_h // 2
                    
                    if hasattr(player.character, 'current_upgrades'):
                        for i, upgrade in enumerate(player.character.current_upgrades):
                            rect = pygame.Rect(start_x + i * (card_w + spacing), start_y, card_w, card_h)
                            if rect.collidepoint(mx, my):
                                if player.character.apply_upgrade(upgrade):
                                    start_next_wave()
                                    game_state = STATE_PLAYING
                                else:
                                    # Transitioned to REPLACE state (wave starts after)
                                    pass
                                break
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or \
                     (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and smartphone_mode):
                    # Skip reward (can also tap on phone)
                    start_next_wave()
                    game_state = STATE_PLAYING


            elif game_state == STATE_BOSS_REWARD:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    scale = 0.7
                    card_w, card_h = int(280 * scale), int(420 * scale)
                    spacing = 50
                    total_w = 3 * card_w + 2 * spacing
                    start_x = (width - total_w) // 2
                    start_y = height // 2 - card_h // 2
                    
                    for i in range(3):
                        rect = pygame.Rect(start_x + i * (card_w + spacing), start_y, card_w, card_h)
                        if rect.collidepoint(mx, my):
                            # Apply reward
                            if i == 0: # Increase upgrade slots
                                player.character.upgrade_slots += 1
                            elif i == 1: # Skill evolution
                                # [Translated/Cleaned Comment]
                                # User requested "1 skill evolution", so randomly enhance one owned skill
                                if player.character.skills:
                                    s = random.choice(player.character.skills)
                                    s.damage_bonus += 3
                            elif i == 2: # Hero's Blessing
                                player.max_hp += 10
                                player.hp = player.max_hp
                                player.defense += 1
                            
                            start_next_wave()
                            game_state = STATE_PLAYING
                            break

            elif game_state == STATE_REPLACE_SKILL:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # [Translated/Cleaned Comment]
                    for i in range(len(player.character.skills)):
                        rect = pygame.Rect(200 + i * 160, 250, 80, 80)
                        if rect.collidepoint(mx, my):
                            # Swap skill
                            player.character.skills[i] = player.character.queued_skill
                            player.character.queued_skill = None
                            start_next_wave()
                            game_state = STATE_PLAYING
                            break
                    # [Translated/Cleaned Comment]
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or \
                     (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and smartphone_mode):
                    # [Translated/Cleaned Comment]
                    player.character.queued_skill = None
                    start_next_wave()
                    game_state = STATE_PLAYING


            elif game_state == STATE_PLAYING:
                player.handle_event(event, enemies if wave_start_wait_timer <= 0 else [])
                if event.type == pygame.KEYDOWN:
                    if event.key == key_config['pause']:
                        game_state = STATE_PAUSED
                    if event.key == pygame.K_p and not is_combat_mode:
                        # Start combat mode
                        is_combat_mode = True
                        wave_number = 0
                        start_next_wave()
                    if event.key == pygame.K_r: # Manual spawn
                        enemies.append(Enemy(width - 100, ground))
        
            elif game_state == STATE_PAUSED:
                if event.type == pygame.KEYDOWN and event.key == key_config['pause']:
                    game_state = STATE_PLAYING
                
                pt_x, pt_y = -1, -1
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pt_x, pt_y = pygame.mouse.get_pos()
                elif event.type == pygame.FINGERDOWN:
                    pt_x, pt_y = event.x * width, event.y * height
                    
                if pt_x != -1:
                    btn_w, btn_h = 300, 60
                    resume_rect = pygame.Rect(width//2 - btn_w//2, height//2 - 20, btn_w, btn_h)
                    title_rect = pygame.Rect(width//2 - btn_w//2, height//2 + 70, btn_w, btn_h)
                    if resume_rect.collidepoint(pt_x, pt_y):
                        game_state = STATE_PLAYING
                    elif title_rect.collidepoint(pt_x, pt_y):
                        player.reset()
                        game_state = STATE_LOBBY
                        hit_stop_timer = 0

                
            elif game_state == STATE_GAMEOVER:
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_r) or \
                   (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and smartphone_mode):
                    player.character = None
                    player.reset()
                    enemies = []
                    enemy_bullets = []
                    wave_number = 0
                    wave_clear_timer = 0
                    wave_start_wait_timer = 0
                    is_combat_mode = False
                    game_state = STATE_LOBBY


        keys = pygame.key.get_pressed()
    
        # Update logic
        if game_state in [STATE_PLAYING, STATE_LOBBY]:
            if hit_stop_timer > 0:
                hit_stop_timer -= 1
            else:
                player.update_timers()
                # During READY (countdown), don't pass enemy list to skills (prevent damage)
                enemies_for_player = enemies if (game_state == STATE_PLAYING and wave_start_wait_timer <= 0) else []
                player.update(keys, enemies_for_player)

                if wave_start_wait_timer > 0:
                    wave_start_wait_timer -= 1

                # Collision separation
                active_list = [e for e in enemies if e.hp > 0]
                separate_actors([player] + active_list)

                active_enemies = 0
                for e in enemies:
                    if e.hp > 0:
                        e.update(player)
                        active_enemies += 1
                    elif isinstance(e, BomberEnemy) and e.exploded and e.explosion_timer > 0:
                        if e.explosion_timer == 20:
                            e.explode(player)
                        e.explosion_timer -= 1
                    e.update_debris()

                # Update enemy bullets
                for b in enemy_bullets[:]:
                    if b.update(player) or b.timer <= 0:
                        enemy_bullets.remove(b)
            
                # Next wave when cleared (with interval)
                if is_combat_mode and active_enemies == 0:
                    if wave_clear_timer <= 0:
                        wave_clear_timer = 120 # Wait 2 seconds
                    else:
                        wave_clear_timer -= 1
                        if wave_clear_timer == 1:
                            is_reincarn = player.character and getattr(player.character, 'is_reincarnator_mode', False)
                            if is_reincarn:
                                if wave_number > 0 and wave_number % 5 == 0:
                                    # Special reward after boss defeat
                                    game_state = STATE_BOSS_REWARD
                                    wave_clear_timer = 0
                                else:
                                    player.character.generate_upgrades()
                                    game_state = STATE_UPGRADE
                                    wave_clear_timer = 0
                            else:
                                # Non-roguelike mode: heal 1 HP per stage, +5 max HP every 5 stages
                                player.hp = min(player.max_hp, player.hp + 1)
                                if wave_number > 0 and wave_number % 5 == 0:
                                    player.max_hp += 5
                                    player.hp = min(player.max_hp, player.hp + 5)
                                start_next_wave()
                                wave_clear_timer = 0

        # Draw
        screen.fill((155, 155, 155))
        pygame.draw.rect(screen, (155, 200, 200), (0, ground, 2000, 100))
    
        # Draw platform
        if game_state in [STATE_PLAYING, STATE_LOBBY]:
            pygame.draw.rect(screen, (120, 140, 160), (PLATFORM_X, PLATFORM_Y, PLATFORM_W, PLATFORM_H))
            pygame.draw.rect(screen, (180, 200, 220), (PLATFORM_X, PLATFORM_Y, PLATFORM_W, 4))
    
        # Draw UI
        if game_state != STATE_SELECT_CHAR:
            hp_text = font_main.render(f"PLAYER HP: {player.hp} / {player.max_hp}", True, (0, 0, 0))
            screen.blit(hp_text, (width - 320, 20))
            if is_combat_mode:
                wave_text = font_main.render(f"WAVE: {wave_number}", True, (0, 0, 0))
                screen.blit(wave_text, (width - 320, 70))
                if wave_clear_timer > 0:
                    clear_text = font_main.render(f"WAVE {wave_number} CLEARED!", True, (0, 150, 0))
                    screen.blit(clear_text, (width // 2 - 150, height // 2 - 100))
            
                if wave_start_wait_timer > 0:
                    ready_msg = font_main.render("READY?", True, (255, 0, 0))
                    screen.blit(ready_msg, (width // 2 - 70, height // 2))

        player.draw(screen)
        for e in enemies:
            e.draw(screen)  # draw handles both alive (block visuals) and dead (debris)
        for b in enemy_bullets:
            b.draw(screen)

        # Lobby and select screen overlay
        if game_state == STATE_LOBBY:
            # Main button (ENTER / Tap to start)
            btn_rect = pygame.Rect(width//2 - 300, 45, 600, 60)
            pygame.draw.rect(screen, (30, 30, 50), btn_rect, border_radius=10)
            pygame.draw.rect(screen, (200, 200, 255), btn_rect, 2, border_radius=10)
            
            prompt_text = font_title.render("Tap to open Character Select", True, (255, 255, 200))
            screen.blit(prompt_text, (width//2 - prompt_text.get_width()//2, 55))
            
            # Smartphone mode toggle button
            s_btn_rect = pygame.Rect(width//2 - 150, 130, 300, 50)
            s_color = (100, 200, 255) if smartphone_mode else (80, 80, 80)
            pygame.draw.rect(screen, (40, 40, 60), s_btn_rect, border_radius=5)
            pygame.draw.rect(screen, s_color, s_btn_rect, 2, border_radius=5)
            
            if smartphone_mode == 1: s_text = "Smartphone Mode: ON 1"
            elif smartphone_mode == 2: s_text = "Smartphone Mode: ON 2"
            else: s_text = "Smartphone Mode: OFF"
            s_surf = font_settings_hint.render(s_text, True, s_color)
            screen.blit(s_surf, (width//2 - s_surf.get_width()//2, 140))

            hint_text = font_settings_footer.render("Press [S] for Key Settings", True, (180, 200, 255))
            screen.blit(hint_text, (width//2 - hint_text.get_width()//2, 200))

        
        elif game_state == STATE_SETTINGS:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 220))
            screen.blit(overlay, (0, 0))
        
            title_s = font_settings_title.render("Key Settings", True, (255, 255, 255))
            screen.blit(title_s, (width // 2 - title_s.get_width() // 2, 50))
        
            mx, my = pygame.mouse.get_pos()
            for idx, (action, keycode) in enumerate(key_config.items()):
                y = 130 + idx * 45
                name = KEY_ACTION_NAMES.get(action, action)
                is_selected = settings_selecting == action
                is_hovered = 350 <= mx <= 850 and y <= my <= y + 38
            
                if is_selected:
                    bg_color = (80, 80, 180)
                elif is_hovered:
                    bg_color = (70, 70, 90)
                else:
                    bg_color = (40, 40, 50)
                
                pygame.draw.rect(screen, bg_color, (350, y, 500, 38), border_radius=5)
                pygame.draw.rect(screen, (100, 100, 120), (350, y, 500, 38), 1, border_radius=5)
            
                label = font_settings_row.render(name, True, (255, 255, 255))
                screen.blit(label, (370, y + 8))
            
                if is_selected:
                    key_text = font_settings_row.render("Press a key...", True, (255, 255, 0))
                else:
                    key_name = pygame.key.name(keycode).upper()
                    key_text = font_settings_row.render(f"[{key_name}]", True, (200, 200, 200))
                screen.blit(key_text, (650, y + 8))
        
            hint = font_settings_footer.render("Click to select, press key to rebind. ESC to return.", True, (160, 160, 180))
            screen.blit(hint, (width // 2 - hint.get_width() // 2, height - 50))

        elif game_state in [STATE_UPGRADE, STATE_BOSS_REWARD]:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            title_text = "BOSS CLEAR REWARD" if game_state == STATE_BOSS_REWARD else "WAVE CLEAR REWARD"
            title_s = font_settings_title.render(title_text, True, (255, 215, 0))
            screen.blit(title_s, (width // 2 - title_s.get_width() // 2, 80))
            
            scale = 0.7
            card_w, card_h = int(280 * scale), int(420 * scale)
            spacing = 50
            
            rewards = []
            if game_state == STATE_BOSS_REWARD:
                rewards = [
                    {"name": "Choice Slot+", "desc": "Normal upgrade choices +1", "color": (100, 200, 255)},
                    {"name": "Evolution", "desc": "One skill Damage +3", "color": (255, 100, 100)},
                    {"name": "Hero's Blessing", "desc": "Max HP+10, Heal, Def+1", "color": (255, 215, 0)}
                ]
            else:
                if hasattr(player.character, 'current_upgrades'):
                    color_mapping = {
                        "heal": (100, 255, 100), "maxhp": (100, 255, 100),
                        "jump": (100, 200, 255), "speed": (100, 200, 255),
                        "attack": (255, 150, 100), "defense": (255, 150, 100),
                        "cd": (200, 100, 255), "skill": (255, 215, 0)
                    }
                    for upg in player.character.current_upgrades:
                        color = color_mapping.get(upg.get("type", ""), (200, 200, 200))
                        rewards.append({"name": upg["name"], "desc": upg["desc"], "color": color})
            
            total_w = len(rewards) * card_w + (len(rewards) - 1) * spacing
            start_x = (width - total_w) // 2
            start_y = height // 2 - card_h // 2
            
            mx, my = pygame.mouse.get_pos()
            for i, r in enumerate(rewards):
                rx = start_x + i * (card_w + spacing)
                ry = start_y
                rect = pygame.Rect(rx, ry, card_w, card_h)
                is_hover = rect.collidepoint(mx, my)
                
                draw_rect = pygame.Rect(rx, ry - (15 if is_hover else 0), card_w, card_h)
                
                # Card background
                bg_color = [min(255, int(c * (0.6 if is_hover else 0.4))) for c in r["color"]]
                pygame.draw.rect(screen, bg_color, draw_rect, border_radius=15)
                outline_color = (255, 255, 255) if is_hover else [min(255, int(c * 0.8)) for c in r["color"]]
                pygame.draw.rect(screen, outline_color, draw_rect, 4 if is_hover else 2, border_radius=15)
                
                # Text
                name_color = r["color"] if is_hover else (255, 255, 255)
                name_s = font_upgrade_name.render(r["name"], True, name_color)
                desc_s = font_upgrade_desc.render(r["desc"], True, (220, 220, 220) if is_hover else (200, 200, 200))
                screen.blit(name_s, (rx + 15, draw_rect.y + 30))
                # Simple newline handling
                screen.blit(desc_s, (rx + 15, draw_rect.y + 120))

        elif game_state == STATE_PAUSED:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            pause_text = font_title.render("PAUSED", True, (255, 255, 255))
            screen.blit(pause_text, (width//2 - pause_text.get_width()//2, height//2 - 150))
            
            rmx, rmy = pygame.mouse.get_pos()
            btn_w, btn_h = 300, 60
            resume_rect = pygame.Rect(width//2 - btn_w//2, height//2 - 20, btn_w, btn_h)
            title_rect = pygame.Rect(width//2 - btn_w//2, height//2 + 70, btn_w, btn_h)
            
            res_hover = resume_rect.collidepoint(rmx, rmy)
            tit_hover = title_rect.collidepoint(rmx, rmy)
            
            pygame.draw.rect(screen, (80, 80, 100) if res_hover else (50, 50, 70), resume_rect, border_radius=10)
            pygame.draw.rect(screen, (200, 255, 200), resume_rect, 3 if res_hover else 1, border_radius=10)
            res_t = font_main.render("Resume", True, (255, 255, 255))
            screen.blit(res_t, (width//2 - res_t.get_width()//2, height//2 - 20 + 15))
            
            pygame.draw.rect(screen, (100, 60, 60) if tit_hover else (70, 40, 40), title_rect, border_radius=10)
            pygame.draw.rect(screen, (255, 150, 150), title_rect, 3 if tit_hover else 1, border_radius=10)
            tit_t = font_main.render("Return to Title", True, (255, 255, 255))
            screen.blit(tit_t, (width//2 - tit_t.get_width()//2, height//2 + 70 + 15))
            
            if smartphone_mode == 0:
                hint_text = font_settings_hint.render("Press 'Q' to Resume", True, (200, 200, 200))
                screen.blit(hint_text, (width//2 - hint_text.get_width()//2, height//2 + 160))


        elif game_state == STATE_SELECT_CHAR:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
        
            cards = [
                {"name": "Swordsman", "color": (150, 20, 20), "skills": "J:DashStrike K:Rising\nL:Fire N:BraveCharge\nM:Gravity"},
                {"name": "Archer", "color": (20, 100, 20), "skills": "J:PierceArrow K:Mirror\nL:WarpArrow N:ArrowRain\nM:PinArrow"},
                {"name": "MagicSwordsman", "color": (80, 20, 150), "skills": "J:MagicSword K:Thunder\nL:IceEnchant N:FireEnchant\nM:BraveCharge"},
                {"name": "Warrior", "color": (150, 100, 20), "skills": "J:HammerThrow K:SuperArmor\nL:Energy N:Earthquake\nM:WarCry"},
                {"name": "Pyromancer", "color": (200, 50, 0), "skills": "J:Lava K:SpreadFire\nL:Eruption N:FlameDash\nM:Meteor"},
                {"name": "Lancer", "color": (50, 150, 150), "skills": "J:Javelin K:VaultStrike\nL:RapidThrust N:Sweep\nM:DragonDive"},
                {"name": "MonsterBeta", "color": (120, 30, 30), "skills": "J:Pounce K:ScaleShot\nL:Roar N:Ampule\nM:Rampage"},
                {"name": "IceMage", "color": (100, 200, 255), "skills": "J:AlHuma K:IceBrand\nL:Lance N:Shield\nM:Cocytus"}
            ]
        
            scale = 0.52
            card_w_s_base, card_h_s_base = int(280 * scale), int(420 * scale)
            spacing_x = 30
            spacing_y = 30
            columns = 4
            total_w = columns * card_w_s_base + (columns - 1) * spacing_x
            start_x = (width - total_w) // 2
            start_y = 50
        
            mx, my = pygame.mouse.get_pos()
            for i, card in enumerate(cards):
                row = i // columns
                col = i % columns
                cx = start_x + col * (card_w_s_base + spacing_x)
                cy = start_y + row * (card_h_s_base + spacing_y)
                rect = pygame.Rect(cx, cy, card_w_s_base, card_h_s_base)
                is_hovered = rect.collidepoint(mx, my)
            
                draw_rect = pygame.Rect(cx, cy - (10 if is_hovered else 0), card_w_s_base, card_h_s_base)
                pygame.draw.rect(screen, card["color"], draw_rect, border_radius=10)
                pygame.draw.rect(screen, (255, 255, 255), draw_rect, 2, border_radius=10)
            
                name_text = font_card_name.render(card["name"], True, (255, 255, 255))
                screen.blit(name_text, (cx + 10, cy + (10 if is_hovered else 20)))
                # Display skill names
                for si, skill_line in enumerate(card["skills"].split("\n")):
                    st = font_card_skill.render(skill_line, True, (220, 220, 220))
                    screen.blit(st, (cx + 10, cy + (45 if is_hovered else 55) + si * 18))

            # Reincarnator mode toggle display
            mode_text = "Reincarnator Mode: ON" if player.reincarnator_mode else "Reincarnator Mode: OFF"
            mode_color = (100, 255, 100) if player.reincarnator_mode else (150, 150, 150)
            mode_surf = font_main.render(mode_text, True, mode_color)
            
            # Smartphone mode toggle display
            if smartphone_mode == 1: s_mode_text = "Smartphone Mode: ON 1"
            elif smartphone_mode == 2: s_mode_text = "Smartphone Mode: ON 2"
            else: s_mode_text = "Smartphone Mode: OFF"
            s_mode_color = (100, 200, 255) if smartphone_mode else (150, 150, 150)
            s_mode_surf = font_main.render(s_mode_text, True, s_mode_color)
            
            # Draw button backgrounds
            rmx, rmy = pygame.mouse.get_pos()
            r_hover = height - 120 <= rmy <= height - 50 and 300 < rmx < width // 2 - 10
            s_hover = height - 120 <= rmy <= height - 50 and width // 2 + 10 < rmx < 900
            
            r_rect = pygame.Rect(width // 2 - mode_surf.get_width() - 30, height - 110, mode_surf.get_width() + 20, mode_surf.get_height() + 20)
            s_rect = pygame.Rect(width // 2 + 10, height - 110, s_mode_surf.get_width() + 20, s_mode_surf.get_height() + 20)
            
            pygame.draw.rect(screen, (50, 50, 70) if r_hover else (30, 30, 40), r_rect, border_radius=5)
            pygame.draw.rect(screen, mode_color, r_rect, 2, border_radius=5)
            
            pygame.draw.rect(screen, (50, 50, 70) if s_hover else (30, 30, 40), s_rect, border_radius=5)
            pygame.draw.rect(screen, s_mode_color, s_rect, 2, border_radius=5)

            screen.blit(mode_surf, (width // 2 - mode_surf.get_width() - 20, height - 100))
            screen.blit(s_mode_surf, (width // 2 + 20, height - 100))
            
            hint_surf = font_settings_hint.render("Tap buttons, 'R' (Reincarn) / 'T' (Smartphone) to toggle", True, (200, 200, 200))
            screen.blit(hint_surf, (width // 2 - hint_surf.get_width() // 2, height - 40))

        elif game_state == STATE_CHOOSE_WEAPON:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
        
            prompt_text = font_main.render("Choose Your Starting Weapon", True, (255, 255, 255))
            screen.blit(prompt_text, (width//2 - prompt_text.get_width()//2, 40))
        
            cards = [
                {"name": "Sword", "color": (150, 50, 50), "desc": "Standard Sword\nAverage speed/dmg"},
                {"name": "Hammer", "color": (150, 100, 20), "desc": "Heavy Hammer\nHigh damage"},
                {"name": "Spear", "color": (50, 150, 150), "desc": "Long Spear\nGood reach"}
            ]
        
            scale = 0.6
            card_w, card_h = int(280 * scale), int(420 * scale)
            spacing = 50
            total_w = 3 * card_w + 2 * spacing
            start_x = (width - total_w) // 2
            start_y = height // 2 - card_h // 2
        
            mx, my = pygame.mouse.get_pos()
            for i, card in enumerate(cards):
                cx = start_x + i * (card_w + spacing)
                cy = start_y
                rect = pygame.Rect(cx, cy, card_w, card_h)
                is_hovered = rect.collidepoint(mx, my)
            
                draw_rect = pygame.Rect(cx, cy - (10 if is_hovered else 0), card_w, card_h)
                pygame.draw.rect(screen, card["color"], draw_rect, border_radius=10)
                pygame.draw.rect(screen, (255, 255, 255), draw_rect, 2, border_radius=10)
            
                name_text = font_weapon_name.render(card["name"], True, (255, 255, 255))
                screen.blit(name_text, (cx + 10, draw_rect.y + 20))
            
                for di, d_line in enumerate(card["desc"].split("\n")):
                    dt = font_weapon_desc.render(d_line, True, (220, 220, 220))
                    screen.blit(dt, (cx + 10, draw_rect.y + 70 + di * 25))

        elif game_state == STATE_UPGRADE:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
        
            prompt_text = font_main.render(f"WAVE {wave_number-1} CLEARED! Choose Upgrade", True, (255, 255, 100))
            screen.blit(prompt_text, (width//2 - prompt_text.get_width()//2, 40))
        
            if hasattr(player.character, 'current_upgrades'):
                scale = 0.6
                card_w, card_h = int(280 * scale), int(420 * scale)
                spacing = 50
                total_w = 3 * card_w + 2 * spacing
                start_x = (width - total_w) // 2
                start_y = height // 2 - card_h // 2
            
                mx, my = pygame.mouse.get_pos()
                for i, upgrade in enumerate(player.character.current_upgrades):
                    cx = start_x + i * (card_w + spacing)
                    cy = start_y
                    rect = pygame.Rect(cx, cy, card_w, card_h)
                    is_hovered = rect.collidepoint(mx, my)
                
                    draw_rect = pygame.Rect(cx, cy - (10 if is_hovered else 0), card_w, card_h)
                
                    # Check type for color
                    color = (50, 50, 150)
                    if upgrade["type"] == "skill": color = (150, 50, 150)
                    elif upgrade["type"] == "heal" or "hp" in upgrade["type"]: color = (50, 150, 50)
                    elif "attack" in upgrade["type"]: color = (150, 50, 50)
                
                    pygame.draw.rect(screen, color, draw_rect, border_radius=10)
                    pygame.draw.rect(screen, (255, 255, 255), draw_rect, 2, border_radius=10)
                
                    name_text = font_upgrade_name.render(upgrade["name"], True, (255, 255, 255))
                    screen.blit(name_text, (cx + 10, draw_rect.y + 20))
                
                    # Word wrap or split lines
                    desc = upgrade["desc"]
                    dt = font_upgrade_desc.render(desc, True, (220, 220, 220))
                    screen.blit(dt, (cx + 10, draw_rect.y + 70))

        elif game_state == STATE_REPLACE_SKILL:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 220))
            screen.blit(overlay, (0, 0))
            
            title_text = font_main.render("Select a skill to replace", True, (255, 255, 100))
            screen.blit(title_text, (width // 2 - title_text.get_width() // 2, 100))
            
            # Display current skills
            for i, s in enumerate(player.character.skills):
                sx = 200 + i * 160
                sy = 250
                icon_rect = pygame.Rect(sx, sy, 80, 80)
                pygame.draw.rect(screen, s.color_ready, icon_rect, border_radius=5)
                pygame.draw.rect(screen, (255, 255, 255), icon_rect, 2, border_radius=5)
                
                # Skill name (inferred from class name)
                skill_name = type(s).__name__.replace("Skill", "")
                st = font_card_skill.render(skill_name, True, (255, 255, 255))
                screen.blit(st, (sx, sy + 90))

            # Display new skill
            new_s = player.character.queued_skill
            if new_s:
                nx = width // 2 - 40
                ny = 420
                new_rect = pygame.Rect(nx, ny, 80, 80)
                pygame.draw.rect(screen, new_s.color_ready, new_rect, border_radius=5)
                pygame.draw.rect(screen, (255, 255, 0), new_rect, 3, border_radius=5)
                
                nt = font_main.render("NEW", True, (255, 255, 0))
                screen.blit(nt, (nx + 10, ny - 40))
                
                skill_name = type(new_s).__name__.replace("Skill", "")
                st = font_card_name.render(skill_name, True, (255, 255, 255))
                screen.blit(st, (nx - 20, ny + 90))

            hint_text = font_settings_hint.render("Click a skill to replace, or ESC to skip", True, (150, 150, 150))
            screen.blit(hint_text, (width // 2 - hint_text.get_width() // 2, height - 50))

        elif game_state == STATE_GAMEOVER:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((200, 0, 0, 150))
            screen.blit(overlay, (0, 0))
            go_text = font_gameover.render("GAME OVER", True, (255, 255, 255))
            retry_label = "Tap" if smartphone_mode else "Press 'R'"
            retry_text = font_main.render(f"{retry_label} to Retry", True, (255, 255, 255))
            screen.blit(go_text, (width//2 - 220, height//2 - 50))
            screen.blit(retry_text, (width//2 - 150, height//2 + 50))

            if keys[pygame.K_r]:
                player = Player()
                enemies = []
                enemy_bullets = []
                wave_number = 0
                is_combat_mode = False
                wave_clear_timer = 0
                wave_start_wait_timer = 0
                game_state = STATE_LOBBY

        # --- Draw virtual pad for smartphone (topmost) ---
        if smartphone_mode:
            v_overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            for btn_name, rect in V_PAD.items():
                # Draw each button (semi-transparent white)
                color = (255, 255, 255, 60)
                # Brighten while pressed
                if touch_keys.get(btn_name, False):
                    color = (255, 255, 255, 120)
                
                if btn_name == 'attack':
                    pygame.draw.circle(v_overlay, color, rect.center, rect.width // 2)
                    atk_text = font_upgrade_name.render("ATK", True, (255, 255, 255))
                    v_overlay.blit(atk_text, (rect.centerx - atk_text.get_width()//2, rect.centery - atk_text.get_height()//2))
                else:
                    pygame.draw.circle(v_overlay, color, rect.center, rect.width // 2)
                    label = "L" if btn_name == 'left' else ("R" if btn_name == 'right' else ("UP" if btn_name == 'up' else "||"))
                    lbl_text = font_upgrade_name.render(label, True, (255, 255, 255))
                    v_overlay.blit(lbl_text, (rect.centerx - lbl_text.get_width()//2, rect.centery - lbl_text.get_height()//2))
            
            screen.blit(v_overlay, (0, 0))

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

asyncio.run(main())
pygame.quit()
