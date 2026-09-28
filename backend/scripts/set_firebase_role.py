"""Assign a Firebase custom role claim to an existing user.

Usage:
  python scripts/set_firebase_role.py <uid> procurement_manager
"""
import sys

import firebase_admin
from firebase_admin import auth, credentials

VALID = {"admin", "owner_manager", "procurement_manager"}
if len(sys.argv) != 3 or sys.argv[2] not in VALID:
    raise SystemExit("Usage: python scripts/set_firebase_role.py <uid> <admin|owner_manager|procurement_manager>")
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.ApplicationDefault())
auth.set_custom_user_claims(sys.argv[1], {"role": sys.argv[2]})
print(f"Assigned {sys.argv[2]} to {sys.argv[1]}")
