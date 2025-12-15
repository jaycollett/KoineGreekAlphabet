"""Similar letter pairs for advanced difficulty levels.

This module defines visually and phonetically confusing Greek letter pairs
used for generating more challenging distractors in Level 2 and Level 3.
"""
from typing import Dict, Set, List
from app.db.models import Letter

# Letter name -> Set of similar letter names
# Based on visual similarity (shape) and phonetic similarity (sound)
SIMILAR_LETTER_PAIRS: Dict[str, Set[str]] = {
    # Visual similarities (uppercase)
    "Rho": {"Pi", "Beta"},  # Ρ looks like P, similar to Π, Β
    "Pi": {"Rho", "Gamma", "Tau"},  # Π similar to Ρ, Γ, Τ
    "Nu": {"Upsilon", "Psi"},  # ν, υ, ψ (lowercase look similar)
    "Upsilon": {"Nu", "Psi"},  # υ, ν, ψ
    "Omicron": {"Omega", "Theta"},  # Ο, Ω, Θ (circles)
    "Omega": {"Omicron", "Theta"},  # Ω, Ο, Θ
    "Epsilon": {"Eta", "Sigma"},  # Ε, Η (similar shapes)
    "Eta": {"Epsilon", "Nu"},  # Η, Ε
    "Kappa": {"Chi"},  # Κ, Χ (similar angles)
    "Chi": {"Kappa", "Psi"},  # Χ, Κ, Ψ
    "Beta": {"Rho"},  # Β, Ρ
    "Gamma": {"Pi", "Tau"},  # Γ, Π, Τ (corners/angles)
    "Tau": {"Gamma", "Pi"},  # Τ, Γ, Π
    "Sigma": {"Epsilon", "Xi"},  # Σ, Ε, Ξ
    "Xi": {"Sigma", "Zeta"},  # Ξ, Σ, Ζ (complex shapes)
    "Zeta": {"Xi"},  # Ζ, Ξ
    "Psi": {"Chi", "Upsilon"},  # Ψ, Χ, Υ
    "Phi": {"Theta"},  # Φ, Θ (circular elements)
    "Theta": {"Phi", "Omicron", "Omega"},  # Θ, Φ, Ο, Ω

    # Letters with fewer confusable pairs
    "Alpha": {"Delta", "Lambda"},  # Α, Δ, Λ (triangular)
    "Delta": {"Alpha", "Lambda"},  # Δ, Α, Λ
    "Lambda": {"Alpha", "Delta"},  # Λ, Α, Δ
    "Iota": {"Tau"},  # Ι, Τ (straight lines)
    "Mu": {},  # М is fairly unique
}


def get_similar_letters(
    target_letter: Letter,
    all_letters: List[Letter],
    count: int = 3
) -> List[Letter]:
    """
    Get visually/phonetically similar letters for use as distractors.

    Falls back to random selection if not enough similar letters exist.

    Args:
        target_letter: The correct answer letter
        all_letters: List of all available letters
        count: Number of similar letters needed

    Returns:
        List of Letter objects (similar to target)
    """
    import random

    # Get similar letter names for the target
    similar_names = SIMILAR_LETTER_PAIRS.get(target_letter.name, set())

    # Find Letter objects that match similar names
    similar_letters = [
        letter for letter in all_letters
        if letter.name in similar_names and letter.id != target_letter.id
    ]

    # If we have enough similar letters, return random subset
    if len(similar_letters) >= count:
        return random.sample(similar_letters, count)

    # Not enough similar letters - supplement with random ones
    other_letters = [
        letter for letter in all_letters
        if letter.id != target_letter.id and letter not in similar_letters
    ]

    # Combine similar letters with random ones
    remaining_count = count - len(similar_letters)
    random_supplement = random.sample(other_letters, min(remaining_count, len(other_letters)))

    result = similar_letters + random_supplement
    random.shuffle(result)  # Mix similar and random distractors

    return result[:count]
