#!/usr/bin/env python3

# FastAPI config
#
# Listening IP and PORT
ip = '149.210.137.179'
port = 8008
# Optional authentication token. 'None' means disabled.
token = None
#
# Don't change stuff below here unless you know what you're doing
#
# Can be set to 'False'/'True' to include deprecated entries in the
# matrix. You really shouldn't set this here.
#
deprecated = True
#
# Can be set to 'False'/'True' to include deprecated entries in the
# matrix. You really shouldn't set this here.
#
revoked = True
#
# Verbose mode, lots of output to the logfile
#
verbose = False
logfile = 'attackmatrix.log'
#
# Always download a clean copy of the matrices and overwrite the
# cache file. You really shouldn't set this here.
#
force = False
#
# Paths for storing matrix cache
#
cachedir = 'matrices/'
cachefile = 'matrices/merged.json'
