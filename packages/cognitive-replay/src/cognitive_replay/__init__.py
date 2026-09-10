"""Replay a single historical defect; corpus selection and role scoring stay in COS."""
from .environment import freeze_environment_profile, validate_environment_profile
from .sandbox import qualify_candidate_in_sandbox

__all__ = ["freeze_environment_profile", "validate_environment_profile", "qualify_candidate_in_sandbox"]
