# common.py — CORE (vereist door app.py)

_FEED_CACHE = {}
_ARTICLE_CACHE = {}

def clear_feed_caches():
    """Wordt gebruikt door app.py voor 'Ververs' knop"""
    _FEED_CACHE.clear()
    _ARTICLE_CACHE.clear()
