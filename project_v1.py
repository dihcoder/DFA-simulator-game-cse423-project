
import random 
import math
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import cos, radians, sin, sqrt, pi

# ══════════════════════════════════════════════════════════════════
#  SCREEN FSM:  INTRO -> MENU -> PLAYING  |  GAMEOVER  |  VICTORY
# ══════════════════════════════════════════════════════════════════
SCREEN      = "INTRO"
intro_timer = 0.0
INTRO_DUR   = 3.5

menu_hover   = 0
MENU_OPTIONS = ["START GAME", "HOW TO PLAY", "QUIT"]
show_how_to  = False

# ── Window / panel layout ─────────────────────────────────────────
LEFT_W  = 420      # 2-D HUD panel width
RIGHT_W = 780      # 3-D scene panel width
WIN_W   = LEFT_W + RIGHT_W   # = 1200
WIN_H   = 860

# ══════════════════════════════════════════════════════════════════
#  DFA CORE STATE
# ══════════════════════════════════════════════════════════════════
states      = {}
transitions = {}
edge_list   = []

selected_state = None
state_id       = 0

camera_x = 45
camera_y = 35
camera_z = 450

# ── Scoring / question ────────────────────────────────────────────
mode               = "CHALLENGE"   # "CHALLENGE" | "FREE"
current_question   = 0
score              = 0
total_score        = 0
attempts_left      = 5
question_submitted = False
result_lines       = []

# ── Simulation animation (step-by-step marker) ───────────────────
sim_states  = []
sim_index   = -1
sim_timer   = 0
sim_string  = ""
SIM_DELAY   = 30       # frames between steps
frame_count = 0

# ── Particle / flash animation ────────────────────────────────────
time_val         = 0.0
particle_list    = []
pulse_states     = {}
flash_edges      = []
travel_particles = []

# ── Transition mode ───────────────────────────────────────────────
transition_mode = False
transition_src  = None
transition_dst  = None    # set by right-click; None means "use selected_state"

# ── Decorative intro nodes / stars ───────────────────────────────
_stars       = None
_intro_nodes = None

# ── Mouse drag ────────────────────────────────────────────────────
mouse_x, mouse_y = 0, 0
dragging_state   = None
cam_drag_active  = False
cam_drag_ox = 0;  cam_drag_oy = 0
cam_drag_cx = 0;  cam_drag_cy = 0

# ══════════════════════════════════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════════════════════════════════
questions = [
    {"rule": "Strings ending with 01",
     "alphabet": ["0","1"],
     "test_strings": ["01","101","1101","10","111"],
     "expected": {"01":True,"101":True,"1101":True,"10":False,"111":False}},
    {"rule": "Strings containing 00",
     "alphabet": ["0","1"],
     "test_strings": ["00","100","010","11","101"],
     "expected": {"00":True,"100":True,"010":False,"11":False,"101":False}},
    {"rule": "Strings of even length",
     "alphabet": ["0","1"],
     "test_strings": ["","01","1001","0","100","11"],
     "expected": {"":True,"01":True,"1001":True,"0":False,"100":False,"11":True}},
    {"rule": "Strings starting with 1",
     "alphabet": ["0","1"],
     "test_strings": ["1","10","110","0","01","001"],
     "expected": {"1":True,"10":True,"110":True,"0":False,"01":False,"001":False}},
    {"rule": "Strings with odd number of 1s",
     "alphabet": ["0","1"],
     "test_strings": ["1","11","111","0","10","110"],
     "expected": {"1":True,"11":False,"111":True,"0":False,"10":True,"110":False}},
    {"rule": "Strings not containing 11",
     "alphabet": ["0","1"],
     "test_strings": ["0","10","101","11","011","110"],
     "expected": {"0":True,"10":True,"101":True,"11":False,"011":False,"110":False}},
]

# ══════════════════════════════════════════════════════════════════
#  RULE / VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════
def check_rule(rule, s):
    if rule == "Strings ending with 01":        return s.endswith("01")
    if rule == "Strings containing 00":         return "00" in s
    if rule == "Strings of even length":        return len(s) % 2 == 0
    if rule == "Strings starting with 1":       return s.startswith("1")
    if rule == "Strings with odd number of 1s": return s.count("1") % 2 == 1
    if rule == "Strings not containing 11":     return "11" not in s
    return False

def generate_strings(alphabet, max_len=4):
    res = [""]
    for _ in range(max_len):
        res += [s+c for s in res for c in alphabet]
    return list(set(res))

def validate_against_rule(rule, alphabet):
    for s in generate_strings(alphabet, 4):
        ok, _ = simulate_dfa(s)
        if ok != check_rule(rule, s):
            return False
    return True

def check_dfa_completeness(alphabet=None):
    if alphabet is None: alphabet = ["0","1"]
    warnings = []
    for s in sorted(states.keys()):
        for ch in alphabet:
            if (s, ch) not in transitions:
                warnings.append(f"Missing: q{s} --'{ch}'--> ?")
    return warnings

# ══════════════════════════════════════════════════════════════════
#  DFA CORE
# ══════════════════════════════════════════════════════════════════
def find_start():
    for s in states:
        if states[s]["is_start"]: return s
    return None

def find_accept():
    return {s for s in states if states[s]["is_accept"]}

def simulate_dfa(string):
    start = find_start()
    if start is None: return False, []
    cur = start; path = [cur]
    for ch in string:
        if (cur, ch) not in transitions: return False, path
        cur = transitions[(cur, ch)]; path.append(cur)
    return cur in find_accept(), path

def reset_connections():
    for s in states:
        states[s]["is_start"]  = False
        states[s]["is_accept"] = False
    transitions.clear(); edge_list.clear(); flash_edges.clear()

def reset_all():
    global selected_state, state_id, result_text, result_lines
    global sim_states, sim_index, sim_timer, sim_string, score
    states.clear(); transitions.clear(); edge_list.clear()
    flash_edges.clear(); particle_list.clear()
    selected_state = None; state_id = 0
    result_text = ""; result_lines = []; score = 0
    sim_states = []; sim_index = -1; sim_timer = 0; sim_string = ""

# ══════════════════════════════════════════════════════════════════
#  PARTICLES
# ══════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════
#  TRAVEL PARTICLES  (slide along edges)
# ══════════════════════════════════════════════════════════════════
def spawn_travel_particle(path, color=(1,1,1), speed=0.6):
    for i in range(len(path)-1):
        travel_particles.append({"src":path[i],"dst":path[i+1],
                                  "t":0.0,"speed":speed,"color":color})

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

# ══════════════════════════════════════════════════════════════════
#  STAR FIELD
# ══════════════════════════════════════════════════════════════════
def get_stars():
    global _stars
    if _stars is None:
        _stars = [(random.uniform(-800,800),
                   random.uniform(-800,800),
                   random.uniform(-100,600),
                   random.uniform(0.3,1.0)) for _ in range(200)]
    return _stars

def draw_stars():
    glPointSize(2)
    glBegin(GL_POINTS)
    for sx,sy,sz,b in get_stars():
        tw=(sin(time_val*2.3+sx*0.01)+1)*0.3
        glColor3f(b*(0.5+tw),b*(0.6+tw),b*(0.9+tw*0.5))
        glVertex3f(sx,sy,sz)
    glEnd()

def draw_floor():
    for i in range(-300,300,30):
        for j in range(-300,300,30):
            glBegin(GL_QUADS)
            if (i+j)//30 % 2 == 0: glColor3f(0.12,0.12,0.22)
            else:                   glColor3f(0.06,0.06,0.13)
            glVertex3f(i,j,0);       glVertex3f(i+30,j,0)
            glVertex3f(i+30,j+30,0); glVertex3f(i,j+30,0)
            glEnd()
    # Animated horizon ring
    glLineWidth(2)
    for i in range(64):
        a0=2*pi*i/64; a1=2*pi*(i+1)/64
        p=(sin(time_val*1.2+a0*2)+1)*0.5
        glColor3f(0.0,0.25+0.2*p,0.45+0.3*p)
        glBegin(GL_LINES)
        glVertex3f(280*cos(a0),280*sin(a0),0)
        glVertex3f(280*cos(a1),280*sin(a1),0)
        glEnd()

def draw_axes():
    glLineWidth(2)
    a=(sin(time_val*0.5)+1)*0.2+0.3
    glBegin(GL_LINES)
    glColor3f(a,0.2*a,0.2*a); glVertex3f(0,0,0); glVertex3f(60,0,0)
    glColor3f(0.2*a,a,0.2*a); glVertex3f(0,0,0); glVertex3f(0,60,0)
    glColor3f(0.2*a,0.5*a,a); glVertex3f(0,0,0); glVertex3f(0,0,60)
    glEnd()

# ══════════════════════════════════════════════════════════════════
#  ARROW HEAD (from doc2)
# ══════════════════════════════════════════════════════════════════
def draw_arrowhead(x1,y1,z1, x2,y2,z2, offset=28, arrow_len=18, arrow_width=9):
    dx=x2-x1; dy=y2-y1; dz=z2-z1
    length=math.sqrt(dx*dx+dy*dy+dz*dz)
    if length<1e-6: return
    ndx=dx/length; ndy=dy/length; ndz=dz/length
    tip_x=x2-ndx*offset; tip_y=y2-ndy*offset; tip_z=z2-ndz*offset
    bc_x=tip_x-ndx*arrow_len; bc_y=tip_y-ndy*arrow_len; bc_z=tip_z-ndz*arrow_len
    if abs(ndz)<0.99: px,py,pz=ndy,-ndx,0.0
    else:             px,py,pz=1.0,0.0,0.0
    pl=math.sqrt(px*px+py*py+pz*pz)
    if pl>1e-6: px/=pl; py/=pl; pz/=pl
    glBegin(GL_TRIANGLES)
    glVertex3f(tip_x,tip_y,tip_z)
    glVertex3f(bc_x+px*arrow_width, bc_y+py*arrow_width, bc_z+pz*arrow_width)
    glVertex3f(bc_x-px*arrow_width, bc_y-py*arrow_width, bc_z-pz*arrow_width)
    glEnd()

def draw_self_loop(x,y,z,char,src):
    R=42; segs=32; cx=x; cy=y; cz=z+28+R
    glColor3f(1,0.6,0); glLineWidth(2)
    glBegin(GL_LINE_LOOP)
    for i in range(segs):
        angle=2*math.pi*i/segs
        glVertex3f(cx+R*math.cos(angle), cy+R*math.sin(angle), cz)
    glEnd()

# ══════════════════════════════════════════════════════════════════
#  TEXT / 2-D DRAW HELPERS
#  draw_text uses LEFT panel ortho (0..LEFT_W x 0..WIN_H)
#  draw_text_scene uses scene-space 3-D position via glRasterPos3f
# ══════════════════════════════════════════════════════════════════
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    """Render 2-D overlay text in the LEFT HUD panel coordinate space."""
    glColor3f(*color)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, LEFT_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_scene(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    """Render 2-D overlay text in the FULL window coordinate space (used by menus)."""
    glColor3f(*color)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_3d(x,y,z,text,r,g,b,font=GLUT_BITMAP_HELVETICA_12):
    glColor3f(r,g,b)
    glRasterPos3f(x,y,z)
    for ch in text:
        glutBitmapCharacter(font,ord(ch))

def text_width_full(text, font=GLUT_BITMAP_HELVETICA_18):
    return sum(glutBitmapWidth(font,ord(c)) for c in text)

def draw_text_centered_full(cy, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    w = text_width_full(text, font)
    draw_text_scene(WIN_W//2 - w//2, cy, text, font, color)

def draw_rect_2d(x,y,w,h,color):
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*color)
    glBegin(GL_QUADS)
    glVertex2f(x,y); glVertex2f(x+w,y); glVertex2f(x+w,y+h); glVertex2f(x,y+h)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)

def draw_rect_outline_2d(x,y,w,h,color,lw=2):
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*color); glLineWidth(lw)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x,y); glVertex2f(x+w,y); glVertex2f(x+w,y+h); glVertex2f(x,y+h)
    glEnd()
    glLineWidth(1)
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)

# ══════════════════════════════════════════════════════════════════
#  INTRO / MENU  FLOATING NODES
# ══════════════════════════════════════════════════════════════════
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
    nodes=get_intro_nodes()
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            ni,nj=nodes[i],nodes[j]
            dist=sqrt((ni["x"]-nj["x"])**2+(ni["y"]-nj["y"])**2)
            if dist<220:
                alp=(1-dist/220)*0.35
                glLineWidth(1); glColor3f(0.2*alp,0.6*alp,alp)
                glBegin(GL_LINES); glVertex2f(ni["x"],ni["y"]); glVertex2f(nj["x"],nj["y"]); glEnd()
    for n in nodes:
        pulse=(sin(time_val*2+n["phase"])+1)*0.5
        r=n["r"]+4*pulse; cr,cg,cb=n["col"]
        glColor3f(cr*0.25,cg*0.25,cb*0.25)
        glBegin(GL_TRIANGLE_FAN); glVertex2f(n["x"],n["y"])
        for k in range(25): a=2*pi*k/24; glVertex2f(n["x"]+r*cos(a),n["y"]+r*sin(a))
        glEnd()
        glColor3f(cr,cg,cb); glLineWidth(2)
        glBegin(GL_LINE_LOOP)
        for k in range(24): a=2*pi*k/24; glVertex2f(n["x"]+r*cos(a),n["y"]+r*sin(a))
        glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glEnable(GL_DEPTH_TEST)

# ══════════════════════════════════════════════════════════════════
#  INTRO SCREEN
# ══════════════════════════════════════════════════════════════════
TITLE1 = "3D  DFA  SIMULATOR"
TITLE2 = "Build . Test . Master Finite Automata"

def draw_intro_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.02,0.02,0.06))
    draw_intro_nodes()
    sy=int((time_val*60)%WIN_H)
    draw_rect_2d(0,sy,WIN_W,2,(0.06,0.18,0.28))
    fade=min(1.0,intro_timer/1.5)
    pulse=(sin(time_val*1.8)+1)*0.5
    r=0.4+0.4*pulse; g=0.7+0.2*pulse
    draw_text_centered_full(500,TITLE1,font=GLUT_BITMAP_TIMES_ROMAN_24,color=(r*fade,g*fade,fade))
    fade2=max(0,min(1.0,(intro_timer-1.0)/1.0))
    draw_text_centered_full(458,TITLE2,color=(0.55*fade2,0.78*fade2,0.88*fade2))
    if intro_timer > INTRO_DUR-0.6:
        blink=(sin(time_val*3)+1)*0.5
        draw_text_centered_full(395,"Press any key to continue ...",
                                color=(0.55*blink,0.88*blink,1.0*blink))

# ══════════════════════════════════════════════════════════════════
#  GAME OVER / VICTORY  SCREENS
# ══════════════════════════════════════════════════════════════════
def draw_gameover_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.10,0.01,0.01))
    draw_intro_nodes()
    pulse=(sin(time_val*2)+1)*0.5
    draw_text_centered_full(520,"GAME  OVER",
                            font=GLUT_BITMAP_TIMES_ROMAN_24,
                            color=(1.0,0.2+0.2*pulse,0.2))
    draw_text_centered_full(468,"You ran out of attempts.",
                            color=(1.0,0.75,0.75))
    draw_text_centered_full(420,f"Final Score: {total_score}",
                            color=(1.0,0.85,0.3))
    draw_text_centered_full(340,"Press  R  to restart",
                            color=(1.0,1.0,0.5))
    draw_text_centered_full(300,"Press  TAB  for Free Mode",
                            color=(0.6,0.8,1.0))

def draw_victory_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.01,0.09,0.01))
    draw_intro_nodes()
    pulse=(sin(time_val*2.5)+1)*0.5
    draw_text_centered_full(540,"CONGRATULATIONS!",
                            font=GLUT_BITMAP_TIMES_ROMAN_24,
                            color=(0.2+0.6*pulse,1.0,0.2+0.3*pulse))
    draw_text_centered_full(488,"All questions solved!",
                            color=(0.7,1.0,0.7))
    draw_text_centered_full(440,f"Total Score: {total_score}",
                            color=(1.0,0.95,0.3))
    draw_text_centered_full(360,"Press  R  to play again",
                            color=(1.0,1.0,0.5))

# ══════════════════════════════════════════════════════════════════
#  MENU SCREEN
# ══════════════════════════════════════════════════════════════════
def _menu_item_rect(i):
    item_h=52; gap=14
    total=(len(MENU_OPTIONS)*item_h+(len(MENU_OPTIONS)-1)*gap)
    base_y=WIN_H//2-total//2-20
    w=320; x=WIN_W//2-w//2
    y=base_y+(len(MENU_OPTIONS)-1-i)*(item_h+gap)
    return x,y,w,item_h

def draw_menu_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.02,0.02,0.06))
    draw_intro_nodes()
    sy=int((time_val*60)%WIN_H)
    draw_rect_2d(0,sy,WIN_W,2,(0.04,0.12,0.22))
    pulse=(sin(time_val*1.8)+1)*0.5
    draw_text_centered_full(724,TITLE1,font=GLUT_BITMAP_TIMES_ROMAN_24,
                            color=(0.4+0.3*pulse,0.7+0.2*pulse,1.0))
    draw_text_centered_full(686,TITLE2,color=(0.5,0.75,0.85))
    draw_rect_2d(WIN_W//2-170,664,340,2,(0.2,0.45,0.75))
    for i,label in enumerate(MENU_OPTIONS):
        x,y,w,h=_menu_item_rect(i)
        hov=(i==menu_hover)
        if hov:
            hp=(sin(time_val*4)+1)*0.5
            bg=(0.08+0.08*hp,0.18+0.08*hp,0.32+0.08*hp)
        else: bg=(0.05,0.08,0.14)
        draw_rect_2d(x,y,w,h,bg)
        if hov:
            bp=(sin(time_val*5)+1)*0.5
            bc=(0.3+0.4*bp,0.6+0.2*bp,1.0); lw=2
        else: bc=(0.18,0.32,0.52); lw=1
        draw_rect_outline_2d(x,y,w,h,bc,lw)
        if hov:            tc=(1.0,0.95,0.45)
        elif label=="QUIT":tc=(1.0,0.4,0.35)
        else:              tc=(0.8,0.9,1.0)
        tw=text_width_full(label,GLUT_BITMAP_HELVETICA_18)
        draw_text_scene(x+w//2-tw//2,y+h//2-8,label,color=tc)
    draw_text_centered_full(28,"Mouse click or UP/DOWN + ENTER to select",
                            font=GLUT_BITMAP_HELVETICA_12,color=(0.38,0.5,0.55))

def draw_how_to_overlay():
    draw_rect_2d(80,60,WIN_W-160,WIN_H-120,(0.04,0.06,0.12))
    draw_rect_outline_2d(80,60,WIN_W-160,WIN_H-120,(0.3,0.6,1.0),2)
    draw_text_centered_full(WIN_H-100,"HOW  TO  PLAY",
                            font=GLUT_BITMAP_TIMES_ROMAN_24,color=(0.4,0.9,1.0))
    lines=[
        "C               Create a new state (grid-snapped position)",
        "K               Cycle selected state",
        "W/A/S/D         Move selected state in X-Y plane",
        "Q / E           Move selected state up / down (Z axis)",
        "F               Set selected state as START  (blue)",
        "G               Toggle selected state as ACCEPT  (gold)",
        "T               Enter transition mode from selected state",
        "  then 0 or 1   Choose transition character",
        "OR Right-click src, then Right-click dst, then type char",
        "SPACE           Validate DFA against test strings",
        "M               Next question  (only if perfect score!)",
        "N               Next question  (challenge mode, no lock)",
        "R               Full reset / restart from Game Over",
        "X               Undo last edge",
        "TAB             Toggle Challenge / Free mode",
        "Arrow keys      Rotate camera   +/-=zoom",
        "Left-drag       Move selected state sphere",
        "Right-drag      Orbit camera",
        "Scroll wheel    Zoom in / out",
        "H               Toggle this help screen",
        "",
        "Colours:  Green=normal   Blue=start   Gold=accept",
        "          Cyan=start+accept   Red=selected   Magenta=sim step",
    ]
    y=WIN_H-140
    for ln in lines:
        if ln=="": y-=8; continue
        col=(0.85,0.9,0.95) if not ln.startswith(" ") else (0.6,0.7,0.75)
        draw_text_scene(100,y,ln,font=GLUT_BITMAP_HELVETICA_12,color=col)
        y-=21
    draw_text_centered_full(80,"Press H or ESC to close",
                            font=GLUT_BITMAP_HELVETICA_12,color=(0.4,0.6,0.7))

# ══════════════════════════════════════════════════════════════════
#  3-D SCENE: STATES
# ══════════════════════════════════════════════════════════════════
def draw_states():
    for s in states:
        if s not in pulse_states:
            pulse_states[s]=random.uniform(0,2*pi)
        pulse=(sin(time_val*2.0+pulse_states[s])+1)*0.5
        x,y,z=states[s]["pos"]
        is_sim=(sim_index>=0 and sim_index<len(sim_states) and sim_states[sim_index]==s)

        # Determine colour
        if s==selected_state:
            gr,gg,gb=1.0,0.3,0.1                          # red
        elif states[s]["is_start"] and states[s]["is_accept"]:
            gr,gg,gb=0.2,0.8,0.8                          # cyan
        elif states[s]["is_start"]:
            gr,gg,gb=0.2,0.5,1.0                          # blue
        elif states[s]["is_accept"]:
            gr,gg,gb=1.0,0.9,0.0                          # gold
        else:
            gr,gg,gb=0.1,0.9,0.5                          # green

        # ── Glow rings  (FIX: second ring in its own PushMatrix) ──
        glPushMatrix(); glTranslatef(x,y,z)
        glow_r=34+4*pulse; glLineWidth(2)
        glColor3f(gr*0.5*pulse,gg*0.5*pulse,gb*0.5*pulse)
        glBegin(GL_LINES)
        for i in range(32):
            a0=2*pi*i/32; a1=2*pi*(i+1)/32
            glVertex3f(glow_r*cos(a0),glow_r*sin(a0),0)
            glVertex3f(glow_r*cos(a1),glow_r*sin(a1),0)
        glEnd()
        glPopMatrix()

        # Tilted second ring in its own matrix (no contamination)
        glPushMatrix(); glTranslatef(x,y,z); glRotatef(60,1,0,0)
        glColor3f(gr*0.3*pulse,gg*0.3*pulse,gb*0.3*pulse)
        glBegin(GL_LINES)
        for i in range(32):
            a0=2*pi*i/32; a1=2*pi*(i+1)/32
            glVertex3f(glow_r*cos(a0),glow_r*sin(a0),0)
            glVertex3f(glow_r*cos(a1),glow_r*sin(a1),0)
        glEnd()
        glPopMatrix()

        # ── Core sphere ───────────────────────────────────────────
        glPushMatrix(); glTranslatef(x,y,z)
        sc=1.0+0.08*pulse; glScalef(sc,sc,sc)
        glColor3f(gr,gg,gb)
        q=gluNewQuadric(); gluSphere(q,28,20,20)
        if states[s]["is_accept"]:
            glColor3f(1.0,1.0,0.3); gluSphere(q,34+3*pulse,14,14)
        glPopMatrix()

        # ── Simulation step highlight ─────────────────────────────
        if is_sim:
            glPushMatrix(); glTranslatef(x,y,z+56)
            glColor3f(1,0,1)
            gluSphere(gluNewQuadric(),12,12,12)
            glPopMatrix()

        # Label  (rendered in 3-D world space)
        draw_text_3d(x+32, y+32, z, f"q{s}", 1, 1, 1)

# ══════════════════════════════════════════════════════════════════
#  3-D SCENE: EDGES  (with arrowheads + self-loops + flow dots)
# ══════════════════════════════════════════════════════════════════
def draw_edges():
    glLineWidth(3)
    # Group by (src,dst) so we can combine labels and handle bidirectional offset
    grouped = {}
    for src,dst,ch in edge_list:
        grouped.setdefault((src,dst),[])
        if ch not in grouped[(src,dst)]:
            grouped[(src,dst)].append(ch)
    keys_list = list(grouped.keys())
    for (src,dst),chars in grouped.items():
        if src not in states or dst not in states: continue
        x1,y1,z1=states[src]["pos"]; x2,y2,z2=states[dst]["pos"]
        combined=("/".join(sorted(chars)))

        if src==dst:
            draw_self_loop(x1,y1,z1,combined,src)
            continue

        # Bidirectional offset
        has_rev=any(e[0]==dst and e[1]==src for e in edge_list)
        if has_rev:
            ddx=x2-x1; ddy=y2-y1
            seg_l=math.sqrt(ddx*ddx+ddy*ddy)
            if seg_l>1e-6:
                px=ddy/seg_l; py=-ddx/seg_l
            else: px=py=0
            off=14
            lx1=x1+px*off; ly1=y1+py*off; lz1=z1
            lx2=x2+px*off; ly2=y2+py*off; lz2=z2
        else:
            lx1,ly1,lz1=x1,y1,z1
            lx2,ly2,lz2=x2,y2,z2

        # Base line
        glColor3f(0.6,0.75,1.0)
        glBegin(GL_LINES); glVertex3f(lx1,ly1,lz1); glVertex3f(lx2,ly2,lz2); glEnd()

        # Arrowhead
        glColor3f(0.35,1.0,0.55)
        draw_arrowhead(lx1,ly1,lz1,lx2,ly2,lz2)

        # Flow dots
        num_dots=5; idx_ = keys_list.index((src,dst))
        offset=(time_val*(0.55+0.08*(idx_%4)))%1.0
        glPointSize(7)
        glBegin(GL_POINTS)
        for d in range(num_dots):
            t=((d/num_dots)+offset)%1.0
            fx=lx1+(lx2-lx1)*t; fy=ly1+(ly2-ly1)*t; fz=lz1+(lz2-lz1)*t
            bri=sin(t*pi)
            glColor3f(0.3*bri,0.8*bri,1.0*bri)
            glVertex3f(fx,fy,fz)
        glEnd()

        # Mid-edge label in 3-D
        mx=(lx1+lx2)/2; my=(ly1+ly2)/2; mz=(lz1+lz2)/2+14
        draw_text_3d(mx,my,mz,combined,1.0,0.9,0.3)

    # Flash edges (after validation)
    for fe in flash_edges[:]:
        src,dst,prog,col=fe[0],fe[1],fe[2],fe[3]
        if src not in states or dst not in states: continue
        x1,y1,z1=states[src]["pos"]; x2,y2,z2=states[dst]["pos"]
        alp=max(0,1-prog); glLineWidth(6)
        glColor3f(col[0]*alp,col[1]*alp,col[2]*alp)
        glBegin(GL_LINES); glVertex3f(x1,y1,z1); glVertex3f(x2,y2,z2); glEnd()
        glLineWidth(3)

# ══════════════════════════════════════════════════════════════════
#  LEFT HUD PANEL
#  Coordinate space: 0..LEFT_W  x  0..WIN_H
# ══════════════════════════════════════════════════════════════════
def draw_hud():
    # ── Header ───────────────────────────────────────────────────
    if mode=="CHALLENGE":
        q=questions[current_question]
        pulse=(sin(time_val*1.5)+1)*0.5
        draw_text(10,840,f"[CHALLENGE]  Q{current_question+1}/{len(questions)}  |  Total: {total_score}",
                  color=(0.3+0.4*pulse,0.9,1.0))
        draw_text(10,815,f"Rule: {q['rule']}",color=(1.0,0.85,0.2))
        att_col=(1.0,0.35,0.35) if attempts_left<=2 else (1.0,0.7,0.3)
        draw_text(10,790,f"Attempts left: {attempts_left}",color=att_col)
    else:
        draw_text(10,840,"[FREE MODE]  Build any DFA",color=(0.6,1.0,0.6))
        draw_text(10,815,"TAB = back to Challenge",color=(0.5,0.7,0.6),
                  font=GLUT_BITMAP_HELVETICA_12)

    # ── Controls ─────────────────────────────────────────────────
    cc=(0.55,0.72,0.62)
    f=GLUT_BITMAP_HELVETICA_12
    draw_text(10,762,"C=new  K=cycle  F=start  G=accept  T+0/1=transition",color=cc,font=f)
    draw_text(10,746,"WASD/Q/E=move  +/-=zoom  Arrows=orbit  R=reset",color=cc,font=f)
    draw_text(10,730,"SPACE=validate  M=next(perfect)  N=next  TAB=mode  H=help",color=cc,font=f)
    draw_text(10,714,"RClick=set transition dst  drag=move state  scroll=zoom",color=cc,font=f)

    # Divider
    draw_text(10,700,"-"*52,color=(0.25,0.25,0.45),font=GLUT_BITMAP_HELVETICA_12)

    # ── State info ───────────────────────────────────────────────
    sc=(1.0,0.45,0.2) if selected_state is not None else (0.4,0.4,0.4)
    draw_text(10,682,f"Selected : q{selected_state}",color=sc)
    draw_text(10,660,f"Start    : q{find_start()}",color=(0.35,0.65,1.0))
    draw_text(10,638,f"Accept   : {sorted(find_accept())}",color=(1.0,0.85,0.2))

    if transition_mode:
        blink=(sin(time_val*6)+1)*0.5
        dst_label = f"q{transition_dst}" if transition_dst is not None else f"q{selected_state}"
        draw_text(10,612,f">> TRANSITION  q{transition_src} --> {dst_label}  (type char)",
                  color=(1.0,blink,0.0))
    else:
        draw_text(10,612,"",color=(0,0,0))   # blank placeholder

    # Divider
    draw_text(10,594,"-"*52,color=(0.25,0.25,0.45),font=GLUT_BITMAP_HELVETICA_12)

    # ── Transition table ─────────────────────────────────────────
    draw_text(10,576,"Transitions:",color=(0.55,0.82,1.0))
    ty=556
    for e in edge_list:
        draw_text(14,ty,f"q{e[0]} --{e[2]}--> q{e[1]}",
                  color=(0.75,0.88,1.0),font=GLUT_BITMAP_HELVETICA_12)
        ty-=17
        if ty<310: break

    # Divider
    draw_text(10,300,"-"*52,color=(0.25,0.25,0.45),font=GLUT_BITMAP_HELVETICA_12)

    # ── Validation results ────────────────────────────────────────
    draw_text(10,282,"Validation Results:",color=(0.55,0.82,1.0))
    yr=260
    for line in result_lines:
        if "OK"    in line: col=(0.2,1.0,0.4)
        elif "WRONG" in line: col=(1.0,0.3,0.3)
        elif "Score" in line or "PERFECT" in line:
            tot=len(questions[current_question]["test_strings"])
            col=((0.2,1.0,0.4) if score==tot else
                 (1.0,0.85,0.2) if score>tot//2 else (1.0,0.3,0.3))
        elif "!!" in line: col=(1.0,0.5,0.0)
        else: col=(0.8,0.8,0.8)
        draw_text(10,yr,line,color=col,font=GLUT_BITMAP_HELVETICA_12); yr-=18
        if yr<30: break

    # ── LEVEL CLEAR banner ────────────────────────────────────────
    if mode=="CHALLENGE" and score==len(questions[current_question]["test_strings"]) and result_lines:
        blink=(sin(time_val*5)+1)*0.5
        draw_text(10,16,"LEVEL CLEARED! Press M for next",
                  color=(0.2,1.0,0.35*blink+0.2))
    else:
        draw_text(10,16,"Blue=Start  Gold=Accept  Cyan=Both  Red=Sel  Magenta=Sim",
                  color=(0.4,0.4,0.6),font=GLUT_BITMAP_HELVETICA_12)

# ══════════════════════════════════════════════════════════════════
#  CAMERA
# ══════════════════════════════════════════════════════════════════
def setupCamera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(75, RIGHT_W/WIN_H, 0.1, 2000)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    ex=camera_z*cos(radians(camera_y))*cos(radians(camera_x))
    ey=camera_z*cos(radians(camera_y))*sin(radians(camera_x))
    ez=camera_z*sin(radians(camera_y))
    gluLookAt(ex,ey,ez,0,0,0,0,0,1)
    
# ══════════════════════════════════════════════════════════════════
#   DFA correctness checker
# ══════════════════════════════════════════════════════════════════
def build_reference_dfa(rule):
    # returns: states, transitions, start, accept_set

    if rule == "Strings ending with 01":
        states = {0,1,2}
        start = 0
        accept = {2}

        trans = {
            (0,'0'):1, (0,'1'):0,
            (1,'0'):1, (1,'1'):2,
            (2,'0'):1, (2,'1'):0
        }
        return states, trans, start, accept
def get_user_dfa():
    start = find_start()
    accept = find_accept()

    return set(states.keys()), transitions.copy(), start, accept
    # You can add more rules here later

from collections import deque

def are_dfa_equivalent():
    q = questions[current_question]

    ref_states, ref_trans, ref_start, ref_accept = build_reference_dfa(q["rule"])
    usr_states, usr_trans, usr_start, usr_accept = get_user_dfa()

    if usr_start is None:
        return False, "No start state"

    alphabet = q["alphabet"]

    # Product automaton BFS
    visited = set()
    queue = deque()

    queue.append((usr_start, ref_start))
    visited.add((usr_start, ref_start))

    while queue:
        u, r = queue.popleft()

        # ❗ CORE CHECK: mismatch in acceptance
        if (u in usr_accept) != (r in ref_accept):
            return False, f"Mismatch found at state pair ({u},{r})"

        for ch in alphabet:
            if (u, ch) not in usr_trans or (r, ch) not in ref_trans:
                return False, "Incomplete DFA during equivalence check"

            u2 = usr_trans[(u, ch)]
            r2 = ref_trans[(r, ch)]

            if (u2, r2) not in visited:
                visited.add((u2, r2))
                queue.append((u2, r2))

    return True, "DFA is CORRECT"
# ══════════════════════════════════════════════════════════════════
#  SIMULATION TICKER  (frame-based, from doc2)
# ══════════════════════════════════════════════════════════════════
def tick_simulation():
    global sim_index, sim_timer
    if sim_index<0 or sim_index>=len(sim_states): return
    sim_timer+=1
    if sim_timer>=SIM_DELAY:
        sim_timer=0; sim_index+=1
        if sim_index>=len(sim_states):
            sim_index=len(sim_states)-1

# ══════════════════════════════════════════════════════════════════
#  MOUSE
# ══════════════════════════════════════════════════════════════════
def mouseListener(button, state_btn, x, y):
    global selected_state, SCREEN, show_how_to
    global camera_z, menu_hover
    global transition_mode, transition_src, transition_dst
    global dragging_state, cam_drag_active
    global cam_drag_ox, cam_drag_oy, cam_drag_cx, cam_drag_cy

    gl_y = WIN_H - y

    if SCREEN=="INTRO":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if intro_timer>=INTRO_DUR-0.6: SCREEN="MENU"
        return

    if SCREEN=="MENU":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if show_how_to: show_how_to=False; return
            for i in range(len(MENU_OPTIONS)):
                rx,ry,rw,rh=_menu_item_rect(i)
                if rx<=x<=rx+rw and ry<=gl_y<=ry+rh:
                    _handle_menu_select(i); return
        return

    if SCREEN in ("GAMEOVER","VICTORY"):
        return   # keyboard handles restart

    if SCREEN=="PLAYING":
        if show_how_to:
            if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN: show_how_to=False
            return

        # Only interact with 3-D scene area (right panel)
        scene_x = x - LEFT_W
        if scene_x < 0:
            return   # click was in the HUD panel

        if button==GLUT_LEFT_BUTTON:
            if state_btn==GLUT_DOWN:
                hit=_pick_state_scene(scene_x, y)
                if hit is not None:
                    selected_state=hit; dragging_state=hit
                else:
                    selected_state=None; dragging_state=None
            else:
                dragging_state=None

        if button==GLUT_RIGHT_BUTTON:
            if state_btn==GLUT_DOWN:
                hit=_pick_state_scene(scene_x, y)
                if hit is not None:
                    # First right-click = set transition source + prompt
                    # Second right-click = set destination, enter char mode
                    if transition_mode and transition_src is not None:
                        transition_dst = hit   # destination chosen
                    else:
                        transition_src = hit
                        transition_dst = None
                        transition_mode = True
                        selected_state  = hit
                else:
                    # Right-drag on empty space = orbit camera
                    cam_drag_active=True
                    cam_drag_ox=x; cam_drag_oy=y
                    cam_drag_cx=camera_x; cam_drag_cy=camera_y
            else:
                cam_drag_active=False

        if button==3 and state_btn==GLUT_DOWN:
            if camera_z>100: camera_z-=20
        if button==4 and state_btn==GLUT_DOWN:
            if camera_z<1500: camera_z+=20

def _pick_state_scene(sx, sy):
    """Pick state inside the RIGHT (3-D) panel.
    sx/sy are pixel coordinates relative to the right panel origin."""
    try:
        viewport   = glGetIntegerv(GL_VIEWPORT)
        modelview  = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        best_sid=None; best_dist=999
        for sid,st in states.items():
            wx,wy,wz=st["pos"]
            px,py,pz=gluProject(wx,wy,wz,modelview,projection,viewport)
            # viewport is already in right-panel coords (glViewport sets that)
            d=sqrt((sx-px)**2+((WIN_H-sy)-py)**2)
            if d<40 and d<best_dist:
                best_dist=d; best_sid=sid
        return best_sid
    except Exception:
        return None

def _handle_menu_select(i):
    global SCREEN, show_how_to
    label=MENU_OPTIONS[i]
    if label=="START GAME":    SCREEN="PLAYING"
    elif label=="HOW TO PLAY": show_how_to=True
    elif label=="QUIT":        glutLeaveMainLoop()

# ══════════════════════════════════════════════════════════════════
#  KEYBOARD
# ══════════════════════════════════════════════════════════════════
def keyboardListener(key, x, y):
    global SCREEN, state_id, selected_state
    global transition_mode, transition_src, transition_dst
    global current_question, result_text, result_lines
    global camera_z, score, total_score
    global attempts_left, question_submitted
    global sim_states, sim_index, sim_timer, sim_string
    global flash_edges, flow_string, flow_index
    global show_how_to, menu_hover, mode

    # ── INTRO ─────────────────────────────────────────────────────
    if SCREEN=="INTRO":
        if intro_timer>=INTRO_DUR-0.6: SCREEN="MENU"
        return

    # ── MENU ──────────────────────────────────────────────────────
    if SCREEN=="MENU":
        if show_how_to:
            if key in (b'h',b'H',b'\x1b'): show_how_to=False
            return
        if key in (b'\r',b'\n'):
            if 0<=menu_hover<len(MENU_OPTIONS): _handle_menu_select(menu_hover)
        if key==b'\t':
            _handle_menu_select(0)   # TAB on menu = start
        return

    # ── GAME OVER / VICTORY ──────────────────────────────────────
    if SCREEN=="GAMEOVER":
        if key==b'r':
            _full_restart()
        if key==b'\t':
            mode="FREE"; _full_restart()
        return

    if SCREEN=="VICTORY":
        if key==b'r': _full_restart()
        return

    # ── PLAYING ───────────────────────────────────────────────────
    if show_how_to:
        if key in (b'h',b'H',b'\x1b'): show_how_to=False
        return

    if key in (b'h',b'H'): show_how_to=True; return

    # Create state
    if key==b'c':
        a=round(random.uniform(-160,160)/20)*20
        b=round(random.uniform(-160,160)/20)*20
        states[state_id]={"pos":[a,b,60],"is_start":False,"is_accept":False}
        spawn_particles(a,b,60,20,(0.1,0.9,0.5),speed=8)
        selected_state=state_id; state_id+=1

    # Cycle selected
    if key==b'k' and states:
        keys=list(states.keys())
        if selected_state not in keys: selected_state=keys[0]
        else:
            idx=keys.index(selected_state)
            selected_state=keys[(idx+1)%len(keys)]

    # Move / assign selected state
    if selected_state is not None and selected_state in states:
        pos=states[selected_state]["pos"]
        if key==b'w': pos[1]+=15
        if key==b's': pos[1]-=15
        if key==b'a': pos[0]-=15
        if key==b'd': pos[0]+=15
        if key==b'q': pos[2]+=15
        if key==b'e': pos[2]-=15
        if key==b'f':
            for sid in states: states[sid]["is_start"]=False
            states[selected_state]["is_start"]=True
            spawn_particles(*states[selected_state]["pos"],30,(0.2,0.5,1.0),speed=10)
        if key==b'g':
            states[selected_state]["is_accept"]=not states[selected_state]["is_accept"]
            if states[selected_state]["is_accept"]:
                spawn_particles(*states[selected_state]["pos"],40,(1.0,0.9,0.0),speed=12)

    # Start keyboard transition mode
    if key==b't' and selected_state is not None:
        transition_mode=True; transition_src=selected_state; transition_dst=None
        return
    # Undo last edge
    if key==b'x':
        if edge_list:
            last=edge_list.pop()
            transitions.pop((last[0],last[2]),None)
        transition_mode=False; transition_src=None; transition_dst=None

    # Set transition label (keyboard: destination = selected_state if no right-click dst)
    if transition_mode and transition_src is not None:
        try:
            char=key.decode("utf-8","ignore")
        except Exception:
            char=""
        if char.isalnum():
            dst = transition_dst if transition_dst is not None else selected_state
            if dst is not None and dst in states:
                tkey=(transition_src,char)
                transitions[tkey]=dst
                edge_list.append((transition_src,dst,char))
                if transition_src in states:
                    px=(states[transition_src]["pos"][0]+states[dst]["pos"][0])/2
                    py=(states[transition_src]["pos"][1]+states[dst]["pos"][1])/2
                    pz=(states[transition_src]["pos"][2]+states[dst]["pos"][2])/2
                    spawn_particles(px,py,pz,25,(0.3,0.8,1.0),speed=6)
            transition_mode=False; transition_src=None; transition_dst=None
            return   # don't fall through to other key checks

    # Validate (SPACE)
    if key==b' ':
        _validate()

    # Next question – locked behind perfect score (M)
    if key==b'm':
        q=questions[current_question]
        if score==len(q["test_strings"]):
            _next_question(lock=True)
        else:
            result_lines=["Must achieve perfect score first!"]

    # Next question – unlocked (N, same as old 'n'/'m' in doc2)
    if key in (b'n',):
        _next_question(lock=False)

    # Zoom
    if key in (b'+',b'='): 
        if camera_z>100: camera_z-=30
    if key==b'-':
        if camera_z<1500: camera_z+=30

    # Reset current question
    if key==b'r':
        reset_all()
        attempts_left=5; question_submitted=False; result_lines=[]

    # Toggle mode (TAB)
    if key==b'\t':
        mode="FREE" if mode=="CHALLENGE" else "CHALLENGE"
        reset_all()
        current_question=0; total_score=0
        attempts_left=5; question_submitted=False; result_lines=[]


def _validate():
    global score, total_score, question_submitted
    global sim_states, sim_index, sim_timer, sim_string, result_lines

    sim_states=[]; sim_index=-1; result_lines=[]

    alph=questions[current_question]["alphabet"] if mode=="CHALLENGE" else ["0","1"]
    incomplete=check_dfa_completeness(alph)

    if not states:
        result_lines.append("No states defined yet.")
        return
    if find_start() is None:
        result_lines.append("No start state!  Press F to set one.")
        return
    if incomplete:
        result_lines.append("!! DFA INCOMPLETE !!")
        for w in incomplete[:5]: result_lines.append(w)
        if len(incomplete)>5: result_lines.append(f"  (+{len(incomplete)-5} more...)")
        return

    if mode=="CHALLENGE":
        q=questions[current_question]
        q_score=0
        flash_edges.clear()
        for string in q["test_strings"]:
            res,path=simulate_dfa(string)
            if not sim_states:
                sim_states=path; sim_string=string
            correct=q["expected"][string]
            disp=repr(string) if string=="" else string
            if res==correct:
                q_score+=1; result_lines.append(f"'{disp}': OK"); col=(0.2,1.0,0.4)
            else:
                result_lines.append(f"'{disp}': WRONG"); col=(1.0,0.3,0.3)
            spawn_travel_particle(path,col)
            for i in range(len(path)-1):
                flash_edges.append([path[i],path[i+1],0.0,col])
        total=len(q["test_strings"])
        score=q_score
        correct, msg = are_dfa_equivalent()

        if correct:
            result_lines.append("✔ DFA is formally correct")
        else:
            result_lines.append("✘ DFA is incorrect")
            result_lines.append(msg)
        if q_score==total:
            result_lines.append(f"Score: {q_score}/{total} - PERFECT!")
            for sid in states:
                spawn_particles(*states[sid]["pos"],60,(1.0,0.9,0.1),speed=15,lifetime=2.5)
            if not question_submitted:
                total_score+=q_score; question_submitted=True
        else:
            result_lines.append(f"Score: {q_score}/{total}")
            if not question_submitted:
                attempts_left-=1
                if attempts_left<=0:
                    global SCREEN
                    SCREEN="GAMEOVER"
    else:
        result_lines.append("Free Mode - no scoring.")
        if states:
            test_str="01"
            res,path=simulate_dfa(test_str)
            sim_states=path; sim_string=test_str
            result_lines.append(f"Sim '{test_str}': {'ACCEPT' if res else 'REJECT'}")
        score=0

    if sim_states: sim_index=0; sim_timer=0


def _next_question(lock=True):
    global current_question, question_submitted, attempts_left, SCREEN
    global result_lines, score
    if mode!="CHALLENGE": return
    if lock and score!=len(questions[current_question]["test_strings"]):
        result_lines=["Need a perfect score to advance!"]
        return
    if current_question<len(questions)-1:
        current_question+=1
        question_submitted=False; attempts_left=5
        reset_connections(); result_lines=[]; score=0
    else:
        SCREEN="VICTORY"


def _full_restart():
    global SCREEN, current_question, total_score, attempts_left
    global question_submitted, score
    SCREEN="PLAYING"
    current_question=0; total_score=0; attempts_left=5
    question_submitted=False; score=0
    reset_all(); result_lines=[]


def specialKeyListener(key, x, y):
    global camera_x, camera_y, menu_hover
    if SCREEN=="MENU":
        if key==GLUT_KEY_DOWN: menu_hover=(menu_hover+1)%len(MENU_OPTIONS)
        if key==GLUT_KEY_UP:   menu_hover=(menu_hover-1)%len(MENU_OPTIONS)
        return
    if SCREEN not in ("PLAYING",): return
    if key==GLUT_KEY_LEFT:  camera_x-=5
    if key==GLUT_KEY_RIGHT: camera_x+=5
    if key==GLUT_KEY_UP:
        if camera_y<89: camera_y+=5
    if key==GLUT_KEY_DOWN:
        if camera_y>5:  camera_y-=5

# ══════════════════════════════════════════════════════════════════
#  MAIN DISPLAY  (split-panel layout from doc2)
# ══════════════════════════════════════════════════════════════════
def showScreen():
    glClearColor(0.04,0.04,0.10,1)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

    if SCREEN in ("INTRO","MENU","GAMEOVER","VICTORY"):
        glLoadIdentity()
        glViewport(0,0,WIN_W,WIN_H)
        glDisable(GL_SCISSOR_TEST)
        glDisable(GL_DEPTH_TEST)
        if SCREEN=="INTRO":       draw_intro_screen()
        elif SCREEN=="MENU":
            draw_menu_screen()
            if show_how_to: draw_how_to_overlay()
        elif SCREEN=="GAMEOVER":  draw_gameover_screen()
        elif SCREEN=="VICTORY":   draw_victory_screen()
        glEnable(GL_DEPTH_TEST)

    elif SCREEN=="PLAYING":
        # ── LEFT PANEL: dark bg + 2-D HUD ────────────────────────
        glEnable(GL_SCISSOR_TEST)
        glScissor(0,0,LEFT_W,WIN_H)
        glViewport(0,0,LEFT_W,WIN_H)
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluOrtho2D(0,LEFT_W,0,WIN_H)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        glColor3f(0.06,0.07,0.13)
        glBegin(GL_QUADS)
        glVertex2f(0,0); glVertex2f(LEFT_W,0)
        glVertex2f(LEFT_W,WIN_H); glVertex2f(0,WIN_H)
        glEnd()
        # Thin separator
        glColor3f(0.2,0.3,0.5)
        glBegin(GL_LINES)
        glVertex2f(LEFT_W-1,0); glVertex2f(LEFT_W-1,WIN_H)
        glEnd()
        draw_hud()

        # ── RIGHT PANEL: 3-D scene ────────────────────────────────
        glScissor(LEFT_W,0,RIGHT_W,WIN_H)
        glViewport(LEFT_W,0,RIGHT_W,WIN_H)
        glEnable(GL_DEPTH_TEST)
        glLoadIdentity()
        setupCamera()
        draw_stars(); draw_floor(); draw_axes()
        draw_edges(); draw_states()
        draw_particles(); draw_travel_particles()
        if show_how_to: draw_how_to_overlay()

        glDisable(GL_SCISSOR_TEST)

    glutSwapBuffers()

# ══════════════════════════════════════════════════════════════════
#  IDLE
# ══════════════════════════════════════════════════════════════════
_last_time=[0.0]

def idle():
    global time_val, intro_timer, frame_count
    now=glutGet(GLUT_ELAPSED_TIME)/1000.0
    dt=min(now-_last_time[0],0.05)
    _last_time[0]=now
    time_val+=dt; frame_count+=1

    if SCREEN in ("INTRO",):
        intro_timer+=dt
        update_intro_nodes(dt)
    elif SCREEN in ("MENU","GAMEOVER","VICTORY"):
        update_intro_nodes(dt)
    elif SCREEN=="PLAYING":
        update_particles(dt)
        update_travel_particles(dt)
        for fe in flash_edges:
            fe[2]=min(1.0,fe[2]+dt*0.6)
        tick_simulation()

    glutPostRedisplay()

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(WIN_W,WIN_H)
    glutInitWindowPosition(40,40)
    glutCreateWindow(b"3D DFA Builder - CSE 423")
    glEnable(GL_DEPTH_TEST)

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutMainLoop()

if __name__=="__main__":
    main()






