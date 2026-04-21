# gen_black.py
# Command processor that reads a script file and applies mesh operations (add, delete, texture, mirror) to a .vob file using the blackwood API.

import os
import blackwood
import objread


def get_optimized_vertex(vlist, tol=0.001):
    # Returns an identity vertex index map (optimization pass is disabled)
    n = len(vlist)
    vl = [i for i in range(n)]
    return vl


def msg(s):
    print s


def process(file_command, file_input):
    # Open the command script for reading
    lns = open(file_command, "r")

    # OBJ geometry buffers: vertices, faces, UV coords
    o_vt, obj, obj_uv = {}, {}, {}

    # Vertex remapping table (maps OBJ vertex index -> VOB vertex index)
    vtab = {}

    # Load the VOB (Blackwood binary) file
    vob = blackwood.blk_file()
    vob.load(file_input)

    mirror = 1   # Mirror mode: 1 = on
    imodel = 0   # Active model index
    vop = []     # Optimized vertex index map

    # Print all object names and their associated texture files
    print "OBJ NAMES"
    for k in vob.get_obj_names():
        print k, " " * (20 - len(k)), vob.get_obj_file_texture(k)

    enable = True

    for l in lns:
        li = l.split()
        if len(li) == 0:
            continue
        if li[0] == "#":
            continue

        cmd = li[0].upper()
        print "___" * 6
        print ">", l

        # Toggle command processing on/off
        if cmd == "ENABLE":
            enable = True
        if cmd == "DISABLE":
            enable = False

        if enable == False:
            continue

        # --- LOAD: read an OBJ file and build vertex/face buffers ---
        if cmd == "LOAD":
            file_obj = li[1]
            o_vt, obj, obj_uv = objread.read_obj_faces_names(file_obj)
            vtab = {}
            for i in range(len(o_vt)):
                vtab[i] = None
            vop = get_optimized_vertex(o_vt)

        # --- MIRROR: set the mirror/body render mode ---
        if cmd == "MIRROR":
            mode = li[1].upper()
            mirror_map = {
                "ON":      (1, "MIRROR ON"),
                "OFF":     (0, "MIRROR OFF"),
                "FIX":     (2, "MIRROR FIX"),
                "GLASS":   (3, "MIRROR GLASS"),
                "FIX2":    (4, "MIRROR FIX2"),
                "FIX3":    (5, "MIRROR FIX3"),
                "BODYOFF": (6, "MIRROR BODY OFF"),
                "BODYON":  (7, "MIRROR BODY ON"),
                "BODYFIX": (8, "MIRROR BODY FIX"),
            }
            if mode in mirror_map:
                mirror, label = mirror_map[mode]
                msg(label)

        # --- POSITION: set position/mirror mode by shorthand key ---
        if cmd == "POSITION":
            pos = li[1].upper()
            if pos == "M":
                msg("MIRROR ON")
                mirror = 1
            if pos == "I":
                msg("DRIVER POSITION")
                mirror = 0
            if pos == "0":
                msg("POSITION 0")
                mirror = 2

        # --- GLUE: merge vertices of two OBJ parts within a distance threshold ---
        if cmd == "GLUE":
            obj_name  = li[1]
            obj2_name = li[2]
            dist      = float(li[3])
            print "clean model", obj_name, obj2_name
            o_fc1 = obj[obj_name]
            o_fc2 = obj[obj2_name]
            obj[obj_name] = vob.glue_vertex(o_vt, o_fc1, o_fc2, dist)

        # --- MESH: switch active mesh ID and reset vertex remap table ---
        if cmd == "MESH":
            mid = int(li[1])
            msg("set mesh as %i" % mid)
            vob.set_mid(mid)
            vtab = {}
            for i in range(len(o_vt)):
                vtab[i] = None
            print "OBJ NAMES"
            for k in vob.get_obj_names():
                print k

        # --- SUBMESHES_COUNT: set mesh ID to 1 and define child submesh count ---
        if cmd == "SUBMESHES_COUNT":
            sub = int(li[1])
            msg("sub mesh count %i" % sub)
            vob.set_mid(1)
            vob.set_child(sub)

        # --- MIRROR_STATE: set per-object mirror state flags ---
        if cmd == "MIRROR_STATE":
            m_s = li[1].upper()
            if m_s == "MIRROR_ONLY":
                msg("MIRROR ONLY")
                mirror_s = 227
            if m_s == "MIRROR_FIX_POSSIBLE":
                msg("MIRROR FIX POSSIBLE")
                mirror_s = 226
            vob.set_mirror_state(mirror_s)

        # --- MESH_TYPE: classify mesh role (main body, caliper, wheel, etc.) ---
        if cmd == "MESH_TYPE":
            m_t = li[1].upper()
            mesh_type_map = {
                "MAIN":          (0,  "MAIN MESH"),
                "CALIPER":       (1,  "BRAKE CALIPER"),
                "WHEEL":         (2,  "STEERING WHEEL"),
                "DEFAULT":       (3,  "DEFAULT MESH"),
                "ALWAYS_VISIBLE":(5,  "ALWAYS VISIBLE, EVEN IN F MODE"),
                "MIRROR":        (10, "CENTRAL REARVIEW MIRROR"),
            }
            if m_t in mesh_type_map:
                mesh_t, label = mesh_type_map[m_t]
                msg(label)
                vob.set_mesh_type(mesh_t)

        # --- MESH_FIX: enable or disable mirror-fix behavior for this mesh ---
        if cmd == "MESH_FIX":
            m_f = li[1].upper()
            if m_f == "ON":
                msg("MIRROR FIX WORKS")
                mesh_f = 1
            if m_f == "OFF":
                msg("MIRROR FIX NOT WORK")
                mesh_f = 2
            vob.set_mesh_fix(mesh_f)

        # --- EXIT: stop processing the command file ---
        if cmd == "EXIT":
            break

        # --- DELETE_ALL / CLEAN_ALL: remove all non-base faces from every object ---
        if cmd == "DELETE_ALL" or cmd == "CLEAN_ALL":
            g = vob.get_obj_names()
            for ij in range(vob.mn):
                msg("Delete %s" % g[ij])
                for j in range(vob.nf - 1, -1, -1):
                    fii = vob.off_fc + j * 12
                    # MESH 14 - handle object delete fix
                    if (vob.data[fii + 2] == ij) or (vob.data[fii + 4] == 0):
                        vob.delete_face(j)

        # --- MODEL: set the active model index for subsequent ADD/DELETE commands ---
        if cmd == "MODEL":
            imodel = int(li[1])

        # --- DELETE_COL / CLEAN_COL: remove collision faces from a named object ---
        if cmd == "DELETE_COL" or cmd == "CLEAN_COL":
            vob_name = li[1]
            g = vob.get_obj_names()
            if not (vob_name in g):
                msg("PART %s NOT FOUND " % vob_name)
            else:
                vob.delete_faces_col(vob_name)

        # --- DELETE_SHADOW / CLEAN_SHADOW: remove shadow faces from a named object ---
        if cmd == "DELETE_SHADOW" or cmd == "CLEAN_SHADOW":
            vob_name = li[1]
            g = vob.get_obj_names()
            if not (vob_name in g):
                msg("PART %s NOT FOUND " % vob_name)
            else:
                vob.delete_faces_shadow(vob_name)

        # --- DELETE_MODEL / CLEAN_MODEL / DEL_M: remove model faces from a named object ---
        if cmd == "DELETE_MODEL" or cmd == "CLEAN_MODEL" or cmd == "DEL_M":
            vob_name = li[1]
            g = vob.get_obj_names()
            if not (vob_name in g):
                msg("PART %s NOT FOUND " % vob_name)
            else:
                vob.delete_faces_model(vob_name, model=imodel)

        # --- DEL: delete faces with optional shadow/model filter flags ---
        if cmd == "DEL":
            vob_name = li[1]
            shadow   = int(li[2])
            nomodel  = int(li[3])
            g = vob.get_obj_names()
            if not (vob_name in g):
                msg("PART %s NOT FOUND " % vob_name)
            else:
                if nomodel == -1:
                    vob.delete_faces_norm(vob_name, shadow)
                else:
                    vob.delete_faces_del(vob_name, shadow, nomodel)

        # --- DELETE / CLEAN: remove all faces from a named object ---
        if cmd == "DELETE" or cmd == "CLEAN":
            vob_name = li[1]
            df = 0
            g = vob.get_obj_names()
            if not (vob_name in g):
                msg("PART %s NOT FOUND " % vob_name)
            else:
                flist = vob.get_face_list(vob_name)
                flist.sort()
                print "will delete ", len(flist)
                msg("Delete %s" % vob_name)
                for i in range(len(flist) - 1, -1, -1):
                    vob.delete_face(flist[i])
                    df += 1
                msg("%i faces deleted " % df)

        # --- DELETE_BLANK: remove all faces from a unnamed object ---
        if cmd == "DELETE_BLANK":
            df = 0
            g = vob.get_obj_names()
            blank_ids = [i for i, n in enumerate(g) if n.strip() == ""]
            if not blank_ids:
                msg("No blank-named objects found")
            else:
                for oid in blank_ids:
                    msg("Deleting blank object at index %i" % oid)
                    for j in range(vob.nf - 1, -1, -1):
                        fii = vob.off_fc + j * 12
                        if vob.data[fii + 2] == oid:
                            vob.delete_face(j)
                            df += 1
                msg("%i faces deleted" % df)

        # --- ADD: insert OBJ faces into a VOB object at model layer 0 ---
        if cmd == "ADD":
            vob_name = li[1]
            obj_name = li[2]
            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            o_fc = obj[obj_name]
            oid  = gl.index(vob_name)
            recl = 0
            fnew = 0
            msg("ADD in %s  the contents of %s" % (vob_name, obj_name))
            vob.scan_vertex()

            for fi in range(len(o_fc)):
                ffj = vob.add_face()
                vls = []  # Collect 3 vertex indices for this face

                for vk in [o_fc[fi][0], o_fc[fi][1], o_fc[fi][2]]:
                    vo = vop[vk]

                    # Try to reuse a free existing VOB vertex slot
                    if vtab[vo] is None:
                        for vi in range(vob.nv):
                            if vob.vfree[vi] == 0:
                                vob.vfree[vi] += 1
                                vtab[vo] = vi
                                recl += 1
                                break

                    # Allocate a new vertex if none was reused
                    if vtab[vo] is None:
                        vvk = vob.add_vertex()
                        vob.vfree[vvk] = 1
                        fnew += 1
                        vtab[vo] = vvk

                    vob.set_vertex(vtab[vo], o_vt[vo][0], o_vt[vo][1], o_vt[vo][2])
                    vls.append(vtab[vo])

                vob.set_face(ffj, vls[0], vls[1], vls[2], oid, mirror, model=imodel)

            vob.scan_normals(oid)
            msg("reclicled %i vertex, new %i vertex" % (recl, fnew))

        # --- ADD_LOD1 / ADD_SHADOW: insert OBJ faces as LOD1/shadow layer (aid=1) ---
        if cmd == "ADD_LOD1" or cmd == "ADD_SHADOW":
            vob_name = li[1]
            obj_name = li[2]
            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            o_fc = obj[obj_name]
            oid  = gl.index(vob_name)
            recl = 0
            fnew = 0
            msg("ADD in %s  the contents of %s" % (vob_name, obj_name))
            vob.scan_vertex()

            for fi in range(len(o_fc)):
                ffj = vob.add_face()
                vls = []

                for vk in [o_fc[fi][0], o_fc[fi][1], o_fc[fi][2]]:
                    vo = vop[vk]

                    if vtab[vo] is None:
                        for vi in range(vob.nv):
                            if vob.vfree[vi] == 0:
                                vob.vfree[vi] += 1
                                vtab[vo] = vi
                                recl += 1
                                break

                    if vtab[vo] is None:
                        vvk = vob.add_vertex()
                        vob.vfree[vvk] = 1
                        fnew += 1
                        vtab[vo] = vvk

                    vob.set_vertex(vtab[vo], o_vt[vo][0], o_vt[vo][1], o_vt[vo][2])
                    vls.append(vtab[vo])

                vob.set_face(ffj, vls[0], vls[1], vls[2], oid, mirror, model=imodel, aid=1)

            vob.scan_normals(oid)
            msg("reclicled %i vertex, new %i vertex" % (recl, fnew))

        # --- ADD_LOD2 / ADD_COL: insert OBJ faces as LOD2/collision layer (aid=2) ---
        if cmd == "ADD_LOD2" or cmd == "ADD_COL":
            vob_name = li[1]
            obj_name = li[2]
            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            o_fc = obj[obj_name]
            oid  = gl.index(vob_name)
            recl = 0
            fnew = 0
            msg("ADD in %s  the contents of %s" % (vob_name, obj_name))
            vob.scan_vertex()

            for fi in range(len(o_fc)):
                ffj = vob.add_face()
                vls = []

                for vk in [o_fc[fi][0], o_fc[fi][1], o_fc[fi][2]]:
                    vo = vop[vk]

                    if vtab[vo] is None:
                        for vi in range(vob.nv):
                            if vob.vfree[vi] == 0:
                                vob.vfree[vi] += 1
                                vtab[vo] = vi
                                recl += 1
                                break

                    if vtab[vo] is None:
                        vvk = vob.add_vertex()
                        vob.vfree[vvk] = 1
                        fnew += 1
                        vtab[vo] = vvk

                    vob.set_vertex(vtab[vo], o_vt[vo][0], o_vt[vo][1], o_vt[vo][2])
                    vls.append(vtab[vo])

                vob.set_face(ffj, vls[0], vls[1], vls[2], oid, mirror, model=imodel, aid=2)

            vob.scan_normals(oid)
            msg("reclicled %i vertex, new %i vertex" % (recl, fnew))

        # --- ADJUST_TEXTURE_SIZE: fit texture BB to object geometry at a given aspect ratio ---
        if cmd == "ADJUST_TEXTURE_SIZE":
            vob_name = li[1]
            rt       = float(li[2])
            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError

            morr = vob.get_orient_obj(vob_name)
            txid = vob.get_obj_texid(vob_name)
            du, dv = vob.get_texture_slot_size(txid)
            print du, dv

            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            print "original limits", x1, x2, y1, y2

            # Determine whether to extend symmetrically around the origin
            if x1 * x2 > 0:
                extend = False
            else:
                extend = True

            pori = vob.get_orient_obj(vob_name)
            x1, x2, y1, y2 = vob.get_axis_limits(vob_name, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], pori)
            print "new limits", x1, x2, y1, y2

            if extend and morr != 3:
                x2 = max(abs(x1), abs(x2))
                x1 = -x2

            dx = abs(x2 - x1)
            dy = abs(y2 - y1)

            # Scale target ratio by texture slot aspect ratio
            brt = du / float(dv)
            rt  = rt * brt

            dyi = dy
            dxi = dx

            # Expand dimensions to reach the target aspect ratio
            while dxi / dyi > rt:
                dyi = dyi * 1.05
            while dxi / dyi < rt:
                dxi = dxi * 1.05

            sx = 1.0
            sy = 1.0
            if dx > 0 or dy > 0:
                sx = dxi / dx
                sy = dyi / dy

            xm = 0.5 * (x1 + x2)
            ym = 0.5 * (y1 + y2)

            if extend:
                px1 = xm - dxi / 2.0
                px2 = xm + dxi / 2.0
                py1 = ym - dyi / 2.0
                py2 = ym + dyi / 2.0
            else:
                x1, x2, y1, y2 = vob.get_material_bb(mat_name)
                px1 = x1
                px2 = x1 + dxi
                py1 = y1
                py2 = y1 + dyi

            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            print x1, x2, y1, y2, " ->  ", px1, px2, py1, py2
            vob.set_material_bb(mat_name, px1, px2, py1, py2)

        # --- FRONT_TEXTURE_FIX: flip horizontal UV bounds and apply material fix ---
        if cmd == "FRONT_TEXTURE_FIX":
            vob_name = li[1]
            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            vob.set_material_bb(mat_name, x2, x1, y1, y2)
            vob.fix_material(mat_name)

        # --- CHECK_BB: print current bounding box of a material ---
        if cmd == "CHECK_BB":
            vob_name = li[1]
            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            print x1, x2, y1, y2

        # --- SET_BB: manually assign a bounding box to a material ---
        if cmd == "SET_BB":
            vob_name = li[1]
            px1 = float(li[2])
            px2 = float(li[3])
            py1 = float(li[4])
            py2 = float(li[5])
            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            print x1, x2, y1, y2, " ->  ", px1, px2, py1, py2
            vob.set_material_bb(mat_name, px1, px2, py1, py2)

        # --- SCALE_TEXTURE: uniformly scale texture UV bounding box ---
        if cmd == "SCALE_TEXTURE":
            vob_name = li[1]
            scale    = float(li[2])
            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)
            px1 = x1 / scale
            px2 = x2 / scale
            py1 = y1 / scale
            py2 = y2 / scale
            print x1, x2, y1, y2, " ->  ", px1, px2, py1, py2
            vob.set_material_bb(mat_name, px1, px2, py1, py2)

        # --- MOVE_TEXTURE: translate texture UV bounding box horizontally and vertically ---
        if cmd == "MOVE_TEXTURE":
            vob_name = li[1]
            side     = float(li[2])
            updown   = float(li[3])
            mat_name = vob.get_obj_material(vob_name)
            x1, x2, y1, y2 = vob.get_material_bb(mat_name)

            # Positive side shifts left; negative side shifts right
            if side < 0:
                px1 = x1 + side
                px2 = x2 + side
            else:
                px1 = x1 - side
                px2 = x2 - side

            # Positive updown shifts down; negative updown shifts up
            if updown < 0:
                py1 = y1 + updown
                py2 = y2 + updown
            else:
                py1 = y1 - updown
                py2 = y2 - updown

            print x1, x2, y1, y2, " ->  ", px1, px2, py1, py2
            vob.set_material_bb(mat_name, px1, px2, py1, py2)

        # --- RENDER_TEMPLATE: render both sides of an object from a template file ---
        if cmd == "RENDER_TEMPLATE":
            vob_name = li[1]
            file_temp = li[2]
            s_models  = li[3:]
            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            oid = gl.index(vob_name)
            for im in s_models:
                vob.render_template(oid, int(im), file_temp)
                vob.render_template(oid, int(im), file_temp, kside=1)

        # --- SET_TEXTURE_SLOT3: assign a texture slot to a single object (simple form) ---
        if cmd == "SET_TEXTURE_SLOT3":
            vob_name = li[1]
            dds_name = li[2]
            extend   = li[3].upper()
            orient   = li[4].upper()
            sp1      = 0

            extend = (extend != "SINGLE")
            slots  = [int(j) for j in li[5:]]

            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError

            oid = gl.index(vob_name)
            dc  = {"LSIDE": 4, "SIDE": 3, "TOP": 5, "BACK": 2, "FRONT": 1, "UNDER": 6}

            if orient not in dc:
                msg("SET_TEXTURE_SLOT accepts only SIDE, LSIDE, TOP, BACK, FRONT, UNDER planes")
                msg("Received: %s" % orient)

            x1, x2, y1, y2 = vob.get_axis_limits(vob_name, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dc[orient])

            if extend and dc[orient] != 3:
                x2 = max(abs(x1), x2)
                x1 = -x2

            mti, nada, nada2 = vob.get_mat_info()
            mat_name = vob_name + "@"
            if mat_name not in nada2:
                vob.add_material(mat_name)

            vob.set_obj_material(oid, mat_name)
            vob.set_material_bb(mat_name, x1, x2, y1, y2)

            tid = vob.get_obj_texid(vob_name)
            tf, ti, mt = vob.get_mat_pos()
            vi   = ti[0] + tid * 24
            shin = vob.data[vi + 16]

            u, v, du, dv = blackwood.calc_slot([int(ki) for ki in slots])
            v = 64 - (v + dv)  # Flip V coordinate to match texture mode 2

            tex_file_id = vob.add_texture_file(dds_name)
            tex_id      = vob.set_tex_id(sp1, vob_name + "@", shin, tex_file_id, u, v, du, dv, orie=0)
            vob.set_material(mat_name, dc[orient], vob_name + "@")

        # --- SET_TEXTURE_SLOT: assign a texture slot to one or more objects (extended form) ---
        if cmd == "SET_TEXTURE_SLOT":
            vob_name  = li[1]
            sp1       = 0
            vob_names = []
            gl        = vob.get_obj_names()
            sj        = 1
            print li

            # Locate the EXTEND or SINGLE keyword position
            valid = False
            for sk in range(len(li)):
                if li[sk].upper() == "EXTEND" or li[sk].upper() == "SINGLE":
                    sj    = sk
                    valid = True

            vob_names = li[1:sj - 1]
            msg("Found " + " ".join(vob_names))

            dds_name = li[sj - 1]
            extend   = li[sj].upper()
            orient   = li[sj + 1].upper()
            extend   = (extend != "SINGLE")
            slots    = [int(j) for j in li[sj + 2:]]

            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            if vob_names == []:
                msg("No parts found")
                raise NameError

            dc = {"LSIDE": 4, "SIDE": 3, "TOP": 5, "BACK": 2, "FRONT": 1, "UNDER": 6}
            if orient not in dc:
                msg("SET_TEXTURE_SLOT accepts only SIDE, LSIDE, TOP, BACK, FRONT, UNDER planes")
                msg("Received: %s" % orient)

            # Compute the merged bounding box across all named objects
            x1, x2, y1, y2 = vob.get_axis_limits(vob_names[0], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dc[orient])
            for vn in vob_names:
                px1, px2, py1, py2 = vob.get_axis_limits(vn, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dc[orient])
                x1 = min(x1, px1)
                y1 = min(y1, py1)
                x2 = max(x2, px2)
                y2 = max(y2, py2)

            if extend and dc[orient] != 3:
                x2 = max(abs(x1), x2)
                x1 = -x2

            mti, nada, nada2 = vob.get_mat_info()

            for vn in vob_names:
                oid  = gl.index(vn)
                tid  = vob.get_obj_texid(vn)
                tf, ti, mt = vob.get_mat_pos()
                vi   = ti[0] + tid * 24
                shin = vob.data[vi + 16]  # Save shininess value

                mat_name = vn + "@"
                if mat_name not in nada2:
                    vob.add_material(mat_name)

                vob.set_obj_material(oid, mat_name)
                vob.set_material_bb(mat_name, x1, x2, y1, y2)

                u, v, du, dv = blackwood.calc_slot([int(ki) for ki in slots])
                v = 64 - (v + dv)  # Flip V coordinate to match texture mode 2

                tex_file_id = vob.add_texture_file(dds_name)
                tex_id      = vob.set_tex_id(sp1, vn + "@", shin, tex_file_id, u, v, du, dv, orie=0)
                vob.set_material(mat_name, dc[orient], vn + "@")

                # Restore shininess after material slot assignment
                tid = vob.get_obj_texid(vn)
                tf, ti, mt = vob.get_mat_pos()
                vi = ti[0] + tid * 24
                vob.data[vi + 16] = shin

        # --- SET_TEXTURE_SLOT2: same as SET_TEXTURE_SLOT with explicit slot index prefix ---
        if cmd == "SET_TEXTURE_SLOT2":
            sp1      = int(li[1])
            vob_name = li[2]
            vob_names = []
            gl        = vob.get_obj_names()
            sj        = 1
            print li

            # Locate the EXTEND or SINGLE keyword position
            valid = False
            for sk in range(len(li)):
                if li[sk].upper() == "EXTEND" or li[sk].upper() == "SINGLE":
                    sj    = sk
                    valid = True

            vob_names = li[2:sj - 1]
            msg("Found " + " ".join(vob_names))

            dds_name = li[sj - 1]
            extend   = li[sj].upper()
            orient   = li[sj + 1].upper()
            extend   = (extend != "SINGLE")
            slots    = [int(j) for j in li[sj + 2:]]

            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError
            if vob_names == []:
                msg("No parts found")
                raise NameError

            dc = {"LSIDE": 4, "SIDE": 3, "TOP": 5, "BACK": 2, "FRONT": 1, "UNDER": 6}
            if orient not in dc:
                msg("SET_TEXTURE_SLOT accepts only SIDE, LSIDE, TOP, BACK, FRONT, UNDER planes")
                msg("Received: %s" % orient)

            # Compute the merged bounding box across all named objects
            x1, x2, y1, y2 = vob.get_axis_limits(vob_names[0], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dc[orient])
            for vn in vob_names:
                px1, px2, py1, py2 = vob.get_axis_limits(vn, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dc[orient])
                x1 = min(x1, px1)
                y1 = min(y1, py1)
                x2 = max(x2, px2)
                y2 = max(y2, py2)

            if extend and dc[orient] != 3:
                x2 = max(abs(x1), x2)
                x1 = -x2

            mti, nada, nada2 = vob.get_mat_info()

            for vn in vob_names:
                oid  = gl.index(vn)
                tid  = vob.get_obj_texid(vn)
                tf, ti, mt = vob.get_mat_pos()
                vi   = ti[0] + tid * 24
                shin = vob.data[vi + 16]  # Save shininess value

                mat_name = vn + "@"
                if mat_name not in nada2:
                    vob.add_material(mat_name)

                vob.set_obj_material(oid, mat_name)
                vob.set_material_bb(mat_name, x1, x2, y1, y2)

                u, v, du, dv = blackwood.calc_slot([int(ki) for ki in slots])
                v = 64 - (v + dv)  # Flip V coordinate to match texture mode 2

                tex_file_id = vob.add_texture_file(dds_name)
                tex_id      = vob.set_tex_id(sp1, vn + "@", shin, tex_file_id, u, v, du, dv, orie=0)
                vob.set_material(mat_name, dc[orient], vn + "@")

                # Restore shininess after material slot assignment
                tid = vob.get_obj_texid(vn)
                tf, ti, mt = vob.get_mat_pos()
                vi = ti[0] + tid * 24
                vob.data[vi + 16] = shin

        # --- NEW_OBJECT: add a new blank white object to the VOB ---
        if cmd == "NEW_OBJECT":
            vob_name = li[1]
            vob.add_object(vob_name, (255, 255, 255), 0)

        # --- WRITE: save the modified VOB to disk ---
        if cmd == "WRITE":
            name = li[1]
            msg("WRITE OUT %s" % name)
            vob.write(name)

        # --- SET_COLOR: set RGB color and shininess flag for an object ---
        if cmd == "SET_COLOR":
            vob_name = li[1]
            shine    = li[2].upper()
            rgb      = [int(k) for k in li[3:]]
            sh       = 0

            if shine == "SHINE":
                print "SHINE"
                sh = 0
            if shine == "OPAQUE":
                sh = 1
                print "OPAQUE"

            gl = vob.get_obj_names()
            if not (vob_name in gl):
                msg("PART %s NOT FOUND " % vob_name)
                raise NameError

            oid = gl.index(vob_name)
            vob.data[vob.off_obj + oid * 16    ] = rgb[0]
            vob.data[vob.off_obj + oid * 16 + 1] = rgb[1]
            vob.data[vob.off_obj + oid * 16 + 2] = rgb[2]

            tid = vob.get_obj_texid(vob_name)
            tf, ti, mt = vob.get_mat_pos()
            vi = ti[0] + tid * 24
            vob.data[vi + 16] = sh
