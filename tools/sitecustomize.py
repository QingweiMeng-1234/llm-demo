import os
import tempfile
import uuid


def _mkdtemp_without_acl_mode(suffix=None, prefix=None, dir=None):
    suffix = suffix or ""
    prefix = prefix or "tmp"
    base_dir = dir if dir is not None else tempfile.gettempdir()
    os.makedirs(base_dir, exist_ok=True)

    for _ in range(1024):
        candidate = os.path.join(base_dir, f"{prefix}{uuid.uuid4().hex}{suffix}")
        try:
            # Avoid passing an explicit mode on Windows to inherit parent ACL.
            os.mkdir(candidate)
            return candidate
        except FileExistsError:
            continue

    raise FileExistsError("Unable to allocate temporary directory")


tempfile.mkdtemp = _mkdtemp_without_acl_mode
