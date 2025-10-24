def clamp_limit(limit:int|None, default=50, max_=100):
    return default if limit is None else min(max(limit,1), max_)
