"""
Legacy exercise configuration map.
Delegates to unified rehabilitation.exercises.EXERCISE_REGISTRY
to ensure ExerciseDefinition remains the single source of truth.
"""
from rehabilitation.exercises import EXERCISE_REGISTRY, ExerciseDefinition


class _ExerciseConfigProxy(dict):
    """Dynamically proxies configuration from unified EXERCISE_REGISTRY."""

    def __getitem__(self, key: str):
        if key not in EXERCISE_REGISTRY:
            raise KeyError(key)
        ex: ExerciseDefinition = EXERCISE_REGISTRY[key]
        return {
            "angle_name": ex.joint_angle,
            "landmarks": list(ex.landmarks),
            "flexed_threshold": ex.flexed_threshold,
            "extended_threshold": ex.extended_threshold,
        }

    def __contains__(self, key: str):
        return key in EXERCISE_REGISTRY

    def keys(self):
        return EXERCISE_REGISTRY.keys()

    def get(self, key: str, default=None):
        if key in EXERCISE_REGISTRY:
            return self[key]
        return default

    def items(self):
        return [(k, self[k]) for k in EXERCISE_REGISTRY.keys()]

    def values(self):
        return [self[k] for k in EXERCISE_REGISTRY.keys()]

    def __len__(self):
        return len(EXERCISE_REGISTRY)


EXERCISE_CONFIG = _ExerciseConfigProxy()
