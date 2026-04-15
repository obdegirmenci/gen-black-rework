# objread.py
# Parses .obj files and returns vertex/face/UV data as Python structures.

import math


def znormal(p1, p2, p3):
    # Compute normalized face normal from three vertex positions
    d1 = p3[0]-p1[0], p3[1]-p1[1], p3[2]-p1[2]
    d2 = p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]
    x = d1[1]*d2[2] - d1[2]*d2[1]
    y = d1[0]*d2[2] - d1[2]*d2[0]
    z = d1[1]*d2[0] - d1[0]*d2[1]
    nnz = math.sqrt(x*x + y*y + z*z)
    if nnz == 0:
        nnz = 1.0
    return x/nnz, y/nnz, z/nnz


def similar_v(xyz1, xyz2, pr=0.01):
    # Return True if two vertices are within tolerance pr on all axes
    if abs(xyz1[0]-xyz2[0]) > pr: return False
    if abs(xyz1[1]-xyz2[1]) > pr: return False
    if abs(xyz1[2]-xyz2[2]) > pr: return False
    return True


def vo_replace_get(vbase, vmod, bin):
    # Print vertex differences between two OBJ files
    v1 = read_obj(vbase)
    v2 = read_obj(vmod)
    for i in range(len(v1)):
        if similar_v(v1[i], v2[i]) == False:
            print v1[i], "->", v2[i]
    print v1


def _join_continuation_lines(lns):
    # Merge lines ending with backslash into single logical lines
    i = 0
    while i < len(lns):
        if len(lns[i]) > 3 and lns[i][-2] == "\\":
            lns[i] = lns[i][0:-2] + lns[i+1]
            del lns[i+1]
            i -= 1
        i += 1
    return lns


def read_obj(fname):
    # Read only vertex positions from an OBJ file; returns list of (x,y,z)
    f = open(fname, "r")
    lns = _join_continuation_lines(f.readlines())
    f.close()
    vtx = []
    for l in lns:
        if l[0] != 'v':
            continue
        ls = l.split()
        if len(ls) == 0:
            continue
        if ls[0] == 'v':
            v, x, y, z = l.split()
            vtx.append((float(x), float(y), float(z)))
    print "read", len(vtx), "vertices"
    return vtx


def read_obj_faces_names(fname):
    # Parse OBJ file; returns (vertices, face_groups, uv_groups)
    # face_groups and uv_groups are dicts keyed by group name
    f = open(fname, "r")
    lns = _join_continuation_lines(f.readlines())
    f.close()
    print len(lns)

    vtx = []
    uv  = []

    gr_atc = "DEFAULT"
    gr     = {gr_atc: []}   # face index triangles per group
    gr_uv  = {gr_atc: []}   # UV triangles per group

    for l in lns:
        ls = l.split()
        if len(ls) == 0:
            continue

        if ls[0] == 'v':
            # Vertex position
            v, x, y, z = l.split()
            vtx.append((float(x), float(y), float(z)))

        elif ls[0] == 'vt':
            # Texture coordinate
            v, x, y, z = l.split()
            uv.append((float(x), float(y), float(z)))

        elif ls[0] == 'g':
            # Group (object) declaration
            if len(ls) == 1:
                print "Object with no name found"
                ls.append("DEFAULT")
            gr_atc = ls[1]
            gr[gr_atc]    = []
            gr_uv[gr_atc] = []

        elif ls[0] == 'f':
            # Face: triangulate polygons
            fcs = ls[1:]

            if len(uv) > 0:
                # Extract UV indices if present
                if len(fcs[0].split("/")) > 1:
                    uvi = [int(k.split("/")[1])-1 for k in fcs]
                else:
                    uvi = (1, 1, 1, 1, 1, 1)
                for i in range(2, len(uvi)):
                    gr_uv[gr_atc].append([uv[uvi[0]], uv[uvi[i-1]], uv[uvi[i]]])

            vi = [int(k.split("/")[0])-1 for k in fcs]
            for i in range(2, len(vi)):
                gr[gr_atc].append([vi[0], vi[i-1], vi[i]])

    return vtx, gr, gr_uv


def read_obj_faces_names_x(fname):
    # Convenience wrapper: returns only vertices and faces (no normals)
    a, b, c = read_obj_faces_normals(fname)
    return a, b


def read_obj_faces_normals(fname):
    # Parse OBJ file with normals; returns (vertices, faces, face_normals, uv_faces)
    f = open(fname, "r")
    lns = _join_continuation_lines(f.readlines())
    f.close()
    print len(lns)

    vtx = []
    vnn = []   # vertex normals
    uv  = []
    fc  = []   # face index list
    vfn = []   # computed face normals
    fuv = []   # face UV list

    for l in lns:
        ls = l.split()
        if len(ls) == 0:
            continue

        if ls[0] == 'v':
            # Vertex position
            v, x, y, z = l.split()
            vtx.append((float(x), float(y), float(z)))

        elif ls[0] == 'vt':
            # Texture coordinate
            v, x, y, z = l.split()
            uv.append((float(x), float(y), float(z)))

        elif ls[0] == 'vn':
            # Vertex normal (normalized)
            v, x, y, z = l.split()
            x, y, z = float(x), float(y), float(z)
            normz = math.sqrt(x*x + y*y + z*z)
            if normz == 0:
                vnn.append((0, 0, 1))
            vnn.append((x/normz, y/normz, z/normz))

        elif ls[0] == 'f':
            # Face: triangulate polygons
            fcs = ls[1:]
            vi  = [int(k.split("/")[0])-1 for k in fcs]

            if len(uv) > 0:
                uvi = [int(k.split("/")[1])-1 for k in fcs]
                for i in range(2, len(uvi)):
                    fuv.append([uv[0], uv[i-1], uv[i]])

            for i in range(2, len(vi)):
                fc.append([vi[0], vi[i-1], vi[i]])
                vfn.append(znormal(vtx[vi[0]], vtx[vi[i-1]], vtx[vi[i]]))

    return vtx, fc, vfn, fuv
