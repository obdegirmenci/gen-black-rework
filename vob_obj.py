# vob_obj.py
# Dumps all submeshes of a .vob file to .obj files.

import os
import sys
import blackwood

# Resolve the project root relative to this script's location.
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    #Fallback
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# Input file path (relative to script directory)
# Blackwood WLD files
#file_input  = os.path.join(SCRIPT_DIR, "Base", "H", "wld", "Blackwood.wld")

# Helmet SRE files
#file_input  = os.path.join(SCRIPT_DIR, "Base", "H", "hmn", "helmet.sre")

# Rim CEM files
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "rim", "XRG_base_rim_mod.cem")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "rim", "XRG_base_rim_org.cem")

# Vehicle VOB files
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base_fix_max.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base_off_max.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base4_fix.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base4_off.vob")
file_input  = os.path.join(SCRIPT_DIR, "Base", "H", "veh", "XR.vob")

# Parent directory of the input file
parent_dir = os.path.basename(os.path.dirname(file_input))

# Output directory for dumped mesh OBJ files
dump_dir = os.path.join(SCRIPT_DIR, "Dump", parent_dir)

# Dump method
is_file_locked = False

if not os.path.exists(dump_dir):
    os.makedirs(dump_dir)

# Load the VOB/CEM/WLD file
s = blackwood.blk_file()
s.load(file_input)

# Iterate over sub-meshes and export each as a Wavefront OBJ file
for me in range(1, 240):
    s.set_mid(me)

    # Decide dump method
    if is_file_locked:
        ti = s.dump_mesh_as_string2()
    else:
        ti = s.dump_mesh_as_string()

    out_path = os.path.join(dump_dir, "mesh_%i.obj" % me)
    open(out_path, "w").write("".join(ti))
    print "MESH", me, "DONE"
