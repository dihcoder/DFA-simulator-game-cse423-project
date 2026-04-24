import random
#import math
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from math import cos, radians, sin



states = {}
transitions = {}   # (from, char) -> to
edge_list = []     # for drawing

selected_state = None
state_id = 0

camera_x = 45
camera_y = 35
camera_z = 350

current_question = 0
#mode = "CHALLENGE"
score=0

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
    }

    #****we need a lot more questions.***
]

# transition building
transition_mode = False
transition_src = None

# result display
result_text = ""



def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(1,1,1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0,1000,0,800)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glRasterPos2f(x,y)
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
    #acc=[]
    acc = set() # multiple accept states ---> does not allow duplicate
    for s in states:
        if states[s]["is_accept"]:
            acc.add(s)
    return acc

def simulate_dfa(string):
    start = find_start()
    accepts = find_accept()

    if start is None:
        return False

    current = start
    for ch in string:
        if (current, ch) not in transitions:
            return False
        current = transitions[(current, ch)]

   
    if current in accepts:
        return True
    else:      
        return False

def reset_connections():
    # states.clear()
    for s in states:
        states[s]["is_start"] = False
        states[s]["is_accept"] = False
    transitions.clear()
    edge_list.clear()
       

    # label transition with 0 or 1
    if transition_mode:
        if key ==b'0' or key == b'1':
            dest = selected_state
            char = key.decode() # B string ---> char

            # transitions[(transition_src, char)] = dest
            # edge_list.append((transition_src, dest, char))
            key = (transition_src, char)

            if key in transitions:
                print(" Transition already exists ")
            else:
                transitions[key] = dest
                edge_list.append((transition_src, dest, char))

            transition_mode = False
            transition_src = None

    # VALIDATE
    if key == b' ':
        q = questions[current_question]
        score = 0
        result_text = ""

        for string in q["test_strings"]:
            res = simulate_dfa(string)
            correct = q["expected"][string]

            if res==correct:
                score+= 1
                result_text += f"{string}: OK\n"
            else:
                result_text += f"{string}: WRONG\n"

        total = len(q["test_strings"])
        result_text += f"Score: {score}/{total}"

    # next question
    if key == b'm':
        if current_question < len(questions)-1:
            current_question += 1
        reset_connections() # the state nodes remain but all connections are removed
        


    # zoom in-out using + and - keys
    if key == b'+' or key == b'=':
        if camera_z > 120:   
             camera_z -= 25
        
    if key == b'-':
        if camera_z < 1200:
             camera_z += 25
       

    # reset
    if key == b'r':
        states.clear()
        transitions.clear()
        edge_list.clear()
        selected_state = None
        state_id = 0
        result_text = ""

def specialKeyListener(key, x, y):
    global camera_x, camera_y

    if key == GLUT_KEY_LEFT:
        camera_x -= 5
    if key == GLUT_KEY_RIGHT:
        camera_x += 5
    if key == GLUT_KEY_UP:
        if camera_y < 85:
            camera_y += 5
    if key == GLUT_KEY_DOWN:
        if camera_y > 10:
            camera_y -= 5




def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(120,1.25,0.1,1500)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    x = camera_z * cos(radians(camera_y)) * cos(radians(camera_x))
    y = camera_z * cos(radians(camera_y)) * sin(radians(camera_x))
    z = camera_z * sin(radians(camera_y))
    gluLookAt(x,y,z,0,0,0,0,0,1)



def draw_floor():
    for i in range(-200,200,20):
        for j in range(-200,200,20):

            glBegin(GL_QUADS)

            if (i+j)//20 % 2 == 0:
                glColor3f(0.7,0.7,0.7)
            else:
                glColor3f(0.3,0.3,0.3)

            glVertex3f(i,j,0)
            glVertex3f(i+20,j,0)
            glVertex3f(i+20,j+20,0)
            glVertex3f(i,j+20,0)

            glEnd()


def draw_edges():
    h = 760

  
    for e in edge_list:
        src=e[0]
        dst=e[1]
        ch=e[2]
        x1,y1,z1 = states[src]["pos"]
        x2,y2,z2 = states[dst]["pos"]

        glColor3f(1,1,1)
        glLineWidth(10)
        glBegin(GL_LINES)
        glVertex3f(x1,y1,z1)
        glVertex3f(x2,y2,z2)
        glEnd()

        draw_text(860, h, f"q{src} --{ch}--> q{dst}")
        h-=20



def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0,0,1000,800)

    setupCamera()

    draw_floor()
    #draw_states()
    draw_edges()

    # UI
    q = questions[current_question]
    draw_text(10,760, f"Rule: {q['rule']}")
    draw_text(10,730, "C=create k=switch states W/A/S/D move Q/E up-down")
    draw_text(10,700, "F=start G=accept T=transition 0/1=set")
    draw_text(10,670, "SPACE=validate M=next R=reset")
    draw_text(10,640, "Arrow keys=rotate camera  +/- = zoom")

    draw_text(650,760, f"selected state: q{selected_state}")
    draw_text(650,730, f"start state: q{find_start()}")
    draw_text(650,700, f"accept states: q{find_accept()}")

    h = 600
    for line in result_text.split("\n"):
        draw_text(10,h,line)
        h -= 20

    glutSwapBuffers()

def idle():
    glutPostRedisplay()







def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000,800)
    glutCreateWindow(b"3D DFA Builder")

    glEnable(GL_DEPTH_TEST)

    glutDisplayFunc(showScreen)
   # glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
   # glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    
    glutMainLoop()

if __name__ == "__main__":
    main()
