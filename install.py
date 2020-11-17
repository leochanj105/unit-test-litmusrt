#!/usr/bin/env python

################################################################################
# Description
################################################################################

# This script installes (or re-installs) the unit_trace Python module, so that
# the unit_trace library can be imported with `import unit_trace` by a Python
# script, from anywhere on the system.

# The installation merely copies the unit-trace script and the unit_trace
# folder to ~/bin. You can also do this manually if you want to.

# We do not use the Distutils system, provided by Python, because that
# is less convenient :-)


################################################################################
# Imports
################################################################################

import sys
import shutil
import os


################################################################################
# Do the install
################################################################################

# Determine destination directory for unit_trace module
dst = '~/bin/unit_trace'
dst = os.path.expanduser(dst)

try:
    # If the destination exists
    if os.path.exists(dst):
        # Delete it
        shutil.rmtree(dst)
    # Copy source to destination
    shutil.copytree('unit_trace', dst)
except:
    print "Unexpected error:", sys.exc_info()
    exit()

# Determine destination directory for unit-trace script
dst = '~/bin/unit-trace'
dst = os.path.expanduser(dst)
try:
    shutil.copyfile('unit-trace', dst)
    # Keep same permissions
    shutil.copystat('unit-trace', dst)
except:
    print "Unexpected error:", sys.exc_info()
    exit()
