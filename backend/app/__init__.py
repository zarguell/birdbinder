from app.huey_instance import huey as huey_instance  # noqa: F401

# Import task modules so @huey.task() decorators register them in the Huey registry.
# The huey consumer only loads app.huey_instance — without these imports, tasks
# would never be registered and dequeue would fail with "not found in TaskRegistry".
import app.services.identifier  # noqa: F401
import app.services.card_gen  # noqa: F401
