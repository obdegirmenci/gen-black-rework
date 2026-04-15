# interface.py
# Entry point: compiles dependencies and runs the mesh processing pipeline.

import os
import sys

# Resolve the project root relative to this script's location.
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    #Fallback
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# Compile updated source files before importing them.
import compiler
compiler.compileFile(os.path.join(SCRIPT_DIR, "blackwood.py"))
compiler.compileFile(os.path.join(SCRIPT_DIR, "gen_black.py"))

import gen_black

# Directory that contains the command file and input assets.
#base_dir    = os.path.join(SCRIPT_DIR, "Input", "wld", "fooObject")
#base_dir    = os.path.join(SCRIPT_DIR, "Input", "hmn", "fooHelmet")
#base_dir    = os.path.join(SCRIPT_DIR, "Input", "rim", "fooRim")
base_dir    = os.path.join(SCRIPT_DIR, "Input", "veh", "fooCar")

# Command script that drives the processing pipeline.
file_command = "cmd.txt"

# Source files to be processed.
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base_fix_max.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base_off_max.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base4_fix.vob")
#file_input  = os.path.join(SCRIPT_DIR, "Base", "Custom", "veh", "XR_base4_off.vob")
file_input  = os.path.join(SCRIPT_DIR, "Base", "H", "veh", "XR.vob")

os.chdir(base_dir)
gen_black.process(file_command, file_input)

print "DONE"
