"""Memory decay (Task 4.4.8): unused facts fade, expired facts purge."""

from __future__ import annotations

import logging
import time

from jarvis.brain.memory.store import MemoryStore

logger = logging.getLogger(__name__)

DECAY_PER_DAY = 0.02
MIN_IMPORTANCE = 0.05


def decay(store: MemoryStore) -> int:
    """Decay importance of facts by age since last use. Returns count touched."""
    now = time.time()
    touched = 0
    for fact in store.all_facts():
        try:
            ts = time.mktime(time.strptime(fact.last_used, "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        age_days = max(0.0, (now - ts) / 86400.0)
        new_imp = max(MIN_IMPORTANCE, fact.importance - DECAY_PER_DAY * age_days)
        if new_imp < fact.importance:
            store.touch_fact(fact.id, importance=new_imp)
            touched += 1
    purged = store.purge_expired()
    logger.info("decay touched %d facts, purged %d expired", touched, purged)
    return touched
