import os
import sys

if os.getenv('CHARM_DIR'):
    lib_path = os.path.join(os.getenv('CHARM_DIR'), 'lib')
else:
    lib_path = 'lib'

sys.path.append(lib_path)
