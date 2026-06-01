import os
import time
import uuid

# Clean up old database
if os.path.exists('phi_audit.db'):
    os.remove('phi_audit.db')
    print('Old database removed')
    time.sleep(1)

from backend.shared.auth_manager import auth_manager
from backend.shared.mode_manager import mode_manager

# Create unique user
username = 'testuser_' + uuid.uuid4().hex[:8]
success, msg, user = auth_manager.signup(username, 'test@ex.com', 'password123456')
print('[Signup] Success=' + str(success) + ', Message=' + msg)

if success:
    user_id = user.get('user_id')
    print('[User Created] ID=' + str(user_id))
    
    # Set mode
    success, msg = mode_manager.set_mode(user_id, 'private', 120)
    print('[Mode Set] Success=' + str(success) + ', Message=' + msg)
    
    # Get current mode
    current = mode_manager.get_current_mode(user_id)
    mode = current.get('mode')
    print('[Current Mode] ' + mode)
else:
    print('Failed to create user')
