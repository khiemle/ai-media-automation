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
