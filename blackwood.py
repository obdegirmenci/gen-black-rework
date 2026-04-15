# blackwood.py
# Binary .vob file parser and low-level mesh manipulation library (vertices, faces, materials, textures).

from PIL import Image, ImageDraw
import os
import os.path
import struct
import math
import random
from objread import *

# Vertex index mask (14-bit: 16383)
fmask = 63 * 256 + 255


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def to_word(x):
    """Pack integer x into a little-endian (lo, hi) byte pair."""
    if x > 65536:
        print "OVERFLOW \n\n\n"
    return x & 0xff, (x & 0xff00) / 256


def toname(d, fill=False):
    """Convert a byte array to a null-terminated ASCII string.
    Spaces are replaced with underscores. If fill=True, nulls become spaces."""
    s = ""
    for k in d:
        if k == 0:
            if fill:
                s += " "
            else:
                return s
        else:
            cs = chr(k)
            if cs == " ":
                s += "_"
            else:
                s += chr(k)
    return s


def toname2(d):
    """Convert a byte array to an ASCII string (no null termination, spaces -> underscores)."""
    s = " "
    for k in d:
        cs = chr(k)
        if cs == " ":
            s += "_"
        else:
            s += chr(k)
    return s


def ss(g, x=3):
    """Format a list of integers as a space-separated string with fixed-width fields."""
    s = ""
    for i in g:
        if x == 3:
            s += "%03i " % (i)
        if x == 5:
            s += "%5i " % (i)
    return s


def fixed(sd):
    """Unpack a 4-byte little-endian fixed-point value (16.16) to float."""
    s = chr(sd[0]) + chr(sd[1]) + chr(sd[2]) + chr(sd[3])
    return (struct.unpack("i", s)[0]) / 65536.0


def bin_vd(d, x, y, z):
    """Pack vertex data: flag byte d followed by three 16.16 fixed-point coords."""
    s = (struct.pack("iii", x * 65536.0, y * 65536.0, z * 65536.0))
    return [d, 0, 0, 0] + [ord(i) for i in s]


def read_axyz(d):
    """Read four sequential 16.16 fixed-point values: (a, x, y, z)."""
    vi = 0
    s = fixed(d[vi:vi + 4]); vi += 4
    x = fixed(d[vi:vi + 4]); vi += 4
    y = fixed(d[vi:vi + 4]); vi += 4
    z = fixed(d[vi:vi + 4]); vi += 4
    return [s, x, y, z]


def fit_area(x1, x2, y1, y2, du, dv, two_side=True, ratio=True):
    """Expand UV tile dimensions (du, dv) to fit the given world-space bounding box
    while preserving aspect ratio. Optionally symmetrises the X range."""
    if two_side and x1 * x2 > 0:
        limit = max(abs(x1), abs(x2))
        x1, x2 = -limit, +limit

    if two_side == False and x1 * x2 < 0:
        limit = max(abs(x1), abs(x2))
        if x1 > 0:
            x1, x2 = 0.001, +limit
        else:
            x1, x2 = -limit, -0.001

    dx, dy = x2 - x1, float(y2 - y1)
    ajust = True
    sx = du / dx
    sy = dv / dy

    if ajust:
        du1 = dx * sx
        dv1 = dy * sx
        if not (du1 > du or dv1 > dv):
            du, dv = du1, dv1
        else:
            du2 = dx * sy
            dv2 = dy * sy
            if not (du2 > du or dv2 > dv):
                du, dv = du2, dv2

    print "ratio", du / dx, dv / dy
    return x1, x2, y1, y2, du, dv


def calc_slot(sl, ori=0):
    """Convert a list of 4x4 texture-atlas slot indices to (u, v, du, dv) pixel coords."""
    u, v, du, dv = [], [], [], []
    for s in sl:
        j, i = int(s / 4), s % 4
        u.append(i * 16)
        v.append(j * 16)
        du.append((i + 1) * 16)
        dv.append((j + 1) * 16)
    return min(u), min(v), max(du) - min(u), max(dv) - min(v)


def find_header(data, voff):
    """Scan the binary data starting at voff to locate a valid mesh block header.
    Returns (header_offset, end_of_materials_offset) or (None, None) on failure."""
    i = voff - 1
    start = False
    dsz = len(data)

    while start == False:
        start = True
        i += 1

        if i + 3 > len(data):
            return None, None

        nv = data[i] + data[i + 1] * 256
        nf = data[i + 2] + data[i + 3] * 256
        mn = data[i + 30]          # object count at offset 60
        off_obj = i + 32           # object table at offset 62
        off_vi = off_obj + 16 * mn
        off_fc = off_vi + 16 * nv
        face_end = off_fc + nf * 12

        # Bounds check
        if face_end > dsz or off_vi > dsz or off_fc > dsz:
            start = False
        if start == False:
            continue

        # Minimum geometry sanity check
        if mn < 1 or nv < 2 or nf < 9:
            start = False
            continue

        if start == False:
            continue

        # Validate first character of each object name
        for k in range(mn):
            for s in range(1):
                name = data[off_obj + 4 + 16 * k + s]
                if name < 20 and name > 0:
                    start = False
                    break
        if start == False:
            continue

        # Validate vertex high bytes (must be zero)
        for k in range(nv):
            kv = k * 16 + off_vi
            a, x, y, z = read_axyz(data[kv:kv + 16])
            if data[kv + 2] > 0 or data[kv + 3] > 0:
                start = False
                break

        # Validate face object indices
        for k in range(nf):
            kf = k * 12 + off_fc
            if data[kf + 2] > mn:
                start = False
                break

        if start == False:
            continue

        # Walk past texture file table
        tex_off = face_end + 0
        while data[tex_off] == 0:
            tex_off += 1

        num_tex = data[tex_off]
        tex_off += 4
        vi = tex_off + 0
        for j in range(num_tex):
            skp_name = data[tex_off + 20 * j + 4]
            if skp_name < 20 or skp_name > 150:
                start = False
            vi += 20

        ktex_num = data[vi] + 256 * data[vi + 1]
        vi += 4
        for j in range(ktex_num):
            vi += 24

        num_mat = data[vi]
        vi += 4
        for j in range(num_mat):
            vi += 44

        return i, vi

    print "OUT", i


# ---------------------------------------------------------------------------
# Main VOB file class
# ---------------------------------------------------------------------------

class blk_file:

    # --- I/O ---

    def load(self, fname):
        """Load a binary VOB file into self.data and select mesh 1."""
        self.data = []
        self.mid = 1
        self.offset = 0
        f = open(fname, 'rb')
        buf = f.read(256000)
        while buf != "":
            for s in buf:
                self.data.append(struct.unpack("B", s)[0])
            buf = f.read(256000)
        self.data.append(struct.unpack("B", s)[0])
        self.set_mid(1)

    def write(self, fname):
        """Write self.data back to a binary VOB file."""
        f = open(fname, "wb")
        for x in self.data:
            f.write(struct.pack("B", x))
        f.close()

    # --- Mesh selection & header fields ---

    def set_mid(self, mid):
        """Select the active mesh block by 1-based index and refresh geometry offsets."""
        n = mid + 0
        vprox = 0
        vnext = 0
        while n > 0:
            n -= 1
            ss = find_header(self.data, vprox)
            if ss[0] is None:
                print "MESH OUT OF RANGE !"
                raise IndexError
            vnext, vprox = ss
        self.mid = mid + 0
        self.offset = vnext
        print "```" * 6
        if mid == 1 and self.data[self.offset - 20] != 0:
            print "Submeshes Count:", self.data[self.offset + 4]
        self.get_mirror_state(mid)
        self.get_mesh_type(mid)
        self.get_mesh_fix(mid)
        print "```" * 6
        self.update_geo_num()
        self.vfree = {}

    def set_child(self, sub):
        """Set the sub-mesh count field in the current mesh header."""
        i = self.offset
        self.data[i + 4] = sub

    def set_mirror_state(self, mirror_s):
        """Write mirror-state byte into the header of the current mesh."""
        i = self.offset
        if self.mid == 1 and self.data[i - 20] != 0:
            self.data[i - 20] = mirror_s
        else:
            self.data[i - 12] = mirror_s

    def set_mesh_type(self, mesh_t):
        """Write mesh-type byte into the header of the current mesh."""
        i = self.offset
        if self.mid == 1 and self.data[i - 20] != 0:
            self.data[i - 18] = mesh_t
        else:
            self.data[i - 10] = mesh_t

    def set_mesh_fix(self, mesh_f):
        """Write mirror-fix flag byte into the header of the current mesh."""
        i = self.offset
        if self.mid == 1 and self.data[i - 20] != 0:
            self.data[i - 17] = mesh_f
        else:
            self.data[i - 9] = mesh_f

    def get_mirror_state(self, n):
        """Print the mirror state stored in the mesh header."""
        i = self.offset
        MIRROR_ONLY_VALS = (226, 195, 35, 99)
        if n == 1 and self.data[i - 20] != 0:
            val = self.data[i - 20]
        else:
            val = self.data[i - 12]
        if val in MIRROR_ONLY_VALS:
            print "Mirror State: MIRROR ONLY"
        else:
            print "Mirror State: MIRROR FIX POSSIBLE"

    def get_mesh_type(self, n):
        """Print the mesh type stored in the mesh header."""
        MESH_TYPES = {
            0: "MAIN MESH",
            1: "BRAKE CALIPER",
            2: "STEERING WHEEL",
            3: "DEFAULT MESH",
            5: "ALWAYS VISIBLE, EVEN IN F MODE",
            10: "CENTRAL REARVIEW MIRROR",
        }
        i = self.offset
        if n == 1 and self.data[i - 20] != 0:
            val = self.data[i - 18]
        else:
            val = self.data[i - 10]
        label = MESH_TYPES.get(val, "UNKNOWN")
        print "Mesh Type: %s" % label

    def get_mesh_fix(self, n):
        """Print the mirror-fix flag stored in the mesh header."""
        i = self.offset
        if n == 1 and self.data[i - 20] != 0:
            val = self.data[i - 17]
        else:
            val = self.data[i - 9]
        if val == 2:
            print "Mesh Fix Flag: MIRROR FIX NOT WORK"
        else:
            print "Mesh Fix Flag: MIRROR FIX WORKS"

    # --- Geometry counters ---

    def update_geo_num(self):
        """Recalculate nv, nf, mn and derived offsets from the current mesh header."""
        i = self.offset
        self.nv = self.data[i] + self.data[i + 1] * 256
        self.nf = self.data[i + 2] + self.data[i + 3] * 256
        self.mn = self.data[i + 30]   # object count
        self.off_obj = i + 32
        self.off_vi = self.off_obj + 16 * self.mn
        self.off_fc = self.off_vi + 16 * self.nv

    # --- Vertex operations ---

    def add_vertex(self):
        """Append a zeroed vertex slot, increment nv, return new vertex index."""
        self.update_geo_num()
        i = self.offset
        for j in range(16):
            self.data.insert(j + self.off_vi + self.nv * 16, 0)
        self.data[i], self.data[i + 1] = to_word(self.nv + 1)
        self.update_geo_num()
        return self.nv - 1

    def get_vertex(self, k):
        """Return (a, x, y, z) for vertex index k, applying fmask if out of range."""
        self.update_geo_num()
        if k > self.nv:
            kv = (k & fmask) * 16 + self.off_vi
        else:
            kv = k * 16 + self.off_vi
        a, x, y, z = read_axyz(self.data[kv:kv + 16])
        a = self.data[kv]
        return a, x, y, z

    def set_vertex(self, i, x, y, z, a=1, tol=0.01):
        """Write position (x, y, z) to vertex i. Sets flag=2 for on-centre vertices."""
        vdata = bin_vd(a, x, y, z)
        for j in range(0, 4):
            self.data[j + self.off_vi + i * 16] = 0
        for j in range(4, 16):
            self.data[j + self.off_vi + i * 16] = vdata[j]
        if abs(x) < tol:
            self.data[self.off_vi + i * 16] = 2   # centre vertex
        else:
            self.data[self.off_vi + i * 16] = 1

    def scan_vertex(self):
        """Build self.vfree: reference counts for all vertices used by faces."""
        for j in range(self.nv):
            self.vfree[j] = 0
        for j in range(self.nf):
            fi = self.off_fc + j * 12
            k1 = self.data[fi + 6] + 256 * self.data[fi + 7]
            k2 = self.data[fi + 8] + 256 * self.data[fi + 9]
            k3 = self.data[fi + 10] + 256 * self.data[fi + 11]
            for kv in (k1, k2, k3):
                k = kv & fmask
                if k < self.nv:
                    self.vfree[k] += 1

    def glue_vertex(self, vtx, fc1, fc2, dist=0.01):
        """Weld vertices in fc1 to the nearest vertex in fc2 within dist.
        Returns the remapped face list fc1."""
        self.update_geo_num()
        print "----------------------------\n\n"
        print vtx[0]
        v1 = []
        v2 = []
        vc = {}
        for f1 in fc1:
            v1.extend(f1)
        for f2 in fc2:
            v2.extend(f2)
        dg = 0
        for u1 in v1:
            dmin = dist + 0
            vc[u1 + 0] = u1 + 0
            for u2 in v2:
                if abs(vtx[u1][0] - vtx[u2][0]) > dmin: continue
                if abs(vtx[u1][1] - vtx[u2][1]) > dmin: continue
                if abs(vtx[u1][2] - vtx[u2][2]) > dmin: continue
                dmin = min([abs(vtx[u1][k] - vtx[u2][k]) for k in (0, 1, 2)])
                vc[u1 + 0] = u2 + 0
                dg += 1
        for i in range(len(fc1)):
            fc1[i][0] = vc[fc1[i][0]]
            fc1[i][1] = vc[fc1[i][1]]
            fc1[i][2] = vc[fc1[i][2]]
        print "weld ", dg
        self.update_geo_num()
        return fc1

    # --- Face operations ---

    def add_face(self):
        """Append a zeroed face slot, increment nf, return new face index."""
        self.update_geo_num()
        i = self.offset
        self.data[i + 2], self.data[i + 3] = to_word(self.nf + 1)
        self.update_geo_num()
        for j in range(12):
            self.data.insert(j + self.off_fc + (self.nf - 1) * 12, 0)
        return self.nf - 1

    def delete_face(self, k):
        """Remove face k from the face table and decrement nf."""
        self.update_geo_num()
        if k >= self.nf:
            raise IndexError
            return
        i = self.offset
        del self.data[self.off_fc + k * 12:self.off_fc + k * 12 + 12]
        self.data[i + 2], self.data[i + 3] = to_word(self.nf - 1)
        self.update_geo_num()

    def set_face_type(self, i, tipo):
        """Set the type/aid byte (offset +4) of face i."""
        self.update_geo_num()
        fi = self.off_fc + i * 12
        self.data[fi + 4] = tipo

    def set_face(self, i, vv1, vv2, vv3, obj_id, mirror, model=0, aid=0):
        """Write all 12 bytes of face i: mirror flags, model, object, vertex indices."""
        self.update_geo_num()
        fi = self.off_fc + i * 12

        # Update reference counts for old vertices
        k1 = self.data[fi + 6] + 256 * self.data[fi + 7]
        k2 = self.data[fi + 8] + 256 * self.data[fi + 9]
        k3 = self.data[fi + 10] + 256 * self.data[fi + 11]
        for k in (k1, k2, k3):
            if k < self.nv:
                self.vfree[k] -= 1
        for k in (k1, k2, k3):
            if k < self.nv:
                self.vfree[k] += 1

        fd = [0 for j in range(12)]

        # Mirror mode -> face flag byte mapping
        MIRROR_FLAGS = {
            0: 16,   # off
            1: 1,    # on
            2: 0,    # fix
            3: 4,    # glass
            4: 2,    # fix2
            5: 8,    # fix3
            6: 16,   # bodyoff
            7: 1,    # bodyon
            8: 0,    # bodyfix
        }
        fd[0] = MIRROR_FLAGS.get(mirror, 1)

        # Zero vertex flag for fixed-mirror modes
        if mirror == 2 or mirror == 8:
            self.data[self.off_vi + 16 * vv1] = 0
            self.data[self.off_vi + 16 * vv2] = 0
            self.data[self.off_vi + 16 * vv3] = 0

        fd[1] = model
        fd[2] = obj_id
        fd[3] = 0 if (mirror == 1 or mirror == 7) else 1   # type flag
        fd[4] = aid + 0   # Collision=2, Shadow=1, Normal=0

        # Smooth group by mirror mode
        if mirror == 3:
            fd[5] = 3
        elif mirror in (6, 7, 8):
            fd[5] = 7
        else:
            fd[5] = 0

        fd[6], fd[7] = to_word(vv1)
        fd[8], fd[9] = to_word(vv2)
        fd[10], fd[11] = to_word(vv3)

        for j in range(12):
            self.data[j + fi] = fd[j]

    def get_triangle_index(self, fi):
        """Return the three vertex indices (k1, k2, k3) for face fi."""
        fii = self.off_fc + fi * 12
        k1 = self.data[fii + 6] + 256 * self.data[fii + 7]
        k2 = self.data[fii + 8] + 256 * self.data[fii + 9]
        k3 = self.data[fii + 10] + 256 * self.data[fii + 11]
        return [k for k in (k1, k2, k3)]

    def face_is_safe(self, fi):
        """Return True if all three vertex indices of face fi are within range."""
        fii = self.off_fc + fi * 12
        k1 = self.data[fii + 6] + 256 * self.data[fii + 7]
        k2 = self.data[fii + 8] + 256 * self.data[fii + 9]
        k3 = self.data[fii + 10] + 256 * self.data[fii + 11]
        if k1 >= self.nv or k2 >= self.nv or k3 >= self.nv:
            return False
        return True

    def delete_faces_col(self, vob_name):
        """Delete all faces belonging to vob_name (any type)."""
        df = 0
        self.update_geo_num()
        oi = self.get_obj_names().index(vob_name)
        for j in range(self.nf - 1, -1, -1):
            if self.data[12 * j + self.off_fc + 2] == oi:
                self.delete_face(j)
                df += 1
        print "faces deleted ", df
        self.update_geo_num()

    def delete_faces_shadow(self, vob_name):
        """Delete shadow faces (aid==1) belonging to vob_name."""
        df = 0
        self.update_geo_num()
        oi = self.get_obj_names().index(vob_name)
        for j in range(self.nf - 1, -1, -1):
            if (self.data[12 * j + self.off_fc + 2] == oi and
                    self.data[12 * j + self.off_fc + 4] == 1):
                self.delete_face(j)
                df += 1
        print "faces deleted ", df
        self.update_geo_num()

    def delete_faces_model(self, vob_name, model=0):
        """Delete normal faces (aid==0) in the given model slot for vob_name."""
        df = 0
        self.update_geo_num()
        oi = self.get_obj_names().index(vob_name)
        for j in range(self.nf - 1, -1, -1):
            if (self.data[12 * j + self.off_fc + 1] == model and
                    self.data[12 * j + self.off_fc + 2] == oi and
                    self.data[12 * j + self.off_fc + 4] == 0):
                self.delete_face(j)
                df += 1
        print "faces deleted ", df
        self.update_geo_num()

    def delete_faces_del(self, vob_name, shadow=0, nomodel=0):
        """Delete faces matching exact (model, object, aid) triple for vob_name."""
        df = 0
        self.update_geo_num()
        oi = self.get_obj_names().index(vob_name)
        for j in range(self.nf - 1, -1, -1):
            if (self.data[12 * j + self.off_fc + 1] == nomodel and
                    self.data[12 * j + self.off_fc + 2] == oi and
                    self.data[12 * j + self.off_fc + 4] == shadow):
                self.delete_face(j)
                df += 1
        print "faces deleted ", df
        self.update_geo_num()

    def delete_faces_norm(self, vob_name, shadow):
        """Delete faces for vob_name matching the given aid/shadow value."""
        df = 0
        self.update_geo_num()
        oi = self.get_obj_names().index(vob_name)
        for j in range(self.nf - 1, -1, -1):
            if (self.data[12 * j + self.off_fc + 2] == oi and
                    self.data[12 * j + self.off_fc + 4] == shadow):
                self.delete_face(j)
                df += 1
        print "faces deleted ", df
        self.update_geo_num()

    # --- Object operations ---

    def get_obj_names(self):
        """Return a list of object names from the current mesh block."""
        lst = []
        for j in range(self.mn):
            oz = self.data[self.off_obj + j * 16:self.off_obj + j * 16 + 16]
            lst.append(toname(oz[4:16]))
        return lst

    def get_obj_names2(self):
        """Return object names without null termination (all bytes decoded)."""
        lst = []
        for j in range(self.mn):
            oz = self.data[self.off_obj + j * 16:self.off_obj + j * 16 + 16]
            lst.append(toname2(oz[4:16]))
        return lst

    def add_object(self, name, rgb, mat_id):
        """Append a new object entry to the object table."""
        self.update_geo_num()
        i = self.offset
        self.nv = self.data[i] + self.data[i + 1] * 256
        self.nf = self.data[i + 2] + self.data[i + 3] * 256
        self.mn = self.data[i + 30]
        self.off_obj = i + 32
        self.off_vi = self.off_obj + 16 * self.mn
        self.off_fc = self.off_vi + 16 * self.nv

        for j in range(16):
            self.data.insert(self.off_vi, 0)
        self.data[i + 30] = self.mn + 1

        self.update_geo_num()
        oid = self.data[i + 30] - 1

        for j in range(min(10, len(name))):
            self.data[self.off_obj + oid * 16 + j + 4] = ord(name[j])

        self.data[self.off_obj + oid * 16] = rgb[0]
        self.data[self.off_obj + oid * 16 + 1] = rgb[1]
        self.data[self.off_obj + oid * 16 + 2] = rgb[2]
        self.data[self.off_obj + oid * 16 + 14], self.data[self.off_obj + oid * 16 + 15] = to_word(mat_id)

    def get_obj_material_id(self, obj_name):
        """Return the material index assigned to obj_name."""
        l = self.get_obj_names()
        j = l.index(obj_name)
        mid = self.data[self.off_obj + j * 16 + 14] + 256 * self.data[self.off_obj + j * 16 + 15]
        return mid

    def get_obj_material(self, obj_name):
        """Return the material name string assigned to obj_name."""
        mid = self.get_obj_material_id(obj_name)
        tf, ti, mt = self.get_mat_info()
        return mt[mid]

    def set_obj_material(self, oid, mat_name):
        """Assign a material by name to the object at index oid."""
        self.update_geo_num()
        mat_id = self.get_mat_info()[2].index(mat_name)
        self.data[self.off_obj + oid * 16 + 14], self.data[self.off_obj + oid * 16 + 15] = to_word(mat_id)

    def get_obj_file_texture(self, name):
        """Return the texture filename string used by object name."""
        texid = self.get_obj_texid(name)
        mtf, mti, mmt = self.get_mat_info()
        tf, ti, mt = self.get_mat_pos()
        vi = ti[0] + 24 * texid
        return mtf[self.data[vi + 18]]

    # --- Face list queries ---

    def get_face_list(self, name, models=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
        """Return indices of normal (aid==0) faces belonging to object name."""
        self.update_geo_num()
        oid = self.get_obj_names()
        obj_id = oid.index(name)
        out = []
        for j in range(self.nf):
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] == obj_id):
                if (self.data[fii + 4] == 0):
                    out.append(j + 0)
        return out

    def get_face_list2(self, name, models=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
        """Return normal face indices for object name using toname2 name table."""
        self.update_geo_num()
        oid = self.get_obj_names2()
        obj_id = oid.index(name)
        out = []
        for j in range(self.nf):
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] == obj_id):
                if (self.data[fii + 4] == 0):
                    out.append(j + 0)
        return out

    def get_face_list_id(self, obj_id, models=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
        """Return normal face indices for a given numeric object id."""
        out = []
        for j in range(self.nf):
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] == obj_id and
                    self.data[fii + 4] == 0 and
                    models.count(self.data[fii + 1]) > 0):
                out.append(j + 0)
        return out

    # --- Geometry helpers ---

    def get_axis_limits(self, name, models, plane):
        """Return (x1, x2, y1, y2) bounding box of object name on the given projection plane."""
        flists = self.get_face_list(name, models)
        u, v = 1, 2
        if plane == 5:
            u, v = 1, 2
        elif plane == 3:
            u, v = 2, 3
        elif plane in (2, 1):
            u, v = 1, 3
        elif plane == 4:
            u, v = 2, 3

        pu = []
        pv = []
        if len(flists) < 1:
            return 0, 0.01, 0, 0.01
        for fi in flists:
            for j in self.get_triangle_index(fi):
                pt = self.get_vertex(j)
                pu.append(pt[u] * 1.0)
                pv.append(pt[v] * 1.0)

        x1, x2, y1, y2 = min(pu), max(pu), min(pv), max(pv)
        return x1, x2, y1, y2

    def get_orient_obj(self, name):
        """Return the orientation/projection byte stored in the material of object name."""
        mat_name = self.get_obj_material(name)
        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        return self.data[vi + 16]

    # --- Normal group computation ---

    def scan_normals(self, obj_id, q=0.404):
        """Assign smooth-group IDs to faces of obj_id based on shared vertices and
        face-normal dot-product threshold q."""
        import math

        def vertex_same(s1, s2):
            """Count how many of s1's vertices appear in s2."""
            k = 0
            k += min(s2.count(s1[0]), 1)
            k += min(s2.count(s1[1]), 1)
            k += min(s2.count(s1[2]), 1)
            return k

        def znormal(v1, v2, v3):
            """Compute unit face normal from three vertex indices."""
            a, x1, y1, z1 = self.get_vertex(v1)
            a, x2, y2, z2 = self.get_vertex(v2)
            a, x3, y3, z3 = self.get_vertex(v3)
            v1 = x2 - x1, y2 - y1, z2 - z1
            v2 = x3 - x2, y3 - y2, z3 - z2
            nx = v1[1] * v2[2] - v1[2] * v2[1]
            ny = v1[2] * v2[0] - v1[0] * v2[2]
            nz = v1[1] * v2[0] - v1[0] * v2[1]
            nn = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nn > 0:
                return nx / nn, ny / nn, nz / nn
            return 1, 0, 0

        def dot(a, b):
            return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

        fvi = []    # vertex index triples per face
        nv = []     # face normals
        viz = []    # adjacency (faces that share a smooth edge)
        valid = 0

        for j in range(self.nf):
            nv.append([])
            fvi.append([])
            viz.append([])
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] != obj_id or
                    self.data[fii + 4] > 0 or
                    self.data[fii + 1] != 4):
                continue
            k1 = self.data[fii + 6] + 256 * self.data[fii + 7]
            k2 = self.data[fii + 8] + 256 * self.data[fii + 9]
            k3 = self.data[fii + 10] + 256 * self.data[fii + 11]
            if k1 > self.nv or k2 > self.nv or k3 > self.nv:
                continue
            nv[j] = znormal(k1, k2, k3)
            fvi[j] = [k1 + 0, k2 + 0, k3 + 0]
            valid += 1

        nviz = 0

        # Build adjacency list: faces that share vertices and have similar normals
        for fi in range(self.nf):
            if fvi[fi] == []:
                continue
            for fj in range(fi + 1, self.nf):
                if fvi[fj] == []:
                    continue
                if vertex_same(fvi[fi], fvi[fj]) > 0:
                    if dot(nv[fi], nv[fj]) > q:
                        viz[fi].append(fj + 0)
                        viz[fj].append(fi + 0)
            if viz[fi] == []:
                nviz += 1

        # Flood-fill connected face groups
        gr = []
        ungr = []
        for j in range(self.nf):
            if fvi[j] != []:
                ungr.append(j + 0)

        print "len :", valid, len(ungr)

        while ungr != []:
            seed = ungr[0]
            tgr = [seed + 0]
            tail = 0
            while tail < len(tgr):
                fi = tgr[tail]
                for fj in ungr:
                    if tgr.count(fj) > 0:
                        continue
                    if fvi[fj] == []:
                        continue
                    if viz[fi].count(fj):
                        tgr.append(fj)
                tail += 1
            gr.append(tgr + [])
            for k in tgr:
                ungr.remove(k)

        # Assign group IDs; increment ID when groups share a boundary vertex
        gid = [1 for i in gr]
        sh = [[] for i in gr]
        for i in range(len(gr)):
            for j in range(i + 1, len(gr)):
                for fi in gr[i]:
                    for fj in gr[j]:
                        if vertex_same(fvi[fi], fvi[fj]) > 0:
                            if gid[i] == gid[j]:
                                gid[j] = gid[i] + 1
                                sh[i].append(j + 0)
                                sh[j].append(i + 0)
                                break
            print "group ", i, " has id", gid[i], "  share ", sh[i]

        # Write group IDs into face data
        for i in range(len(gr)):
            for fi in gr[i]:
                self.data[12 * fi + self.off_fc + 5] = gid[i]

    # --- Material / texture table access ---

    def get_mat_info(self):
        """Return [tex_file_names, tex_id_names, mat_names] lists parsed from file data."""
        face_end = self.off_fc + self.nf * 12
        tex_off = face_end + 0
        out = [[], [], []]
        while self.data[tex_off] == 0:
            tex_off += 1
        num_tex = self.data[tex_off]
        tex_off += 4
        vi = tex_off + 0
        for i in range(num_tex):
            out[0].append(toname(self.data[vi + 4:vi + 20]))
            vi += 20
        ktex_num = self.data[vi] + 256 * self.data[vi + 1]
        vi += 4
        for i in range(ktex_num):
            out[1].append(toname(self.data[vi:vi + 15]))
            vi += 24
        num_mat = self.data[vi] + 0
        vi += 4
        for i in range(num_mat):
            out[2].append(toname(self.data[vi:vi + 15]))
            vi += 44
        return out

    def get_mat_pos(self):
        """Return [[tex_file_off, count], [tex_id_off, count], [mat_off, count]]
        pointing to the raw positions of each table in self.data."""
        face_end = self.off_fc + self.nf * 12
        tex_off = face_end + 0
        out = []
        while self.data[tex_off] == 0:
            tex_off += 1
        num_tex = self.data[tex_off]
        tex_off += 4
        vi = tex_off + 0
        out.append([tex_off + 0, num_tex + 0])
        for i in range(num_tex):
            vi += 20
        ktex_num = self.data[vi] + 256 * self.data[vi + 1]
        vi += 4
        tex_id_off = vi + 0
        out.append([tex_id_off + 0, ktex_num + 0])
        for i in range(ktex_num):
            vi += 24
        num_mat = self.data[vi] + 0
        vi += 4
        out.append([vi + 0, num_mat + 0])
        return out

    def get_material_id(self, mat_name):
        """Return the index of mat_name in the material list (spaces or underscores)."""
        a, b, c = self.get_mat_info()
        for k in range(len(c)):
            if c[k] == mat_name:
                return k
        for k in range(len(c)):
            tmp = c[k].replace(" ", "_")
            if tmp == mat_name:
                return k
        raise NameError

    def get_material_bb(self, mat_name):
        """Return [x1, x2, y1, y2] bounding box stored in the material entry."""
        out = []
        tf, ti, mt = self.get_mat_pos()
        mat = self.get_material_id(mat_name)
        vi = mt[0] + mat * 44
        for k in range(4):
            out.append(fixed(self.data[vi + 20 + 4 * k:vi + 20 + 4 * k + 4]))
        return out

    def set_material_bb(self, mat_name, x1, x2, y1, y2):
        """Write x1, x2, y1, y2 as 16.16 fixed-point into the material entry."""
        def bin_nt(x, y, z, w):
            s = (struct.pack("iiii", x * 65536.0, y * 65536.0, z * 65536.0, w * 65536.0))
            return [ord(i) for i in s]
        tf, ti, mt = self.get_mat_pos()
        mat = self.get_material_id(mat_name)
        vi = mt[0] + mat * 44
        tmp = bin_nt(x1, x2, y1, y2)
        for k in range(16):
            self.data[vi + 20 + k] = tmp[k] + 0

    def add_material(self, base_name):
        """Append a new 44-byte material entry named base_name to the material table."""
        tf, ti, mt = self.get_mat_pos()
        for i in range(44):
            self.data.insert(mt[0] + mt[1] * 44, 0)
        for i in range(min(10, len(base_name))):
            self.data[mt[0] + mt[1] * 44 + i] = ord(base_name[i])
        self.data[mt[0] - 4], self.data[mt[0] - 3] = to_word(mt[1] + 1)

    def set_material(self, mat_name, orientation, tex_id_name):
        """Assign orientation and texture-id-name to an existing material entry."""
        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        btf, bti, bmt = self.get_mat_info()
        tex_id = bti.index(tex_id_name)
        self.data[vi + 16] = orientation
        self.data[vi + 36] = tex_id + 0
        self.data[vi + 40] = tex_id + 0
        print mat_name, "  -> ", tex_id_name

    def fix_material(self, mat_name):
        """Force orientation=2 and rotate=1 on a material (front-texture fix)."""
        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        self.data[vi + 16] = 2
        self.data[vi + 17] = 1

    # --- Texture-id table ---

    def get_obj_texid(self, vob_name):
        """Return the tex-id index used by the material of vob_name."""
        mat_name = self.get_obj_material(vob_name)
        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        return self.data[vi + 36] + 0

    def get_texture_slot_size(self, tex_id):
        """Return (du, dv) pixel dimensions for the given tex-id slot."""
        tf, ti, mt = self.get_mat_pos()
        vi = ti[0] + tex_id * 24
        print ss(range(24))
        print ss(self.data[vi:vi + 24])
        duv = float(self.data[vi + 20]), float(self.data[vi + 21])
        return duv[0], duv[1]

    def new_tex_id(self, tname):
        """Insert a new 24-byte tex-id slot named tname and return its index."""
        tf, ti, mt = self.get_mat_pos()
        for j in range(24):
            self.data.insert(ti[0] + 24 * ti[1], 0)
        for j in range(min(12, len(tname))):
            self.data[ti[0] + 24 * ti[1] + j] = ord(tname[j])
        vi = ti[0] + 0
        vi -= 4
        self.data[vi] += 1
        self.update_geo_num()
        return self.data[vi] - 1

    def set_tex_id(self, sp1, tname, sh, tex_file_id, u, v, du, dv, orie=0):
        """Write tex-id slot fields: shininess, orientation, file ref, UV rect, transparency."""
        tf, ti, mt = self.get_mat_info()
        if tname in ti:
            tid = ti.index(tname)
        else:
            tid = self.new_tex_id(tname)
        tf, ti, mt = self.get_mat_pos()
        vi = ti[0] + tid * 24
        self.data[vi + 16] = sh           # sky reflection / shininess
        self.data[vi + 17] = orie         # rotation flag
        self.data[vi + 18] = tex_file_id  # texture file index
        self.data[vi + 19] = sp1 + 0      # transparency: 0=opaque, 1=full, 2=glass, 3=light
        self.data[vi + 20] = du + 0
        self.data[vi + 21] = dv + 0
        self.data[vi + 22] = u + 0
        self.data[vi + 23] = v + 0
        return tid

    def add_texture_file(self, file_name):
        """Register a texture filename; return existing index if already present."""
        tf, ti, mt = self.get_mat_pos()
        vi = tf[0]
        for j in range(tf[1]):
            tex_nome = toname(self.data[j * 20 + vi + 4:j * 20 + vi + 20])
            if tex_nome == file_name:
                return j
        # Append new entry
        tf, ti, mt = self.get_mat_pos()
        self.data[tf[0] - 4], self.data[tf[0] - 3] = to_word(tf[1] + 1)
        fp = [0 for i in range(20)]
        for i in range(min(len(file_name), 15)):
            fp[i + 4] = ord(file_name[i])
        for k in range(20):
            self.data.insert(tf[0] + tf[1] * 20 + k, fp[k])
        self.update_geo_num()
        return tf[1]

    # --- UV / template rendering ---

    def get_xyzuf_list(self, obj_name, model, kside=0):
        """Return list of [x, y, z, u, v] tuples for all visible faces of obj_name in model."""
        xyzuv = []
        size = 1.0
        dss = size / 64.0
        obj_id = self.get_obj_names().index(obj_name)
        mat_name = self.get_obj_material(obj_name)
        x1, x2, y1, y2 = self.get_material_bb(mat_name)
        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        pori = self.data[vi + 16]
        tex_id = self.data[vi + 36]
        vi = ti[0] + tex_id * 24
        duv = float(self.data[vi + 20]), float(self.data[vi + 21])
        uv = float(self.data[vi + 22]), float(self.data[vi + 23])
        uflag = self.data[vi + 17]

        def get_uv(x, y, uf=1):
            dx = (x - x1) / float(x2 - x1)
            dy = (y - y1) / float(y2 - y1)
            if uf == 0:
                ku = (dx) * duv[0] + uv[0]
                kv = 64 - (dy * duv[1] + uv[1])
            elif uf == 1:
                ku = 64 - (dy * duv[1] + uv[1])
                kv = 64 - (dx * duv[0] + uv[0])
            elif uf == 2:
                ku = dx * duv[0] + uv[0]
                kv = 64 - (dy * duv[1] + uv[1])
            elif uf == 3:
                ku = dx * duv[0] + uv[0]
                kv = dy * duv[1] + uv[1]
                kv, ku = ku, kv
            elif uf == 4:
                ku = 64 - (dx * duv[0] + uv[0])
                kv = 64 - (dy * duv[1] + uv[1])
            else:
                ku = dx * duv[0] + uv[0]
                kv = dy * duv[1] + uv[1]
            return ku * dss, kv * dss

        sside = 1.0
        xflip = 1.0
        if kside > 0:
            sside = -1.0

        u_ax, v_ax = 1, 2
        if pori == 5:   u_ax, v_ax = 1, 2
        elif pori == 3: u_ax, v_ax = 2, 3
        elif pori in (2, 1): u_ax, v_ax = 1, 3
        elif pori == 4: u_ax, v_ax = 2, 3

        for j in range(self.nf):
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] != obj_id or
                    self.data[fii + 4] > 0 or
                    self.data[fii + 1] != model):
                continue
            if self.data[fii] != 1 and sside < 0:
                continue
            xflip = -1.0 if self.data[fii] == 16 else 1.0
            k1 = self.data[fii + 6] + 256 * self.data[fii + 7]
            k2 = self.data[fii + 8] + 256 * self.data[fii + 9]
            k3 = self.data[fii + 10] + 256 * self.data[fii + 11]
            v1 = self.get_vertex(k1)
            v2 = self.get_vertex(k2)
            v3 = self.get_vertex(k3)
            fv1, fv2, fv3 = [[vk[0], sside * xflip * vk[1], vk[2], vk[3]]
                              for vk in (v1, v2, v3)]
            for vj in (fv1, fv2, fv3):
                puv = get_uv(vj[u_ax], vj[v_ax], uflag)
                xyzuv.append([vj[1], vj[2], vj[3], puv[0], puv[1]])

        return xyzuv

    def render_template(self, obj_id, model, image_name, size=4096, kside=0):
        """Render a UV-unwrap wireframe of obj_id/model onto image_name (PNG or JPG)."""
        jpg = ".jpg"
        if os.path.exists(image_name):
            img = Image.open(image_name)
        else:
            if jpg in image_name:
                img = Image.new("RGB", [size, size])
            else:
                img = Image.new("RGBA", [size, size], (255, 255, 255, 0))

        draw = ImageDraw.Draw(img)
        obj_name = self.get_obj_names()[obj_id]
        dss = size / 64.0

        mat_name = self.get_obj_material(obj_name)
        x1, x2, y1, y2 = self.get_material_bb(mat_name)
        print obj_name
        print x1, y1, x2, y2

        mat = self.get_material_id(mat_name)
        tf, ti, mt = self.get_mat_pos()
        vi = mt[0] + mat * 44
        pori = self.data[vi + 16]
        tex_id = self.data[vi + 36]
        vi = ti[0] + tex_id * 24
        duv = float(self.data[vi + 20]), float(self.data[vi + 21])
        uv = float(self.data[vi + 22]), float(self.data[vi + 23])
        uflag = self.data[vi + 17]

        def get_uv(x, y, uf=1):
            dx = (x - x1) / float(x2 - x1)
            dy = (y - y1) / float(y2 - y1)
            if uf == 0:
                ku = (dx) * duv[0] + uv[0]
                kv = 64 - (dy * duv[1] + uv[1])
            elif uf == 1:
                ku = 64 - (dy * duv[1] + uv[1])
                kv = 64 - (dx * duv[0] + uv[0])
            elif uf == 2:
                ku = dx * duv[0] + uv[0]
                kv = 64 - (dy * duv[1] + uv[1])
            elif uf == 3:
                ku = dx * duv[0] + uv[0]
                kv = dy * duv[1] + uv[1]
                kv, ku = ku, kv
            elif uf == 4:
                ku = 64 - (dx * duv[0] + uv[0])
                kv = 64 - (dy * duv[1] + uv[1])
            else:
                ku = dx * duv[0] + uv[0]
                kv = dy * duv[1] + uv[1]
            return ku * dss, kv * dss

        sside = 1.0
        xflip = 1.0
        if kside > 0:
            sside = -1.0

        u_ax, v_ax = 1, 2
        if pori == 5:   u_ax, v_ax = 1, 2
        elif pori == 3: u_ax, v_ax = 2, 3
        elif pori in (2, 1): u_ax, v_ax = 1, 3
        elif pori == 4: u_ax, v_ax = 2, 3

        for j in range(self.nf):
            fii = self.off_fc + j * 12
            if (self.data[fii + 2] != obj_id or
                    self.data[fii + 4] > 0 or
                    self.data[fii + 1] != model):
                continue
            if self.data[fii] != 1 and sside < 0:
                continue
            xflip = -1.0 if self.data[fii] == 16 else 1.0
            k1 = self.data[fii + 6] + 256 * self.data[fii + 7]
            k2 = self.data[fii + 8] + 256 * self.data[fii + 9]
            k3 = self.data[fii + 10] + 256 * self.data[fii + 11]
            v1 = self.get_vertex(k1)
            v2 = self.get_vertex(k2)
            v3 = self.get_vertex(k3)
            fv1, fv2, fv3 = [[vk[0], sside * xflip * vk[1], vk[2], vk[3]]
                              for vk in (v1, v2, v3)]
            puv = [get_uv(vj[u_ax], vj[v_ax], uflag) for vj in (fv1, fv2, fv3)]
            if jpg in image_name:
                draw.polygon(puv[0] + puv[1] + puv[2], fill=(155, 155, 155))
            draw.line(puv[0] + puv[1], fill=(0, 0, 0))
            draw.line(puv[1] + puv[2], fill=(0, 0, 0))
            draw.line(puv[2] + puv[0], fill=(0, 0, 0))

        # Draw bounding-box outline
        draw.line(get_uv(x1, y1, uflag) + get_uv(x1, y2, uflag), fill=(0, 0, 0))
        draw.line(get_uv(x1, y2, uflag) + get_uv(x2, y2, uflag), fill=(0, 0, 0))
        draw.line(get_uv(x2, y2, uflag) + get_uv(x2, y1, uflag), fill=(0, 0, 0))
        draw.line(get_uv(x2, y1, uflag) + get_uv(x1, y1, uflag), fill=(0, 0, 0))

        del draw
        if jpg in image_name:
            img.save(image_name)
        else:
            img.save(image_name, 'PNG')
        del img

    # --- OBJ export ---

    def dump_mesh_as_string(self):
        """Export current mesh to a list of OBJ-format lines (vertices + faces by object/model)."""
        so = []
        self.update_geo_num()
        for i in range(self.nv):
            vi = self.off_vi + i * 16
            a, x, y, z = read_axyz(self.data[vi:vi + 16])
            so.append("v  %f %f %f \n" % (x, y, z))
        for name in self.get_obj_names():
            for model in range(0, 9):
                fl = self.get_face_list(name, [model + 0])
                if len(fl) > 0:
                    so.append("g m%i_%s \n" % (model, name))
                    for fj in fl:
                        if self.data[fj * 12 + self.off_fc + 1] != model:
                            continue
                        v1, v2, v3 = self.get_triangle_index(fj)
                        v1 = v1 & fmask
                        v2 = v2 & fmask
                        v3 = v3 & fmask
                        if v1 < self.nv and v2 < self.nv and v3 < self.nv:
                            so.append("f %i %i %i \n" % (v1 + 1, v2 + 1, v3 + 1))
        return so

    def dump_mesh_as_string2(self):
        """Like dump_mesh_as_string but uses the toname2 object name table."""
        so = []
        self.update_geo_num()
        for i in range(self.nv):
            vi = self.off_vi + i * 16
            a, x, y, z = read_axyz(self.data[vi:vi + 16])
            so.append("v  %f %f %f \n" % (x, y, z))
        for name in self.get_obj_names2():
            for model in range(0, 9):
                fl = self.get_face_list2(name, [model + 0])
                if len(fl) > 0:
                    so.append("g m%i_%s \n" % (model, name))
                    for fj in fl:
                        if self.data[fj * 12 + self.off_fc + 1] != model:
                            continue
                        v1, v2, v3 = self.get_triangle_index(fj)
                        v1 = v1 & fmask
                        v2 = v2 & fmask
                        v3 = v3 & fmask
                        if v1 < self.nv and v2 < self.nv and v3 < self.nv:
                            so.append("f %i %i %i \n" % (v1 + 1, v2 + 1, v3 + 1))
        return so
