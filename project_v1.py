import random
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import cos, radians, sin, sqrt, pi, atan2

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────
states = {}
transitions = {}
edge_list = []

selected_state = None
state_id = 0

camera_x = 45
camera_y = 35
camera_z = 350

current_question = 0
score = 0
result_text = ""
# ___MOUSE LISTENER
mouse_x, mouse_y = 0,0
dragging_state = None
# ─── animation globals ───────────────────────
time_val = 0.0          # global clock (incremented in idle)
particle_list = []       # list of active particles
pulse_states = {}        # state_id -> pulse phase
flash_edges = []         # (src, dst, progress 0‑1, color)
travel_particles = []   # moving along edges
sim_path = []            # [(state_id, color)] for last simulation run
sim_flash_t = 0.0        # how far through the sim flash we are
ACCEPT_GLOW = {}         # state_id -> glow intensity
camera_orbit = 0.0       # auto‑orbit angle when idle
orbit_active = False

# ─── validated string animation ───────────────
validation_tokens = []   # list of dicts: {string, accepted, phase, x}
VALID_ANIM_SPEED = 0.8

# ─────────────────────────────────────────────
#   STRING FLOWING
flow_string = "string"
flow_index = 0
flow_timer = 0
# ─────────────────────────────────────────────
#  QUESTIONS
# ─────────────────────────────────────────────
questions = [
    {
        "rule": "Strings ending with 01",
        "alphabet": ['0', '1'],
        "test_strings": ["01", "101", "1101", "10", "111"],
        "expected": {"01": True, "101": True, "1101": True, "10": False, "111": False}
    },
    {
        "rule": "Strings containing 00",
        "alphabet": ['0', '1'],
        "test_strings": ["00", "100", "001", "11", "101"],
        "expected": {"00": True, "100": True, "001": True, "11": False, "101": False}
    },
    {
        "rule": "Strings of even length",
        "alphabet": ['0', '1'],
        "test_strings": ["", "01", "1001", "0", "100", "11"],
        "expected": {"": True, "01": True, "1001": True, "0": False, "100": False, "11": True}
    },
    {
        "rule": "Strings starting with 1",
        "alphabet": ['0', '1'],
        "test_strings": ["1", "10", "110", "01", "001"],
        "expected": {"1": True, "10": True, "110": True, "01": False, "001": False}
    },
    {
        "rule": "Strings with odd number of 1s",
        "alphabet": ['0', '1'],
        "test_strings": ["1", "11", "111", "0", "010"],
        "expected": {"1": True, "11": False, "111": True, "0": False, "010": False}
    },
]

transition_mode = False
transition_src = None

# ─────────────────────────────────────────────
#  GENERATE STRING
# ─────────────────────────────────────────────
def generate_strings(alphabet, max_len=4):
    res = [""]

    for _ in range(max_len):
        new = []
        for s in res:
            for ch in alphabet:
                new.append(s+ch)
        res += new

    return list(set(res))

def check_rule(rule, string):
    if rule == "Strings ending with 01":
        return string.endswith("01")

    if rule == "Strings containing 00":
        return "00" in string

    if rule == "Strings of even length":
        return len(string) % 2 == 0

    if rule == "Strings starting with 1":
        return string.startswith("1")

    if rule == "Strings with odd number of 1s":
        return string.count("1") % 2 == 1

    return False

def validate_against_rule(rule, alphabet):
    strings = generate_strings(alphabet, 4)

    for s in strings:
        dfa_result, path = simulate_dfa(s)
        expected = check_rule(rule, s)

        if dfa_result != expected:
            print(f"❌ Mismatch on '{s}'")
            return False

    print("✅ DFA matches rule")
    return True
# ─────────────────────────────────────────────
#  PARTICLES
# ─────────────────────────────────────────────
def spawn_particles(x, y, z, count, color, speed=5.0, lifetime=1.2):
    for _ in range(count):
        angle = random.uniform(0, 2 * pi)
        elev  = random.uniform(-pi/3, pi/3)
        spd   = random.uniform(speed * 0.5, speed * 1.5)
        vx = spd * cos(elev) * cos(angle)
        vy = spd * cos(elev) * sin(angle)
        vz = spd * sin(elev)
        particle_list.append({
            "x": x, "y": y, "z": z,
            "vx": vx, "vy": vy, "vz": vz,
            "r": color[0], "g": color[1], "b": color[2],
            "life": lifetime,
            "max_life": lifetime,
            "size": random.uniform(3, 8)
        })
# ─────────────────────────────────────────────
#  INPUT FLOW
# ─────────────────────────────────────────────
def draw_input_flow():
    if flow_string == "":
        return

    visible = flow_string[:flow_index]
    draw_text(400, 750, f"INPUT: {visible}", color=(1,1,0))
# ─────────────────────────────────────────────
#  TRAVEL PARTICLES
# ─────────────────────────────────────────────
def draw_travel_particles():
    glPointSize(10)
    glBegin(GL_POINTS)

    for p in travel_particles:
        if p["src"] not in states or p["dst"] not in states:
            continue

        x1,y1,z1 = states[p["src"]]["pos"]
        x2,y2,z2 = states[p["dst"]]["pos"]

        t = p["t"]

        x = x1 + (x2-x1)*t
        y = y1 + (y2-y1)*t
        z = z1 + (z2-z1)*t

        glColor3f(*p["color"])
        glVertex3f(x,y,z)

    glEnd()

def update_particles(dt):
    dead = []
    for p in particle_list:
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["z"] += p["vz"] * dt
        p["vz"] -= 9.8 * dt          # gravity
        p["life"] -= dt
        if p["life"] <= 0:
            dead.append(p)
    for p in dead:
        particle_list.remove(p)

def draw_particles():
    glDisable(GL_DEPTH_TEST)
    glPointSize(6)
    glBegin(GL_POINTS)
    for p in particle_list:
        alpha = p["life"] / p["max_life"]
        glColor3f(p["r"] * alpha, p["g"] * alpha, p["b"] * alpha)
        glVertex3f(p["x"], p["y"], p["z"])
    glEnd()
    glEnable(GL_DEPTH_TEST)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1, 1, 1)):
    glColor3f(*color)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def find_start():
    for s in states:
        if states[s]["is_start"]:
            return s
    return None


def find_accept():
    acc = set()
    for s in states:
        if states[s]["is_accept"]:
            acc.add(s)
    return acc


def simulate_dfa(string):
    start = find_start()
    accepts = find_accept()

    if start is None:
        print("❌ No start state defined")
        return False, []

    current = start
    path = [current]

    for ch in string:
        if (current, ch) not in transitions:
            print(f"❌ Rejected: No transition from q{current} on '{ch}'")
            return False, path

        current = transitions[(current, ch)]
        path.append(current)

    print("Path:", " -> ".join(f"q{s}" for s in path))

    if current in accepts:
        print(f"✅ Accepted at q{current}")
        return True, path
    else:
        print(f"❌ Rejected at q{current} (not final)")
        return False, path

def reset_connections():
    for s in states:
        states[s]["is_start"] = False
        states[s]["is_accept"] = False
    transitions.clear()
    edge_list.clear()
    flash_edges.clear()
    sim_path.clear()

def spawn_travel_particle(path, color=(1,1,1), speed=0.6):
    # path = [q0, q1, q2, ...]
    for i in range(len(path)-1):
        travel_particles.append({
            "src": path[i],
            "dst": path[i+1],
            "t": 0.0,
            "speed": speed,
            "color": color
        })
# ─────────────────────────────────────────────
#  DRAW: ANIMATED FLOOR GRID
# ─────────────────────────────────────────────
def draw_floor():
    glLineWidth(1)
    grid_range = range(-200, 201, 20)
    for i in grid_range:
        t = (sin(time_val * 0.4 + i * 0.05) + 1) * 0.5
        brightness = 0.08 + 0.06 * t
        glColor3f(brightness * 0.4, brightness * 0.8, brightness)
        glBegin(GL_LINES)
        glVertex3f(i, -200, 0)
        glVertex3f(i, 200, 0)
        glEnd()
        glBegin(GL_LINES)
        glVertex3f(-200, i, 0)
        glVertex3f(200, i, 0)
        glEnd()

    # Horizon glow ring
    glLineWidth(2)
    segs = 64
    for i in range(segs):
        a0 = 2 * pi * i / segs
        a1 = 2 * pi * (i + 1) / segs
        pulse = (sin(time_val * 1.2 + a0 * 2) + 1) * 0.5
        glColor3f(0.0, 0.3 + 0.2 * pulse, 0.5 + 0.3 * pulse)
        glBegin(GL_LINES)
        glVertex3f(220 * cos(a0), 220 * sin(a0), 0)
        glVertex3f(220 * cos(a1), 220 * sin(a1), 0)
        glEnd()


# ─────────────────────────────────────────────
#  DRAW: STATES AS ANIMATED SPHERES
# ─────────────────────────────────────────────
def draw_states():
    global pulse_states
    for s in states:
        if s not in pulse_states:
            pulse_states[s] = random.uniform(0, 2 * pi)
        phase = pulse_states[s]
        pulse = (sin(time_val * 2.0 + phase) + 1) * 0.5

        x, y, z = states[s]["pos"]

        # Outer glow ring (flat circle on xz-plane around state)
        glPushMatrix()
        glTranslatef(x, y, z)
        glLineWidth(2)
        segs = 32
        glow_r = 34 + 4 * pulse
        if s == selected_state:
            gr, gg, gb = 1.0, 0.3, 0.1
        elif states[s]["is_start"]:
            gr, gg, gb = 0.2, 0.5, 1.0
        elif states[s]["is_accept"]:
            gr, gg, gb = 1.0, 0.9, 0.0
        else:
            gr, gg, gb = 0.1, 0.9, 0.5

        glColor3f(gr * 0.5 * pulse, gg * 0.5 * pulse, gb * 0.5 * pulse)
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2 * pi * i / segs
            glVertex3f(glow_r * cos(a), glow_r * sin(a), 0)
        glEnd()

        # Second ring (tilted)
        glRotatef(60, 1, 0, 0)
        glColor3f(gr * 0.3 * pulse, gg * 0.3 * pulse, gb * 0.3 * pulse)
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2 * pi * i / segs
            glVertex3f(glow_r * cos(a), glow_r * sin(a), 0)
        glEnd()
        glPopMatrix()

        # Core sphere
        glPushMatrix()
        glTranslatef(x, y, z)
        scale = 1.0 + 0.08 * pulse
        glScalef(scale, scale, scale)
        glColor3f(gr, gg, gb)
        q = gluNewQuadric()
        gluSphere(q, 28, 20, 20)

        # Accept double ring
        if states[s]["is_accept"]:
            glColor3f(1.0, 1.0, 0.3)
            gluSphere(q, 33 + 3 * pulse, 14, 14)

        glPopMatrix()

        # State label
        draw_text(x + 10, y + 35 + z, f"q{s}",
                  font=GLUT_BITMAP_HELVETICA_12,
                  color=(gr, gg, gb))


# ─────────────────────────────────────────────
#  DRAW: EDGES WITH FLOWING ANIMATION
# ─────────────────────────────────────────────
def draw_edges():
    h = 760
    glLineWidth(3)

    for idx, e in enumerate(edge_list):
        src, dst, ch = e[0], e[1], e[2]
        if src not in states or dst not in states:
            continue
        x1, y1, z1 = states[src]["pos"]
        x2, y2, z2 = states[dst]["pos"]

        # Animated flow dots along edge
        num_dots = 6
        speed = 0.6 + 0.1 * (idx % 3)
        offset = (time_val * speed) % 1.0

        # Base line
        glColor3f(0.3, 0.6, 0.9)
        glBegin(GL_LINES)
        glVertex3f(x1, y1, z1)
        glVertex3f(x2, y2, z2)
        glEnd()

        # Flow dots
        glPointSize(7)
        glBegin(GL_POINTS)
        for d in range(num_dots):
            t = ((d / num_dots) + offset) % 1.0
            fx = x1 + (x2 - x1) * t
            fy = y1 + (y2 - y1) * t
            fz = z1 + (z2 - z1) * t
            brightness = sin(t * pi)
            glColor3f(0.3 * brightness, 0.8 * brightness, 1.0 * brightness)
            glVertex3f(fx, fy, fz)
        glEnd()

        # Label
        draw_text(860, h, f"q{src} --{ch}--> q{dst}",
                  color=(0.4, 0.85, 1.0))
        h -= 22

    # Flash edges from last simulation
    for fe in flash_edges[:]:
        src, dst, progress, col = fe[0], fe[1], fe[2], fe[3]
        if src not in states or dst not in states:
            continue
        x1, y1, z1 = states[src]["pos"]
        x2, y2, z2 = states[dst]["pos"]
        alpha = max(0, 1 - progress)
        glLineWidth(6)
        glColor3f(col[0] * alpha, col[1] * alpha, col[2] * alpha)
        glBegin(GL_LINES)
        glVertex3f(x1, y1, z1)
        glVertex3f(x2, y2, z2)
        glEnd()
        glLineWidth(3)


# ─────────────────────────────────────────────
#  DRAW: HUD  
# ─────────────────────────────────────────────
def draw_hud():
    q = questions[current_question]

    # Top banner
    pulse = (sin(time_val * 1.5) + 1) * 0.5
    title_r = 0.3 + 0.4 * pulse
    draw_text(10, 775, f"*** DFA BUILDER ***  Q{current_question + 1}/{len(questions)}",
              font=GLUT_BITMAP_HELVETICA_18, color=(title_r, 0.9, 1.0))

    draw_text(10, 752, f"RULE: {q['rule']}",
              color=(1.0, 0.85, 0.2))

    # Controls
    ctrl_color = (0.5, 0.7, 0.6)
    draw_text(10, 620, "C=create  K=cycle  WASD=move  Q/E=Z",  color=ctrl_color)
    draw_text(10, 600, "F=start  G=accept  T=transition  0/1=label",  color=ctrl_color)
    draw_text(10, 580, "SPACE=validate  M=next  R=reset  X=undo edge", color=ctrl_color)
    draw_text(10, 560, "Arrows=rotate cam  +/-=zoom", color=ctrl_color)

    # State info panel
    sel_color = (1.0, 0.4, 0.2) if selected_state is not None else (0.4, 0.4, 0.4)
    draw_text(700, 752, f"SELECTED: q{selected_state}", color=sel_color)
    draw_text(700, 730, f"START:    q{find_start()}", color=(0.3, 0.6, 1.0))
    draw_text(700, 708, f"ACCEPTS:  {find_accept()}", color=(1.0, 0.9, 0.2))

    # Validation results
    h = 620
    draw_text(10, h + 22, "─── RESULTS ───", color=(0.6, 0.6, 0.8))
    for line in result_text.split("\n"):
        if "OK" in line:
            col = (0.2, 1.0, 0.4)
        elif "WRONG" in line:
            col = (1.0, 0.3, 0.3)
        elif "Score" in line:
            sc_val = score
            tot = len(q["test_strings"])
            if sc_val == tot:
                col = (0.2, 1.0, 0.4)
            elif sc_val > tot // 2:
                col = (1.0, 0.85, 0.2)
            else:
                col = (1.0, 0.3, 0.3)
        else:
            col = (0.8, 0.8, 0.8)
        draw_text(10, h, line, color=col)
        h -= 22

    # Transition mode indicator
    if transition_mode:
        blink = (sin(time_val * 6) + 1) * 0.5
        draw_text(400, 30,
                  f"TRANSITION MODE: from q{transition_src}  →  press 0 or 1",
                  color=(1.0, blink, 0.0))
        
# ─────────────────────────────────────────────
#  DFA transition Validation
# ─────────────────────────────────────────────
def validate_transition(from_state, char, to_state):
    if from_state not in states:
        print(f"❌ State q{from_state} does not exist")
        return False

    if to_state not in states:
        print(f"❌ State q{to_state} does not exist")
        return False

    if char == "":
        print("❌ Input cannot be empty")
        return False

    # DFA rule: only ONE transition per input from a state
    if (from_state, char) in transitions:
        print(f"❌ Transition already exists for input '{char}' from q{from_state}")
        return False

    return True

# ─────────────────────────────────────────────
#  MOUSE
# ─────────────────────────────────────────────
def mouseListener(button, state, x, y):
    global dragging_state, selected_state

    if button == GLUT_LEFT_BUTTON:
        if state == GLUT_DOWN:
            # pick closest state
            for s in states:
                sx,sy,_ = states[s]["pos"]

                if abs(x - (sx+500)) < 30 and abs(y - (800 - sy)) < 30:
                    dragging_state = s
                    selected_state = s
                    break

        else:
            dragging_state = None
            
def motionListener(x, y):
    global dragging_state

    if dragging_state is not None:
        states[dragging_state]["pos"][0] = x - 500
        states[dragging_state]["pos"][1] = 800 - y
# ─────────────────────────────────────────────
#  KEYBOARD
# ─────────────────────────────────────────────
def keyboardListener(key, x, y):
    global state_id, selected_state, transition_mode, transition_src
    global current_question, result_text, camera_z, score
    global orbit_active, sim_path, flash_edges, validation_tokens

    if key == b'c':
        a = random.uniform(-150, 150)
        b = random.uniform(-150, 150)
        c = random.uniform(50, 220)
        states[state_id] = {
            "pos": [a, b, c],
            "is_start": False,
            "is_accept": False
        }
        spawn_particles(a, b, c, 20, (0.1, 0.9, 0.5), speed=8)
        selected_state = state_id
        state_id += 1

    if key == b'k' and len(states) > 0:
        keys = list(states.keys())
        if selected_state not in keys:
            selected_state = keys[0]
        else:
            i = keys.index(selected_state)
            selected_state = keys[(i + 1) % len(keys)]

    if selected_state is not None and selected_state in states:
        pos = states[selected_state]["pos"]
        if key == b'w': pos[1] += 10
        if key == b's': pos[1] -= 10
        if key == b'a': pos[0] -= 10
        if key == b'd': pos[0] += 10
        if key == b'q': pos[2] += 10
        if key == b'e': pos[2] -= 10

        if key == b'f':
            for s in states:
                states[s]["is_start"] = False
            states[selected_state]["is_start"] = True
            spawn_particles(*states[selected_state]["pos"], 30, (0.2, 0.5, 1.0), speed=10)

        if key == b'g':
            states[selected_state]["is_accept"] = not states[selected_state]["is_accept"]
            if states[selected_state]["is_accept"]:
                spawn_particles(*states[selected_state]["pos"], 40, (1.0, 0.9, 0.0), speed=12)

    if key == b't':
        if selected_state is None:
            print("❌ Select a state first")
        else:
            transition_mode = True
            transition_src = selected_state

    if key == b'x':
        if edge_list:
            last = edge_list.pop()
            transitions.pop((last[0], last[2]), None)
        transition_mode = False
        transition_src = None

    if transition_mode:
        if key == b'0' or key == b'1':
            dest = selected_state
            char = key.decode()
            tkey = (transition_src, char)
            if tkey not in transitions:
                transitions[tkey] = dest
                edge_list.append((transition_src, dest, char))
                # spawn connection particles between the two states
                if transition_src in states and dest in states:
                    px = (states[transition_src]["pos"][0] + states[dest]["pos"][0]) / 2
                    py = (states[transition_src]["pos"][1] + states[dest]["pos"][1]) / 2
                    pz = (states[transition_src]["pos"][2] + states[dest]["pos"][2]) / 2
                    spawn_particles(px, py, pz, 25, (0.3, 0.8, 1.0), speed=6)
            transition_mode = False
            transition_src = None

    if key == b' ':
        q = questions[current_question]
        score = 0
        result_text = ""
        flash_edges.clear()
        
        is_valid = validate_against_rule(q["rule"], q["alphabet"])
        if is_valid:
            print("Deep validation passed!")
        
        if not is_complete_dfa(q["alphabet"]):
            print("⚠️ Warning: DFA is incomplete")

        for string in q["test_strings"]:
            res, path = simulate_dfa(string)
            spawn_travel_particle(path, col)
            correct = q["expected"][string]
            if res == correct:
                score += 1
                result_text += f"'{string}': OK\n"
                col = (0.2, 1.0, 0.4)
            else:
                result_text += f"'{string}': WRONG\n"
                col = (1.0, 0.3, 0.3)

            # Animate the path
            for i in range(len(path) - 1):
                flash_edges.append([path[i], path[i + 1], 0.0, col])

        total = len(q["test_strings"])
        result_text += f"Score: {score}/{total}"

        if score == total:
            # Big celebration burst
            for s in states:
                spawn_particles(*states[s]["pos"], 60, (1.0, 0.9, 0.1), speed=15, lifetime=2.5)
        elif score > 0:
            for s in find_accept():
                spawn_particles(*states[s]["pos"], 30, (0.2, 1.0, 0.4), speed=10)

    if key == b'm':
        if current_question < len(questions) - 1:
            current_question += 1
        reset_connections()
        result_text = ""
        score = 0

    if key == b'+' or key == b'=':
        if camera_z > 120:
            camera_z -= 25
    if key == b'-':
        if camera_z < 1200:
            camera_z += 25

    if key == b'r':
        states.clear()
        transitions.clear()
        edge_list.clear()
        flash_edges.clear()
        particle_list.clear()
        selected_state = None
        state_id = 0
        result_text = ""
        score = 0


def is_complete_dfa(alphabet=['0','1']):
    for s in states:
        for ch in alphabet:
            if (s, ch) not in transitions:
                print(f"⚠️ Missing transition: q{s} --{ch}--> ?")
                return False
    return True

def specialKeyListener(key, x, y):
    global camera_x, camera_y
    if key == GLUT_KEY_LEFT:  camera_x -= 5
    if key == GLUT_KEY_RIGHT: camera_x += 5
    if key == GLUT_KEY_UP:
        if camera_y < 85: camera_y += 5
    if key == GLUT_KEY_DOWN:
        if camera_y > 5: camera_y -= 5


# ─────────────────────────────────────────────
#  CAMERA
# ─────────────────────────────────────────────
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(70, 1.25, 0.1, 2000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    x = camera_z * cos(radians(camera_y)) * cos(radians(camera_x))
    y = camera_z * cos(radians(camera_y)) * sin(radians(camera_x))
    z = camera_z * sin(radians(camera_y))
    gluLookAt(x, y, z, 0, 0, 80, 0, 0, 1)


# ─────────────────────────────────────────────
#  STARFIELD BACKGROUND  
# ─────────────────────────────────────────────
_stars = None
def get_stars():
    global _stars
    if _stars is None:
        _stars = [(random.uniform(-800, 800),
                   random.uniform(-800, 800),
                   random.uniform(-100, 600),
                   random.uniform(0.3, 1.0)) for _ in range(200)]
    return _stars

def draw_stars():
    glPointSize(2)
    glBegin(GL_POINTS)
    for sx, sy, sz, bright in get_stars():
        twinkle = (sin(time_val * 2.3 + sx * 0.01) + 1) * 0.3
        glColor3f(bright * (0.5 + twinkle),
                  bright * (0.6 + twinkle),
                  bright * (0.9 + twinkle * 0.5))
        glVertex3f(sx, sy, sz)
    glEnd()


# ─────────────────────────────────────────────
#  DRAW AXES
# ─────────────────────────────────────────────
def draw_axes():
    glLineWidth(2)
    alpha = (sin(time_val * 0.5) + 1) * 0.2 + 0.3

    glBegin(GL_LINES)
    glColor3f(1.0 * alpha, 0.2 * alpha, 0.2 * alpha)
    glVertex3f(0, 0, 0); glVertex3f(60, 0, 0)

    glColor3f(0.2 * alpha, 1.0 * alpha, 0.2 * alpha)
    glVertex3f(0, 0, 0); glVertex3f(0, 60, 0)

    glColor3f(0.2 * alpha, 0.5 * alpha, 1.0 * alpha)
    glVertex3f(0, 0, 0); glVertex3f(0, 0, 60)
    glEnd()


# ─────────────────────────────────────────────
#  UPDATE flash edges
# ─────────────────────────────────────────────
def update_flash_edges(dt):
    for fe in flash_edges:
        fe[2] = min(1.0, fe[2] + dt * 0.6)

# ─────────────────────────────────────────────
#  Update_travel_particles
# ─────────────────────────────────────────────
def update_travel_particles(dt):
    for p in travel_particles:
        p["t"] += dt * p["speed"]

    # remove finished
    travel_particles[:] = [p for p in travel_particles if p["t"] <= 1.0]

# ─────────────────────────────────────────────
#  UPDATE flow
# ─────────────────────────────────────────────
def update_flow(dt):
    global flow_timer, flow_index

    flow_timer += dt
    if flow_timer > 0.5:
        flow_timer = 0
        flow_index += 1
# ─────────────────────────────────────────────
#  MAIN DISPLAY
# ─────────────────────────────────────────────
def showScreen():
    glClearColor(0.02, 0.02, 0.06, 1)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, 1000, 800)

    setupCamera()

    draw_stars()
    draw_floor()
    draw_axes()
    draw_edges()
    draw_states()
    draw_particles()
    draw_travel_particles()
    draw_input_flow()
    draw_hud()

    glutSwapBuffers()


# ─────────────────────────────────────────────
#  IDLE  (animation tick)
# ─────────────────────────────────────────────
_last_time = [0.0]

def idle():
    global time_val
    now = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    dt = now - _last_time[0]
    _last_time[0] = now

    time_val += dt
    update_particles(dt)
    update_flash_edges(dt)
    update_travel_particles(dt)
    update_flow(dt)

    # Pulse phases drift
    for s in pulse_states:
        pass  # phase is static per state; time_val drives it

    glutPostRedisplay()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(100, 50)
    glutCreateWindow(b"3D DFA Builder - Animated Edition")

    glEnable(GL_DEPTH_TEST)

    glutDisplayFunc(showScreen)
    glutMouseFunc(mouseListener)
    glutMotionFunc(motionListener)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutIdleFunc(idle)

    glutMainLoop()


if __name__ == "__main__":
    main()
