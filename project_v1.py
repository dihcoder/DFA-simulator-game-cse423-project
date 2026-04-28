import random
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import cos, radians, sin, sqrt, pi

# ==============================================
#  GAME SCREEN FSM:  INTRO -> MENU -> PLAYING
# ==============================================
SCREEN      = "INTRO"
intro_timer = 0.0
INTRO_DUR   = 3.5

menu_hover   = 0
MENU_OPTIONS = ["START GAME", "HOW TO PLAY", "QUIT"]
show_how_to  = False

WIN_W, WIN_H = 1000, 800

# ==============================================
#  DFA CORE STATE
# ==============================================
states      = {}
transitions = {}
edge_list   = []

selected_state = None
state_id       = 0

camera_x = 45
camera_y = 35
camera_z = 350

current_question = 0
score        = 0
result_text  = ""

# animation
time_val         = 0.0
particle_list    = []
pulse_states     = {}
flash_edges      = []
travel_particles = []
# transition
transition_mode = False
transition_src  = None
transition_dst  = None
# flow tape
flow_string = ""
flow_index  = 0
flow_timer  = 0.0
# decorative intro nodes
_stars        = None
_intro_nodes  = None

# ==============================================
#  QUESTIONS
# ==============================================
questions = [
    {"rule": "Strings ending with 01",
     "alphabet": ["0","1"],
     "test_strings": ["01","101","1101","10","111"],
     "expected": {"01":True,"101":True,"1101":True,"10":False,"111":False}},
    {"rule": "Strings containing 00",
     "alphabet": ["0","1"],
     "test_strings": ["00","100","001","11","101"],
     "expected": {"00":True,"100":True,"001":True,"11":False,"101":False}},
    {"rule": "Strings of even length",
     "alphabet": ["0","1"],
     "test_strings": ["","01","1001","0","100","11"],
     "expected": {"":True,"01":True,"1001":True,"0":False,"100":False,"11":True}},
    {"rule": "Strings starting with 1",
     "alphabet": ["0","1"],
     "test_strings": ["1","10","110","01","001"],
     "expected": {"1":True,"10":True,"110":True,"01":False,"001":False}},
    {"rule": "Odd number of 1s",
     "alphabet": ["0","1"],
     "test_strings": ["1","11","111","0","010"],
     "expected": {"1":True,"11":False,"111":True,"0":False,"010":False}},
]

# ==============================================
#  RULE / VALIDATION HELPERS
# ==============================================
def check_rule(rule, s):
    if rule == "Strings ending with 01":   return s.endswith("01")
    if rule == "Strings containing 00":    return "00" in s
    if rule == "Strings of even length":   return len(s) % 2 == 0
    if rule == "Strings starting with 1":  return s.startswith("1")
    if rule == "Odd number of 1s":         return s.count("1") % 2 == 1
    return False

def generate_strings(alphabet, max_len=4):
    res = [""]
    for _ in range(max_len):
        new_s = [s+c for s in res for c in alphabet]
        res += new_s
    return list(set(res))

def validate_against_rule(rule, alphabet):
    for s in generate_strings(alphabet, 4):
        ok, _ = simulate_dfa(s)
        if ok != check_rule(rule, s):
            return False
    return True

def is_complete_dfa(alphabet=None):
    if alphabet is None: alphabet = ["0","1"]
    for s in states:
        for ch in alphabet:
            if (s, ch) not in transitions:
                return False
    return True

# ==============================================
#  DFA CORE
# ==============================================
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
        states[s]["is_start"] = False
        states[s]["is_accept"] = False
    transitions.clear(); edge_list.clear(); flash_edges.clear()

# ==============================================
#  PARTICLES
# ==============================================
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
    dead = [p for p in particle_list if p["life"]<=0]
    for p in dead: particle_list.remove(p)
    for p in particle_list:
        p["x"]+=p["vx"]*dt; p["y"]+=p["vy"]*dt; p["z"]+=p["vz"]*dt
        p["vz"]-=9.8*dt; p["life"]-=dt

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

# ==============================================
#  TRAVEL PARTICLES
# ==============================================
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

# ==============================================
#  FLOW TAPE
# ==============================================
def update_flow(dt):
    global flow_timer, flow_index
    flow_timer += dt
    if flow_timer > 0.45:
        flow_timer = 0
        flow_index = min(flow_index+1, len(flow_string))

def draw_input_flow():
    if not flow_string: return
    visible = flow_string[:flow_index]
    draw_text(400, 750, "INPUT: " + visible, color=(1,1,0))

# ==============================================
#  STAR FIELD
# ==============================================
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
    glLineWidth(1)
    for i in range(-200,201,20):
        t=(sin(time_val*0.4+i*0.05)+1)*0.5
        bri=0.08+0.06*t
        glColor3f(bri*0.4,bri*0.8,bri)
        glBegin(GL_LINES); glVertex3f(i,-200,0); glVertex3f(i,200,0); glEnd()
        glBegin(GL_LINES); glVertex3f(-200,i,0); glVertex3f(200,i,0); glEnd()
    glLineWidth(2)
    for i in range(64):
        a0=2*pi*i/64; a1=2*pi*(i+1)/64
        p=(sin(time_val*1.2+a0*2)+1)*0.5
        glColor3f(0.0,0.3+0.2*p,0.5+0.3*p)
        glBegin(GL_LINES)
        glVertex3f(220*cos(a0),220*sin(a0),0)
        glVertex3f(220*cos(a1),220*sin(a1),0)
        glEnd()

def draw_axes():
    glLineWidth(2)
    a=(sin(time_val*0.5)+1)*0.2+0.3
    glBegin(GL_LINES)
    glColor3f(a,0.2*a,0.2*a); glVertex3f(0,0,0); glVertex3f(60,0,0)
    glColor3f(0.2*a,a,0.2*a); glVertex3f(0,0,0); glVertex3f(0,60,0)
    glColor3f(0.2*a,0.5*a,a); glVertex3f(0,0,0); glVertex3f(0,0,60)
    glEnd()

# ==============================================
#  TEXT / 2-D HELPERS
# ==============================================
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    glColor3f(*color)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0,WIN_W,0,WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(x,y)
    for ch in text:
        glutBitmapCharacter(font,ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def text_width(text, font=GLUT_BITMAP_HELVETICA_18):
    return sum(glutBitmapWidth(font,ord(c)) for c in text)

def draw_text_centered(cy, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    w = text_width(text, font)
    draw_text(WIN_W//2 - w//2, cy, text, font, color)

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

# ==============================================
#  INTRO FLOATING NODES
# ==============================================
def get_intro_nodes():
    global _intro_nodes
    if _intro_nodes is None:
        _intro_nodes = []
        for i in range(9):
            _intro_nodes.append({
                "x":random.uniform(80,920),"y":random.uniform(100,700),
                "vx":random.uniform(-20,20),"vy":random.uniform(-15,15),
                "r":random.uniform(16,28),"phase":random.uniform(0,2*pi),
                "col":random.choice([
                    (0.2,0.5,1.0),(0.1,0.9,0.5),(1.0,0.9,0.0),(0.85,0.3,0.85)
                ])
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
                glBegin(GL_LINES)
                glVertex2f(ni["x"],ni["y"]); glVertex2f(nj["x"],nj["y"])
                glEnd()

    for n in nodes:
        pulse=(sin(time_val*2+n["phase"])+1)*0.5
        r=n["r"]+4*pulse
        cr,cg,cb=n["col"]
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

# ==============================================
#  INTRO SCREEN
# ==============================================
TITLE1 = "3D  DFA  SIMULATOR"
TITLE2 = "Build . Test . Master Finite Automata"

def draw_intro_screen():
    draw_rect_2d(0,0,WIN_W,WIN_H,(0.02,0.02,0.06))
    draw_intro_nodes()
    # scanline
    sy=int((time_val*60)%WIN_H)
    draw_rect_2d(0,sy,WIN_W,2,(0.06,0.18,0.28))

    fade=min(1.0,intro_timer/1.5)
    pulse=(sin(time_val*1.8)+1)*0.5
    r=0.4+0.4*pulse; g=0.7+0.2*pulse

    draw_text_centered(500,TITLE1,
                       font=GLUT_BITMAP_TIMES_ROMAN_24,
                       color=(r*fade,g*fade,fade))
    fade2=max(0,min(1.0,(intro_timer-1.0)/1.0))
    draw_text_centered(458,TITLE2,
                       font=GLUT_BITMAP_HELVETICA_18,
                       color=(0.55*fade2,0.78*fade2,0.88*fade2))

    if intro_timer > INTRO_DUR-0.6:
        blink=(sin(time_val*3)+1)*0.5
        draw_text_centered(395,"Press any key to continue ...",
                           font=GLUT_BITMAP_HELVETICA_18,
                           color=(0.55*blink,0.88*blink,1.0*blink))

# ==============================================
#  MENU SCREEN
# ==============================================
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
    draw_text_centered(706,TITLE1,font=GLUT_BITMAP_TIMES_ROMAN_24,
                       color=(0.4+0.3*pulse,0.7+0.2*pulse,1.0))
    draw_text_centered(668,TITLE2,font=GLUT_BITMAP_HELVETICA_18,
                       color=(0.5,0.75,0.85))
    draw_rect_2d(WIN_W//2-170,646,340,2,(0.2,0.45,0.75))

    for i,label in enumerate(MENU_OPTIONS):
        x,y,w,h=_menu_item_rect(i)
        hov=(i==menu_hover)
        if hov:
            hp=(sin(time_val*4)+1)*0.5
            bg=(0.08+0.08*hp,0.18+0.08*hp,0.32+0.08*hp)
        else:
            bg=(0.05,0.08,0.14)
        draw_rect_2d(x,y,w,h,bg)
        if hov:
            bp=(sin(time_val*5)+1)*0.5
            bc=(0.3+0.4*bp,0.6+0.2*bp,1.0); lw=2
        else:
            bc=(0.18,0.32,0.52); lw=1
        draw_rect_outline_2d(x,y,w,h,bc,lw)

        if hov:            tc=(1.0,0.95,0.45)
        elif label=="QUIT":tc=(1.0,0.4,0.35)
        else:              tc=(0.8,0.9,1.0)
        tw=text_width(label,GLUT_BITMAP_HELVETICA_18)
        draw_text(x+w//2-tw//2,y+h//2-8,label,
                  font=GLUT_BITMAP_HELVETICA_18,color=tc)

    draw_text_centered(28,"Mouse click or UP/DOWN + ENTER to select",
                       font=GLUT_BITMAP_HELVETICA_12,color=(0.38,0.5,0.55))

def draw_how_to_overlay():
    draw_rect_2d(110,90,780,615,(0.04,0.06,0.12))
    draw_rect_outline_2d(110,90,780,615,(0.3,0.6,1.0),2)
    draw_text_centered(672,"HOW  TO  PLAY",
                       font=GLUT_BITMAP_TIMES_ROMAN_24,color=(0.4,0.9,1.0))
    lines=[
        "C               Create a new state at a random 3D position",
        "K               Cycle selected state (cycle through all states)",
        "W/A/S/D         Move selected state in X-Y plane",
        "Q / E           Move selected state up / down (Z axis)",
        "F               Set selected state as START  (turns blue)",
        "G               Toggle selected state as ACCEPT  (turns gold)",
        "T               Enter transition mode from selected state",
        "  then 0 or 1   Choose transition character",
        "  then K + 0/1  Pick destination state and confirm",
        "SPACE           Validate DFA against all test strings",
        "M               Next question  (resets edges/start/accept)",
        "R               Full reset",
        "X               Undo last edge",
        "Arrow keys      Rotate camera",
        "+  /  -         Zoom in / out",
        "Left-click      Select / drag a state sphere",
        "H               Toggle this help screen",
        "",
        "Colours:  Green=normal   Blue=start   Gold=accept   Red=selected",
    ]
    y=630
    for ln in lines:
        if ln=="": y-=8; continue
        col=(0.85,0.9,0.95) if not ln.startswith(" ") else (0.6,0.7,0.75)
        draw_text(130,y,ln,font=GLUT_BITMAP_HELVETICA_12,color=col)
        y-=22
    draw_text_centered(104,"Press H or ESC to close",
                       font=GLUT_BITMAP_HELVETICA_12,color=(0.4,0.6,0.7))

# ==============================================
#  GAME HUD + 3-D SCENE
# ==============================================
def draw_states():
    for s in states:
        if s not in pulse_states:
            pulse_states[s]=random.uniform(0,2*pi)
        pulse=(sin(time_val*2.0+pulse_states[s])+1)*0.5
        x,y,z=states[s]["pos"]

        if s==selected_state:        gr,gg,gb=1.0,0.3,0.1
        elif states[s]["is_start"]:  gr,gg,gb=0.2,0.5,1.0
        elif states[s]["is_accept"]: gr,gg,gb=1.0,0.9,0.0
        else:                        gr,gg,gb=0.1,0.9,0.5

        glPushMatrix(); glTranslatef(x,y,z)
        glow_r=34+4*pulse; glLineWidth(2)
        glColor3f(gr*0.5*pulse,gg*0.5*pulse,gb*0.5*pulse)
        glBegin(GL_LINES)
        for i in range(32):
            a0=2*pi*i/32; a1=2*pi*(i+1)/32
            glVertex3f(glow_r*cos(a0),glow_r*sin(a0),0)
            glVertex3f(glow_r*cos(a1),glow_r*sin(a1),0)
        glEnd()
        glRotatef(60,1,0,0)
        glColor3f(gr*0.3*pulse,gg*0.3*pulse,gb*0.3*pulse)
        glBegin(GL_LINES)
        for i in range(32):
            a0=2*pi*i/32; a1=2*pi*(i+1)/32
            glVertex3f(glow_r*cos(a0),glow_r*sin(a0),0)
            glVertex3f(glow_r*cos(a1),glow_r*sin(a1),0)
        glEnd()
        glPopMatrix()

        glPushMatrix(); glTranslatef(x,y,z)
        sc=1.0+0.08*pulse; glScalef(sc,sc,sc)
        glColor3f(gr,gg,gb)
        q=gluNewQuadric(); gluSphere(q,28,20,20)
        if states[s]["is_accept"]:
            glColor3f(1.0,1.0,0.3); gluSphere(q,33+3*pulse,14,14)
        glPopMatrix()
        draw_text(x+10,y+35+z,f"q{s}",
                  font=GLUT_BITMAP_HELVETICA_12,color=(gr,gg,gb))

def draw_edges():
    h=760; glLineWidth(3)
    for idx,e in enumerate(edge_list):
        src,dst,ch=e[0],e[1],e[2]
        if src not in states or dst not in states: continue
        x1,y1,z1=states[src]["pos"]; x2,y2,z2=states[dst]["pos"]
        glColor3f(0.3,0.6,0.9)
        glBegin(GL_LINES); glVertex3f(x1,y1,z1); glVertex3f(x2,y2,z2); glEnd()
        num_dots=6; offset=(time_val*(0.6+0.1*(idx%3)))%1.0
        glPointSize(7)
        glBegin(GL_POINTS)
        for d in range(num_dots):
            t=((d/num_dots)+offset)%1.0
            fx=x1+(x2-x1)*t; fy=y1+(y2-y1)*t; fz=z1+(z2-z1)*t
            bri=sin(t*pi)
            glColor3f(0.3*bri,0.8*bri,1.0*bri)
            glVertex3f(fx,fy,fz)
        glEnd()
        draw_text(860,h,f"q{src}--{ch}->q{dst}",color=(0.4,0.85,1.0)); h-=22

    for fe in flash_edges[:]:
        src,dst,prog,col=fe[0],fe[1],fe[2],fe[3]
        if src not in states or dst not in states: continue
        x1,y1,z1=states[src]["pos"]; x2,y2,z2=states[dst]["pos"]
        alp=max(0,1-prog); glLineWidth(6)
        glColor3f(col[0]*alp,col[1]*alp,col[2]*alp)
        glBegin(GL_LINES); glVertex3f(x1,y1,z1); glVertex3f(x2,y2,z2); glEnd()
        glLineWidth(3)

def draw_hud():
    q=questions[current_question]
    pulse=(sin(time_val*1.5)+1)*0.5
    draw_text(10,775,f"DFA BUILDER  Q{current_question+1}/{len(questions)}",
              color=(0.3+0.4*pulse,0.9,1.0))
    draw_text(10,752,f"RULE: {q['rule']}",color=(1.0,0.85,0.2))

    cc=(0.5,0.7,0.6)
    draw_text(10,620,"C=create  K=cycle  WASD/Q/E=move  F=start  G=accept",color=cc)
    draw_text(10,600,"T -> 0/1 -> K -> 0/1 = add transition   SPACE=validate",color=cc)
    draw_text(10,580,"M=next question   R=full reset   X=undo edge   H=help",color=cc)
    draw_text(10,560,"Arrow keys=orbit  +/-=zoom",color=cc)

    sc=(1.0,0.4,0.2) if selected_state is not None else (0.4,0.4,0.4)
    draw_text(700,752,f"SELECTED: q{selected_state}",color=sc)
    draw_text(700,730,f"START:    q{find_start()}",color=(0.3,0.6,1.0))
    draw_text(700,708,f"ACCEPTS:  {find_accept()}",color=(1.0,0.9,0.2))

    h=650
    draw_text(700, h+22, "--- RESULTS ---", color=(0.6,0.6,0.8))
    for line in result_text.split("\n"):
        if "OK"    in line: col=(0.2,1.0,0.4)
        elif "WRONG" in line: col=(1.0,0.3,0.3)
        elif "Score" in line:
            tot=len(q["test_strings"])
            col=((0.2,1.0,0.4) if score==tot else
                 (1.0,0.85,0.2) if score>tot//2 else (1.0,0.3,0.3))
        else: col=(0.8,0.8,0.8)
        
        # Draw the results at X=700 instead of X=10
        draw_text(700, h, line, color=col)
        h-=22
    if transition_mode:
        blink=(sin(time_val*6)+1)*0.5
        draw_text_centered(30,
                  f"TRANSITION: q{transition_src} -> q{transition_dst} (TYPE A CHARACTER)",
                  font=GLUT_BITMAP_HELVETICA_18,
                  color=(1.0,blink,0.0))

# ==============================================
#  CAMERA
# ==============================================
def setupCamera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(70,WIN_W/WIN_H,0.1,2000)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    ex=camera_z*cos(radians(camera_y))*cos(radians(camera_x))
    ey=camera_z*cos(radians(camera_y))*sin(radians(camera_x))
    ez=camera_z*sin(radians(camera_y))
    gluLookAt(ex,ey,ez,0,0,80,0,0,1)

# ==============================================
#  MOUSE
# ==============================================
def mouseListener(button, state_btn, x, y):
    global selected_state, SCREEN, show_how_to
    global camera_z, menu_hover
    global transition_mode, transition_src, transition_dst

    gl_y = WIN_H - y

    if SCREEN=="INTRO":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if intro_timer >= INTRO_DUR-0.6:
                SCREEN="MENU"
        return

    if SCREEN=="MENU":
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            if show_how_to:
                show_how_to=False; return
            for i in range(len(MENU_OPTIONS)):
                rx,ry,rw,rh=_menu_item_rect(i)
                if rx<=x<=rx+rw and ry<=gl_y<=ry+rh:
                    _handle_menu_select(i); return
        return

    if SCREEN=="PLAYING":
        if show_how_to:
            if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
                show_how_to=False
            return

        # 1. LEFT CLICK: Select the source state (s1)
        if button==GLUT_LEFT_BUTTON and state_btn==GLUT_DOWN:
            hit=_pick_state_2d(x,y)
            if hit is not None:
                selected_state=hit
            else:
                selected_state=None

        # 2. RIGHT CLICK: Select destination (s2) and trigger transition
        if button==GLUT_RIGHT_BUTTON and state_btn==GLUT_DOWN:
            hit=_pick_state_2d(x,y)
            if hit is not None and selected_state is not None:
                transition_src = selected_state
                transition_dst = hit
                transition_mode = True  # Activates the prompt

        # Scroll wheel zooming
        if button==3 and state_btn==GLUT_DOWN:
            if camera_z>120: camera_z-=20
        if button==4 and state_btn==GLUT_DOWN:
            if camera_z<1200: camera_z+=20

def _pick_state_2d(mx,my):
    try:
        viewport  =glGetIntegerv(GL_VIEWPORT)
        modelview =glGetDoublev(GL_MODELVIEW_MATRIX)
        projection=glGetDoublev(GL_PROJECTION_MATRIX)
        best_sid=None; best_dist=999
        for sid,st in states.items():
            sx,sy,sz=gluProject(st["pos"][0],st["pos"][1],st["pos"][2],
                                modelview,projection,viewport)
            d=sqrt((mx-sx)**2+(my-(WIN_H-sy))**2)
            if d<38 and d<best_dist:
                best_dist=d; best_sid=sid
        return best_sid
    except Exception:
        return None


def _handle_menu_select(i):
    global SCREEN,show_how_to
    label=MENU_OPTIONS[i]
    if label=="START GAME":   SCREEN="PLAYING"
    elif label=="HOW TO PLAY":show_how_to=True
    elif label=="QUIT":       glutLeaveMainLoop()

# ==============================================
#  KEYBOARD
# ==============================================
def keyboardListener(key,x,y):
    global SCREEN,state_id,selected_state,transition_mode,transition_src
    global current_question,result_text,camera_z,score
    global flash_edges,flow_string,flow_index,show_how_to,menu_hover

    if SCREEN=="INTRO":
        if intro_timer>=INTRO_DUR-0.6: SCREEN="MENU"
        return

    if SCREEN=="MENU":
        if show_how_to:
            if key in (b'h',b'H',b'\x1b'): show_how_to=False
            return
        if key in (b'\r',b'\n'):
            if 0<=menu_hover<len(MENU_OPTIONS): _handle_menu_select(menu_hover)
        return

    # PLAYING
    if show_how_to:
        if key in (b'h',b'H',b'\x1b'): show_how_to=False
        return

    if key in (b'h',b'H'): show_how_to=True; return

    if key==b'c':
        a=random.uniform(-150,150); b=random.uniform(-150,150); c=random.uniform(50,220)
        states[state_id]={"pos":[a,b,c],"is_start":False,"is_accept":False}
        spawn_particles(a,b,c,20,(0.1,0.9,0.5),speed=8)
        selected_state=state_id; state_id+=1

    if key==b'k' and len(states)>0:
        keys=list(states.keys())
        if selected_state not in keys: selected_state=keys[0]
        else:
            idx=keys.index(selected_state)
            selected_state=keys[(idx+1)%len(keys)]

    if selected_state is not None and selected_state in states:
        pos=states[selected_state]["pos"]
        if key==b'w': pos[1]+=10
        if key==b's': pos[1]-=10
        if key==b'a': pos[0]-=10
        if key==b'd': pos[0]+=10
        if key==b'q': pos[2]+=10
        if key==b'e': pos[2]-=10
        if key==b'f':
            for s in states: states[s]["is_start"]=False
            states[selected_state]["is_start"]=True
            spawn_particles(*states[selected_state]["pos"],30,(0.2,0.5,1.0),speed=10)
        if key==b'g':
            states[selected_state]["is_accept"]=not states[selected_state]["is_accept"]
            if states[selected_state]["is_accept"]:
                spawn_particles(*states[selected_state]["pos"],40,(1.0,0.9,0.0),speed=12)

    if key==b't':
        if selected_state is not None:
            transition_mode=True; transition_src=selected_state

    if key==b'x':
        if edge_list:
            last=edge_list.pop()
            transitions.pop((last[0],last[2]),None)
        transition_mode=False; transition_src=None

    if transition_mode:
        # Decode the key to a string
        char = key.decode('utf-8', 'ignore')
        
        # Check if the user pressed a valid letter or number (0, 1, a, b, etc.)
        if char.isalnum():
            tkey = (transition_src, char)
            
            # Create transition if it doesn't already exist
            if tkey not in transitions:
                transitions[tkey] = transition_dst
                edge_list.append((transition_src, transition_dst, char))
                
                # Spawn connection particles
                if transition_src in states and transition_dst in states:
                    px=(states[transition_src]["pos"][0]+states[transition_dst]["pos"][0])/2
                    py=(states[transition_src]["pos"][1]+states[transition_dst]["pos"][1])/2
                    pz=(states[transition_src]["pos"][2]+states[transition_dst]["pos"][2])/2
                    spawn_particles(px,py,pz,25,(0.3,0.8,1.0),speed=6)
        
        # Always exit transition mode after a key is pressed
        transition_mode = False
        transition_src = None
        transition_dst = None
        return

    if key==b' ':
        q=questions[current_question]; score=0; result_text=""; flash_edges.clear()
        if not is_complete_dfa(q["alphabet"]):
            result_text="Warning: DFA is incomplete!\n"
        for string in q["test_strings"]:
            res,path=simulate_dfa(string); correct=q["expected"][string]
            if res==correct:
                score+=1; result_text+=f"'{string}': OK\n"; col=(0.2,1.0,0.4)
            else:
                result_text+=f"'{string}': WRONG\n"; col=(1.0,0.3,0.3)
            spawn_travel_particle(path,col)
            for i in range(len(path)-1):
                flash_edges.append([path[i],path[i+1],0.0,col])
        flow_string=q["test_strings"][-1]; flow_index=0
        total=len(q["test_strings"]); result_text+=f"Score: {score}/{total}"
        if score==total:
            for s in states:
                spawn_particles(*states[s]["pos"],60,(1.0,0.9,0.1),speed=15,lifetime=2.5)
        elif score>0:
            for s in find_accept():
                spawn_particles(*states[s]["pos"],30,(0.2,1.0,0.4),speed=10)

    if key==b'm':
        if current_question<len(questions)-1: current_question+=1
        reset_connections(); result_text=""; score=0; flow_string=""; flow_index=0

    if key in (b'+',b'='):
        if camera_z>120: camera_z-=25
    if key==b'-':
        if camera_z<1200: camera_z+=25

    if key==b'r':
        states.clear(); transitions.clear(); edge_list.clear()
        flash_edges.clear(); particle_list.clear()
        selected_state=None; state_id=0; result_text=""; score=0
        flow_string=""; flow_index=0

def specialKeyListener(key,x,y):
    global camera_x,camera_y,menu_hover
    if SCREEN=="MENU":
        if key==GLUT_KEY_DOWN: menu_hover=(menu_hover+1)%len(MENU_OPTIONS)
        if key==GLUT_KEY_UP:   menu_hover=(menu_hover-1)%len(MENU_OPTIONS)
        return
    if key==GLUT_KEY_LEFT:  camera_x-=5
    if key==GLUT_KEY_RIGHT: camera_x+=5
    if key==GLUT_KEY_UP:
        if camera_y<85: camera_y+=5
    if key==GLUT_KEY_DOWN:
        if camera_y>5: camera_y-=5

# ==============================================
#  MAIN DISPLAY
# ==============================================
def showScreen():
    glClearColor(0.02,0.02,0.06,1)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0,0,WIN_W,WIN_H)

    if SCREEN=="INTRO":
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluOrtho2D(0,WIN_W,0,WIN_H)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        draw_intro_screen()

    elif SCREEN=="MENU":
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluOrtho2D(0,WIN_W,0,WIN_H)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        draw_menu_screen()
        if show_how_to: draw_how_to_overlay()

    elif SCREEN=="PLAYING":
        setupCamera()
        draw_stars(); draw_floor(); draw_axes()
        draw_edges(); draw_states()
        draw_particles(); draw_travel_particles()
        draw_input_flow(); draw_hud()
        if show_how_to: draw_how_to_overlay()

    glutSwapBuffers()

# ==============================================
#  IDLE
# ==============================================
_last_time=[0.0]

def idle():
    global time_val,intro_timer
    now=glutGet(GLUT_ELAPSED_TIME)/1000.0
    dt=min(now-_last_time[0],0.05)
    _last_time[0]=now
    time_val+=dt

    if SCREEN in ("INTRO","MENU"):
        intro_timer+=dt if SCREEN=="INTRO" else 0
        update_intro_nodes(dt)
    elif SCREEN=="PLAYING":
        update_particles(dt)
        update_travel_particles(dt)
        update_flow(dt)
        for fe in flash_edges:
            fe[2]=min(1.0,fe[2]+dt*0.6)

    glutPostRedisplay()

# ==============================================
#  MAIN
# ==============================================
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(WIN_W,WIN_H)
    glutInitWindowPosition(80,40)
    glutCreateWindow(b"3D DFA Simulator")
    glEnable(GL_DEPTH_TEST)
    glutDisplayFunc(showScreen)
    glutMouseFunc(mouseListener)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutIdleFunc(idle)
    glutMainLoop()

if __name__=="__main__":
    main()
