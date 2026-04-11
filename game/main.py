# -*- coding: utf-8 -*-
import pygame
import math # 数学的な計算（円や角度）のために追加
import random
import asyncio

width=1200  
height=600

ground=540

# pygame.init() and screen setup moved inside main() for better stability in web environment

# --- ゲーム状態の定義 ---
STATE_TITLE = "title"         # タイトル画面（未実装だが定義）
STATE_LOBBY = "lobby"         # キャラクター選択前のロビー状態
STATE_PLAYING = "playing"     # メインの戦闘・探索中
STATE_PAUSED = "paused"       # ポーズメニュー表示中
STATE_GAMEOVER = "gameover"   # ゲームオーバー画面
STATE_SELECT_CHAR = "select_char" # キャラクター選択中（転生者モード切替含む）
STATE_CHOOSE_WEAPON = "choose_weapon" # 武器選択
STATE_UPGRADE = "upgrade"     # ウェーブクリア後のスキル・ステータス強化
STATE_SETTINGS = "settings"   # キー操作設定
STATE_REPLACE_SKILL = "replace_skill" # スキル上限時に新しいスキルと入れ替える画面
STATE_BOSS_REWARD = "boss_reward"    # ボス撃破後の特別報酬選択

# --- キー設定 ---
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

# 反発係数 (衝突分離用)
PUSH_FORCE = 0.5 

def separate_actors(actors):
    """アクター同士の重なりを解消する"""
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            a, b = actors[i], actors[j]
            if not a or not b or a == b: continue
            # 敵は重複を許可するため、分離対象から外す
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
wave_clear_timer = 0 # ウェーブ間の待ち時間用
wave_start_wait_timer = 0 # ウェーブ開始時の待機用

# --- 足場 ---
PLATFORM_X = 450
PLATFORM_Y = 380
PLATFORM_W = 300
PLATFORM_H = 12

# --- スキル クラス定義 ---
class Skill:
    """
    スキルの基底クラス。
    クールタイム管理、発動判定、基本的な描画ロジックを持ちます。
    """
    def __init__(self, x, y, max_cool, color_ready, color_charge):
        self.x = x                          # UI表示時のX座標
        self.y = y                          # UI表示時のY座標
        self.cool = 0                       # 現在のクールタイム残量（0で発動可能）
        self.max_cool = max_cool            # スキルの最大クールタイム
        self.color_ready = color_ready      # 使用可能時のアイコンカラー
        self.color_charge = color_charge    # 充電中のアイコンカラー
        self.damage_bonus = 0               # 進化などによる追加ダメージ

    def update(self, enemies=None, cooldown_speed=1, player=None):
        """毎フレームのクールタイム減少処理"""
        if self.cool > 0:
            cs = cooldown_speed
            # バフスキルの場合はクールタイム短縮に制限をかける (1.3倍ルール)
            if hasattr(self, 'active_timer') and hasattr(self, 'max_cool'):
                duration = getattr(self, 'initial_duration', 0)
                if duration > 0:
                    min_cool_time = duration * 1.3
                    # 実際の冷却速度を制限する (現在値/目標時間)
                    cs = min(cs, self.max_cool / min_cool_time)
            
            self.cool -= cs
            if self.cool < 0: self.cool = 0

    def activate(self, player, enemies=None):
        """スキル発動の試行。クールタイム中ならFalseを返す"""
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
            # 範囲内の接地している敵を凍結
            if enemies:
                for e in enemies:
                    if e.hp > 0 and self.place < e.x + e.width and e.x < self.place + self.width and e.y + e.height >= ground - 5:
                        if hasattr(e, 'frozen_timer'):
                            e.frozen_timer = 120 # 2秒間
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
        # 溶岩らしく赤・オレンジ系 (color_charge: 鮮やかな赤, color_ready: 燃えるようなオレンジ)
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
            # 透過っぽく見せるために少し暗い赤で地面を描画
            pygame.draw.rect(screen, (200, 0, 0), (self.place, ground, self.width, 100))

class FireSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 60, (255, 100, 100), (255, 0, 0))
        self.bullets = [] # list of [x, y, vx, timer]
        self.width = 40
        self.height = 20
        self.speed = 15
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            # 打ち出した時のプレイヤーのスピードを加味
            vx = (self.speed + abs(player.vx)) * player.facing
            # プレイヤーの中心付近から射出 [x, y, vx, timer, hit_enemies]
            self.bullets.append([player.x + 20, player.y + 10, vx, 60, []])
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        new_bullets = []
        for b in self.bullets:
            b[0] += b[2] # x移動
            b[3] -= 1 # 寿命
            # 当たり判定
            bx, by = b[0], b[1]
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x <= bx <= e.x + e.width and e.y <= by <= e.y + e.height:
                        # 貫通：まだこの弾が当たっていない敵ならダメージ
                        if e not in b[4]:
                            if e.take_damage(1 + self.damage_bonus, 1 if b[2] > 0 else -1, element='fire'):
                                b[4].append(e)
            
            # 消滅判定：寿命切れ or 画面外
            if b[3] > 0 and -100 < b[0] < width + 100:
                new_bullets.append(b)
        self.bullets = new_bullets
    def draw_effect(self, screen):
        for b in self.bullets:
            pygame.draw.rect(screen, (255, 0, 0), (int(b[0]), int(b[1]), self.width, self.height))

class ThunderSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 200, (255, 255, 0), (200, 200, 0)) # クールタイムを5倍(40->200)に
        self.range = 0
        self.points = []
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.range = 30 # 表示時間
            # 生きている敵をリストアップ
            alive_enemies = []
            if enemies:
                alive_enemies = [e for e in enemies if e.hp > 0]
            
            if alive_enemies:
                # ランダムな敵を選択
                target_enemy = random.choice(alive_enemies)
                tx = target_enemy.x + target_enemy.width / 2
                target_enemy.take_damage(2 + self.damage_bonus)
            else:
                # 敵がいない場合はランダムな位置
                tx = random.randint(50, width - 50)
                
            self.points = [(tx, 0)]
            curr_y = 0
            while curr_y < ground + 100:
                curr_y += random.randint(30, 60)
                next_x = tx + random.randint(-40, 40)
                self.points.append((next_x, curr_y))
            
            # 当たり判定 (雷が落ちた場所 tx を中心に判定)
            for e in enemies:
                if e.hp > 0:
                    # 稲妻の中心 Y 軸との距離で判定
                    if abs((e.x + e.width/2) - tx) < 40:
                        # 雷は真上からなので source_facing は適当 (0でいいが、一応左右判定)
                        sf = 1 if e.x < tx else -1
                        e.take_damage(3 + self.damage_bonus, sf)
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.range > 0: self.range -= 1
    def draw_effect(self, screen):
        if self.range > 0:
            # 白い稲妻を太めに、少し位置をずらして描画して発光感を出す
            for i in range(2):
                offset_x = random.randint(-3, 3)
                p_list = [(p[0] + offset_x, p[1]) for p in self.points]
                pygame.draw.lines(screen, (255, 255, 255), False, p_list, 5 - i*2)

class DashStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 90, (255, 255, 255), (100, 100, 255))
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.vx = 25 * player.facing
            player.swording = 15
            player.hit_timer = max(player.hit_timer, 20)
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)

class BraveChargeSkill(Skill):
    def __init__(self, x, y):
        # クールタイム900, 持続600
        super().__init__(x, y, 900, (255, 200, 0), (200, 100, 0))
        self.active_timer = 0
        self.initial_duration = 600
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 600 # 10秒間
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
            self.active_timer = 999  # 無限（回数制限のみ）にするため大きな値を設定
            self.swings_left = 6   # 10回まで
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
                self.active_timer = 0 # 終了
        
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        # active_timerの自然減少を削除（swings_leftが0になるまで持続）
        
        new_waves = []
        for w in self.waves:
            w[0] += w[2] # 移動
            w[3] -= 1 # 寿命
            if enemies:
                # 三日月の大きさに合わせた当たり判定 (100x180)
                wave_rect = pygame.Rect(w[0] - 50, w[1] - 90, 100, 180)
                for e in enemies:
                    if e.hp > 0 and wave_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        if e not in w[4]:
                            if e.take_damage(2 + self.damage_bonus, 1 if w[2] > 0 else -1):
                                w[4].append(e)
            if w[3] > 0: new_waves.append(w)
        self.waves = new_waves
    
    def draw_effect(self, screen):
        for w in self.waves:
            # 「真ん中が太く、端が細い」本格的な三日月
            points = []
            direction = 1 if w[2] > 0 else -1
            
            base_r = 100
            max_thickness = 40
            angle_range = 75
            
            # 外側の弧
            for i in range(-angle_range, angle_range + 1, 5):
                rad = math.radians(i)
                px = w[0] + math.cos(rad) * base_r * direction
                py = w[1] + math.sin(rad) * base_r
                points.append((px, py))
            
            # 内側の弧 (コサインを使って中央を太く、端を尖らせる)
            for i in range(angle_range, -angle_range - 1, -5):
                rad = math.radians(i)
                # 中央(i=0)で最大、端(i=75)で0近くなるように調整
                t = max_thickness * math.cos(math.radians(i * 90 / angle_range))
                px = w[0] + (math.cos(rad) * base_r - t) * direction
                py = w[1] + math.sin(rad) * base_r
                points.append((px, py))
            
            if len(points) > 2:
                pygame.draw.polygon(screen, (100, 200, 255), points)

class RisingStrikeSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 60, (255, 100, 50), (150, 50, 0))
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            player.swording = 15
            player.vy = -25
            player.hit_timer = max(player.hit_timer, 25)
            player.y -= 10
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)



class PiercingArrowSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 180, (200, 200, 200), (100, 100, 100))
        self.aiming = False
        self.aim_angle = 45 # 初期角度
        self.arrows = [] # [x, y, vx, vy, hit_enemies]
    def activate(self, player, enemies=None):
        if self.cool == 0 and not self.aiming:
            self.aiming = True
            self.player_ref = player
            self.aim_angle = 0 if player.facing == 1 else 180
            player.vx = 0 # 構え中は停止
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
                        if e.take_damage(2 + self.damage_bonus, 1 if a[2] > 0 else -1):
                            a[4].append(e) # 貫通
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
                        e.take_damage(2, 1 if a[0] > self.spawn_x_base else -1); hit = True; break
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
                        if e.take_damage(1, 1 if a[2] > 0 else -1):
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
                # プレイヤーに戻ってくる
                dx = self.player_ref.x + 20 - h[0]
                dy = self.player_ref.y + 20 - h[1]
                dist = max(1, math.hypot(dx, dy))
                h[2] += (dx / dist) * 2.5
                h[3] += (dy / dist) * 2.5
                if dist < 40: # キャッチ
                    self.hammer = None
                    return
            
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e not in h[6] and e.x < h[0]+30 and h[0]-30 < e.x+e.width and e.y < h[1]+30 and h[1]-30 < e.y+e.height:
                        e.take_damage(4, 1 if h[2]>0 else -1, knockback_x=8, knockback_y=-5, element='heavy')
                        h[6].append(e)
                        
            if h[4] <= -100: self.hammer = None
    def draw_effect(self, screen):
        if self.hammer:
            angle = pygame.time.get_ticks() % 360
            surf = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.rect(surf, (150, 100, 50), (25, 5, 10, 50))       # 柄
            pygame.draw.rect(surf, (100, 100, 100), (10, 5, 40, 20))      # 頭
            rot_surf = pygame.transform.rotate(surf, angle)
            rect = rot_surf.get_rect(center=(int(self.hammer[0]), int(self.hammer[1])))
            screen.blit(rot_surf, rect)

class SuperArmorSkill(Skill):
    def __init__(self, x, y):
        super().__init__(x, y, 900, (200, 200, 255), (100, 100, 255))
        self.active_timer = 0
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
                            # 地面に接しているキャラ全員に攻撃
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

# --- キャラクター クラス定義 ---
class Character:
    """
    全キャラクターの共通基盤となるクラス。
    旧「転生者」クラスのロジックが統合されており、全キャラでローグライクな強化が可能です。
    """
    def __init__(self, player):
        self.player = player
        self.skills = []                 # 所持スキルのインスタンス
        self.is_reincarnator_mode = False # 転生者モードフラグ（キャラ選択時に決定）
        self.max_skills = 5              # スキル所持上限（ボス報酬で増加可能）
        self.upgrade_slots = 3           # アップグレード画面の選択肢数
        self.current_upgrades = []       # アップグレード選択肢
        self.queued_skill = None         # 入れ替え待機中の新規スキル

    def handle_event(self, event, enemies):
        """
        全キャラクター共通のスキル発動キー処理。
        所持しているスキルのリストを順番にキーに割り当てます。
        """
        if event.type == pygame.KEYDOWN:
            # 各スキルの発動キー設定
            keys = [key_config['skill_1'], key_config['skill_2'], key_config['skill_3'], 
                    key_config['skill_4'], key_config['skill_5']]
            for i, k in enumerate(keys):
                if event.key == k and i < len(self.skills):
                    # 敵情報を必要とするスキルかチェックして発動
                    self.skills[i].activate(self.player, enemies)

    def on_sword_hit(self, enemy, source_facing):
        """剣攻撃が敵にヒットした際の追加効果処理（エンチャントスキル用）"""
        for s in self.skills:
            # 氷付与状態のチェック
            if type(s).__name__ == "IceEnchantSkill" and getattr(s, 'active_timer', 0) > 0:
                enemy.frozen_timer = 120
            # 炎付与状態のチェック
            if type(s).__name__ == "FireEnchantSkill" and getattr(s, 'active_timer', 0) > 0:
                enemy.burn_timer = 180
                enemy.take_damage(1, source_facing, status_effect=True, element='fire')

    def update(self, keys, enemies, cooldown_speed):
        """
        キャラクターの状態更新。全スキルのクールタイムや状態変化を処理します。
        """
        # 毎フレーム、ステータスをデフォルト値にリセット（バフ適用前）
        self.player.damage_multiplier = 1.0
        self.player.move_speed = self.get_speed()
        self.player.jump_power = self.get_jump_power()

        # 全体バフ効果の適用計算（加速スキルなど）
        cs = cooldown_speed
        for s in self.skills:
            if type(s).__name__ == "BraveChargeSkill" and getattr(s, 'active_timer', 0) > 0:
                cs *= 2 # クールタイムの減少速度を2倍にする
        
        # 各スキルインスタンスの個別更新
        for s in self.skills: 
            s.update(enemies, cs, player=self.player)
            
        # 特定の持続スキルによるプレイヤー能力値の動的な変更
        for s in self.skills:
            # ブレイブチャージ（暴走）状態
            if type(s).__name__ == "BraveChargeSkill" and getattr(s, 'active_timer', 0) > 0:
                self.player.damage_multiplier = max(self.player.damage_multiplier, 2.0)
                self.player.move_speed = max(self.player.move_speed, 2.0)
                # ジャンプ力アップ
                self.player.jump_power = min(self.player.jump_power, -20)
            
            # ウォークライ（鼓舞）状態
            if type(s).__name__ == "WarCrySkill" and getattr(s, 'active_timer', 0) > 0:
                self.player.damage_multiplier = max(self.player.damage_multiplier, 1.5)
            
            # 重力スキルによる落下速度の軽減
            if type(s).__name__ == "GravitySkill" and getattr(s, 'range', 0) > 0:
                self.player.vy += 0.3

    def draw_effects(self, screen):
        for s in self.skills:
            s.draw_effect(screen)
    def draw_ui(self, screen):
        SKILL_NAMES = {
            'MagicSwordSkill': '魔法剣', 'ThunderSkill': '雷', 'IceEnchantSkill': '氷付与',
            'FireEnchantSkill': '炎付与', 'BraveChargeSkill': '突撃', 'HammerThrowSkill': '投げ槌',
            'SuperArmorSkill': 'SA', 'EarthquakeSkill': '地震',
            'WarCrySkill': '鼓舞', 'LavaSkill': '溶岩', 'EruptionSkill': '噴火',
            'FlameDashSkill': '炎走', 'MeteorSkill': '隕石', 'PiercingArrowSkill': '貫通矢',
            'MirrorSkill': '反転', 'WarpArrowSkill': 'ワープ', 'ArrowRainSkill': '矢の雨',
            'PinningArrowSkill': '拘束矢', 'JavelinThrowSkill': '投槍',
            'VaultingStrikeSkill': '跳撃', 'RapidThrustsSkill': '連撃槍',
            'SweepingStrikeSkill': 'なぎ払い', 'DragonDiveSkill': '竜降下',
            'RisingStrikeSkill': '昇撃', 'DashStrikeSkill': '瞬撃',
            'EnhancedFireSkill': '拡散炎', 'FireSkill': '火球', 'IceSkill': '氷結',
            'DashSkill': 'ダッシュ', 'GravitySkill': '重力',
            'PounceSkill': '飛びかかり', 'ScaleProjectileSkill': '鱗赫',
            'RoarSkill': '咆哮', 'AmpuleSkill': 'アンプル', 'RampageSkill': '暴走',
        }
        skill_keys = ['J', 'K', 'L', 'N', 'M']
        # UI用にスキル名を日本語で表示（クラス変数でキャッシュして毎フレームの負荷を軽減）
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
        # UI用にスキル位置を自動調整
        for i, s in enumerate(self.skills):
            s.x = 15 + i * 60
            s.y = 15
            s.draw(screen)
            # キーと名前の表示
            if i < len(skill_keys):
                ks = font_sm.render(skill_keys[i], True, (255, 255, 0))
                screen.blit(ks, (s.x + 2, s.y - 14))
            
            cls_name = type(s).__name__
            disp_name = SKILL_NAMES.get(cls_name, cls_name.replace('Skill', ''))
            ns = font_sm.render(disp_name, True, (255, 255, 255))
            screen.blit(ns, (s.x, s.y + 52))

    def update_timers(self): pass
    def get_max_hp(self): return 10
    def get_speed(self): return 1.2
    def get_jump_power(self): return -15

    def generate_upgrades(self):
        """ウェーブクリア後の報酬（ステータスUPや新スキル）を3つ生成します"""
        # ステータスアップ項目のプール
        pool = [
            {"type": "heal", "name": "HP Recovery", "desc": "Restore 5 HP"},
            {"type": "maxhp", "name": "Max HP Increase", "desc": "Max HP +3, Restore 3 HP"},
            {"type": "jump", "name": "Extra Jump", "desc": "Gain +1 extra jump in the air"},
            {"type": "attack", "name": "Attack Power UP", "desc": "Increase base damage by +1"},
            {"type": "defense", "name": "Defense Power UP", "desc": "Reduce incoming damage by 1"},
            {"type": "speed", "name": "Movement Speed UP", "desc": "Increase move speed by 20%"},
            {"type": "cd", "name": "Cooldown Reduction", "desc": "Increase skill cooldown speed by 20%"}
        ]
        
        # main.py内で定義されている全スキルクラス
        all_skills_classes = [MagicSwordSkill, ThunderSkill, IceEnchantSkill, FireEnchantSkill, BraveChargeSkill,
                              HammerThrowSkill, SuperArmorSkill, EarthquakeSkill, WarCrySkill,
                              LavaSkill, EruptionSkill, FlameDashSkill, MeteorSkill,
                              PiercingArrowSkill, MirrorSkill, WarpArrowSkill, ArrowRainSkill, PinningArrowSkill,
                              JavelinThrowSkill, VaultingStrikeSkill, RapidThrustsSkill, SweepingStrikeSkill, DragonDiveSkill,
                              RisingStrikeSkill, DashStrikeSkill, EnhancedFireSkill]
                              
        # 既に持っているスキルを除外して候補を作成
        my_skill_types = [type(s) for s in self.skills]
        unacquired = [s for s in all_skills_classes if s not in my_skill_types]
        random.shuffle(unacquired)
        
        # 未修得スキルを最大2つまで報酬候補に加える
        for i in range(min(2, len(unacquired))): 
            name = unacquired[i].__name__.replace("Skill", "")
            pool.append({"type": "skill", "name": "[New Skill]", "desc": f"Learn the skill '{name}'", "skill_class": unacquired[i]})
            
        # プールからランダムに選択して保持
        self.current_upgrades = random.sample(pool, min(self.upgrade_slots, len(pool)))

    def apply_upgrade(self, upgrade):
        """選択された報酬をプレイヤーに適用します。スキル枠がいっぱいなら入れ替え画面へ遷移します。"""
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
            # 新しいスキルのインスタンスを作成（表示位置は仮）
            new_skill = upgrade["skill_class"](0, 15)
            if len(self.skills) < self.max_skills:
                # 所持上限未満なら即時習得
                self.skills.append(new_skill)
            else:
                # 5枠埋まっている場合は入れ替え待機状態にする
                self.queued_skill = new_skill
                game_state = STATE_REPLACE_SKILL
                return False # 特例：次ウェーブに進まず入れ替え入力を待つ
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
            self.active_timer = 90 # 1.5秒間持続
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
                        e.take_damage(1 + self.damage_bonus, self.source_facing, element='fire') # 毎フレーム判定なので低威力
    def draw_effect(self, screen):
        if self.active_timer > 0:
            # 揺らめく炎の柱
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
        self.flames = [] # [x, y, timer, facing]
        self.active_timer = 0
        self.player_ref = None
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            self.active_timer = 40 # 40フレーム持続
            self.player_ref = player
            player.vy = -5
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        
        p = player if player else self.player_ref
        if self.active_timer > 0 and p:
            self.active_timer -= 1
            # 速度を固定＆無敵を付与
            p.vx = 20 * p.facing
            p.invincible_timer = max(p.invincible_timer, 2)
            # 3フレームに1回炎を落とす
            if self.active_timer % 3 == 0:
                self.flames.append([p.x, p.y, 75, p.facing])
                
        for f in self.flames[:]:
            f[2] -= 1
            if enemies:
                f_rect = pygame.Rect(f[0], f[1], 40, 40)
                for e in enemies:
                    if e.hp > 0 and f_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                        e.burn_timer = 180
                        e.take_damage(1 + self.damage_bonus, f[3] if len(f)>3 else 1, status_effect=True, element='fire')
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
            if m[1] >= ground: # 着弾
                if enemies:
                    # 攻撃範囲を2倍に (300 -> 600)
                    blast_rect = pygame.Rect(m[0] - 300, ground - 100, 600, 100)
                    for e in enemies:
                        if e.hp > 0 and blast_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            # 衝撃波の向き
                            sf = 1 if e.x > m[0] else -1
                            e.take_damage(12 + self.damage_bonus, sf, element='fire')
                            e.burn_timer = 180 # やけど付与
                self.meteor = None
    def draw_effect(self, screen):
        if self.meteor:
            m = self.meteor
            pygame.draw.circle(screen, (255, 100, 0), (int(m[0]), int(m[1])), 80) # 少し大きく
            pygame.draw.circle(screen, (255, 200, 50), (int(m[0]), int(m[1])), 50) # 少し大きく
            # 範囲表示を600幅に
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
        return 15 # HP高い
    def get_speed(self):
        return 0.8 # 足遅い
    def get_jump_power(self):
        return -12 # ジャンプ低い

    def handle_event(self, event, enemies):
        """戦士の入力イベント処理（基本攻撃とスキルの個別発動）"""
        super().handle_event(event, enemies) # J,K,L,N,Mキーの共通処理
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack'] and self.hammering == 0:
                self.hammering = 20 # 打撃の振り下ろしフレーム（15から10へ高速化）
                self.hit_enemies = []
            if (event.key == key_config['jump']) and (self.player.y >= ground or self.player.jumpcount > 0):
                self.player.vy = self.player.jump_power
                self.player.jumpcount -= 1
            # 固有スキルの個別発動（キー設定から取得）- 通常モードのみ
            if not self.is_reincarnator_mode:
                if event.key == key_config['skill_1']: self.skill_throw.activate(self.player, enemies)
                if event.key == key_config['skill_2']: self.skill_armor.activate(self.player, enemies)
                if event.key == key_config['skill_3']: self.skill_brave_charge.activate(self.player, enemies)
                if event.key == key_config['skill_4']: self.skill_earthquake.activate(self.player, enemies)
                if event.key == key_config['skill_5']: self.skill_warcry.activate(self.player, enemies)

    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)
        
        # ハンマーの当たり判定処理
        if self.hammering > 0:
            self.hammering -= 1
            if self.hammering < 6: # 10フレーム中、後半の6フレームで判定発生
                hx = self.player.x + (60 * self.player.facing)
                hy = self.player.y + 20
                if enemies:
                    hammer_rect = pygame.Rect(hx - 50, hy - 50, 100, 100)
                    for e in enemies:
                        if e.hp > 0 and e not in self.hit_enemies and hammer_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            if e.take_damage(4 * self.player.damage_multiplier, self.player.facing, knockback_x=12, knockback_y=-8, element='heavy'): # 高威力, 大きく吹き飛ばし
                                self.hit_enemies.append(e)

    def draw_effects(self, screen):
        super().draw_effects(screen)
        
        # ハンマーの描画 (かっこよく)
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
            
            # 残像
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
    """炎の魔術師：遠距離からの火球攻撃と、広範囲の炎スキルを得意とする"""
    def __init__(self, player):
        super().__init__(player)
        self.skill_lava = LavaSkill(15, 15)
        self.skill_enhanced = EnhancedFireSkill(75, 15)
        self.skill_eruption = EruptionSkill(135, 15)
        self.skill_flamedash = FlameDashSkill(195, 15)
        self.skill_meteor = MeteorSkill(255, 15)
        self.skills = [self.skill_lava, self.skill_enhanced, self.skill_eruption, self.skill_flamedash, self.skill_meteor]
        self.fireballs = [] # 現在画面上にある通常攻撃の火球

    def get_max_hp(self):
        return 7 # 低耐久
    def get_speed(self):
        return 1.1
    def get_jump_power(self):
        return -14

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack']:
                # 通常攻撃：ファイアボール
                vx = 20 * self.player.facing
                self.fireballs.append([self.player.x + 20, self.player.y + 20, vx, 40, self.player.facing]) # Add player.facing
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
        # 火の玉の更新
        for fb in self.fireballs[:]:
            fb[0] += fb[2]
            fb[3] -= 1
            hit = False
            if enemies:
                for e in enemies:
                    if e.hp > 0 and e.x < fb[0] < e.x + e.width and e.y < fb[1] < e.y + e.height:
                        if e.take_damage(1, fb[4], element='fire'): # Use fireball's facing
                            hit = True
                            break
            if hit or fb[3] <= 0:
                self.fireballs.remove(fb)
                
        # FlameDashの軌跡追加
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
            vx = 35 * player.facing # 高速
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
                        if e.take_damage(4 + self.damage_bonus, j[5]): # 貫通
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
            player.vy = -20 # 斜めジャンプ
            player.invincible_timer = 20
            self.active_timer = 30 # 空中での受付時間
            self.player_ref = player
            self.source_facing = player.facing
            return True
        return False
    def update(self, enemies=None, cooldown_speed=1, player=None):
        super().update(enemies, cooldown_speed)
        if self.active_timer > 0:
            self.active_timer -= 1
            if self.player_ref.y >= ground - 10: # 着地時
                self.active_timer = 0
                if enemies: # 衝撃波
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
            self.active_timer = 60 # 1秒間連撃
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
            if self.active_timer % 6 == 0: # ヒット間隔を短く(10->6)
                if enemies and self.player_ref:
                    hx = self.player_ref.x + (20 if self.player_ref.facing == 1 else -160)
                    hitbox = pygame.Rect(hx, self.player_ref.y + 10, 180, 30) # 当たり判定拡大
                    for e in enemies:
                        if e.hp > 0 and hitbox.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(1 + self.damage_bonus, self.source_facing)
                            # 吸い込み効果
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
            self.player_ref.vx = 0 # 真上に上がる
            if self.player_ref.vy > -5: # 上昇終了間近
                self.phase = 2
                self.player_ref.vy = 50 # ダイブ速度
        elif self.phase == 2:
            # 急降下中に左右操作可能
            keys = pygame.key.get_pressed()
            move_speed = 10
            if keys[key_config['move_left']]:
                self.player_ref.x -= move_speed
            if keys[key_config['move_right']]:
                self.player_ref.x += move_speed
                
            if self.player_ref.y >= ground:
                self.phase = 0
                if enemies:
                    # 地面衝突時に周囲にダメージ
                    blast = pygame.Rect(self.player_ref.x - 120, self.player_ref.y - 60, 280, 110)
                    for e in enemies:
                        if e.hp > 0 and blast.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(10 + self.damage_bonus, self.source_facing, knockback_y=-15, element='heavy')
    def draw_effect(self, screen):
        if (self.phase == 1 or self.phase == 2) and hasattr(self, 'player_ref') and self.player_ref:
            pygame.draw.circle(screen, (100, 255, 255), (int(self.player_ref.x+20), int(self.player_ref.y+20)), 25)
            pygame.draw.polygon(screen, (50, 200, 200), [(self.player_ref.x+20, self.player_ref.y-20), (self.player_ref.x+50, self.player_ref.y+50), (self.player_ref.x-10, self.player_ref.y+50)])

class Lancer(Character):
    """槍使い：中距離からの強力な突き攻撃と、機動力を活かしたスキルを持つ"""
    def __init__(self, player):
        super().__init__(player)
        self.skill_javelin = JavelinThrowSkill(15, 15)
        self.skill_vault = VaultingStrikeSkill(75, 15)
        self.skill_rapid = RapidThrustsSkill(135, 15)
        self.skill_sweep = SweepingStrikeSkill(195, 15)
        self.skill_dragondive = DragonDiveSkill(255, 15)
        self.skills = [self.skill_javelin, self.skill_vault, self.skill_rapid, self.skill_sweep, self.skill_dragondive]
        self.thrusting = 0 # 突き攻撃の持続タイマー
        self.hit_enemies = []

    def get_max_hp(self):
        return 12
    def get_speed(self):
        return 1.3
    def get_jump_power(self):
        return -18

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack'] and self.thrusting == 0:
                self.thrusting = 15 # 高速突き
                self.hit_enemies = []
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
        
        # 槍突きの判定
        if self.thrusting > 0:
            self.thrusting -= 1
            if self.thrusting == 10: # 発生フレーム
                hx = self.player.x + (20 if self.player.facing == 1 else -140)
                hy = self.player.y + 20
                if enemies:
                    spear_rect = pygame.Rect(hx, hy - 5, 160, 10) # 非常に長い
                    for e in enemies:
                        if e.hp > 0 and e not in self.hit_enemies and spear_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            if e.take_damage(2, self.player.facing, knockback_x=4): # 軽くノックバック
                                self.hit_enemies.append(e)

    def draw_effects(self, screen):
        super().draw_effects(screen)
        
        # 槍攻撃の描画 (かっこよく)
        if self.thrusting > 0:
            px = self.player.x + 20
            py = self.player.y + 20
            progress = (15 - self.thrusting) / 15.0
            reach = 180 * math.sin(progress * math.pi) # 突き出して戻る
            
            # 白い残像ライン
            pygame.draw.line(screen, (255, 255, 255), (px, py), (px + (reach + 20) * self.player.facing, py), 6)
            pygame.draw.line(screen, (100, 200, 255), (px, py), (px + reach * self.player.facing, py), 12)
            
            # 穂先のフラッシュ
            if 5 < self.thrusting < 12:
                flash_surf = pygame.Surface((60, 20), pygame.SRCALPHA)
                pygame.draw.ellipse(flash_surf, (255, 255, 255, 180), (0, 0, 60, 20))
                screen.blit(flash_surf, (px + (reach - 30) * self.player.facing if self.player.facing == 1 else px - reach - 30, py - 10))

class Swordsman(Character):
    """剣士：最も標準的なキャラクター。近接攻撃と移動スキルのバランスが良い"""
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
            if event.key == key_config['attack']:
                self.player.swording = 12
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
            
        # 固有スキルの更新（重力などプレイヤー全体に影響するもの）
        if self.skill_gravity in self.skills and self.skill_gravity.range > 0:
            # Player.update側で重力軽減が処理されているが、ここでも補足可能
            pass

    def draw_effects(self, screen):
        super().draw_effects(screen)

class Archer(Character):
    """弓兵：遠距離攻撃に特化。配置型のボムや、軌道を操る矢のスキルを持つ"""
    def __init__(self, player):
        super().__init__(player)
        self.skill_pierce = PiercingArrowSkill(15, 15)
        self.skill_mirror = MirrorSkill(75, 15)
        self.skill_warp = WarpArrowSkill(135, 15)
        self.skill_rain = ArrowRainSkill(195, 15)
        self.skill_pin = PinningArrowSkill(255, 15)
        self.skills = [self.skill_pierce, self.skill_mirror, self.skill_warp, self.skill_rain, self.skill_pin]
        self.bombs = [] # 画面上に置かれたボムのリスト

    def get_max_hp(self):
        return 10
    def get_speed(self):
        return 1.2
    def get_jump_power(self):
        return -15

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack']:
                # ボム攻撃 (クールタイムなしだが同時存在数制限など設けても良い)
                bx = self.player.x + 60 * self.player.facing
                by = self.player.y + 20
                self.bombs.append([bx, by, 15, self.player.facing]) # 15フレームの爆発
            
            # PiercingArrowのエイム中処理（スキルを所持している場合）
            pierce_skill = next((s for s in self.skills if isinstance(s, PiercingArrowSkill)), None)
            if pierce_skill and pierce_skill.aiming:
                if event.key == key_config['skill_1']: 
                    pierce_skill.activate(self.player, enemies) # 発射
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
        
        # ボムの更新と爆発判定
        for b in self.bombs[:]:
            b[2] -= 1 # タイマー減少
            if b[2] <= 0:
                # 爆発
                if enemies:
                    blast_rect = pygame.Rect(b[0] - 60, b[1] - 40, 120, 80)
                    for e in enemies:
                        if e.hp > 0 and blast_rect.colliderect(pygame.Rect(e.x, e.y, e.width, e.height)):
                            e.take_damage(4, b[3], element='fire') # ダメージ調整
                self.bombs.remove(b)

    def draw_effects(self, screen):
        super().draw_effects(screen)
        # ボムと爆発の描画
        for b in self.bombs:
            if b[2] > 5: # 設置中
                pygame.draw.circle(screen, (30, 30, 30), (int(b[0]), int(b[1])), 10) # 色を濃く
                pygame.draw.circle(screen, (255, 50, 50), (int(b[0]), int(b[1])), 5)
            else: # 爆発
                # 爆発エフェクトを派手に
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

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack']:
                self.player.swording = 12
                # MagicSword発動中なら魔法波を射出
                ms_skill = next((s for s in self.skills if isinstance(s, MagicSwordSkill)), None)
                if ms_skill and ms_skill.active_timer > 0:
                    ms_skill.launch_wave(self.player)
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
        # 基底クラスのon_sword_hit（self.skillsリストからエンチャントを汎用検出）
        super().on_sword_hit(enemy, source_facing)
            
    def update(self, keys, enemies, cooldown_speed):
        super().update(keys, enemies, cooldown_speed)

    def draw_effects(self, screen):
        super().draw_effects(screen)


# --- 怪物β スキル定義 ---
class PounceSkill(Skill):
    """飛びかかり: ダッシュ攻撃。暴走中はHP吸収"""
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
                                    # ▼調整用: 暴走中ダッシュ攻撃の回復量
                                    heal_amount = 1
                                    player.hp = min(player.max_hp, player.hp + heal_amount)
    def draw_effect(self, screen):
        pass

class ScaleProjectileSkill(Skill):
    """鱗赫: 飛び道具。暴走中は貫通"""
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
    """咆哮: 周囲にスタン + 小ダメージ"""
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
    """アンプル投与: 自傷 + バフスタック"""
    def __init__(self, x, y):
        super().__init__(x, y, 120, (100, 200, 100), (50, 100, 50))
    def activate(self, player, enemies=None):
        # 残りHPが1以下の場合は自傷できないため発動不可
        if player.hp <= 1:
            return False
            
        if super().activate(player, enemies):
            # ▼調整用: アンプル投与時の自傷ダメージ量（現在は最大HPの10%、最低1）
            self_dmg = max(1, player.max_hp // 10)
            
            player.hp -= self_dmg
            if player.hp < 1: player.hp = 1
            player._ampule_count = getattr(player, '_ampule_count', 0) + 1
            return True
        return False

class RampageSkill(Skill):
    """暴走: アンプル数に応じて全ステ強化"""
    def __init__(self, x, y):
        super().__init__(x, y, 300, (200, 30, 30), (100, 15, 15))
        self.active_timer = 0
    def activate(self, player, enemies=None):
        if super().activate(player, enemies):
            amps = getattr(player, '_ampule_count', 0)
            
            # ▼調整用: 暴走の持続時間（1秒＝60フレーム。基本180 + アンプル数×30）
            base_duration = 180
            duration_per_ampule = 30
            self.active_timer = base_duration + amps * duration_per_ampule
            self.initial_duration = self.active_timer
            
            player._monster_rampage = self.active_timer
            
            # 暴走発動時にアンプルを半分消費する（切り捨て）
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
    怪物β: アンプル（自己強化アイテム）と暴走状態を組み合わせて戦う特殊な獣型キャラクター。
    """
    def __init__(self, player):
        super().__init__(player)
        # スキルの初期化（アイコン位置を指定）
        self.skill_pounce = PounceSkill(15, 15)
        self.skill_scale = ScaleProjectileSkill(75, 15)
        self.skill_roar = RoarSkill(135, 15)
        self.skill_ampule = AmpuleSkill(195, 15)
        self.skill_rampage = RampageSkill(255, 15)
        # 基底クラスの所持リストに登録
        self.skills = [self.skill_pounce, self.skill_scale, self.skill_roar, self.skill_ampule, self.skill_rampage]
        self.scratch_timer = 0  # 近接攻撃の持続タイマー
        self.hit_enemies = []   # 1回の攻撃でヒット済みの敵リスト
        player._ampule_count = 0     # アンプルの所持数（プレイヤー変数に保持）
        player._monster_rampage = 0  # 暴走タイマー

    def get_max_hp(self): return 12
    def get_speed(self): return 1.5
    def get_jump_power(self): return -16

    def handle_event(self, event, enemies):
        super().handle_event(event, enemies)
        if event.type == pygame.KEYDOWN:
            if event.key == key_config['attack'] and self.scratch_timer == 0:
                self.scratch_timer = 8
                self.hit_enemies = []
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
            # プレイヤー自体を赤く染める
            shade = pygame.Surface((p.width, p.height), pygame.SRCALPHA)
            shade.fill((200, 0, 0, 120))
            screen.blit(shade, (int(p.x), int(p.y)))
            
            # 光る赤い目
            eye_y = int(p.y + 12)
            eye_x = int(p.x + p.width/2 + 10 * p.facing)
            pygame.draw.circle(screen, (255, 0, 0), (eye_x, eye_y), 5)
            pygame.draw.circle(screen, (255, 255, 100), (eye_x, eye_y), 2)
            
            # 荒々しいオーラ
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.015)) * 50
            aura_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            aura_color = (200 + int(pulse), 20, 20, 60 + int(pulse))
            pygame.draw.ellipse(aura_surf, aura_color, (0, 0, 100, 100))
            screen.blit(aura_surf, (int(p.x - 30), int(p.y - 30)))
        
        if amps > 0:
            # アンプル数アイコン表示
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
                # 緑色のアンプル
                pygame.draw.rect(screen, (50, 220, 50), (ix, start_y, icon_w, icon_h))
                # アンプルのフタ（白）
                pygame.draw.rect(screen, (255, 255, 255), (ix, start_y, icon_w, 2))

# --- プレイヤー クラス定義 ---
class Player:
    """
    プレイヤーの物理挙動、描画、キャラクター（クラス）の管理を行う。
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
        self.swording = 0             # 短距離攻撃（剣）の持続タイマー
        self.sword_length = 120
        self.hp = 10
        self.max_hp = 10
        self.defense = 0
        self.bonus_damage = 0         # アップグレードによる追加ダメージ
        self.cooldown_speed_mult = 1.0 # クールタイム短縮倍率
        self.hit_timer = 0            # 被弾時のノックバック/点滅タイマー

        self.character = None         # 現在使用中のキャラクタークラスのインスタンス
        self.invincible_timer = 0     # 無敵タイマー
        self.reincarnator_mode = False # キャラ選択時の設定保持用
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
        if keys[key_config['move_left']]:
            self.ax = -self.move_speed
            self.facing = -1
        if keys[key_config['move_right']]:
            self.ax = self.move_speed
            self.facing = 1

        self.vx += self.ax
        self.vx *= self.friction
        
        # 重力スキルのチェック
        gravity_active = False
        if self.character:
            for s in self.character.skills:
                if type(s).__name__ == "GravitySkill" and getattr(s, 'range', 0) > 0:
                    gravity_active = True
                    break
        elif self.skill_g.range > 0:
            gravity_active = True

        current_ay = 0.3 if gravity_active else 0.8
        self.vy += current_ay

        self.x += self.vx
        self.y += self.vy

        # スキルアップデート
        cooldown_speed = 1.0 * self.cooldown_speed_mult
        if self.character:
            self.character.update(keys, enemies, cooldown_speed)
        
        if game_state == STATE_LOBBY:
            for s in self.skills: s.update(enemies)

        # ダッシュスキルのチェック
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

        # 一方通行足場判定 (下からはすり抜けられる)
        if self.vy > 0:  # 落下中のみ
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
        if self.character: self.character.update_timers()

    def take_damage(self, amount, source_facing=1):
        if self.invincible_timer > 0: return False
        if self.hit_timer == 0:
            amount = max(0, amount - self.defense) # 防御力で軽減 (0ダメージも許容)
            if amount <= 0:
                self.hit_timer = 10 # 短い無敵で連続判定防止
                return False # ダメージ0なのでノーダメ
            self.hp -= amount
            self.hit_timer = 40
            self.vx = source_facing * 10 # ノックバック
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
        self.timer = 180 # 3秒で消滅
        self.damage = damage

    def update(self, player):
        self.x += self.vx
        self.y += self.vy
        self.timer -= 1
        
        # 当たり判定
        if player.x <= self.x <= player.x + 40 and player.y <= self.y <= player.y + 40:
            if player.take_damage(self.damage, 1 if self.vx > 0 else -1):
                return True # 当たった
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
                self.y = ground - self.height # 地面に揃える
            return
            
        if self.hit_timer > 0: self.hit_timer -= 1
        
        # 状態異常の更新
        if self.frozen_timer > 0:
            self.frozen_timer -= 1
            # 凍結中は物理と行動をスキップ
            if self.y < ground - self.height: self.vy += 1
            self.y += self.vy
            self.x += self.vx
            self.vx *= 0.9
            if self.y > ground - self.height: self.y = ground - self.height; self.vy = 0
            # 画面外への脱走を防止
            if self.x < 0:
                self.x = 0
                self.vx *= -0.5
            elif self.x > width - self.width:
                self.x = width - self.width
                self.vx *= -0.5
            return

        if self.burn_timer > 0:
            self.burn_timer -= 1
            if self.burn_timer % 60 == 0: # 1秒ごとにダメージ
                self.take_damage(1, status_effect=True)

        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        # READY中は動かない、ダメージも与えない
        if wave_start_wait_timer > 0:
            return

        self._update_physics()
        if self.hp > 0: self._update_behavior(player)
        
        # 画面外への脱走を防止 (共通処理)
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
        elif self.vy > 0: # 落下中のみ速度0にして接地させる
            self.vy = 0
            self.y = ground - self.height
        
        self.y += self.vy
        self.x += self.vx
        self.vx *= 0.9
        
        # 一方通行足場判定 (地上敵のみ)
        if self.enemy_type != 'pink' and self.vy > 0:
            foot_y = self.y + self.height
            prev_foot_y = foot_y - self.vy
            if prev_foot_y <= PLATFORM_Y and foot_y >= PLATFORM_Y:
                if PLATFORM_X <= self.x + self.width and self.x <= PLATFORM_X + PLATFORM_W:
                    self.y = PLATFORM_Y - self.height
                    self.vy = 0

    def _update_behavior(self, player):
        pass

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None):
        if self.hp <= 0: return False
        
        # 属性シナジー
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
            
        if self.hit_timer > 0: return False
        
        if self.frozen_timer > 0:
            # 凍結中はノックバックしない
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
            # 召喚エフェクト
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
            draw_color = (150, 200, 255) # 凍結中は青白く
        elif self.burn_timer > 0:
            if (self.burn_timer // 10) % 2 == 0:
                draw_color = (255, 100, 0)
        
        pygame.draw.rect(screen, draw_color, (int(self.x), int(self.y), self.width, self.height))
        
        # 炎エフェクト
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
        # 地面固定
        self.vy = 0
        self.y = ground - self.height
        self.x += self.vx
        self.vx *= 0.92 # ユーザー調整済み
        
        # 画面外への脱走を防止
        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5
    def _update_behavior(self, player):
        # 左右のパトロール挙動 (画面端で反転)
        if self.x <= 0:
            self.facing = 1
        elif self.x >= width - self.width:
            self.facing = -1
        
        # プレイヤーとの距離を確認
        dist = math.hypot(player.x - self.x, player.y - self.y)
        
        # 接近時に突進 (クールタイム時のみ)
        if dist < 300 and self.attack_cooldown <= 0:
            dash_dir = 1 if player.x > self.x else -1
            self.vx = dash_dir * 35 # 28 -> 35
            self.attack_cooldown = random.randint(120, 240)
            self.facing = dash_dir # 突進方向に顔を向ける
        
        # 通常時は一定速度で移動 (突進中=vxが大きい時はそちらの物理挙動に任せる)
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing
        
        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

class PinkEnemy(Enemy):
    def __init__(self, x, y, hp=2, attack_damage=1):
        super().__init__(x, y, hp, (255, 100, 200), 'pink', attack_damage)
        self.float_y = y

    def _update_physics(self):
        self.x += self.vx
        self.vx *= 0.92 # ユーザー調整済み
        
        # 画面外への脱走を防止
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
        # 左右のパトロール挙動 (画面端で反転)
        if self.x <= 0:
            self.facing = 1
        elif self.x >= width - self.width:
            self.facing = -1

        # プレイヤーとの距離を確認
        dist = math.hypot(player.x - self.x, player.y - self.y)

        if self.attack_cooldown <= 0:
            if dist < 400 and random.random() < 0.3: # 接近時のみ低確率ダッシュ
                dash_dir = 1 if player.x > self.x else -1
                self.vx = dash_dir * 30 # 22 -> 30
                self.facing = dash_dir
            else: # それ以外は少し離れた空から積極的に射撃
                angle = math.atan2(player.y - self.y, player.x - self.x)
                enemy_bullets.append(EnemyBullet(self.x + 12, self.y + 12, angle, self.attack_damage))
            self.attack_cooldown = random.randint(90, 160) # 間隔をさらに短く
        
        # 通常時は一定速度で移動
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
        # 重力適用
        if self.y < ground - self.height:
            self.vy += 0.8
            self.is_jumping = True
        elif self.vy > 0: # 落下中のみ
            self.vy = 0
            self.y = ground - self.height
            if self.is_jumping:
                self.vx = 0 # 着地時に横移動を止める
                self.is_jumping = False
        
        self.y += self.vy
        self.x += self.vx
        
        # 画面外への脱走を防止
        if self.x < 0:
            self.x = 0
            self.vx *= -0.5
        elif self.x > width - self.width:
            self.x = width - self.width
            self.vx *= -0.5

    def _update_behavior(self, player):
        # 地面にいて攻撃可能ならプレイヤーに向かってジャンプ
        if not self.is_jumping and self.attack_cooldown <= 0:
            dx = player.x - self.x
            self.vy = self.jump_power
            # 距離に応じて横軸速度を調整（少し手前に飛ぶように）
            self.vx = dx * 0.05
            self.attack_cooldown = random.randint(120, 180)
            self.is_jumping = True
        
        # 通常時のパトロール（ジャンプしていない時のみ）
        if not self.is_jumping:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            self.x += self.speed * 0.5 * self.facing

        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

class ShieldEnemy(Enemy):
    """盾持ち: 正面からのダメージを50%軽減"""
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
        # 常にプレイヤーに正面を向ける
        self.facing = 1 if player.x > self.x else -1
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing
        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None):
        # 正面（facing方向）からの攻撃はダメージ半減
        if not status_effect and source_facing == self.facing:
            damage = max(1, damage // 2)
            knockback_x = max(1, knockback_x // 2)
        return super().take_damage(damage, source_facing, knockback_x, knockback_y, status_effect, element)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # 盾を描画
        shield_x = self.x + (self.width if self.facing == 1 else -10)
        shield_color = (200, 100, 200) if self.frozen_timer <= 0 else (150, 200, 255)
        pygame.draw.rect(screen, shield_color, (int(shield_x), int(self.y + 5), 10, 30))

class HealerEnemy(Enemy):
    """回復役: 周囲の敵を定期的に回復する"""
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
        # プレイヤーから距離を取る
        if dist < 200:
            flee_dir = -1 if player.x > self.x else 1
            if abs(self.vx) < 3: self.x += self.speed * 2 * flee_dir
            self.facing = flee_dir
        else:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            if abs(self.vx) < 3: self.x += self.speed * self.facing
        # 回復行動
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
        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # 十字マークを描画
        cx, cy = int(self.x + self.width // 2), int(self.y + self.height // 2)
        pygame.draw.line(screen, (255, 255, 255), (cx - 8, cy), (cx + 8, cy), 3)
        pygame.draw.line(screen, (255, 255, 255), (cx, cy - 8), (cx, cy + 8), 3)
        # 回復エフェクト
        if self.heal_effect_timer > 0:
            radius = int((30 - self.heal_effect_timer) * 7)
            if radius > 0:
                surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
                alpha = int(self.heal_effect_timer / 30 * 150)
                pygame.draw.circle(surf, (100, 255, 100, alpha), (radius + 1, radius + 1), radius, 3)
                screen.blit(surf, (cx - radius - 1, cy - radius - 1))

class BomberEnemy(Enemy):
    """自爆型: 倒されると爆発し範囲ダメージ"""
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
        # プレイヤーに向かって高速突進
        self.facing = 1 if player.x > self.x else -1
        if abs(self.vx) < 3:
            self.x += self.speed * self.facing
        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def _spawn_debris(self):
        super()._spawn_debris()
        self.exploded = True
        self.explosion_timer = 20

    def explode(self, target_player):
        """爆発処理: プレイヤーと周囲の敵にダメージ"""
        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        # プレイヤーへのダメージ
        pdist = math.hypot(target_player.x + 20 - cx, target_player.y + 20 - cy)
        if pdist < self.explosion_radius:
            sf = 1 if target_player.x > cx else -1
            target_player.take_damage(self.explosion_damage, sf)
        # 周囲の敵へのダメージ
        for e in enemies:
            if e is self or e.hp <= 0: continue
            edist = math.hypot(e.x + e.width // 2 - cx, e.y + e.height // 2 - cy)
            if edist < self.explosion_radius:
                sf = 1 if e.x > cx else -1
                e.take_damage(self.explosion_damage, sf, status_effect=True, element='fire')
        # 大量の破片
        for _ in range(20):
            self.debris_particles.append({
                'x': cx + random.randint(-20, 20), 'y': cy + random.randint(-20, 20),
                'vx': random.uniform(-12, 12), 'vy': random.uniform(-20, -5),
                'timer': random.randint(60, 120), 'color': (255, random.randint(100, 200), 0)
            })

    def draw(self, screen):
        if self.explosion_timer > 0:
            # 爆発エフェクト
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
        # 点滅する警告マーク
        if (pygame.time.get_ticks() // 300) % 2 == 0:
            cx = int(self.x + self.width // 2)
            cy = int(self.y + 5)
            pygame.draw.polygon(screen, (255, 255, 0), [(cx, cy - 5), (cx - 4, cy + 5), (cx + 4, cy + 5)])

class SniperEnemy(Enemy):
    """狙撃型: 遠距離から予告線付きの高威力弾"""
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
        # プレイヤーから距離を取る
        if dist < 300:
            flee_dir = -1 if player.x > self.x else 1
            if abs(self.vx) < 3: self.x += self.speed * 2 * flee_dir
        elif abs(self.vx) < 3:
            if self.x <= 0: self.facing = 1
            elif self.x >= width - self.width: self.facing = -1
            self.x += self.speed * 0.5 * self.facing
        # 狙撃: 予告 → 射撃の2段階
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
        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def draw(self, screen):
        super().draw(screen)
        if self.spawn_timer > 0 or self.hp <= 0: return
        # 予告線（レーザーサイト）
        if self.aim_timer > 0:
            sx, sy = int(self.x + 20), int(self.y + 20)
            ex = sx + int(math.cos(self.aim_angle) * 600)
            ey = sy + int(math.sin(self.aim_angle) * 600)
            blink = self.aim_timer % 6 < 3
            color = (255, 0, 0) if blink else (200, 50, 50)
            pygame.draw.line(screen, color, (sx, sy), (ex, ey), 2)
        # 照準マーク
        cx = int(self.x + self.width // 2)
        cy = int(self.y + self.height // 2)
        pygame.draw.circle(screen, (255, 255, 100), (cx, cy), 4)

class BlockGolemBoss(Enemy):
    """
    Wave 5ごとに出現する巨大ボス。
    HPが高く、ジャンププレス、拡散弾、防御シールドを使用する。
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
        # 重力適用
        if self.y < ground - self.height:
            self.vy += 0.8
        elif self.vy > 0:
            self.vy = 0
            self.y = ground - self.height
            # 着地時に衝撃波判定
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
            # 衝撃波ダメージ（プレイヤーが地上にいる場合のみ）
            if player.y + player.height >= ground - 5:
                dist = abs((self.x + self.width // 2) - (player.x + player.width // 2))
                if dist < 300:
                    sf = 1 if player.x > self.x else -1
                    player.take_damage(self.attack_damage, sf)

        if self.action_timer > 0:
            self.action_timer -= 1
            if self.current_action == 'shoot' and self.action_timer % 20 == 0:
                # 拡散弾
                for angle in [-0.2, 0, 0.2]:
                    base_angle = math.atan2(player.y - self.y, player.x - self.x)
                    enemy_bullets.append(EnemyBullet(self.x + 50, self.y + 50, base_angle + angle, self.attack_damage))
            return

        # 次の行動を選択
        r = random.random()
        if r < 0.3: # ジャンプ
            self.current_action = 'jump'
            self.vy = -25
            self.vx = (1 if player.x > self.x else -1) * 10
            self.action_timer = 120
        elif r < 0.6: # 射撃
            self.current_action = 'shoot'
            self.action_timer = 60
        elif r < 0.8: # シールド
            self.current_action = 'shield'
            self.shield_timer = 120
            self.action_timer = 150
        else: # 移動
            self.facing = 1 if player.x > self.x else -1
            self.vx = self.facing * 5
            self.action_timer = 60

        # 接触ダメージ
        if player.x < self.x + self.width and self.x < player.x + player.width and \
           player.y < self.y + self.height and self.y < player.y + player.height:
            player.take_damage(self.attack_damage, 1 if self.x < player.x else -1)

    def take_damage(self, damage, source_facing=1, knockback_x=5, knockback_y=-3, status_effect=False, element=None):
        if self.shield_timer > 0:
            damage = max(1, damage // 5) # シールド中は80%軽減
        # ボスはノックバックしにくい
        return super().take_damage(damage, source_facing, knockback_x * 0.2, knockback_y * 0.2, status_effect, element)

    def draw(self, screen):
        if self.hp <= 0:
            super().draw(screen)
            return
        
        # ボス本体
        color = self.color
        if self.hit_timer > 0: color = (255, 255, 255)
        elif self.shield_timer > 0: color = (200, 200, 255) # 青白く光る
        
        pygame.draw.rect(screen, color, (int(self.x), int(self.y), self.width, self.height))
        # 模様
        pygame.draw.rect(screen, (0, 0, 0), (int(self.x), int(self.y), self.width, self.height), 2)
        pygame.draw.rect(screen, (0, 0, 0), (int(self.x + 20), int(self.y + 20), 60, 60), 1)
        
        # HPバー
        bar_w = 400
        bar_h = 20
        pygame.draw.rect(screen, (50, 50, 50), (width // 2 - bar_w // 2, 20, bar_w, bar_h))
        hp_ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(screen, (255, 0, 0), (width // 2 - bar_w // 2, 20, int(bar_w * hp_ratio), bar_h))
        pygame.draw.rect(screen, (255, 255, 255), (width // 2 - bar_w // 2, 20, bar_w, bar_h), 2)
        
        # 衝撃波エフェクト
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
    enemy_bullets = [] # 前のWaveの弾を消去
    
    # 転生者モードのみボスが出現するように制限
    is_reincarnMode = getattr(player.character, 'is_reincarnator_mode', False)
    
    # Boss Wave Check
    if is_reincarnMode and wave_number > 0 and wave_number % 5 == 0:
        boss_hp = 60 + (wave_number // 5 - 1) * 40 # 100+80n -> 60+40n
        boss_atk = 2 + (wave_number // 5 - 1)
        enemies.append(BlockGolemBoss(width // 2 - 50, ground - 100, hp=boss_hp, attack_damage=boss_atk))
        return

    # Wave 1 は 2体。2 Wave ごとに 1体ずつ増え、最大8体
    num_enemies = min(2 + wave_number // 2, 8)
    
    # 転生者モード以外は強化速度半減
    
    # 敵の強化計算（Wave20以降は2waveおき、Wave40以降は1waveおき）
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
        
        # Wave進行に応じて新種を追加
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
    global screen

    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.SCALED)
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
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                is_fullscreen = not is_fullscreen
            
            if game_state == STATE_LOBBY:
                player.handle_event(event, [])
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        game_state = STATE_SELECT_CHAR
                    elif event.key == pygame.K_s:
                        game_state = STATE_SETTINGS
                
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
                        
                            # Apply reincarnator mode flag to the new character
                            if player.character:
                                player.character.is_reincarnator_mode = player.reincarnator_mode

                            # プレイヤー位置などをリセットし、戦闘開始
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
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        player.reincarnator_mode = not player.reincarnator_mode
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
                                    # REPLACE 状態に遷移した（waveは入れ替え後に開始）
                                    pass
                                break
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # 報酬をスキップ
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
                            # 報酬適用
                            if i == 0: # アップグレード枠増加
                                player.character.upgrade_slots += 1
                            elif i == 1: # スキル進化
                                # TODO: スキル選択画面へ？とりあえず全スキル+3するか、ランダムか。
                                # ユーザー要望は「スキル1つ進化」なので、簡易的に所持スキルのうちランダム1つを強化
                                if player.character.skills:
                                    s = random.choice(player.character.skills)
                                    s.damage_bonus += 3
                            elif i == 2: # 英雄の加護
                                player.max_hp += 10
                                player.hp = player.max_hp
                                player.defense += 1
                            
                            start_next_wave()
                            game_state = STATE_PLAYING
                            break

            elif game_state == STATE_REPLACE_SKILL:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # 描画(200 + i * 160)と合わせた位置で判定
                    for i in range(len(player.character.skills)):
                        rect = pygame.Rect(200 + i * 160, 250, 80, 80)
                        if rect.collidepoint(mx, my):
                            # スキルを入れ替え
                            player.character.skills[i] = player.character.queued_skill
                            player.character.queued_skill = None
                            start_next_wave()
                            game_state = STATE_PLAYING
                            break
                    # キャンセルボタンなどの判定があればここに追加（今回は強制入れ替えまたは継続と想定）
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # キャンセル（入れ替えない）
                    player.character.queued_skill = None
                    start_next_wave()
                    game_state = STATE_PLAYING

            elif game_state == STATE_PLAYING:
                player.handle_event(event, enemies if wave_start_wait_timer <= 0 else [])
                if event.type == pygame.KEYDOWN:
                    if event.key == key_config['pause']:
                        game_state = STATE_PAUSED
                    if event.key == pygame.K_p and not is_combat_mode:
                        # 戦闘モード開始
                        is_combat_mode = True
                        wave_number = 0
                        start_next_wave()
                    if event.key == pygame.K_r: # 手動スポーン
                        enemies.append(Enemy(width - 100, ground))
        
            elif game_state == STATE_PAUSED:
                if event.type == pygame.KEYDOWN and event.key == key_config['pause']:
                    game_state = STATE_PLAYING
                
            elif game_state == STATE_GAMEOVER:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
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
    
        # ロジックの更新
        if game_state in [STATE_PLAYING, STATE_LOBBY]:
            if hit_stop_timer > 0:
                hit_stop_timer -= 1
            else:
                player.update_timers()
                # READY中（カウントダウン中）は、スキルに敵のリストを渡さない（＝ダメージ判定を発生させない）
                enemies_for_player = enemies if (game_state == STATE_PLAYING and wave_start_wait_timer <= 0) else []
                player.update(keys, enemies_for_player)

                if wave_start_wait_timer > 0:
                    wave_start_wait_timer -= 1

                # 衝突分離
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

                # 敵弾の更新
                for b in enemy_bullets[:]:
                    if b.update(player) or b.timer <= 0:
                        enemy_bullets.remove(b)
            
                # 全滅したら次のウェーブへ (インターバルを挟む)
                if is_combat_mode and active_enemies == 0:
                    if wave_clear_timer <= 0:
                        wave_clear_timer = 120 # 2秒間待機
                    else:
                        wave_clear_timer -= 1
                        if wave_clear_timer == 1:
                            is_reincarn = player.character and getattr(player.character, 'is_reincarnator_mode', False)
                            if is_reincarn:
                                if wave_number > 0 and wave_number % 5 == 0:
                                    # ボス撃破後の特別報酬へ
                                    game_state = STATE_BOSS_REWARD
                                    wave_clear_timer = 0
                                else:
                                    player.character.generate_upgrades()
                                    game_state = STATE_UPGRADE
                                    wave_clear_timer = 0
                            else:
                                start_next_wave()
                                wave_clear_timer = 0

        # 描画
        screen.fill((155, 155, 155))
        pygame.draw.rect(screen, (155, 200, 200), (0, ground, 2000, 100))
    
        # 足場の描画
        if game_state in [STATE_PLAYING, STATE_LOBBY]:
            pygame.draw.rect(screen, (120, 140, 160), (PLATFORM_X, PLATFORM_Y, PLATFORM_W, PLATFORM_H))
            pygame.draw.rect(screen, (180, 200, 220), (PLATFORM_X, PLATFORM_Y, PLATFORM_W, 4))
    
        # UIの描画
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

        # ロビーとセレクト画面のオーバーレイ
        if game_state == STATE_LOBBY:
            prompt_text = font_title.render("Press [ENTER] to open Character Select", True, (255, 255, 200))
            screen.blit(prompt_text, (width//2 - prompt_text.get_width()//2, 55))
            hint_text = font_settings_hint.render("Press [S] for Key Settings", True, (180, 200, 255))
            screen.blit(hint_text, (width//2 - hint_text.get_width()//2, 100))
        
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
                    for upg in player.character.current_upgrades:
                        rewards.append({"name": upg["name"], "desc": upg["desc"], "color": (200, 200, 200)})
            
            total_w = len(rewards) * card_w + (len(rewards) - 1) * spacing
            start_x = (width - total_w) // 2
            start_y = height // 2 - card_h // 2
            
            for i, r in enumerate(rewards):
                rx = start_x + i * (card_w + spacing)
                ry = start_y
                rect = pygame.Rect(rx, ry, card_w, card_h)
                
                # カード背景
                pygame.draw.rect(screen, (40, 40, 60), rect, border_radius=15)
                pygame.draw.rect(screen, r["color"], rect, 3, border_radius=15)
                
                # テキスト
                name_s = font_upgrade_name.render(r["name"], True, (255, 255, 255))
                desc_s = font_upgrade_desc.render(r["desc"], True, (200, 200, 200))
                screen.blit(name_s, (rx + 15, ry + 30))
                # 改行対応は簡易的に
                screen.blit(desc_s, (rx + 15, ry + 120))

        elif game_state == STATE_PAUSED:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            pause_text = font_main.render("PAUSED (Press 'Q' to Resume)", True, (255, 255, 255))
            screen.blit(pause_text, (width//2 - 200, height//2))

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
                {"name": "MonsterBeta", "color": (120, 30, 30), "skills": "J:Pounce K:ScaleShot\nL:Roar N:Ampule\nM:Rampage"}
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
                # スキル名の表示
                for si, skill_line in enumerate(card["skills"].split("\n")):
                    st = font_card_skill.render(skill_line, True, (220, 220, 220))
                    screen.blit(st, (cx + 10, cy + (45 if is_hovered else 55) + si * 18))

            # 転生者モードのトグル表示
            mode_text = "Reincarnator Mode: ON" if player.reincarnator_mode else "Reincarnator Mode: OFF"
            mode_color = (100, 255, 100) if player.reincarnator_mode else (150, 150, 150)
            mode_surf = font_main.render(mode_text, True, mode_color)
            hint_surf = font_settings_hint.render("Press 'R' to toggle Reincarnator Mode", True, (200, 200, 200))
            screen.blit(mode_surf, (width // 2 - mode_surf.get_width() // 2, height - 80))
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
            
            # 現在のスキルを表示
            for i, s in enumerate(player.character.skills):
                sx = 200 + i * 160
                sy = 250
                icon_rect = pygame.Rect(sx, sy, 80, 80)
                pygame.draw.rect(screen, s.color_ready, icon_rect, border_radius=5)
                pygame.draw.rect(screen, (255, 255, 255), icon_rect, 2, border_radius=5)
                
                # スキル名（クラス名から推測）
                skill_name = type(s).__name__.replace("Skill", "")
                st = font_card_skill.render(skill_name, True, (255, 255, 255))
                screen.blit(st, (sx, sy + 90))

            # 新しいスキルを表示
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
            retry_text = font_main.render("Press 'R' to Retry", True, (255, 255, 255))
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

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

asyncio.run(main())
pygame.quit()
