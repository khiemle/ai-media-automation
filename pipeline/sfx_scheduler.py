"""Deterministic random SFX scheduler for ASMR/soundscape videos."""
import random


def schedule_sfx(
    pool_ids: list[int],
    density_s: int | None,
    seed: int,
    start_s: float,
    end_s: float,
) -> list[tuple[float, int]]:
    """
    Build a deterministic list of (timestamp, sfx_id) events.

    The same (seed, pool_ids, density_s, start_s, end_s) inputs always return
    the same output. Gaps between events are density_s +/- 50% jitter.

    Returns empty list when pool_ids or density_s is empty/None.
    """
    if not pool_ids or not density_s:
        return []

    rng = random.Random(seed)
    # Burn one number per second of start_s so chunks at different offsets
    # still draw from the seeded stream consistently. Without this, every chunk
    # starts at the seed's first draw and SFX timing collides at chunk boundaries.
    for _ in range(int(start_s)):
        rng.random()

    schedule: list[tuple[float, int]] = []
    t = start_s
    while t < end_s:
        gap = density_s * rng.uniform(0.5, 1.5)
        t += gap
        if t >= end_s:
            break
        sfx_id = rng.choice(pool_ids)
        schedule.append((round(t, 3), sfx_id))
    return schedule


def schedule_sfx_layer(
    pool_ids: list[int],
    interval_min_s: float,
    interval_max_s: float,
    seed: int,
    start_s: float,
    end_s: float,
) -> list[tuple[float, int]]:
    """
    Build a deterministic list of (timestamp, sfx_id) events for one layer.

    Gap between events = rng.uniform(interval_min_s, interval_max_s).
    Seed-burn: advance RNG by int(start_s) steps before drawing so any
    [start_s, end_s) chunk produces non-repeating events relative to
    other chunks of the same video.
    Returns empty list when pool_ids is empty, interval_min_s <= 0, or interval_max_s <= 0.
    interval_max_s must be positive; interval_min_s must be positive (zero is rejected).
    If interval_min_s > interval_max_s, Python's random.uniform swaps them internally; prefer passing them in correct order.
    """
    if not pool_ids or interval_min_s <= 0 or interval_max_s <= 0:
        return []

    rng = random.Random(seed)
    for _ in range(int(start_s)):
        rng.random()

    schedule: list[tuple[float, int]] = []
    t = start_s
    while t < end_s:
        gap = rng.uniform(interval_min_s, interval_max_s)
        t += gap
        if t >= end_s:
            break
        sfx_id = rng.choice(pool_ids)
        schedule.append((round(t, 3), sfx_id))
    return schedule
