from app.profiles import web, backend, mobile_ios, mobile_android, fullstack, devops, data

PROFILES: dict = {
    "web": web,
    "backend": backend,
    "mobile_ios": mobile_ios,
    "mobile_android": mobile_android,
    "fullstack": fullstack,
    "devops": devops,
    "data": data,
}


def get_profile(key: str):
    """Return the profile module for the given key. Falls back to fullstack if not found."""
    return PROFILES.get(key, fullstack)
