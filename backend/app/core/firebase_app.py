from __future__ import annotations

import os

from app.core.config import Settings, get_settings

EMULATOR_ENV_VARS = ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "FIREBASE_STORAGE_EMULATOR_HOST")


def emulator_host() -> str | None:
    """Return the first configured emulator host, if any."""
    for name in EMULATOR_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return None


def _emulator_credential():
    """Anonymous credential for emulator use.

    The emulators authenticate nothing, and resolving Application Default
    Credentials against them fails outright — there is no service account to
    find. firebase-admin ships no anonymous credential, so provide one.
    """
    import google.auth.credentials
    from firebase_admin import credentials

    class _AnonymousCredential(credentials.Base):
        def get_credential(self):
            return google.auth.credentials.AnonymousCredentials()

    return _AnonymousCredential()


def ensure_firebase_app(settings: Settings | None = None) -> None:
    """Initialize the default firebase-admin app exactly once.

    Shared by the Firestore repository, the auth verifier and the storage
    archiver so all three agree on how credentials are resolved.

    Deliberately does not call `get_app()` on the already-initialized path: the
    only question here is whether initialization is still needed, and looking the
    app up would raise if some other app name were registered first.
    """
    import firebase_admin

    if firebase_admin._apps:
        return

    from firebase_admin import credentials

    settings = settings or get_settings()
    project_id = settings.firebase_project_id

    if emulator_host():
        # A project id is mandatory even against an emulator; the demo- prefix
        # keeps the CLI and SDKs from attempting to reach real Google services.
        cred = _emulator_credential()
        project_id = project_id or "demo-retail-procurement"
    else:
        cred_data = settings.firebase_credentials()
        cred = credentials.Certificate(cred_data) if cred_data else credentials.ApplicationDefault()

    options = {"projectId": project_id} if project_id else None
    firebase_admin.initialize_app(cred, options)
