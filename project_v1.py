from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import random
import time
import sys

# ==========================================
# PLANET GUARDIAN 3D - ULTIMATE BOSS & LASER EDITION
# ==========================================

WINDOW_WIDTH, WINDOW_HEIGHT = 1000, 800

game_state = "MENU"
current_level = 1
score = 0
high_score = 0
coins = 0
camera_mode = "FREE"
combo_multiplier = 1.0
combo_timer = 0.0
shake_timer = 0.0
level_unlocked = 1

camera_theta = 45.0
camera_phi = 45.0
camera_dist = 600.0

planet_hp = 100
shield_hp = 0
planet_radius = 40
player_angle = 0.0
orbit_radius = 160

bullets = []
boss_bullets = []
turret_bullets = []
meteors = []
aliens = []
powerups = []
stars = []
particles = []

boss_active = False
boss_hp = 4000
boss_max_hp = 4000
boss_obj = None
boss_warning_timer = 0.0

last_time = 0
time_warp = False
spawn_timer = 0
turret_cooldown = 0
turret_rotation = 0.0

laser_timer = 0.0
laser_fire_cooldown = 0.0
homing_timer = 0.0

# Level configs
levels = {
    1: {"name": "MARS",    "color": (1.0, 0.3, 0.1), "p_rad": 40, "base_spawn": 2.5, "enemy_spd": 40},
    2: {"name": "EARTH",   "color": (0.1, 0.5, 1.0), "p_rad": 50, "base_spawn": 2.0, "enemy_spd": 60},
    3: {"name": "JUPITER", "color": (1.0, 0.6, 0.2), "p_rad": 70, "base_spawn": 1.5, "enemy_spd": 70},
}

def init_lighting():
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLightfv(GL_LIGHT0, GL_POSITION, [200.0, 200.0, 500.0, 1.0])

def generate_stars():
    global stars
    stars = [
        (random.uniform(-1500, 1500), random.uniform(-1500, 1500), random.uniform(-1500, 1500))
        for _ in range(500)
    ]

def draw_stars():
    glDisable(GL_LIGHTING)
    glBegin(GL_POINTS)
    for s in stars:
        dist = math.sqrt(s[0]**2 + s[1]**2 + s[2]**2)
        b = max(0.2, 1.0 - (dist / 2000.0))
        glColor3f(b, b, b)
        glVertex3f(s[0], s[1], s[2])
    glEnd()
    glEnable(GL_LIGHTING)

def draw_orbit(radius, r, g, b):
    glDisable(GL_LIGHTING)
    glColor3f(r, g, b)
    glBegin(GL_LINE_LOOP)
    for i in range(360):
        theta = math.radians(i)
        glVertex3f(radius * math.cos(theta), radius * math.sin(theta), 0)
    glEnd()
    glEnable(GL_LIGHTING)

def draw_text(x, y, text, r=1, g=1, b=1):
    glDisable(GL_LIGHTING)
    glColor3f(r, g, b)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for char in text:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_LIGHTING)

def draw_3d_text(x, y, text, r=1, g=1, b=1):
    glDisable(GL_LIGHTING)
    glColor3f(r, g, b)
    glRasterPos3f(x, y, 15)
    for char in text:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    glEnable(GL_LIGHTING)

def draw_sphere(radius, r, g, b, alpha=1.0):
    glColor4f(r, g, b, alpha)
    glutSolidSphere(radius, 25, 25)

def draw_cube(size, r, g, b):
    glColor3f(r, g, b)
    glutSolidCube(size)

def draw_defense_drone():
    glPushMatrix()
    glScalef(1.0, 0.5, 1.5)
    draw_cube(10, 0.6, 0.6, 0.6)
    glPopMatrix()
    glPushMatrix()
    glScalef(3.0, 0.1, 0.8)
    draw_cube(8, 0.1, 0.3, 0.9)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 7)
    draw_sphere(3, 0.0, 1.0, 1.0)
    glPopMatrix()

def draw_bomb(size):
    draw_sphere(size * 0.8, 0.15, 0.15, 0.15)
    glPushMatrix()
    glTranslatef(0, size * 0.7, 0)
    draw_cube(size * 0.4, 0.6, 0.6, 0.6)
    glPopMatrix()
    if int(time.time() * 8) % 2 == 0:
        glDisable(GL_LIGHTING)
        glPushMatrix()
        glTranslatef(0, size * 0.95, 0)
        draw_sphere(size * 0.25, 1.0, 0.0, 0.0)
        glPopMatrix()
        glEnable(GL_LIGHTING)

def draw_crystal(size, r, g, b):
    glPushMatrix()
    glDisable(GL_LIGHTING)
    glScalef(size * 0.6, size * 0.6, size)
    glColor4f(r, g, b, 1.0)
    glutSolidOctahedron()
    glEnable(GL_LIGHTING)
    glPopMatrix()

def draw_realistic_meteor(size, seed_val):
    prng = random.Random(seed_val)
    glColor3f(0.35, 0.25, 0.15)
    glutSolidSphere(size * 0.7, 15, 15)
    for _ in range(5):
        cx, cy, cz = prng.uniform(-1, 1), prng.uniform(-1, 1), prng.uniform(-1, 1)
        mag = math.sqrt(cx**2 + cy**2 + cz**2)
        if mag == 0:
            continue
        glPushMatrix()
        glTranslatef(cx/mag*(size*0.4), cy/mag*(size*0.4), cz/mag*(size*0.4))
        draw_sphere(size * 0.4, 0.25, 0.15, 0.05)
        glPopMatrix()
    glow = size * (1.1 + 0.05 * math.sin(time.time() * 15))
    glPushMatrix()
    draw_sphere(glow, 1.0, 0.4, 0.0, 0.4)
    glPopMatrix()

def draw_realistic_planet(radius, r, g, b, level):
    glPushMatrix()
    glRotatef(time.time() * 10, 0, 0, 1)  # Planet self-rotation

    if level == 1:  # MARS
        # Base reddish-brown surface
        draw_sphere(radius, 0.75, 0.25, 0.1)

        # Surface craters & highland patches
        prng = random.Random(12)
        for _ in range(14):
            cx, cy, cz = prng.uniform(-1, 1), prng.uniform(-1, 1), prng.uniform(-1, 1)
            mag = math.sqrt(cx**2 + cy**2 + cz**2)
            if mag == 0:
                continue
            glPushMatrix()
            glTranslatef(cx/mag*(radius*0.96), cy/mag*(radius*0.96), cz/mag*(radius*0.96))
            glScalef(1.6, 1.6, 0.18)
            draw_sphere(radius * 0.22, 0.45, 0.12, 0.04)
            glPopMatrix()

        # North Polar Ice Cap
        glPushMatrix()
        glTranslatef(0, 0, radius * 0.85)
        glScalef(1.0, 1.0, 0.08)
        draw_sphere(radius * 0.38, 0.95, 0.93, 0.90)
        glPopMatrix()

        # South Polar Ice Cap
        glPushMatrix()
        glTranslatef(0, 0, -radius * 0.85)
        glScalef(1.0, 1.0, 0.08)
        draw_sphere(radius * 0.28, 0.92, 0.90, 0.88)
        glPopMatrix()

        # Thin reddish atmosphere haze
        glDisable(GL_LIGHTING)
        draw_sphere(radius * 1.06, 0.85, 0.35, 0.15, 0.12)
        glEnable(GL_LIGHTING)

        # Valles Marineris — dark canyon strip
        glPushMatrix()
        glRotatef(20, 0, 1, 0)
        glTranslatef(radius * 0.95, 0, 0)
        glScalef(0.08, 1.2, 0.25)
        draw_sphere(radius * 0.55, 0.28, 0.08, 0.02)
        glPopMatrix()

    elif level == 2:  # EARTH
        # Deep blue ocean base
        draw_sphere(radius, 0.08, 0.38, 0.78)

        # Small green and white hills
        prng = random.Random(42)
        continent_colors = [
            (0.22, 0.72, 0.22),
            (0.55, 0.65, 0.25),
            (0.28, 0.60, 0.18),
        ]
        for i in range(15): # Slightly more of them since they are smaller now
            cx, cy, cz = prng.uniform(-1, 1), prng.uniform(-1, 1), prng.uniform(-1, 1)
            mag = math.sqrt(cx**2 + cy**2 + cz**2)
            if mag == 0:
                continue
            glPushMatrix()
            glTranslatef(cx/mag*(radius*0.95), cy/mag*(radius*0.95), cz/mag*(radius*0.95))
            glScalef(1.2, 1.2, 0.4) # Made less flat to look like round hills
            col = continent_colors[i % len(continent_colors)]
            
            # Smaller green base
            draw_sphere(radius * 0.18, *col) 
            
            # Small white peak on the hill
            glTranslatef(0, 0, radius * 0.05)
            draw_sphere(radius * 0.10, 0.95, 0.95, 0.95)
            glPopMatrix()

        # Arctic Ice Cap (North)
        glPushMatrix()
        glTranslatef(0, 0, radius * 0.88)
        glScalef(1.0, 1.0, 0.10)
        draw_sphere(radius * 0.32, 0.95, 0.97, 1.0)
        glPopMatrix()

        # Antarctic Ice Cap (South)
        glPushMatrix()
        glTranslatef(0, 0, -radius * 0.88)
        glScalef(1.0, 1.0, 0.12)
        draw_sphere(radius * 0.42, 0.97, 0.97, 1.0)
        glPopMatrix()

        # Cloud layer — semi-transparent white sphere
        glDisable(GL_LIGHTING)
        draw_sphere(radius * 1.04, 1.0, 1.0, 1.0, 0.15)
        glEnable(GL_LIGHTING)

        # Blue atmosphere glow
        glDisable(GL_LIGHTING)
        draw_sphere(radius * 1.09, 0.3, 0.6, 1.0, 0.08)
        glEnable(GL_LIGHTING)

    elif level == 3:  # JUPITER
        glPushMatrix()
        glScalef(1.05, 1.05, 0.85)
        draw_sphere(radius, 0.8, 0.6, 0.4)
        glColor3f(0.6, 0.3, 0.1)
        glPushMatrix()
        glTranslatef(0, 0, radius * 0.3)
        glutSolidTorus(radius * 0.1, radius * 0.9, 15, 30)
        glPopMatrix()
        glColor3f(0.7, 0.4, 0.2)
        glPushMatrix()
        glTranslatef(0, 0, -radius * 0.2)
        glutSolidTorus(radius * 0.15, radius * 0.85, 15, 30)
        glPopMatrix()
        glPopMatrix()

        # Saturn-like rings
        glPushMatrix()
        glRotatef(30, 1, 1, 0)
        glColor4f(0.8, 0.7, 0.5, 0.7)
        glutSolidTorus(2, radius + 25, 20, 50)
        glColor4f(0.6, 0.4, 0.2, 0.4)
        glutSolidTorus(4, radius + 35, 20, 50)
        glPopMatrix()

    glPopMatrix()  # End planet rotation

    if level == 2:
        moon_angle = time.time() * 40
        mx = (radius + 45) * math.cos(math.radians(moon_angle))
        my = (radius + 45) * math.sin(math.radians(moon_angle))
        glPushMatrix()
        glTranslatef(mx, my, 5)
        draw_sphere(7, 0.85, 0.85, 0.85)
        # Moon surface craters
        glPushMatrix()
        glTranslatef(3, 2, 2)
        draw_sphere(2.2, 0.65, 0.65, 0.65)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(-4, -1, -1)
        draw_sphere(1.8, 0.70, 0.70, 0.70)
        glPopMatrix()
        glPopMatrix()

def draw_fighter_jet():
    glPushMatrix()
    glScalef(1.8, 0.4, 0.4)
    draw_sphere(8, 0.7, 0.7, 0.8)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(-2, 0, 0)
    glRotatef(35, 0, 0, 1)
    glScalef(0.8, 2.5, 0.1)
    draw_cube(10, 0.3, 0.3, 0.4)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(-2, 0, 0)
    glRotatef(-35, 0, 0, 1)
    glScalef(0.8, 2.5, 0.1)
    draw_cube(10, 0.3, 0.3, 0.4)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(3, 0, 3)
    draw_sphere(3, 0.1, 0.8, 1.0, 0.7)
    glPopMatrix()

def draw_alien_ship():
    glPushMatrix()
    glScalef(1.0, 1.0, 0.3)
    draw_sphere(15, 0.5, 0.1, 0.6)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0, 4)
    draw_sphere(6, 0.1, 0.9, 0.1)
    glPopMatrix()

def draw_boss_spaceship():
    glPushMatrix()
    glScalef(3.0, 3.0, 0.5)
    draw_sphere(20, 0.2, 0.2, 0.25)
    glPopMatrix()

    glPushMatrix()
    glDisable(GL_LIGHTING)
    draw_sphere(12, 1.0, 0.1, 0.1)
    glEnable(GL_LIGHTING)
    glPopMatrix()

    glPushMatrix()
    glRotatef(time.time() * 50, 0, 0, 1)
    glColor3f(0.5, 0.5, 0.6)
    glutSolidTorus(3, 65, 20, 50)
    for i in range(4):
        ang = i * 90
        x, y = 65 * math.cos(math.radians(ang)), 65 * math.sin(math.radians(ang))
        glPushMatrix()
        glTranslatef(x, y, 0)
        glDisable(GL_LIGHTING)
        draw_sphere(5, 0.0, 1.0, 1.0)
        glEnable(GL_LIGHTING)
        glPopMatrix()
    glPopMatrix()

def create_explosion(x, y):
    for _ in range(10):
        particles.append({
            'x': x, 'y': y,
            'vx': random.uniform(-50, 50),
            'vy': random.uniform(-50, 50),
            'life': 0.5,
        })

def start_game(level):
    global game_state, current_level, score, coins, planet_hp, shield_hp, planet_radius
    global bullets, turret_bullets, boss_bullets, meteors, aliens, powerups, particles
    global player_angle, boss_active, boss_hp, boss_obj, laser_timer, laser_fire_cooldown
    global homing_timer, combo_multiplier, boss_warning_timer

    current_level = level
    score, planet_hp, shield_hp = 0, 100, 0
    planet_radius = levels[level]["p_rad"]
    player_angle = 0.0
    combo_multiplier = 1.0
    bullets, turret_bullets, boss_bullets = [], [], []
    meteors, aliens, powerups, particles = [], [], [], []
    boss_active, boss_hp, boss_obj, boss_warning_timer = False, boss_max_hp, None, 0.0
    laser_timer, laser_fire_cooldown, homing_timer = 0.0, 0.0, 0.0
    generate_stars()
    game_state = "PLAYING"

def apply_damage_to_planet(amt):
    global shield_hp, planet_hp, game_state, shake_timer, combo_multiplier
    shake_timer = 0.5
    combo_multiplier = 1.0
    if shield_hp > 0:
        shield_hp -= amt
        if shield_hp < 0:
            planet_hp += shield_hp
            shield_hp = 0
    else:
        planet_hp -= amt
    if planet_hp <= 0:
        planet_hp = 0
        game_state = "GAMEOVER"

def spawn_enemies():
    global spawn_timer, boss_active, boss_obj, boss_hp, boss_warning_timer

    if current_level == 3 and score >= 100 and not boss_active and boss_hp > 0:
        boss_active = True
        boss_warning_timer = 3.0
        boss_obj = {'x': 0, 'y': 1000, 'speed': 40, 'ang': 90, 'fire_timer': 1.5}
        return

    if spawn_timer <= 0:
        angle = random.uniform(0, 360)
        x, y = 900 * math.cos(math.radians(angle)), 900 * math.sin(math.radians(angle))
        speed = levels[current_level]["enemy_spd"]
        choice = random.random()
        is_giant = (current_level == 3)

        if choice < 0.40:
            size_mod = random.uniform(1.2, 1.8) if is_giant else random.uniform(0.7, 1.5)
            meteors.append({'x': x, 'y': y, 'speed': speed / size_mod,
                            'hp': 100 * size_mod, 'size': 14 * size_mod})
        elif choice < 0.70:
            scale = random.uniform(1.5, 2.5) if is_giant else 1.0
            aliens.append({'x': x, 'y': y, 'speed': speed + 20, 'scale': scale})
        else:
            powerups.append({
                'x': x, 'y': y, 'speed': speed - 15,
                'type': random.choice(["TRAP", "SHIELD", "SHIELD", "LASER", "HOMING", "HP", "HP"]),
            })

        spawn_timer = max(0.5, levels[current_level]["base_spawn"] - (score * 0.003))

def update():
    global last_time, spawn_timer, game_state, score, coins, high_score, level_unlocked
    global turret_cooldown, turret_rotation, laser_timer, laser_fire_cooldown, homing_timer
    global combo_multiplier, combo_timer, shake_timer, boss_warning_timer, boss_active, boss_hp
    global planet_hp, shield_hp

    current_time = time.time()
    dt = current_time - last_time
    last_time = current_time
    if game_state != "PLAYING":
        return

    if score >= 300:
        if current_level < 3:
            level_unlocked = max(level_unlocked, current_level + 1)
            start_game(current_level + 1)
            return
        elif boss_active and boss_hp <= 0:
            game_state = "WIN"
            return

    if shake_timer > 0: shake_timer -= dt
    if boss_warning_timer > 0: boss_warning_timer -= dt

    if combo_timer > 0:
        combo_timer -= dt
    else:
        combo_multiplier = 1.0

    enemy_dt = dt * 0.3 if time_warp else dt
    spawn_timer -= dt
    turret_rotation += dt * 45

    if laser_timer > 0:
        laser_timer -= dt
        laser_fire_cooldown -= dt
        if laser_fire_cooldown <= 0:
            px = orbit_radius * math.cos(math.radians(player_angle))
            py = orbit_radius * math.sin(math.radians(player_angle))
            bullets.append({'x': px, 'y': py, 'angle': player_angle, 'is_laser': True})
            laser_fire_cooldown = 0.05

    if homing_timer > 0: homing_timer -= dt

    spawn_enemies()

    # ---- Boss movement & shooting ----
    if boss_active and boss_obj:
        dist = math.sqrt(boss_obj['x']**2 + boss_obj['y']**2)
        if dist > 300:
            boss_obj['x'] -= (boss_obj['x'] / dist) * boss_obj['speed'] * enemy_dt
            boss_obj['y'] -= (boss_obj['y'] / dist) * boss_obj['speed'] * enemy_dt
        else:
            boss_obj['ang'] += dt * 25
            boss_obj['x'] = 300 * math.cos(math.radians(boss_obj['ang']))
            boss_obj['y'] = 300 * math.sin(math.radians(boss_obj['ang']))

            boss_obj['fire_timer'] -= enemy_dt
            if boss_obj['fire_timer'] <= 0:
                px = orbit_radius * math.cos(math.radians(player_angle))
                py = orbit_radius * math.sin(math.radians(player_angle))
                shoot_angle = math.degrees(math.atan2(py - boss_obj['y'], px - boss_obj['x']))
                boss_bullets.append({'x': boss_obj['x'], 'y': boss_obj['y'], 'angle': shoot_angle})
                boss_obj['fire_timer'] = 1.5

    px = orbit_radius * math.cos(math.radians(player_angle))
    py = orbit_radius * math.sin(math.radians(player_angle))

    # ---- Boss bullets ----
    for b in boss_bullets[:]:
        rad = math.radians(b['angle'])
        b['x'] += math.cos(rad) * 350 * dt
        b['y'] += math.sin(rad) * 350 * dt

        if abs(b['x']) > 1500 or abs(b['y']) > 1500:
            boss_bullets.remove(b)
            continue

        if math.sqrt((b['x'] - px)**2 + (b['y'] - py)**2) < 20:
            apply_damage_to_planet(25)
            create_explosion(px, py)
            boss_bullets.remove(b)
            continue

        if math.sqrt(b['x']**2 + b['y']**2) < planet_radius + 15:
            apply_damage_to_planet(20)
            create_explosion(b['x'], b['y'])
            boss_bullets.remove(b)

    # ---- Turret auto-fire ----
    turret_cooldown -= dt
    if turret_cooldown <= 0:
        tr = planet_radius + 35
        for i in range(3):
            angle = turret_rotation + (i * 120)
            tx = tr * math.cos(math.radians(angle))
            ty = tr * math.sin(math.radians(angle))
            target, min_dist = None, 600

            enemies = meteors + aliens
            if boss_active and boss_obj:
                enemies.append(boss_obj)

            for e in enemies:
                d = math.sqrt((e['x'] - tx)**2 + (e['y'] - ty)**2)
                if d < min_dist:
                    min_dist, target = d, e

            if target:
                shoot_angle = math.degrees(math.atan2(target['y'] - ty, target['x'] - tx))
                turret_bullets.append({'x': tx, 'y': ty, 'angle': shoot_angle})

        turret_cooldown = max(1.5, 3.5 - (coins * 0.02))

    # ---- Particles ----
    for p in particles[:]:
        p['x'] += p['vx'] * dt
        p['y'] += p['vy'] * dt
        p['life'] -= dt
        if p['life'] <= 0:
            particles.remove(p)

    def add_score(pts):
        global score, coins, combo_multiplier, combo_timer, high_score, level_unlocked
        score += int(pts * combo_multiplier)
        coins += 5
        combo_multiplier = min(5.0, combo_multiplier + 0.1)
        combo_timer = 3.0
        if score > high_score:
            high_score = score
        if current_level == 1 and score >= 50:
            level_unlocked = max(level_unlocked, 2)
        if current_level == 2 and score >= 100:
            level_unlocked = max(level_unlocked, 3)

    # ---- Player bullets movement ----
    for b in bullets[:]:
        if homing_timer > 0 and not b.get('is_laser', False):
            closest, min_d = None, 800
            targets = aliens + meteors
            if boss_active and boss_obj:
                targets.append(boss_obj)
            for e in targets:
                d = math.sqrt((e['x'] - b['x'])**2 + (e['y'] - b['y'])**2)
                if d < min_d:
                    min_d, closest = d, e
            if closest:
                b['angle'] = math.degrees(math.atan2(closest['y'] - b['y'], closest['x'] - b['x']))

        rad = math.radians(b['angle'])
        spd = 1200 if b.get('is_laser', False) else 750
        b['x'] += math.cos(rad) * spd * dt
        b['y'] += math.sin(rad) * spd * dt
        if abs(b['x']) > 1500 or abs(b['y']) > 1500:
            if b in bullets:
                bullets.remove(b)

    # ---- Turret bullets movement ----
    for b in turret_bullets[:]:
        rad = math.radians(b['angle'])
        b['x'] += math.cos(rad) * 500 * dt
        b['y'] += math.sin(rad) * 500 * dt
        if abs(b['x']) > 1200 or abs(b['y']) > 1200:
            if b in turret_bullets:
                turret_bullets.remove(b)

    # ---- Meteors movement ----
    for m in meteors[:]:
        dist = math.sqrt(m['x']**2 + m['y']**2)
        if dist == 0:
            continue
        m['x'] -= (m['x'] / dist) * m['speed'] * enemy_dt
        m['y'] -= (m['y'] / dist) * m['speed'] * enemy_dt
        if dist < planet_radius + 10:
            apply_damage_to_planet(15)
            create_explosion(m['x'], m['y'])
            if m in meteors:
                meteors.remove(m)

    # ---- Aliens movement ----
    for a in aliens[:]:
        dx, dy = px - a['x'], py - a['y']
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            a['x'] += (dx / dist) * a['speed'] * enemy_dt
            a['y'] += (dy / dist) * a['speed'] * enemy_dt

        scale = a.get('scale', 1.0)
        if dist < 30 * scale:
            apply_damage_to_planet(20)
            create_explosion(a['x'], a['y'])
            if a in aliens:
                aliens.remove(a)

    # ---- Power-ups movement ----
    for p in powerups[:]:
        dist = math.sqrt(p['x']**2 + p['y']**2)
        if dist == 0:
            continue
        p['x'] -= (p['x'] / dist) * p['speed'] * enemy_dt
        p['y'] -= (p['y'] / dist) * p['speed'] * enemy_dt

        if math.sqrt((p['x'] - px)**2 + (p['y'] - py)**2) < 35:
            if p['type'] == "TRAP":
                game_state = "GAMEOVER"
            elif p['type'] == "SHIELD":
                shield_hp = 100
            elif p['type'] == "LASER":
                laser_timer = 10.0
            elif p['type'] == "HOMING":
                homing_timer = 10.0
            elif p['type'] == "HP":
                planet_hp = min(100, planet_hp + 30)
            if p in powerups:
                powerups.remove(p)
        elif dist < planet_radius:
            if p in powerups:
                powerups.remove(p)

    # ---- Player bullet collision ----
    for b in bullets[:]:
        if b not in bullets:
            continue
        hit = False
        is_laser = b.get('is_laser', False)
        p_dmg = 15 if is_laser else (80 if current_level == 3 else 40)

        # Boss hit
        if boss_active and boss_obj:
            if math.sqrt((b['x'] - boss_obj['x'])**2 + (b['y'] - boss_obj['y'])**2) < 60:
                boss_hp -= p_dmg
                create_explosion(b['x'], b['y'])
                if b in bullets:
                    bullets.remove(b)
                if boss_hp <= 0:
                    add_score(500)
                continue

        # Alien hit
        for a in aliens[:]:
            scale = a.get('scale', 1.0)
            if math.sqrt((b['x'] - a['x'])**2 + (b['y'] - a['y'])**2) < 30 * scale:
                create_explosion(a['x'], a['y'])
                if a in aliens:
                    aliens.remove(a)
                hit = True
                add_score(20)
                break
        if hit:
            if b in bullets:
                bullets.remove(b)
            continue

        # Meteor hit
        for m in meteors[:]:
            if math.sqrt((b['x'] - m['x'])**2 + (b['y'] - m['y'])**2) < m['size'] + 10:
                m['hp'] -= (20 if is_laser else 40)
                if m['hp'] <= 0:
                    create_explosion(m['x'], m['y'])
                    if m in meteors:
                        meteors.remove(m)
                    add_score(15)
                hit = True
                break
        if hit:
            if b in bullets:
                bullets.remove(b)
            continue

    # ---- Turret bullet collision ----
    for b in turret_bullets[:]:
        if b not in turret_bullets:
            continue
        hit = False

        # Boss hit
        if boss_active and boss_obj:
            if math.sqrt((b['x'] - boss_obj['x'])**2 + (b['y'] - boss_obj['y'])**2) < 60:
                boss_hp -= 5
                hit = True
                if b in turret_bullets:
                    turret_bullets.remove(b)
                continue

        # Meteor / alien hit
        for e in meteors + (aliens if current_level == 3 else []):
            rad = e.get('size', 25 * e.get('scale', 1.0))
            if math.sqrt((b['x'] - e['x'])**2 + (b['y'] - e['y'])**2) < rad:
                if 'hp' in e:
                    e['hp'] -= 25
                    if e['hp'] <= 0:
                        create_explosion(e['x'], e['y'])
                        if e in meteors:
                            meteors.remove(e)
                        add_score(5)
                else:
                    create_explosion(e['x'], e['y'])
                    if e in aliens:
                        aliens.remove(e)
                    add_score(10)
                hit = True
                break
        if hit:
            if b in turret_bullets:
                turret_bullets.remove(b)

    glutPostRedisplay()

def display():
    if boss_warning_timer > 0 and int(time.time() * 5) % 2 == 0:
        glClearColor(0.4, 0.0, 0.0, 1.0)
    else:
        bg = levels[current_level]["color"] if game_state == "PLAYING" else (0.1, 0.1, 0.2)
        glClearColor(bg[0] * 0.1, bg[1] * 0.1, bg[2] * 0.1, 1.0)

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    if game_state == "MENU":
        draw_text(350, 600, "PLANET GUARDIAN 3D", 0, 1, 1)
        draw_text(400, 500, f"HIGH SCORE: {high_score}", 1, 1, 0)
        draw_text(350, 400, f"1. MARS {'[UNLOCKED]' if level_unlocked >= 1 else ''}")
        draw_text(350, 360, f"2. EARTH {'[UNLOCKED]' if level_unlocked >= 2 else '[LOCKED - Need 50 Score]'}")
        draw_text(350, 320, f"3. JUPITER {'[UNLOCKED]' if level_unlocked >= 3 else '[LOCKED - Need 100 Score]'}")
        draw_text(250, 200, "ESC to Menu | A/D (Move) | Mouse L (Shoot) | C (Cam) | T (Time Warp)", 0.6, 0.6, 0.6)

    elif game_state == "GAMEOVER":
        draw_text(400, 450, "GAME OVER", 1, 0, 0)
        draw_text(420, 400, f"Final Score: {score}")
        draw_text(380, 350, "Press M to Return to Main Menu", 1, 1, 1)

    elif game_state == "WIN":
        draw_text(340, 450, "MOTHERSHIP DESTROYED! YOU WIN!", 0, 1, 0)
        draw_text(420, 400, f"Final Score: {score}")
        draw_text(380, 350, "Press M to Return to Main Menu", 1, 1, 1)

    elif game_state == "PLAYING":
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(65, WINDOW_WIDTH / WINDOW_HEIGHT, 1, 3000)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        px = orbit_radius * math.cos(math.radians(player_angle))
        py = orbit_radius * math.sin(math.radians(player_angle))
        sx = random.uniform(-4, 4) * shake_timer
        sy = random.uniform(-4, 4) * shake_timer

        if camera_mode == "FREE":
            cx = camera_dist * math.cos(math.radians(camera_phi)) * math.cos(math.radians(camera_theta))
            cy = camera_dist * math.cos(math.radians(camera_phi)) * math.sin(math.radians(camera_theta))
            cz = camera_dist * math.sin(math.radians(camera_phi))
            gluLookAt(cx + sx, cy + sy, cz,  0, 0, 0,  0, 0, 1)
        elif camera_mode == "FOLLOW":
            cam_dist = orbit_radius * 0.4
            cx = cam_dist * math.cos(math.radians(player_angle)) + sx
            cy = cam_dist * math.sin(math.radians(player_angle)) + sy
            look_x = (orbit_radius * 3) * math.cos(math.radians(player_angle))
            look_y = (orbit_radius * 3) * math.sin(math.radians(player_angle))
            gluLookAt(cx, cy, 60,  look_x, look_y, 0,  0, 0, 1)
        elif camera_mode == "FPP":
            ex = (orbit_radius + 5) * math.cos(math.radians(player_angle))
            ey = (orbit_radius + 5) * math.sin(math.radians(player_angle))
            lx = ex + math.cos(math.radians(player_angle)) * 200
            ly = ey + math.sin(math.radians(player_angle)) * 200
            gluLookAt(ex + sx, ey + sy, 10,  lx, ly, 10,  0, 0, 1)

        draw_stars()
        draw_realistic_planet(planet_radius, *levels[current_level]["color"], current_level)

        if shield_hp > 0:
            draw_sphere(planet_radius + 8, 0, 0.6, 1.0, 0.4)
        draw_orbit(orbit_radius, 0.4, 0.4, 0.4)
        draw_orbit(planet_radius + 35, 0.2, 0.5, 0.2)

        # Turret drones
        for i in range(3):
            ang = turret_rotation + (i * 120)
            tx = (planet_radius + 35) * math.cos(math.radians(ang))
            ty = (planet_radius + 35) * math.sin(math.radians(ang))
            glPushMatrix()
            glTranslatef(tx, ty, 0)
            glRotatef(ang, 0, 0, 1)
            draw_defense_drone()
            glPopMatrix()

        # Player ship
        if camera_mode != "FPP":
            glPushMatrix()
            glTranslatef(px, py, 0)
            glRotatef(player_angle, 0, 0, 1)
            draw_fighter_jet()
            glPopMatrix()

        # Boss
        if boss_active and boss_obj:
            glPushMatrix()
            glTranslatef(boss_obj['x'], boss_obj['y'], 0)
            b_ang = math.degrees(math.atan2(py - boss_obj['y'], px - boss_obj['x']))
            glRotatef(b_ang, 0, 0, 1)
            draw_boss_spaceship()
            glPopMatrix()

        # Meteors
        for m in meteors:
            glPushMatrix()
            glTranslatef(m['x'], m['y'], 0)
            glRotatef(m['x'] + m['y'], 1, 1, 0)
            draw_realistic_meteor(m['size'], int(m['x'] + m['y']))
            glPopMatrix()

        # Aliens
        for a in aliens:
            glPushMatrix()
            glTranslatef(a['x'], a['y'], 0)
            glRotatef(math.degrees(math.atan2(py - a['y'], px - a['x'])), 0, 0, 1)
            scale = a.get('scale', 1.0)
            glScalef(scale, scale, scale)
            draw_alien_ship()
            glPopMatrix()

        # Power-ups
        for p in powerups:
            glPushMatrix()
            glTranslatef(p['x'], p['y'], 0)
            if p['type'] == "TRAP":
                glRotatef(time.time() * 50, 1, 1, 1)
                draw_bomb(14)
                draw_3d_text(-10, 20, "TRAP", 1, 0, 0)
            else:
                glRotatef(turret_rotation * 10, 0, 0, 1)
                glRotatef(45, 1, 0, 0)
                if p['type'] == "SHIELD":
                    draw_crystal(15, 0.0, 0.8, 1.0)
                    draw_3d_text(-15, 20, "SHIELD", 0, 0.8, 1)
                elif p['type'] == "LASER":
                    draw_crystal(15, 1.0, 0.0, 1.0)
                    draw_3d_text(-15, 20, "LASER", 1, 0, 1)
                elif p['type'] == "HOMING":
                    draw_crystal(15, 0.0, 1.0, 1.0)
                    draw_3d_text(-15, 20, "HOMING", 0, 1, 1)
                elif p['type'] == "HP":
                    draw_crystal(15, 0.2, 1.0, 0.2)
                    draw_3d_text(-10, 20, "HP", 0, 1, 0)
            glPopMatrix()

        # Player bullets
        for b in bullets:
            glPushMatrix()
            glTranslatef(b['x'], b['y'], 0)
            glDisable(GL_LIGHTING)
            if b.get('is_laser', False):
                glRotatef(b['angle'], 0, 0, 1)
                glScalef(3.0, 0.4, 0.4)
                draw_sphere(5, 1.0, 0.0, 1.0)
            elif homing_timer > 0:
                draw_sphere(6, 0, 1, 1)
            else:
                draw_sphere(4, 1, 1, 0)
            glEnable(GL_LIGHTING)
            glPopMatrix()

        # Boss bullets
        for b in boss_bullets:
            glPushMatrix()
            glTranslatef(b['x'], b['y'], 0)
            glDisable(GL_LIGHTING)
            draw_sphere(6, 1.0, 0.2, 0.0)
            glEnable(GL_LIGHTING)
            glPopMatrix()

        # Turret bullets
        for b in turret_bullets:
            glPushMatrix()
            glTranslatef(b['x'], b['y'], 0)
            glDisable(GL_LIGHTING)
            draw_sphere(3, 0, 1, 1)
            glEnable(GL_LIGHTING)
            glPopMatrix()

        # Particles
        glDisable(GL_LIGHTING)
        glBegin(GL_POINTS)
        for p in particles:
            glColor4f(1, 0.5, 0, p['life'] * 2)
            glVertex3f(p['x'], p['y'], 0)
        glEnd()
        glEnable(GL_LIGHTING)

        # HUD
        draw_text(10, 760, f"SCORE: {score}/300  |  COINS: {coins}", 1, 1, 0)
        if combo_multiplier > 1.0:
            draw_text(10, 730, f"COMBO: {combo_multiplier:.1f}x", 1, 0.5, 0)

        hp_c = (1, 0, 0) if planet_hp < 25 and int(time.time() * 5) % 2 == 0 else (0, 1, 0)
        draw_text(10, 700 if combo_multiplier > 1.0 else 730, f"PLANET HP: {planet_hp}%", *hp_c)
        if shield_hp > 0:
            draw_text(10, 670, f"SHIELD: {shield_hp}%", 0, 0.5, 1)

        if boss_active:
            draw_text(400, 760, f"BOSS HP: {boss_hp}/{boss_max_hp}", 1, 0, 0)

        buffs = []
        if laser_timer > 0:  buffs.append(f"LASER ({int(laser_timer)}s)")
        if homing_timer > 0: buffs.append(f"HOMING ({int(homing_timer)}s)")
        if buffs:
            draw_text(400, 730 if boss_active else 760, " + ".join(buffs), 1, 0, 1)
        if time_warp:
            draw_text(400, 700 if boss_active else 730, "TIME WARP", 0, 1, 1)

    glutSwapBuffers()

def keyboard_listener(key, x, y):
    global game_state, player_angle, camera_mode, time_warp

    if key == b'\x1b':
        game_state = "MENU"
        glutPostRedisplay()
        return

    if key in [b'm', b'M'] and game_state in ["PLAYING", "GAMEOVER", "WIN"]:
        game_state = "MENU"

    if game_state == "MENU":
        if key == b'1': start_game(1)
        if key == b'2' and level_unlocked >= 2: start_game(2)
        if key == b'3' and level_unlocked >= 3: start_game(3)
    elif game_state == "PLAYING":
        if key in [b'a', b'A']: player_angle += 5.0
        if key in [b'd', b'D']: player_angle -= 5.0
        if key in [b'c', b'C']:
            modes = ["FREE", "FOLLOW", "FPP"]
            camera_mode = modes[(modes.index(camera_mode) + 1) % 3]
        if key in [b't', b'T']: time_warp = True

    glutPostRedisplay()

def keyboard_up_listener(key, x, y):
    global time_warp
    if key in [b't', b'T']:
        time_warp = False

def mouse_listener(button, state, x, y):
    if game_state == "PLAYING" and button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if laser_timer <= 0:
            px = orbit_radius * math.cos(math.radians(player_angle))
            py = orbit_radius * math.sin(math.radians(player_angle))
            bullets.append({'x': px, 'y': py, 'angle': player_angle, 'is_laser': False})

def special_listener(key, x, y):
    global camera_theta, camera_phi
    if camera_mode == "FREE":
        if key == GLUT_KEY_LEFT:  camera_theta += 5
        if key == GLUT_KEY_RIGHT: camera_theta -= 5
        if key == GLUT_KEY_UP:    camera_phi = min(85, camera_phi + 5)
        if key == GLUT_KEY_DOWN:  camera_phi = max(5, camera_phi - 5)

def main():
    global last_time
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH | GLUT_ALPHA)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(b"Planet Guardian 3D - Ultimate Boss & Laser")
    init_lighting()
    last_time = time.time()
    glutDisplayFunc(display)
    glutIdleFunc(update)
    glutKeyboardFunc(keyboard_listener)
    glutKeyboardUpFunc(keyboard_up_listener)
    glutMouseFunc(mouse_listener)
    glutSpecialFunc(special_listener)
    glutMainLoop()

if __name__ == "__main__":
    main()
