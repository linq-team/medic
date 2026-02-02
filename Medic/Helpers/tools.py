"""Utility functions for Medic."""
import uuid


def generate_random_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())
