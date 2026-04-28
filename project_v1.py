import os
import sys
import random
import math
import time
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import cos, radians, sin, sqrt, pi

# ─────────────────────────────────────────────
#  SCREEN FSM & UI GLOBALS
# ─────────────────────────────────────────────
SCREEN      = "INTRO"
intro_timer = 0.0
INTRO_DUR   = 3.5

menu_hover   = 0
MENU_OPTIONS = ["START GAME", "HOW TO PLAY", "QUIT"]
show_how_to  = False
_intro_nodes = None

# Panel dimensions (pixels)
LEFT_W  = 600
RIGHT_W = 1000
WIN_H   = 900
WIN_W   = LEFT_W + RIGHT_W

# ─────────────────────────────────────────────
#  DFA DATA
# ─────────────────────────────────────────────
states      = {}          # id -> {pos, is_start, is_accept}
transitions = {}          # (from_id, char) -> to_id
edge_list   = []          # [(src, dst, char), ...]

selected_state  = None
state_id        = 0

# ─────────────────────────────────────────────
#  CAMERA
# ─────────────────────────────────────────────
camera_x = 45
camera_y = 35
camera_z = 450

# ─────────────────────────────────────────────
#  MODE  ("CHALLENGE" | "FREE")
# ─────────────────────────────────────────────
mode = "CHALLENGE"

# ─────────────────────────────────────────────
#  SCORING & ATTEMPTS
# ─────────────────────────────────────────────
score              = 0
total_score        = 0
current_question   = 0
question_submitted = False
attempts_left      = 5

# ─────────────────────────────────────────────
#  SIMULATION & PARTICLES
# ─────────────────────────────────────────────
sim_states      = []      
sim_index       = -1      
sim_timer       = 0       
sim_string      = ""      
SIM_DELAY       = 30      
frame_count     = 0       

time_val         = 0.0
particle_list    = []
travel_particles = []
flash_edges      = []
pulse_states     = {}
_stars           = None

# ─────────────────────────────────────────────
#  TRANSITION BUILDING
# ─────────────────────────────────────────────
transition_mode = False
transition_src  = None
transition_dst  = None

# ─────────────────────────────────────────────
#  RESULT TEXT
# ─────────────────────────────────────────────
result_text  = ""
result_lines = []

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
        "test_strings": ["00", "100", "010", "11", "101"],
        "expected": {"00": True, "100": True, "010": False, "11": False, "101": False}
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
        "test_strings": ["1", "10", "110", "0", "01", "001"],
        "expected": {"1": True, "10": True, "110": True, "0": False, "01": False, "001": False}
    },
    {
        "rule": "Strings with odd number of 1s",
        "alphabet": ['0', '1'],
        "test_strings": ["1", "11", "111", "0", "10", "110"],
        "expected": {"1": True, "11": False, "111": True, "0": False, "10": True, "110": False}
    },
    {
        "rule": "Strings not containing 11",
        "alphabet": ['0', '1'],
        "test_strings": ["0", "10", "101", "11", "011", "110"],
        "expected": {"0": True, "10": True, "101": True, "11": False, "011": False, "110": False}
    },
]

# ─────────────────────────────────────────────
#  HELPERS & CORE LOGIC
# ─────────────────────────────────────────────
def find_start():
    for s in states:
        if states[s]["is_start"]: return s
    return None

def find_accept():
    acc = set()
    for s in states:
        if states[s]["is_accept"]: acc.add(s)
    return acc

def simulate_dfa(string):
    start   = find_start()
    accepts = find_accept()
    if start is None: return False, []
    current = start
    path    = [current]
    for ch in string:
        if (current, ch) not in transitions: return False, path
        current = transitions[(current, ch)]
        path.append(current)
    return (current in accepts), path

def reset_connections():
    for s in states:
        states[s]["is_start"]  = False
        states[s]["is_accept"] = False
    transitions.clear(); edge_list.clear()

def reset_all():
    global selected_state, state_id, result_text, result_lines
    global sim_states, sim_index, sim_timer, sim_string, attempts_left
    states.clear(); transitions.clear(); edge_list.clear()
    selected_state = None; state_id = 0
    result_text = ""; result_lines = []
    sim_states = []; sim_index = -1; attempts_left = 5

def check_dfa_completeness(alphabet=None):
    if alphabet is None: alphabet = ['0', '1']
    warnings = []
    for s in sorted(states.keys()):
        for ch in alphabet:
            if (s, ch) not in transitions:
                warnings.append(f"Missing: q{s} --'{ch}'--> ?")
    return warnings

# ─────────────────────────────────────────────
#  MISSING UI / TEXT FUNCTIONS
# ─────────────────────────────────────────────
def text_width_full(text):
    return len(text) * 9

def draw_text_scene(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    glColor3f(*color)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text: glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_centered_full(cy, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    w = text_width_full(text)
    draw_text_scene(WIN_W//2 - w//2, cy, text, font, color)

def draw_rect(x, y, w, h, r, g, b, z=-0.5):
    glColor3f(r, g, b)
    glBegin(GL_QUADS)
    glVertex3f(x, y, z); glVertex3f(x+w, y, z)
    glVertex3f(x+w, y+h, z); glVertex3f(x, y+h, z)
    glEnd()

def draw_rect_outline(x, y, w, h, r, g, b, z=-0.4):
    glColor3f(r, g, b)
    glBegin(GL_LINES)
    glVertex3f(x, y, z); glVertex3f(x+w, y, z)
    glVertex3f(x+w, y, z); glVertex3f(x+w, y+h, z)
    glVertex3f(x+w, y+h, z); glVertex3f(x, y+h, z)
    glVertex3f(x, y+h, z); glVertex3f(x, y, z)
    glEnd()
    
    glLineWidth(1)
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)
# ─────────────────────────────────────────────
#  DRAW HELPERS
# ─────────────────────────────────────────────
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, ortho_w=LEFT_W, ortho_h=WIN_H):
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, ortho_w, 0, ortho_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text: glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_color(x, y, text, r, g, b, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(r, g, b)
    draw_text(x, y, text, font)

def draw_text_3d(x, y, z, text, r, g, b, font=GLUT_BITMAP_HELVETICA_12):
    glColor3f(r, g, b); glRasterPos3f(x, y, z)
    for ch in text: glutBitmapCharacter(font, ord(ch))

def draw_arrowhead(x1, y1, z1, x2, y2, z2, offset=28, arrow_len=20, arrow_width=10):
    dx = x2 - x1;  dy = y2 - y1;  dz = z2 - z1
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    if length < 1e-6: return
    ndx = dx / length;  ndy = dy / length;  ndz = dz / length
    tip_x = x2 - ndx * offset; tip_y = y2 - ndy * offset; tip_z = z2 - ndz * offset
    bc_x = tip_x - ndx * arrow_len; bc_y = tip_y - ndy * arrow_len; bc_z = tip_z - ndz * arrow_len
    if abs(ndz) < 0.99: px, py, pz = ndy, -ndx, 0.0
    else: px, py, pz = 1.0, 0.0, 0.0
    pl = math.sqrt(px*px + py*py + pz*pz)
    if pl > 1e-6: px /= pl;  py /= pl;  pz /= pl
    glBegin(GL_TRIANGLES)
    glVertex3f(tip_x, tip_y, tip_z)
    glVertex3f(bc_x + px * arrow_width, bc_y + py * arrow_width, bc_z + pz * arrow_width)
    glVertex3f(bc_x - px * arrow_width, bc_y - py * arrow_width, bc_z - pz * arrow_width)
    glEnd()

# ─────────────────────────────────────────────
#  MISSING PARTICLES & ENVIRONMENT
# ─────────────────────────────────────────────
def spawn_particles(x, y, z, count, color, speed=5.0, lifetime=1.2):
    for _ in range(count):
        angle = random.uniform(0, 2*pi)
        elev  = random.uniform(-pi/3, pi/3)
        spd   = random.uniform(speed*0.5, speed*1.5)
        particle_list.append({
            "x":x,"y":y,"z":z,
            "vx":spd*cos(elev)*cos(angle),
            "vy":spd*cos(elev)*sin(angle),
            "vz":spd*sin(elev),
            "r":color[0],"g":color[1],"b":color[2],
            "life":lifetime,"max_life":lifetime,
        })

def update_particles(dt):
    global particle_list
    new_particles = []
    for p in particle_list:
        p["life"] -= dt
        if p["life"] > 0:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["z"] += p["vz"] * dt
            p["vz"] -= 9.8 * dt
            new_particles.append(p)
    particle_list = new_particles

def draw_particles():
    glDisable(GL_DEPTH_TEST)
    glPointSize(6)
    glBegin(GL_POINTS)
    for p in particle_list:
        a = max(0, p["life"]/p["max_life"])
        glColor3f(p["r"]*a, p["g"]*a, p["b"]*a)
        glVertex3f(p["x"], p["y"], p["z"])
    glEnd()
    glEnable(GL_DEPTH_TEST)

def spawn_travel_particle(path, color=(1,1,1), speed=0.6):
    for i in range(len(path)-1):
        travel_particles.append({"src":path[i],"dst":path[i+1], "t":0.0,"speed":speed,"color":color})

def update_travel_particles(dt):
    for p in travel_particles: p["t"] += dt*p["speed"]
    travel_particles[:] = [p for p in travel_particles if p["t"]<=1.0]

def draw_travel_particles():
    glPointSize(10)
    glBegin(GL_POINTS)
    for p in travel_particles:
        if p["src"] not in states or p["dst"] not in states: continue
        x1,y1,z1=states[p["src"]]["pos"]; x2,y2,z2=states[p["dst"]]["pos"]
        t=p["t"]
        glColor3f(*p["color"])
        glVertex3f(x1+(x2-x1)*t, y1+(y2-y1)*t, z1+(z2-z1)*t)
    glEnd()

def get_stars():
    global _stars
    if _stars is None:
        _stars = [(random.uniform(-800,800), random.uniform(-800,800),
                   random.uniform(-100,600), random.uniform(0.3,1.0)) for _ in range(200)]
    return _stars

def draw_stars():
    glPointSize(2)
    glBegin(GL_POINTS)
    for sx,sy,sz,b in get_stars():
        tw=(sin(time_val*2.3+sx*0.01)+1)*0.3
        glColor3f(b*(0.5+tw),b*(0.6+tw),b*(0.9+tw*0.5))
        glVertex3f(sx,sy,sz)
    glEnd()

def draw_axes():
    glLineWidth(2)
    a=(sin(time_val*0.5)+1)*0.2+0.3
    glBegin(GL_LINES)
    glColor3f(a,0.2*a,0.2*a); glVertex3f(0,0,0); glVertex3f(60,0,0)
    glColor3f(0.2*a,a,0.2*a); glVertex3f(0,0,0); glVertex3f(0,60,0)
    glColor3f(0.2*a,0.5*a,a); glVertex3f(0,0,0); glVertex3f(0,0,60)
    glEnd()

def draw_floor():
    for i in range(-300, 300, 30):
        for j in range(-300, 300, 30):
            glBegin(GL_QUADS)
            if (i + j) // 30 % 2 == 0: glColor3f(0.15, 0.15, 0.25)
            else:                      glColor3f(0.08, 0.08, 0.15)
            glVertex3f(i,      j,      0)
            glVertex3f(i + 30, j,      0)
            glVertex3f(i + 30, j + 30, 0)
            glVertex3f(i,      j + 30, 0)
            glEnd()

# ─────────────────────────────────────────────
#  MISSING SCREENS & MENUS
# ─────────────────────────────────────────────
def get_intro_nodes():
    global _intro_nodes
    if _intro_nodes is None:
        _intro_nodes = []
        for _ in range(9):
            _intro_nodes.append({
                "x":random.uniform(80,WIN_W-80),"y":random.uniform(100,WIN_H-100),
                "vx":random.uniform(-20,20),"vy":random.uniform(-15,15),
                "r":random.uniform(16,28),"phase":random.uniform(0,2*pi),
                "col":random.choice([(0.2,0.5,1.0),(0.1,0.9,0.5),(1.0,0.9,0.0),(0.85,0.3,0.85)])
            })
    return _intro_nodes

def update_intro_nodes(dt):
    for n in get_intro_nodes():
        n["x"]+=n["vx"]*dt; n["y"]+=n["vy"]*dt
        if n["x"]<n["r"] or n["x"]>WIN_W-n["r"]: n["vx"]*=-1
        if n["y"]<n["r"] or n["y"]>WIN_H-n["r"]: n["vy"]*=-1

def draw_intro_nodes():
    global _intro_nodes
    if _intro_nodes is None:
        _intro_nodes = []
        for _ in range(9):
            _intro_nodes.append({"x":random.uniform(80,WIN_W-80),"y":random.uniform(100,WIN_H-100),
                                 "vx":random.uniform(-20,20),"vy":random.uniform(-15,15),
                                 "r":random.uniform(16,28),"phase":random.uniform(0,2*math.pi),
                                 "col":random.choice([(0.2,0.5,1.0),(0.1,0.9,0.5),(1.0,0.9,0.0)])})
    
    for i in range(len(_intro_nodes)):
        for j in range(i+1, len(_intro_nodes)):
            ni, nj = _intro_nodes[i], _intro_nodes[j]
            dist = math.sqrt((ni["x"]-nj["x"])**2 + (ni["y"]-nj["y"])**2)
            if dist < 220:
                alp = (1 - dist/220) * 0.35
                glColor3f(0.2*alp, 0.6*alp, alp)
                glBegin(GL_LINES)
                # Pushed lines backward to -0.8
                glVertex3f(ni["x"], ni["y"], -0.8); glVertex3f(nj["x"], nj["y"], -0.8)
                glEnd()
    
    for n in _intro_nodes:
        n["x"]+=n["vx"]*0.05; n["y"]+=n["vy"]*0.05
        if n["x"]<n["r"] or n["x"]>WIN_W-n["r"]: n["vx"]*=-1
        if n["y"]<n["r"] or n["y"]>WIN_H-n["r"]: n["vy"]*=-1
        pulse = (math.sin(time_val*2+n["phase"])+1)*0.5
        r = n["r"] + 4*pulse; cr, cg, cb = n["col"]
        # Pushed nodes backward to -0.7 and -0.6
        draw_rect(n["x"]-r, n["y"]-r, r*2, r*2, cr*0.25, cg*0.25, cb*0.25, -0.7)
        draw_rect_outline(n["x"]-r, n["y"]-r, r*2, r*2, cr, cg, cb, -0.6)

def draw_intro_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.02,0.02,0.06))
    draw_intro_nodes()
    fade=min(1.0,intro_timer/1.5)
    pulse=(sin(time_val*1.8)+1)*0.5
    mid_y = WIN_H // 2
    draw_text_centered_full(mid_y + 50, "3D  DFA  SIMULATOR", font=GLUT_BITMAP_TIMES_ROMAN_24, color=((0.4+0.4*pulse)*fade,(0.7+0.2*pulse)*fade,fade))
    if intro_timer > INTRO_DUR-0.6:
        blink=(sin(time_val*3)+1)*0.5
        draw_text_centered_full(mid_y - 50, "Press any key to continue ...", color=(0.55*blink,0.88*blink,1.0*blink))

def draw_menu_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.02,0.02,0.06))
    draw_intro_nodes()
    mid_y = WIN_H // 2
    draw_text_centered_full(mid_y + 150, "Build . Test . Master Finite Automata", color=(0.5,0.75,0.85))
    
    for i,label in enumerate(MENU_OPTIONS):
        x = WIN_W//2 - 160
        y = (mid_y + 20) - i*66
        hov=(i==menu_hover)
        bg=(0.08,0.18,0.32) if hov else (0.05,0.08,0.14)
        draw_rect_2d(x,y,320,52,bg)
        bc=(0.3,0.6,1.0) if hov else (0.18,0.32,0.52)
        draw_rect_outline_2d(x,y,320,52,bc,2 if hov else 1)
        tc=(1.0,0.95,0.45) if hov else (0.8,0.9,1.0)
        draw_text_scene(x + 160 - text_width_full(label)//2, y + 18, label, color=tc)
        
    draw_text_centered_full(30, "Use UP/DOWN + ENTER to select", font=GLUT_BITMAP_HELVETICA_12, color=(0.38,0.5,0.55))
def draw_gameover_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.10,0.01,0.01))
    draw_intro_nodes()
    pulse=(sin(time_val*2)+1)*0.5
    draw_text_centered_full(520,"GAME  OVER",font=GLUT_BITMAP_TIMES_ROMAN_24,color=(1.0,0.2+0.2*pulse,0.2))
    draw_text_centered_full(468,"You ran out of attempts.",color=(1.0,0.75,0.75))
    draw_text_centered_full(420,f"Final Score: {total_score}",color=(1.0,0.85,0.3))
    draw_text_centered_full(340,"Press  R  to restart",color=(1.0,1.0,0.5))

def draw_victory_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.01,0.09,0.01))
    draw_intro_nodes()
    pulse=(sin(time_val*2.5)+1)*0.5
    draw_text_centered_full(540,"CONGRATULATIONS!",font=GLUT_BITMAP_TIMES_ROMAN_24,color=(0.2+0.6*pulse,1.0,0.2+0.3*pulse))
    draw_text_centered_full(488,"All questions solved!",color=(0.7,1.0,0.7))
    draw_text_centered_full(440,f"Total Score: {total_score}",color=(1.0,0.95,0.3))
    draw_text_centered_full(360,"Press  R  to play again",color=(1.0,1.0,0.5))

def draw_how_to_overlay():
    draw_rect_2d(80,60,WIN_W-160,WIN_H-120,(0.04,0.06,0.12))
    draw_rect_outline_2d(80,60,WIN_W-160,WIN_H-120,(0.3,0.6,1.0),2)
    draw_text_centered_full(WIN_H-100,"HOW  TO  PLAY",font=GLUT_BITMAP_TIMES_ROMAN_24,color=(0.4,0.9,1.0))
    lines=[
        "C               Create a new state",
        "K               Cycle selected state",
        "W/A/S/D         Move selected state in X-Y plane",
        "Q / E           Move selected state up / down (Z axis)",
        "F               Set selected state as START  (blue)",
        "G               Toggle selected state as ACCEPT  (gold)",
        "Right-Click     Link Source and Destination states",
        "T               Enter transition mode via Keyboard",
        "SPACE           Validate DFA against test strings",
        "N or M          Next question",
        "R               Full reset",
        "X               Undo last edge",
        "Backspace/Del   Delete the selected state and its edges",
        "TAB             Toggle Challenge / Free mode",
        "Arrow keys      Rotate camera   +/-=zoom",
        "Left-click      Select a state sphere",
        "H               Toggle this help screen",
    ]
    y=WIN_H-140
    for ln in lines:
        draw_text_scene(100,y,ln,font=GLUT_BITMAP_HELVETICA_12,color=(0.85,0.9,0.95))
        y-=21
    draw_text_centered_full(80,"Press H or ESC to close",font=GLUT_BITMAP_HELVETICA_12,color=(0.4,0.6,0.7))

# ─────────────────────────────────────────────
#  STATES & EDGES (Drawing)
# ─────────────────────────────────────────────
def draw_states():
    for s in states:
        if s not in pulse_states: pulse_states[s]=random.uniform(0,2*pi)
        pulse=(sin(time_val*2.0+pulse_states[s])+1)*0.5
        x, y, z = states[s]["pos"]
        is_selected = (s == selected_state)
        is_start    = states[s]["is_start"]
        is_accept   = states[s]["is_accept"]
        is_sim      = (sim_index >= 0 and sim_index < len(sim_states) and sim_states[sim_index] == s)

        # (Color math)
        if is_selected:              gr, gg, gb = 1.0, 0.35, 0.35
        elif is_start and is_accept: gr, gg, gb = 0.2, 0.8, 0.8
        elif is_start:               gr, gg, gb = 0.2, 0.5, 1.0
        elif is_accept:              gr, gg, gb = 1.0, 1.0, 0.0
        else:                        gr, gg, gb = 0.15, 0.75, 0.35

        glPushMatrix(); glTranslatef(x, y, z)
        sc = 1.0 + 0.08 * pulse
        glScalef(sc, sc, sc)
        
        # CHANGED: Removed gluQuadricDrawStyle, GLU_FILL, GLU_LINE
        gluSphere(gluNewQuadric(), 28, 16, 16)

        if states[s]["is_accept"]:
            glColor3f(1.0, 1.0, 0.3)
            gluSphere(gluNewQuadric(), 34 + 3 * pulse, 12, 12)
            
        glPopMatrix()
        # ───────────────────────────────────────────────────────────

        # Simulation step highlight
        if is_sim:
            glPushMatrix(); glTranslatef(x, y, z + 56)
            q_sim = gluNewQuadric()
            
            # Simply draw a solid, pulsing magenta sphere
            # No banned gluQuadricDrawStyle or GLU_LINE functions needed!
            glColor3f(1.0, 0.2, 1.0)
            gluSphere(q_sim, 12 + 2 * pulse, 12, 12)
            
            glPopMatrix()

        draw_text_3d(x + 32, y + 32, z, f"q{s}", 1, 1, 1)

def draw_self_loop(x, y, z, char, src):
    R = 40; cx = x; cy = y; cz = z + 28 + R
    glColor3f(1, 0.6, 0); glLineWidth(2)
    glBegin(GL_LINE_LOOP)
    for i in range(32):
        angle = 2 * math.pi * i / 32
        glVertex3f(cx + R * math.cos(angle), cy + R * math.sin(angle), cz)
    glEnd()
    draw_text_3d(cx + R + 4, cy, cz, f"q{src}-{char}->q{src}", 1, 0.6, 0)

def draw_edges():
    grouped_edges = {}
    for src, dst, ch in edge_list:
        if (src, dst) not in grouped_edges: grouped_edges[(src, dst)] = []
        if ch not in grouped_edges[(src, dst)]: grouped_edges[(src, dst)].append(ch)

    for (src, dst), chars in grouped_edges.items():
        x1, y1, z1 = states[src]["pos"]
        x2, y2, z2 = states[dst]["pos"]
        combined_ch = "/".join(sorted(chars))

        if src == dst:
            draw_self_loop(x1, y1, z1, combined_ch, src)
            continue

        ddx = x2 - x1;  ddy = y2 - y1;  ddz = z2 - z1
        seg_len = math.sqrt(ddx*ddx + ddy*ddy + ddz*ddz)
        if seg_len < 1e-6: continue
        ndx = ddx / seg_len;  ndy = ddy / seg_len;  ndz = ddz / seg_len

        has_reverse = any(e2[0] == dst and e2[1] == src for e2 in edge_list)
        if has_reverse:
            px, py = ndy, -ndx 
            pl = math.sqrt(px*px + py*py)
            if pl > 1e-6: px /= pl;  py /= pl
            off = 14
            lx1 = x1 + px*off;  ly1 = y1 + py*off;  lz1 = z1
            lx2 = x2 + px*off;  ly2 = y2 + py*off;  lz2 = z2
        else:
            lx1, ly1, lz1 = x1, y1, z1
            lx2, ly2, lz2 = x2, y2, z2

        glColor3f(0.75, 0.85, 1.0); glLineWidth(2)
        glBegin(GL_LINES)
        glVertex3f(lx1, ly1, lz1)
        glVertex3f(lx2, ly2, lz2)
        glEnd()

        glColor3f(0.4, 1.0, 0.55)
        draw_arrowhead(lx1, ly1, lz1, lx2, ly2, lz2)

        mx = (lx1 + lx2) / 2; my = (ly1 + ly2) / 2; mz = (lz1 + lz2) / 2 + 12
        draw_text_3d(mx, my, mz, combined_ch, 1.0, 0.9, 0.3)

def draw_sim_marker():
    if sim_index < 0 or sim_index >= len(sim_states): return
    sid = sim_states[sim_index]
    if sid not in states: return
    x, y, z = states[sid]["pos"]
    glPushMatrix(); glTranslatef(x, y, z + 50)
    glColor3f(1, 0, 1); gluSphere(gluNewQuadric(), 12, 12, 12)
    glPopMatrix()

# ─────────────────────────────────────────────
#  CAMERA
# ─────────────────────────────────────────────
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = RIGHT_W / WIN_H
    gluPerspective(90, aspect, 0.1, 2000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    x = camera_z * cos(radians(camera_y)) * cos(radians(camera_x))
    y = camera_z * cos(radians(camera_y)) * sin(radians(camera_x))
    z = camera_z * sin(radians(camera_y))
    gluLookAt(x, y, z, 0, 0, 0, 0, 0, 1)

# ─────────────────────────────────────────────
#  HUD (LEFT PANEL)
# ─────────────────────────────────────────────
def draw_hud():
    if mode == "CHALLENGE":
        q = questions[current_question]
        draw_text_color(10, 875, f"[CHALLENGE]  Q{current_question+1}/{len(questions)}  |  Total Score: {total_score}", 0.4, 0.9, 1.0)
        draw_text_color(10, 850, f"Rule: {q['rule']}", 1.0, 0.85, 0.2)
        att_col=(1.0,0.35,0.35) if attempts_left<=2 else (1.0,0.7,0.3)
        draw_text_color(10,825, f"Attempts left: {attempts_left}", *att_col)
    else:
        draw_text_color(10, 875, "[FREE MODE]  Build any DFA", 0.6, 1.0, 0.6)

    draw_text_color(10, 790, "C=new state  K=cycle select  F=set start  G=set accept", 0.75, 0.75, 0.75, GLUT_BITMAP_HELVETICA_12)
    draw_text_color(10, 774, "T=start transition  0/1=set label  X=undo edge  Backspace=delete state", 0.75, 0.75, 0.75, GLUT_BITMAP_HELVETICA_12)
    draw_text_color(10, 758, "W/A/S/D=move XY  Q/E=move Z  +/-=zoom  Arrows=rotate cam", 0.75, 0.75, 0.75, GLUT_BITMAP_HELVETICA_12)
    draw_text_color(10, 742, "SPACE=validate  N=next Q  R=reset  TAB=toggle free/challenge", 0.75, 0.75, 0.75, GLUT_BITMAP_HELVETICA_12)
    draw_text_color(10, 723, "-" * 60, 0.35, 0.35, 0.55, GLUT_BITMAP_HELVETICA_12)

    sc = (1.0, 0.45, 0.2) if selected_state is not None else (0.4, 0.4, 0.4)
    draw_text_color(10, 703, f"Selected : q{selected_state}", *sc)
    draw_text_color(10, 681, f"Start    : q{find_start()}",   0.4, 0.7, 1.0)
    draw_text_color(10, 659, f"Accept   : {sorted(find_accept())}", 1.0, 0.85, 0.2)

    if transition_mode:
        dst_label = f"q{transition_dst}" if transition_dst is not None else f"q{selected_state}"
        draw_text_color(10, 630, f">> TRANSITION MODE  q{transition_src} -> {dst_label}  (type char)", 1, 0.3, 0.3)

    draw_text_color(10, 600, "Transitions:", 0.6, 0.85, 1.0)
    ty = 580
    for e in edge_list:
        draw_text_color(18, ty, f"q{e[0]} --{e[2]}--> q{e[1]}", 0.8, 0.9, 1.0, GLUT_BITMAP_HELVETICA_12)
        ty -= 18
        if ty < 370: break

    draw_text_color(10, 355, "-" * 60, 0.35, 0.35, 0.55, GLUT_BITMAP_HELVETICA_12)
    draw_text_color(10, 335, "Validation Results:", 0.6, 0.85, 1.0)
    y_r = 313
    for line in result_lines:
        if "OK" in line:    draw_text_color(10, y_r, line, 0.3, 1.0, 0.4)
        elif "WRONG" in line: draw_text_color(10, y_r, line, 1.0, 0.3, 0.3)
        elif "Score" in line: draw_text_color(10, y_r, line, 1.0, 0.85, 0.2)
        else:               draw_text_color(10, y_r, line, 1, 1, 1)
        y_r -= 22

    draw_text_color(10, 18, "Blue=Start  Yellow=Accept  Cyan=Start+Accept  Red=Sel  Magenta=Sim", 0.5, 0.5, 0.65, GLUT_BITMAP_HELVETICA_12)

# ─────────────────────────────────────────────
#  MOUSE INTERACTION (From GitHub Version)
# ─────────────────────────────────────────────

def mouseListener(button, state_btn, x, y):
    global selected_state, SCREEN, show_how_to, camera_z, menu_hover
    global transition_mode, transition_src, transition_dst

    gl_y = WIN_H - y

    if SCREEN=="INTRO":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if intro_timer>=INTRO_DUR-0.6: SCREEN="MENU"
        return

    if SCREEN=="MENU":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if show_how_to: show_how_to=False; return
            # Simple check for Menu buttons
            for i in range(len(MENU_OPTIONS)):
                item_h=52; gap=14
                total=(len(MENU_OPTIONS)*item_h+(len(MENU_OPTIONS)-1)*gap)
                base_y=WIN_H//2-total//2-20
                w=320; bx=WIN_W//2-w//2
                by=base_y+(len(MENU_OPTIONS)-1-i)*(item_h+gap)
                if bx<=x<=bx+w and by<=gl_y<=by+item_h:
                    if MENU_OPTIONS[i]=="START GAME": SCREEN="PLAYING"
                    elif MENU_OPTIONS[i]=="HOW TO PLAY": show_how_to=True
                    elif MENU_OPTIONS[i]=="QUIT": 
                        os._exit(0)  # <--- CHANGED THIS LINE
                    return
        return

    if SCREEN in ("GAMEOVER","VICTORY"): return


# ─────────────────────────────────────────────
#  KEYBOARD (Your Core Logic + Screens)
# ─────────────────────────────────────────────
def keyboardListener(key, x, y):
    global state_id, selected_state, transition_mode, transition_src, transition_dst
    global current_question, result_text, result_lines, camera_z, SCREEN, attempts_left
    global score, total_score, mode, question_submitted, show_how_to, menu_hover
    global sim_states, sim_index, sim_timer, sim_string
    global edge_list, flash_edges, travel_particles, sim_states, sim_index

    if SCREEN=="INTRO":
        if intro_timer>=INTRO_DUR-0.6: SCREEN="MENU"
        return
    if SCREEN=="MENU":
        if show_how_to and key in (b'h',b'H',b'\x1b'): show_how_to=False; return
        if key in (b'\r',b'\n'):
            if menu_hover==0: SCREEN="PLAYING"
            elif menu_hover==1: show_how_to=True
            elif menu_hover==2:
                os._exit(0)
        return
    if SCREEN=="GAMEOVER" or SCREEN=="VICTORY":
        if key==b'r': SCREEN="PLAYING"; reset_all(); current_question=0; total_score=0
        return

    if show_how_to and key in (b'h',b'H',b'\x1b'): show_how_to=False; return
    if key in (b'h',b'H'): show_how_to=True; return

    if key == b'c':
        a = random.uniform(-180, 180)
        b = random.uniform(-180, 180)
        states[state_id] = {"pos": [a, b, 60], "is_start": False, "is_accept": False}
        spawn_particles(a,b,60,20,(0.1,0.9,0.5),speed=8)
        selected_state = state_id
        state_id += 1

    if key == b'k' and states:
        keys = list(states.keys())
        if selected_state not in keys: selected_state = keys[0]
        else:
            i = keys.index(selected_state)
            selected_state = keys[(i + 1) % len(keys)]

    if selected_state is not None and selected_state in states:
        pos = states[selected_state]["pos"]
        if key == b'w': pos[1] += 15
        if key == b's': pos[1] -= 15
        if key == b'a': pos[0] -= 15
        if key == b'd': pos[0] += 15
        if key == b'q': pos[2] += 15
        if key == b'e': pos[2] -= 15
        if key == b'f':
            for sid in states: states[sid]["is_start"] = False
            states[selected_state]["is_start"] = True
            spawn_particles(*states[selected_state]["pos"],30,(0.2,0.5,1.0),speed=10)
        if key == b'g':
            states[selected_state]["is_accept"] = not states[selected_state]["is_accept"]

    if key == b't' and selected_state is not None:
        transition_mode = True
        transition_src  = selected_state
        return

    if key == b'x':
        if edge_list:
            last = edge_list.pop()
            key_t = (last[0], last[2])
            if key_t in transitions: del transitions[key_t]
        transition_mode = False
        transition_src  = None

    if transition_mode and transition_src is not None:
        try: char=key.decode("utf-8","ignore")
        except Exception: char=""
        if char.isalnum():
            dst = transition_dst if transition_dst is not None else selected_state
            if dst is not None and dst in states:
                tkey = (transition_src, char)
                if tkey in transitions:
                    old_dst = transitions[tkey]
                    if (transition_src, old_dst, char) in edge_list:
                        edge_list.remove((transition_src, old_dst, char))
                transitions[tkey] = dst
                edge_list.append((transition_src, dst, char))
                if transition_src in states:
                    px=(states[transition_src]["pos"][0]+states[dst]["pos"][0])/2
                    py=(states[transition_src]["pos"][1]+states[dst]["pos"][1])/2
                    pz=(states[transition_src]["pos"][2]+states[dst]["pos"][2])/2
                    spawn_particles(px,py,pz,25,(0.3,0.8,1.0),speed=6)
            transition_mode=False; transition_src=None; transition_dst=None
            return
    # ── Delete Selected State (Backspace or Delete key) ───────
    if key in (b'\x08', b'\x7f'): 
        if selected_state is not None and selected_state in states:
            target_id = selected_state

            # 1. Remove the state itself
            del states[target_id]

            # 2. Remove any transitions involving this state (both incoming and outgoing)
            keys_to_delete = []
            for (src, char), dst in transitions.items():
                if src == target_id or dst == target_id:
                    keys_to_delete.append((src, char))
            for k in keys_to_delete:
                del transitions[k]

            # 3. Clean up visual edge list
            edge_list = [e for e in edge_list if e[0] != target_id and e[1] != target_id]

            # 4. Clean up any active animations to prevent crashes
            flash_edges = [fe for fe in flash_edges if fe[0] != target_id and fe[1] != target_id]
            travel_particles = [p for p in travel_particles if p["src"] != target_id and p["dst"] != target_id]
            
            if target_id in sim_states:
                sim_states = []
                sim_index = -1

            # 5. Clear transition mode if we deleted the source
            if transition_src == target_id:
                transition_mode = False
                transition_src = None
                transition_dst = None

            # 6. Deselect
            selected_state = None
    # YOUR CORE VALIDATION
    if key == b' ':
        sim_states   = []
        sim_index    = -1
        result_lines = []

        alph = questions[current_question]["alphabet"] if mode == "CHALLENGE" else ['0', '1']
        incomplete = check_dfa_completeness(alph)

        if not states:
            result_lines.append("No states defined yet.")
        elif find_start() is None:
            result_lines.append("No start state! Press F to set one.")
        elif incomplete:
            result_lines.append("!! DFA INCOMPLETE !!")
            for w in incomplete[:6]: result_lines.append(w)
            if len(incomplete) > 6: result_lines.append(f"  (+{len(incomplete)-6} more...)")
        else:
            if mode == "CHALLENGE":
                q       = questions[current_question]
                q_score = 0
                for string in q["test_strings"]:
                    res, path = simulate_dfa(string)
                    if not sim_states:
                        sim_states = path; sim_string = string
                    correct = q["expected"][string]
                    disp    = repr(string) if string == "" else string
                    
                    if res == correct:
                        q_score += 1
                        result_lines.append(f"'{disp}': OK")
                        col = (0.2,1.0,0.4) 
                    else:
                        result_lines.append(f"'{disp}': WRONG")
                        col = (1.0,0.3,0.3)
                    spawn_travel_particle(path, col)
                total = len(q["test_strings"])
                
                # Scoring & Attempts
                if q_score == total:
                    result_lines.append(f"Score: {q_score}/{total} - PERFECT!")
                    for s in states: spawn_particles(*states[s]["pos"], 60, (1.0,0.9,0.1), speed=15, lifetime=2.5)
                    if not question_submitted:
                        total_score += q_score; question_submitted = True
                else:
                    attempts_left -= 1
                    result_lines.append(f"Score: {q_score}/{total} - Attempts: {attempts_left}")
                    if attempts_left <= 0: SCREEN = "GAMEOVER"
            else:
                result_lines.append("Free Mode - no scoring.")
                if states:
                    test_str = "01"
                    res, path = simulate_dfa(test_str)
                    sim_states = path; sim_string = test_str
                    result_lines.append(f"Sim '{test_str}': {'ACCEPT' if res else 'REJECT'}")

        if sim_states: sim_index = 0; sim_timer = 0

    if key in (b'n', b'm'):
        if mode == "CHALLENGE" and current_question < len(questions) - 1:
            current_question   += 1
            question_submitted  = False
            attempts_left       = 5
        elif mode == "CHALLENGE" and current_question == len(questions) - 1:
            SCREEN = "VICTORY"
        reset_connections()
        result_lines = []; sim_states = []; sim_index = -1

    if key in (b'+', b'='):
        if camera_z > 100: camera_z -= 30
    if key == b'-':
        if camera_z < 1500: camera_z += 30

    if key == b'r':
        reset_all(); current_question=0; total_score=0; question_submitted=False

    if key == b'\t':
        mode = "FREE" if mode == "CHALLENGE" else "CHALLENGE"
        reset_all(); current_question=0; total_score=0; question_submitted=False

def specialKeyListener(key, x, y):
    global camera_x, camera_y, menu_hover
    if SCREEN=="MENU":
        if key == GLUT_KEY_DOWN: menu_hover = min(len(MENU_OPTIONS)-1, menu_hover+1)
        if key == GLUT_KEY_UP:   menu_hover = max(0, menu_hover-1)
        return
    if key == GLUT_KEY_LEFT:  camera_x -= 5
    if key == GLUT_KEY_RIGHT: camera_x += 5
    if key == GLUT_KEY_UP:
        if camera_y < 89: camera_y += 5
    if key == GLUT_KEY_DOWN:
        if camera_y > 5:  camera_y -= 5

# ─────────────────────────────────────────────
#  SIMULATION TICK
# ─────────────────────────────────────────────
def tick_simulation():
    global sim_index, sim_timer
    if sim_index < 0 or sim_index >= len(sim_states): return
    sim_timer += 1
    if sim_timer >= SIM_DELAY:
        sim_timer  = 0
        sim_index += 1
        if sim_index >= len(sim_states):
            sim_index = len(sim_states) - 1

# ─────────────────────────────────────────────
#  DISPLAY
# ─────────────────────────────────────────────
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    if SCREEN in ("INTRO", "MENU", "GAMEOVER", "VICTORY"):
        glViewport(0, 0, WIN_W, WIN_H)
        glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluOrtho2D(0, WIN_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()

        # Banned glClearColor replacement: Draw massive quad pushed far back to -0.9
        if SCREEN == "GAMEOVER": draw_rect(0,0,WIN_W,WIN_H, 0.1,0.0,0.0, -0.9)
        elif SCREEN == "VICTORY": draw_rect(0,0,WIN_W,WIN_H, 0.0,0.1,0.0, -0.9)
        else: draw_rect(0,0,WIN_W,WIN_H, 0.02,0.02,0.06, -0.9)

        draw_intro_nodes()
        mid_y = WIN_H // 2

        if SCREEN == "INTRO":
            fd = min(1.0, intro_timer/1.5)
            t1 = "3D DFA SIMULATOR"
            draw_text_color(WIN_W//2 - text_width_est(t1)//2, mid_y+50, t1, 0.4*fd, 0.7*fd, fd)
            if intro_timer > 1.5: 
                t2 = "Press any key..."
                draw_text_color(WIN_W//2 - text_width_est(t2)//2, mid_y-50, t2, 0.6, 0.9, 1.0)
        elif SCREEN == "MENU":
            t3 = "Master Finite Automata"
            draw_text_color(WIN_W//2 - text_width_est(t3)//2, mid_y+150, t3, 0.5, 0.75, 0.85)
            for i, lbl in enumerate(MENU_OPTS):
                y = (mid_y+20) - i*66
                draw_rect(WIN_W//2-160, y, 320, 52, 0.05, 0.08, 0.14, -0.5)
                draw_rect_outline(WIN_W//2-160, y, 320, 52, 0.18, 0.32, 0.52, -0.4)
                draw_text_color(WIN_W//2 - text_width_est(lbl)//2, y+18, lbl, 0.8, 0.9, 1.0)
            if show_how_to:
                draw_rect(80,60,WIN_W-160,WIN_H-120, 0.04,0.06,0.12, -0.2)
                draw_rect_outline(80,60,WIN_W-160,WIN_H-120, 0.3,0.6,1.0, -0.1)
                t4 = "HOW TO PLAY"
                draw_text_color(WIN_W//2 - text_width_est(t4)//2, WIN_H-100, t4, 0.4, 0.9, 1.0)
                draw_text_color(100, WIN_H-160, "NO MOUSE IN 3D DUE TO CONSTRAINTS.", 1,1,0)
                draw_text_color(100, WIN_H-200, "C: New State | K: Cycle State | DEL: Delete", 0.8,0.9,1)
                draw_text_color(100, WIN_H-230, "T: Transition (Select Source, Press T, Select Dest, Press 0/1)", 0.8,0.9,1)
        elif SCREEN == "GAMEOVER":
            t5 = "GAME OVER"
            t6 = "Press R to Restart"
            draw_text_color(WIN_W//2 - text_width_est(t5)//2, mid_y+50, t5, 1,0.2,0.2)
            draw_text_color(WIN_W//2 - text_width_est(t6)//2, mid_y, t6, 1,1,0.5)
        elif SCREEN == "VICTORY":
            t7 = "CONGRATULATIONS"
            draw_text_color(WIN_W//2 - text_width_est(t7)//2, mid_y+50, t7, 0.2,1.0,0.2)

    elif SCREEN == "PLAYING":
        # 3D Scene (Right Panel)
        glViewport(LEFT_W, 0, RIGHT_W, WIN_H)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(90, RIGHT_W/WIN_H, 0.1, 2000)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        ex = camera_z * math.cos(math.radians(camera_y)) * math.cos(math.radians(camera_x))
        ey = camera_z * math.cos(math.radians(camera_y)) * math.sin(math.radians(camera_x))
        ez = camera_z * math.sin(math.radians(camera_y))
        gluLookAt(ex, ey, ez, 0, 0, 0, 0, 0, 1)

        draw_floor()
        draw_axes()
        draw_edges()
        draw_states()
        draw_particles()

        # 2D HUD (Left Panel)
        glViewport(0, 0, LEFT_W, WIN_H)
        glClear(GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluOrtho2D(0, LEFT_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        
        # Pushed the HUD background far back to -0.9 so HUD text shows up!
        draw_rect(0,0,LEFT_W,WIN_H, 0.07,0.07,0.14, -0.9) 
        draw_hud()

    glutSwapBuffers()

_last_time = [0.0]

def idle():
    global frame_count, time_val, intro_timer
    now = time.time()
    dt = min(now - _last_time[0], 0.05)
    _last_time[0] = now
    
    time_val += dt
    frame_count += 1

    if SCREEN in ("INTRO","MENU","GAMEOVER","VICTORY"):
        if SCREEN=="INTRO": intro_timer+=dt
        update_intro_nodes(dt)
    elif SCREEN=="PLAYING":
        update_particles(dt)
        update_travel_particles(dt)
        for fe in flash_edges:
            fe[2] = min(1.0, fe[2] + dt * 0.6)
        tick_simulation()

    glutPostRedisplay()

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"3D DFA Builder - CSE 423")

    glEnable(GL_DEPTH_TEST)
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()

if __name__ == "__main__":
    main()
