# -*- coding: utf-8 -*-
"""
viewer.py  -  OpenGL viewer for .vob and .wld / .cem files.
Python 2.7 compatible.

Camera / View controls:
  Left mouse drag      : orbit (yaw + pitch, no roll)
  Middle mouse drag    : dolly (zoom in/out)
  Right mouse drag     : pan (move target in camera plane)
  Mouse wheel          : zoom in / out
  F                    : auto-fit all visible geometry
  R                    : toggle auto-rotate
  Arrow keys           : orbit  (left/right = yaw, up/down = pitch)
  W / S                : dolly forward / backward
  A / D                : pan left / right
  Q / E                : pan up / down
  + / -                : zoom in / out
  Z                    : toggle wireframe
  X                    : toggle x-ray
  C                    : toggle isolate
  V                    : toggle outline

Mesh navigation:
  Page Up / Page Down  : next / previous mesh (sub-mesh index)

Object selection (VOB mode):
  1 / 2                : previous / next named object (highlights it)

Background colour:
  3 / 4                : cycle background colour backward / forward

General:
  ESC                  : exit
"""

import sys
import os
import struct
import math

from PIL import Image
from OpenGL.GL   import *
from OpenGL.GLU  import *
from OpenGL.GLUT import *

import blackwood

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ESCAPE       = '\033'
DEFAULT_TEX  = 'DEFAULT'
TEX_BASE_DIR = 'tex\\jpg'
MAX_TEX_DIM  = 1024

# ---------------------------------------------------------------------------
# HUD state
# ---------------------------------------------------------------------------
g_hud_message = ["LFC Viewer"]
g_hud_timer   = [300]

# ---------------------------------------------------------------------------
# Background colour palette  (name, R, G, B)
# ---------------------------------------------------------------------------
g_bg_colors = [
    # --- Black / White / Gray ---
    ("White",                0.90, 0.90, 0.90),   # 0
    ("Black",                0.10, 0.10, 0.10),   # 1
    ("Warm Gray",            0.25, 0.24, 0.22),   # 2
    ("Cool Gray",            0.22, 0.24, 0.26),   # 3
    ("Medium Anthracite",    0.28, 0.28, 0.28),   # 4
    ("Soft Charcoal",        0.20, 0.20, 0.22),   # 5
    # --- Beige / Warm Neutral ---
    ("Cream / Ivory",        0.94, 0.92, 0.82),   # 6
    ("Dusty Beige",          0.86, 0.82, 0.75),   # 7
    ("Sepia Light Gray",     0.80, 0.76, 0.69),   # 8
    ("Pale Warm Beige",      0.92, 0.88, 0.80),   # 9
    ("Vintage Paper",        0.90, 0.85, 0.75),   # 10
    # --- Green ---
    ("Dark Olive",           0.20, 0.22, 0.16),   # 11
    ("Forest Green",         0.18, 0.25, 0.18),   # 12
    ("Tea Green",            0.16, 0.21, 0.14),   # 13
    ("Muted Green-Gray",     0.19, 0.22, 0.17),   # 14
    # --- Blue ---
    ("Night Blue",           0.14, 0.18, 0.24),   # 15
    ("Dusty Navy",           0.12, 0.16, 0.22),   # 16
    ("Dark Sea Blue",        0.13, 0.19, 0.21),   # 17
    ("Anthracite Blue",      0.16, 0.19, 0.23),   # 18
    ("Dark Gray-Blue",       0.18, 0.18, 0.22),   # 19
    # --- Brown / Earth ---
    ("Muted Clay",           0.35, 0.25, 0.20),   # 20
    ("Dusty Taupe",          0.30, 0.26, 0.24),   # 21
    ("Warm Cocoa",           0.28, 0.22, 0.18),   # 22
    ("Faded Umber",          0.32, 0.28, 0.22),   # 23
    # --- Orange / Amber ---
    ("Faded Amber",          0.50, 0.35, 0.15),   # 24
    ("Dusty Terracotta",     0.48, 0.30, 0.22),   # 25
    ("Muted Pumpkin",        0.45, 0.32, 0.18),   # 26
    # --- Purple / Lavender ---
    ("Dusty Lavender",       0.35, 0.30, 0.40),   # 27
    ("Faded Mauve",          0.40, 0.32, 0.38),   # 28
    ("Soft Plum",            0.30, 0.25, 0.35),   # 29
    # --- Red / Burgundy ---
    ("Dusty Rose",           0.38, 0.28, 0.30),   # 30
    ("Faded Brick",          0.40, 0.25, 0.22),   # 31
    ("Vintage Burgundy",     0.35, 0.22, 0.25),   # 32
]
g_bg_index = [18]   # Default background colour index

# ---------------------------------------------------------------------------
# Camera state  (spherical / orbit model)
#
#   Eye is placed at g_cam['dist'] from g_cam['target'],
#   rotated by yaw (horizontal) and pitch (vertical) in degrees.
#   Up vector is world +Z; pitch is clamped to [-89, +89].
# ---------------------------------------------------------------------------
g_cam_default = {
    'target'   : [0.0, 0.0, 0.0],
    'dist'     : 0.0,
    'yaw'      : 30.0,
    'pitch'    : 15.0,
    'fov'      : 45.0,
    'speed'    : 0.05,
    'rot_speed': 5.0,
}

g_cam = {
    'target'   : g_cam_default['target'],
    'dist'     : g_cam_default['dist'],
    'yaw'      : g_cam_default['yaw'],
    'pitch'    : g_cam_default['pitch'],
    'fov'      : g_cam_default['fov'],
    'speed'    : g_cam_default['speed'],
    'rot_speed': g_cam_default['rot_speed'],
    'auto_rot' : False,
}

g_mouse = {
    'button'   : None,
    'x'        : 0,
    'y'        : 0,
}

# ---------------------------------------------------------------------------
# View state
# ---------------------------------------------------------------------------

g_view = {
    'outline'  : True,
    'isolate'  : False,
    'wireframe': False,
    'xray'     : False,
}


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

g_objects   = []      # list of OBJETO instances (VOB mode)
g_textures  = {}      # texture filename  -> GL texture id (or None on failure)
g_tex_cache = {}      # object name       -> texture filename (WLD mode)
g_glists    = {}      # object name       -> GL display list id (WLD mode)
g_sel       = [0]     # selected object index (VOB mode)
g_blk       = [None]  # blackwood.blk_file instance (WLD mode)
g_mode      = [None]  # 'vob' or 'wld'
g_fname     = ['']    # loaded file path
g_mid       = [1]     # active mesh index (1-based)

g_bbox = {
    'min'   : [ 1e9,  1e9,  1e9],
    'max'   : [-1e9, -1e9, -1e9],
    'valid' : False,
}


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def next_p2(n):
    """Return the smallest power of two >= n."""
    v = 1

    while v < n:
        v <<= 1
    return v


def toname(d, fill=False):
    """Convert a byte list to a null-terminated Python string."""
    s = ''

    for k in d:
        if k == 0:
            if fill:
                s += ' '
            else:
                return s
        else:
            s += chr(k)
    return s


def fixed(sd):
    """Decode 4 bytes as a 16.16 fixed-point signed value."""
    raw = chr(sd[0]) + chr(sd[1]) + chr(sd[2]) + chr(sd[3])
    return struct.unpack('i', raw)[0] / 65536.0


def read_axyz(d):
    """Unpack flag + x, y, z from 16 bytes of fixed-point data."""
    vi = 0
    s = fixed(d[vi:vi + 4]); vi += 4
    x = fixed(d[vi:vi + 4]); vi += 4
    y = fixed(d[vi:vi + 4]); vi += 4
    z = fixed(d[vi:vi + 4]); vi += 4
    return s, x, y, z


def znormal(p1, p2, p3):
    """Return the unit normal of triangle (p1, p2, p3)."""
    d1 = p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]
    d2 = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
    x  = d1[1] * d2[2] - d1[2] * d2[1]
    y  = d1[0] * d2[2] - d1[2] * d2[0]
    z  = d1[1] * d2[0] - d1[0] * d2[1]
    nn = math.sqrt(x * x + y * y + z * z)
    if nn == 0:
        nn = 1.0
    return x / nn, y / nn, z / nn


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------

def _bbox_add(x, y, z):
    """Expand the global bounding box to include point (x, y, z)."""
    bb = g_bbox

    if x < bb['min'][0]: bb['min'][0] = x
    if y < bb['min'][1]: bb['min'][1] = y
    if z < bb['min'][2]: bb['min'][2] = z
    if x > bb['max'][0]: bb['max'][0] = x
    if y > bb['max'][1]: bb['max'][1] = y
    if z > bb['max'][2]: bb['max'][2] = z

    bb['valid'] = True


def bbox_from_objects():
    """Rebuild the global bounding box from all OBJETO vertices (VOB mode)."""
    g_bbox['min'] = [ 1e9,  1e9,  1e9]
    g_bbox['max'] = [-1e9, -1e9, -1e9]
    g_bbox['valid'] = False

    for obj in g_objects:
        for v in obj.vt:
            _bbox_add(v[0], v[1], v[2])


def bbox_from_wld():
    """Rebuild the global bounding box from WLD vertices via the blackwood API."""
    s = g_blk[0]

    g_bbox['min'] = [ 1e9,  1e9,  1e9]
    g_bbox['max'] = [-1e9, -1e9, -1e9]
    g_bbox['valid'] = False

    s.update_geo_num()

    for k in range(s.nv):
        _, x, y, z = s.get_vertex(k)
        _bbox_add( x, y, z)
        _bbox_add(-x, y, z)   # mirrored side


def camera_fit():
    """Set camera distance and target so all geometry fits inside the frustum."""
    if not g_bbox['valid']:
        return

    cx = (g_bbox['min'][0] + g_bbox['max'][0]) * 0.5
    cy = (g_bbox['min'][1] + g_bbox['max'][1]) * 0.5
    cz = (g_bbox['min'][2] + g_bbox['max'][2]) * 0.5
    dx = g_bbox['max'][0] - g_bbox['min'][0]
    dy = g_bbox['max'][1] - g_bbox['min'][1]
    dz = g_bbox['max'][2] - g_bbox['min'][2]

    radius = math.sqrt(dx * dx + dy * dy + dz * dz) * 0.5
    dist   = radius / math.sin(math.radians(g_cam['fov']) * 0.5) * 1.1

    g_cam['target'] = [cx, cy, cz]
    g_cam['dist']   = max(dist, 0.05)


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def apply_camera():
    """Build the modelview matrix from spherical orbit parameters."""
    glLoadIdentity()

    pitch = max(-89.0, min(89.0, g_cam['pitch']))
    yr = math.radians(g_cam['yaw'])
    pr = math.radians(pitch)
    d  = g_cam['dist']

    # Spherical -> Cartesian, Z-up convention
    ex = d * math.cos(pr) * math.sin(yr)
    ey = d * math.cos(pr) * math.cos(yr)
    ez = d * math.sin(pr)

    tx, ty, tz = g_cam['target']
    gluLookAt(tx + ex, ty + ey, tz + ez,
              tx,      ty,      tz,
              0.0,     0.0,     1.0)


def _pan(dx_cam, dy_cam):
    """
    Translate the camera target in the camera's local right direction (dx_cam)
    and world Z (dy_cam).  The right vector is derived from yaw only so it
    stays horizontal regardless of pitch.
    """
    yr = math.radians(g_cam['yaw'])
    rx =  math.cos(yr)
    ry = -math.sin(yr)

    g_cam['target'][0] += dx_cam * rx
    g_cam['target'][1] += dx_cam * ry
    g_cam['target'][2] += dy_cam


def _move_forward(dz):
    """
    Move camera target forward/backward in the camera's view direction (horizontal).
    dz > 0 moves backward, dz < 0 moves forward.
    """
    yr = math.radians(g_cam['yaw'])
    fx = math.sin(yr)   # forward X
    fz = math.cos(yr)   # forward Z (Horizontal plane in Z-up world)

    g_cam['target'][0] += dz * fx
    g_cam['target'][1] += dz * fz


# ---------------------------------------------------------------------------
# Texture loading
# ---------------------------------------------------------------------------

def build_texture(path):
    """
    Load an image file and upload it as an OpenGL texture.
    Returns (True, tex_id) on success, (False, 0) on failure.
    """
    try:
        pic = Image.open(path)
    except Exception:
        print 'Texture not found: %s' % path
        return False, 0

    w, h = pic.size

    if w > MAX_TEX_DIM or h > MAX_TEX_DIM:
        if w >= h:
            nw = MAX_TEX_DIM
            nh = max(1, int(h * float(MAX_TEX_DIM) / w))
        else:
            nh = MAX_TEX_DIM
            nw = max(1, int(w * float(MAX_TEX_DIM) / h))
    else:
        if w >= h:
            nw = next_p2(w)
            nh = max(1, int(h * float(nw) / w))
        else:
            nh = next_p2(h)
            nw = max(1, int(w * float(nh) / h))

    pic    = pic.resize((nw, nh))
    lw     = next_p2(nw)
    lh     = next_p2(nh)
    padded = Image.new('RGB', (lw, lh), (0, 0, 0))

    padded.paste(pic)

    bits = padded.tostring('raw', 'RGBX', 0, -1)

    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, 3, lw, lh, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, bits)
    return True, tid


def bind_texture(fname):
    """Bind a named texture, loading it from disk on the first call."""
    if fname not in g_textures:
        xname = fname if fname != DEFAULT_TEX else 'HEL_DEFAULT'
        ok, tid = build_texture(os.path.join(TEX_BASE_DIR, xname + '.jpg'))
        g_textures[fname] = tid if ok else None

    tid = g_textures[fname]

    if tid is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tid)
    else:
        glDisable(GL_TEXTURE_2D)


# ---------------------------------------------------------------------------
# OBJETO  -  single named mesh part
# ---------------------------------------------------------------------------

class OBJETO(object):
    """Single named mesh part: vertices, triangles, flags, and material data."""

    def __init__(self, name):
        self.name       = name
        self.color      = (1.0, 1.0, 1.0, 1.0)
        self.material   = None
        self.mat_id     = 0
        self.mat_num_id = 0
        self.vt         = []    # vertex positions stored in Z-up order
        self.fc         = []    # face index triples
        self.fflags     = []    # per-face flag bytes
        self.vflags     = []    # per-vertex flag bytes
        self.nv_list    = []    # per-face normals
        self.enable     = True
        self.GLcalllist = None
        self.mat_data   = []
        self.mat_quad   = []
        self.tex_data   = []
        self.tex_files  = []

    def add_face(self, xyz1, xyz2, xyz3, fbin=None, vbin=None):
        """
        Append a triangle.  Input coords are in the game Y-up space (x, y, z).
        They are stored as (x, z, y) so that the stored geometry is Z-up,
        matching the camera convention used by the viewer — no world rotation
        is required at draw time for VOB mode.
        """
        ni = len(self.vt)
        zup1 = (xyz1[0], xyz1[2], xyz1[1])
        zup2 = (xyz2[0], xyz2[2], xyz2[1])
        zup3 = (xyz3[0], xyz3[2], xyz3[1])
        self.vt.extend([zup1, zup2, zup3])
        self.vflags.extend(vbin if vbin else [[0, 0, 0, 0]] * 3)
        self.fflags.append(fbin if fbin else [0] * 12)
        self.fc.append([ni, ni + 1, ni + 2])
        self.nv_list.append(znormal(xyz1, xyz2, xyz3))

    def _geo_render(self):
        """Emit GL geometry for all visible (non-collision, non-shadow) faces."""
        for f in range(len(self.fc)):
            if self.fflags[f][4] != 0:
                continue

            glNormal3f(*self.nv_list[f])

            for vi in self.fc[f]:
                ori = self.mat_data[1] if len(self.mat_data) > 1 else 5
                if   ori == 3: ixu, ixv = 1, 2
                elif ori == 2: ixu, ixv = 0, 2
                elif ori == 1: ixu, ixv = 0, 2
                elif ori == 4: ixu, ixv = 1, 2
                else:          ixu, ixv = 0, 1

                xu = xv = 0.0

                if len(self.mat_quad) >= 4:
                    mq = self.mat_quad

                    if mq[1] != mq[0]:
                        xu = (self.vt[vi][ixu] - mq[0]) / float(mq[1] - mq[0])

                    if mq[3] != mq[2]:
                        xv = (self.vt[vi][ixv] - mq[2]) / float(mq[3] - mq[2])

                if self.tex_data:
                    td      = self.tex_data[0][1]
                    uv_flag = td[1]
                    du = float(td[4]); dv = float(td[5])
                    u0 = float(td[6]); v0 = float(td[7])

                    if uv_flag == 0:
                        tu = xu * (du / 64.0) + u0 / 64.0
                        tv = xv * (dv / 64.0) + v0 / 64.0
                    elif uv_flag == 1:
                        tv = xu * (du / 64.0) - u0 / 64.0
                        tu = 1.0 - (xv * (dv / 64.0) + v0 / 64.0)
                        tv = 1.0 - tv
                    elif uv_flag == 2:
                        tu = xu * (du / 64.0) + u0 / 64.0
                        tv = xv * (dv / 64.0) + v0 / 64.0
                    elif uv_flag == 3:
                        tv = xu * (du / 64.0) + u0 / 64.0
                        tu = xv * (dv / 64.0) + v0 / 64.0
                        tv = 1.0 - tv
                    else:
                        tu = 1.0 - (xu * (du / 64.0) + u0 / 64.0)
                        tv = 1.0 - (xv * (dv / 64.0) + v0 / 64.0)
                        tv = 1.0 - tv

                    glTexCoord2f(tu, tv)

                glVertex3f(*self.vt[vi])

    def render(self, wireframe = False, optional_col = False):
        """
            Render the object via a GL display list, binding its texture first.
            (Wireframe - no texture)

        """
        if not self.enable or not self.fc:
            return

        if self.tex_data and self.tex_files:
            idx = self.tex_data[0][1][2]

            if idx < len(self.tex_files) and wireframe == False:
                bind_texture(self.tex_files[idx])

        if wireframe == False:
            glColor3fv(self.color[:3])

        if optional_col:
            glColor4f(*optional_col)

        if self.GLcalllist is None:
            self.GLcalllist = glGenLists(1)
            glNewList(self.GLcalllist, GL_COMPILE)
            self._geo_render()
            glEndList()

        glBegin(GL_TRIANGLES)
        glCallList(self.GLcalllist)
        glEnd()


# ---------------------------------------------------------------------------
# VOB file helpers
# ---------------------------------------------------------------------------

def _load_raw_vob():
    """Read the current VOB file and return it as a raw byte list."""
    f   = open(g_fname[0], 'rb')
    raw = []
    buf = f.read(65536)

    while buf:
        for b in buf:
            raw.append(struct.unpack('B', b)[0])

        buf = f.read(65536)

    f.close()
    return raw


def parse_vob(data):
    """
    Parse raw VOB bytes (starting at offset 0) into a list of OBJETO instances.
    Header location is delegated to blackwood.find_header to avoid duplication.
    Returns (obj_list, tex_files, tex_if, m_list).
    """
    result = blackwood.find_header(data, 0)
    if result is None or result[0] is None:
        print 'parse_vob: no valid header found'
        return [], [], [], []

    i, _ = result

    nv = data[i]     + data[i + 1] * 256
    nf = data[i + 2] + data[i + 3] * 256
    mn = data[i + 30]
    mi = i + 32

    # --- Object metadata table ---
    obj_meta = []

    for k in range(mn):
        oz   = data[mi + k * 16 : mi + k * 16 + 16]
        rgba = [g / 256.0 for g in oz[0:4]]
        name = toname(oz[4:14])
        mat  = oz[14] + 256 * oz[15]
        obj_meta.append((rgba, name, mat))

    # --- Vertex table ---
    vi_base = mi + mn * 16
    vtx     = []
    vtx_raw = []

    for k in range(nv):
        kv = k * 16 + vi_base
        _, x, y, z = read_axyz(data[kv : kv + 16])

        vtx.append((x, z, y))      # store in Z-up order for add_face
        vtx_raw.append(data[kv : kv + 4])

    # --- Face table ---
    fc_base = vi_base + 16 * nv
    faces   = [data[fc_base + k * 12 : fc_base + k * 12 + 12] for k in range(nf)]

    # --- Texture file list ---
    vi = fc_base + nf * 12

    while data[vi] == 0:
        vi += 1

    num_tex   = data[vi]; vi += 4
    tex_files = []

    for _ in range(num_tex):
        tex_files.append(toname(data[vi + 4 : vi + 20]))
        vi += 20

    # --- Texture-id (tex_if) table ---
    ktex_num = data[vi] + 256 * data[vi + 1]; vi += 4
    tex_if   = []

    for _ in range(ktex_num):
        tname = toname(data[vi : vi + 16])
        tdata = data[vi + 16 : vi + 24]
        tex_if.append([tname, tdata[:], tex_files[tdata[2]]])
        vi += 24

    # --- Material table ---
    num_mat = data[vi]; vi += 4
    m_list  = []

    for _ in range(num_mat):
        mname = toname(data[vi : vi + 15])
        mdata = data[vi + 15 : vi + 44]
        m_list.append([mname, mdata[:]])
        vi += 44

    # --- Build OBJETO list ---
    fmask    = 63 * 256 + 255
    obj_list = []

    for oid in range(mn):
        rgba, name, mat = obj_meta[oid]
        obj             = OBJETO(name)
        obj.color       = tuple(rgba)
        obj.material    = name
        obj.mat_id      = mat
        obj.mat_num_id  = mat

        for oz in faces:
            if oz[2] != oid or oz[4] != 0:
                continue

            v1 = (oz[6]  + 256 * (oz[7]  & (fmask >> 8))) & fmask
            v2 = (oz[8]  + 256 * (oz[9]  & (fmask >> 8))) & fmask
            v3 = (oz[10] + 256 * (oz[11] & (fmask >> 8))) & fmask

            if v1 >= nv or v2 >= nv or v3 >= nv:
                continue

            obj.add_face(vtx[v1], vtx[v2], vtx[v3],
                         fbin=list(oz),
                         vbin=[vtx_raw[v1][:], vtx_raw[v2][:], vtx_raw[v3][:]])

        obj.mat_data = m_list[mat][1][:]
        obj.mat_quad = [fixed(obj.mat_data[5 + 4 * t : 5 + 4 * (t + 1)]) for t in range(4)]
        safe_len     = len(tex_if) - 1 if tex_if else 0
        i40 = min(obj.mat_data[25] if len(obj.mat_data) > 25 else 0, safe_len)
        i36 = min(obj.mat_data[21] if len(obj.mat_data) > 21 else 0, safe_len)
        obj.tex_data  = [tex_if[i40], tex_if[i36]] if tex_if else []
        obj.tex_files = tex_files[:]

        obj_list.append(obj)

    return obj_list, tex_files, tex_if, m_list


# ---------------------------------------------------------------------------
# WLD rendering
# ---------------------------------------------------------------------------

def render_wld_obj(name):
    """Render one named WLD object via the blackwood API, using a display-list cache."""
    s = g_blk[0]

    if name not in g_tex_cache:
        g_tex_cache[name] = s.get_obj_file_texture(name)

    fname = g_tex_cache[name]

    if fname == DEFAULT_TEX:
        fname = 'HEL_DEFAULT'

    bind_texture(fname)

    if name in g_glists:
        glBegin(GL_TRIANGLES)
        glCallList(g_glists[name])
        glEnd()
        return

    glist = glGenLists(1)
    g_glists[name] = glist

    glNewList(glist, GL_COMPILE)

    for m in range(9):
        for p in s.get_xyzuf_list(name, m):
            glTexCoord2f(p[3], 1.0 - p[4])
            glVertex3f(p[0], p[2], -p[1])
        for p in s.get_xyzuf_list(name, m, kside=1):
            glTexCoord2f(p[3], 1.0 - p[4])
            glVertex3f(p[0], p[2], -p[1])

    glEndList()
    glBegin(GL_TRIANGLES)
    glCallList(g_glists[name])
    glEnd()


# ---------------------------------------------------------------------------
# GLUT callbacks
# ---------------------------------------------------------------------------

def draw_hud():
    """Overlay a single-line text message in the top-left corner."""
    if not g_hud_message[0]:
        return

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()

    w = glutGet(GLUT_WINDOW_WIDTH)
    h = glutGet(GLUT_WINDOW_HEIGHT)

    gluOrtho2D(0, w, 0, h)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)

    # Choose text colour for contrast against the current background.
    _name, bg_r, bg_g, bg_b = g_bg_colors[g_bg_index[0]]
    brightness = bg_r * 0.5 + bg_g * 0.5 + bg_b * 0.5
    if brightness > 1:
        glColor3f(0.0, 0.0, 0.0)
    else:
        glColor3f(1.0, 1.0, 1.0)

    glRasterPos2i(10, h - 25)
    for ch in g_hud_message[0]:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

    g_hud_timer[0] -= 1
    if g_hud_timer[0] <= 0:
        g_hud_message[0] = ""

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_grid(size = 10.0, step = 1.0):
    """Draw a flat ground grid on the XY plane (Z=0)."""
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)

    glColor3f(0.35, 0.35, 0.35)
    glLineWidth(1.0)

    glBegin(GL_LINES)

    x = -size
    while x <= size + 0.001:
        glVertex3f(x, -size, 0.0)
        glVertex3f(x,  size, 0.0)
        x += step

    y = -size
    while y <= size + 0.001:
        glVertex3f(-size, y, 0.0)
        glVertex3f( size, y, 0.0)
        y += step

    glEnd()

    # X axis: red, Y axis: green
    glLineWidth(4.0)
    glBegin(GL_LINES)

    glColor3f(0.8, 0.2, 0.2)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(size, 0.0, 0.0)
    glColor3f(0.2, 0.8, 0.2)
    glVertex3f(0.0, 0.0, 0.0)
    glVertex3f(0.0, size, 0.0)

    glEnd()

    glEnable(GL_LIGHTING)


def draw_outline_stencil(obj, outline_color = (0.4, 1.0, 0.8)):
    """Draw outline using stencil buffer (glowing effect)."""

    # Mode 0: Outline OFF
    if g_view['outline'] == False:
        obj.render()
        return

    # Clear Stencil buffer
    glClearStencil(0)
    glClear(GL_STENCIL_BUFFER_BIT)
    glEnable(GL_STENCIL_TEST)

    # Mode 1: Outline ON
    if g_view['wireframe'] == False and g_view['xray'] == False:
        # Draw base mesh
        glStencilFunc(GL_ALWAYS, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)

        obj.render(wireframe = False)

        # Draw outline
        glStencilFunc(GL_NOTEQUAL, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)

        glColor3f(*outline_color)
        glLineWidth(8.0)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        obj.render(wireframe = True)

    # Mode 2: Outline ON, X-Ray OFF
    if g_view['wireframe'] == False and g_view['xray'] == True:
        # Draw base mesh
        glStencilFunc(GL_ALWAYS, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)

        obj.render(optional_col = (0.0, 0.8, 0.6, 0.3))

        # Draw outline
        glStencilFunc(GL_NOTEQUAL, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)

        glColor3f(*outline_color)
        glLineWidth(8.0)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        obj.render(wireframe = True)


    # Mode 3: Wireframe ON - X-Ray OFF
    if g_view['wireframe'] == True and g_view['xray'] == False:
        # Draw base mesh
        glStencilFunc(GL_ALWAYS, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        glDisable(GL_LIGHTING)

        obj.render(wireframe = False, optional_col = (0.3, 0.6, 0.5, 1.0))

    # Mode 4: Wireframe ON
    if g_view['wireframe'] == True:
        # Draw wireframe
        glStencilFunc(GL_NOTEQUAL, 1, 1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)

        glColor3f(*outline_color)
        glLineWidth(2.0)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        obj.render(wireframe = True)

    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
    glEnable(GL_LIGHTING)
    glDisable(GL_STENCIL_TEST)


def draw():
    """Clear buffers, apply camera, render the scene, swap buffers."""
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

    glLightfv(GL_LIGHT0, GL_POSITION, (0.5, -1.0, -0.5, 0.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  (1.0, 1.0, 1.0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT,  (0.40, 0.40, 0.40, 0.0))

    apply_camera()

    if g_cam['auto_rot']:
        g_cam['yaw'] = (g_cam['yaw'] + 0.8) % 360.0

    if g_mode[0] == 'wld':
        # WLD vertices from get_xyzuf_list are emitted as (x, z, -y), placing
        # geometry in OpenGL Y-up space.  A 90 degree X-rotation maps that to
        # Z-up so the object stands upright with the camera looking level.
        glColor3f(1.0, 1.0, 1.0)
        glPushMatrix()
        glRotatef(90.0, 1.0, 0.0, 0.0)

        for name in g_blk[0].get_obj_names():
            render_wld_obj(name)

        glPopMatrix()

    elif g_mode[0] == 'vob':
        # VOB vertices are already stored in Z-up order by OBJETO.add_face
        # (x, y, z -> x, z, y swap at load time), so no world rotation needed.
        selected_obj = g_objects[g_sel[0]]

        for obj in (g_objects):

            if obj != selected_obj:
                if g_view['isolate'] == False:
                   obj.render()
            else:
                draw_outline_stencil(selected_obj)

    draw_grid()
    draw_hud()
    glutSwapBuffers()


def init_gl(width, height):
    """One-time OpenGL state initialisation."""
    name, r, g, b = g_bg_colors[g_bg_index[0]]

    glClearColor(r, g, b, 0.0)
    glClearDepth(1.0)
    glShadeModel(GL_SMOOTH)
    glDepthFunc(GL_LESS)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_NORMALIZE)
    glEnable(GL_COLOR_MATERIAL)
    glEnable(GL_BLEND)

    _set_projection(width, height)


def _set_projection(width, height):
    """Rebuild the projection matrix for the current viewport size."""
    if height == 0:
        height = 1

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(g_cam['fov'], float(width) / float(height), 0.01, 1000.0)
    glMatrixMode(GL_MODELVIEW)


def resize(width, height):
    """GLUT reshape callback."""
    glViewport(0, 0, width, height)
    _set_projection(width, height)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def switch_mesh(mid):
    """Switch to sub-mesh index mid (1-based) in the currently loaded file."""
    if mid < 1:
        print 'Mesh index must be >= 1'
        return

    if g_mode[0] == 'wld':
        s = g_blk[0]

        try:
            s.set_mid(mid)
        except (IndexError, Exception) as e:
            print 'Mesh %i not available: %s' % (mid, e)
            return

        for gid in g_glists.values():
            glDeleteLists(gid, 1)

        g_glists.clear()
        g_tex_cache.clear()

        g_mid[0] = mid

        bbox_from_wld()
        camera_fit()
        print 'Mesh %i: %s' % (mid, ', '.join(s.get_obj_names()))

    else:   # vob
        raw  = _load_raw_vob()
        voff = 0

        for step in range(mid - 1):
            _, next_off = blackwood.find_header(raw, voff)

            if next_off is None:
                print 'Mesh %i not available (only %i found)' % (mid, step + 1)
                return

            voff = next_off

        objs, _, _, _ = parse_vob(raw[voff:] if voff else raw)

        if not objs:
            print 'Mesh %i: no objects found' % mid
            return

        for obj in g_objects:
            if obj.GLcalllist is not None:
                glDeleteLists(obj.GLcalllist, 1)

        del g_objects[:]
        g_objects.extend(objs)

        g_sel[0] = 0
        g_mid[0] = mid

        bbox_from_objects()
        camera_fit()
        print 'Mesh %i: %i objects' % (mid, len(g_objects))

    glutSetWindowTitle('LFC Viewer - %s  mesh %i'
                       % (os.path.basename(g_fname[0]), g_mid[0]))


def cycle_background(forward=True):
    """Advance or retreat the background colour index and update the clear colour."""
    if forward:
        g_bg_index[0] = (g_bg_index[0] + 1) % len(g_bg_colors)
    else:
        g_bg_index[0] = (g_bg_index[0] - 1) % len(g_bg_colors)

    name, r, g, b = g_bg_colors[g_bg_index[0]]
    glClearColor(r, g, b, 0.0)

    total = len(g_bg_colors)
    g_hud_message[0] = "Background: %s (%d/%d)" % (name, g_bg_index[0] + 1, total)
    g_hud_timer[0] = 120

    print 'Background: %s (%d/%d) - RGB(%.2f, %.2f, %.2f)' % (
        name, g_bg_index[0] + 1, total, r, g, b)


def toggle_key(var, key):
    """ Toggle a value with True or False in a key """
    if var[key] == True:
        var[key] = False
    else:
        var[key] = True
    return var[key]


# ---------------------------------------------------------------------------
# Keyboard events
# ---------------------------------------------------------------------------

def key_pressed(*args):
    """Regular key callback — see module docstring for the full key map."""
    key = args[0]

    if key == ESCAPE:
        glutDestroyWindow(glutGetWindow())
        sys.exit(0)

    elif key in ('z', 'Z'):
        toggle_key(g_view, 'wireframe')
        print 'Wireframe %s' % ('ON' if g_view['wireframe'] else 'OFF')

    elif key in ('x', 'X'):
        toggle_key(g_view, 'xray')
        print 'X-Ray %s' % ('ON' if g_view['xray'] else 'OFF')

    elif key in ('c', 'C'):
        toggle_key(g_view, 'isolate')
        print 'Isolate %s' % ('ON' if g_view['isolate'] else 'OFF')

    elif key in ('v', 'V'):
        toggle_key(g_view, 'outline')
        print 'Outline %s' % ('ON' if g_view['outline'] else 'OFF')

    elif key in ('r', 'R'):
        toggle_key(g_cam, 'auto_rot')
        print 'Auto-rotate %s' % ('ON' if g_cam['auto_rot'] else 'OFF')

    elif key in ('f', 'F'):
        g_cam['yaw']   = g_cam_default['yaw']
        g_cam['pitch'] = g_cam_default['pitch']

        if g_mode[0] == 'wld':
            bbox_from_wld()
        else:
            bbox_from_objects()

        camera_fit()

    elif key == '+' or key == '=':
        g_cam['dist'] = max(g_cam['dist'] * 0.9, 0.01)

    elif key == '-':
        g_cam['dist'] *= 1.1

    elif key in ('w', 'W'):
        speed = g_cam['speed'] * g_cam['dist']    # Speed factor
        _move_forward(-speed)                     # Forward move

    elif key in ('s', 'S'):
        speed = g_cam['speed'] * g_cam['dist']    # Speed factor
        _move_forward(speed)                      # Back move

    elif key in ('a', 'A'):
        _pan( g_cam['speed'] * g_cam['dist'], 0.0)

    elif key in ('d', 'D'):
        _pan(-g_cam['speed'] * g_cam['dist'], 0.0)

    elif key in ('q', 'Q'):
        _pan(0.0, -g_cam['speed'] * g_cam['dist'])

    elif key in ('e', 'E'):
        _pan(0.0,  g_cam['speed'] * g_cam['dist'])

    elif key == '1' and g_mode[0] == 'vob':
        g_sel[0] = max(g_sel[0] - 1, 0)
        print 'Object [%i]: %s' % (g_sel[0], g_objects[g_sel[0]].name)

    elif key == '2' and g_mode[0] == 'vob':
        g_sel[0] = min(g_sel[0] + 1, len(g_objects) - 1)
        print 'Object [%i]: %s' % (g_sel[0], g_objects[g_sel[0]].name)

    elif key == '3':
        cycle_background(forward=False)

    elif key == '4':
        cycle_background(forward=True)

    glutPostRedisplay()


def special_key_pressed(*args):
    """Special key callback: arrows for orbit, Page Up/Down for mesh switching."""
    key = args[0]

    if   key == GLUT_KEY_LEFT:
        g_cam['yaw']   -= g_cam['rot_speed']
    elif key == GLUT_KEY_RIGHT:
        g_cam['yaw']   += g_cam['rot_speed']
    elif key == GLUT_KEY_UP:
        g_cam['pitch']  = min(g_cam['pitch'] + g_cam['rot_speed'],  89.0)
    elif key == GLUT_KEY_DOWN:
        g_cam['pitch']  = max(g_cam['pitch'] - g_cam['rot_speed'], -89.0)
    elif key == GLUT_KEY_PAGE_UP:
        switch_mesh(g_mid[0] + 1)
    elif key == GLUT_KEY_PAGE_DOWN:
        switch_mesh(max(1, g_mid[0] - 1))

    glutPostRedisplay()


# ---------------------------------------------------------------------------
# Mouse events
# ---------------------------------------------------------------------------

def mouse_button(button, state, x, y):
    """Record mouse button state; handle scroll-wheel zoom (GLUT buttons 3 / 4)."""
    if state == GLUT_DOWN:
        g_mouse['button'] = button
        g_mouse['x']      = x
        g_mouse['y']      = y
        if button == 3:
            g_cam['dist'] = max(g_cam['dist'] * 0.93, 0.01)
            glutPostRedisplay()
        elif button == 4:
            g_cam['dist'] *= 1.07
            glutPostRedisplay()
    else:
        g_mouse['button'] = None


def mouse_motion(x, y):
    """Handle mouse drag: left = orbit, middle = dolly, right = pan."""
    dx = x - g_mouse['x']
    dy = y - g_mouse['y']
    g_mouse['x'] = x
    g_mouse['y'] = y
    btn = g_mouse['button']

    if btn == GLUT_LEFT_BUTTON:
        g_cam['yaw']   = (g_cam['yaw'] + dx * 0.4) % 360.0
        g_cam['pitch'] = max(-89.0, min(89.0, g_cam['pitch'] + dy * 0.4))

    elif btn == GLUT_MIDDLE_BUTTON:
        factor = 1.0 - dy * 0.01
        g_cam['dist'] = max(g_cam['dist'] * factor, 0.01)

    elif btn == GLUT_RIGHT_BUTTON:
        speed = g_cam['dist'] * 0.0015
        _pan(dx * speed, dy * speed)

    glutPostRedisplay()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """
    Usage:
      python viewer.py <file.vob|wld|cem> [mesh_id]
    mesh_id defaults to 1.
    """
    if len(sys.argv) < 2:
        print __doc__
        sys.exit(1)

    fname      = sys.argv[1]
    ext        = os.path.splitext(fname)[1].lower()
    mid        = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    g_fname[0] = fname
    g_mid[0]   = mid

    if ext == '.vob':
        g_mode[0] = 'vob'
        print 'Loading VOB: %s  mesh=%i' % (fname, mid)
    elif ext in ('.wld', '.cem'):
        g_mode[0] = 'wld'
        print 'Loading WLD: %s  mesh=%i' % (fname, mid)
    else:
        print 'Unsupported file type: %s' % ext
        sys.exit(1)

    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_ALPHA | GLUT_DEPTH | GLUT_STENCIL)
    glutInitWindowSize(900, 650)
    glutInitWindowPosition(100, 80)
    glutCreateWindow('LFC Viewer - %s  mesh %i' % (os.path.basename(fname), mid))

    glutDisplayFunc(draw)
    glutIdleFunc(draw)
    glutReshapeFunc(resize)
    glutKeyboardFunc(key_pressed)
    glutSpecialFunc(special_key_pressed)
    glutMouseFunc(mouse_button)
    glutMotionFunc(mouse_motion)
    init_gl(900, 650)

    # Load mesh after OpenGL ready
    if g_mode[0] == 'vob':
        switch_mesh(g_mid[0])          # VOB mesh selection
    else:  # wld / cem
        s = blackwood.blk_file()
        s.load(g_fname[0])
        s.set_mid(g_mid[0])
        g_blk[0] = s
        print 'Objects: %s' % ', '.join(s.get_obj_names())
        bbox_from_wld()
        camera_fit()

    glutMainLoop()

    sys.exit(0)


if __name__ == '__main__':
    main()
