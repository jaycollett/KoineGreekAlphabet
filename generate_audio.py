"""Generate audio pronunciation files for Greek letters using gTTS."""
import os
from gtts import gTTS

# Greek alphabet letter names
GREEK_LETTERS = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta",
    "Eta", "Theta", "Iota", "Kappa", "Lambda", "Mu",
    "Nu", "Xi", "Omicron", "Pi", "Rho", "Sigma",
    "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega"
]

def generate_audio_files():
    """Generate MP3 audio files for each Greek letter pronunciation."""
    audio_dir = "app/static/audio"
    os.makedirs(audio_dir, exist_ok=True)

    for letter_name in GREEK_LETTERS:
        filename = f"{letter_name.lower()}.mp3"
        filepath = os.path.join(audio_dir, filename)

        print(f"Generating audio for {letter_name}...")

        try:
            # Create gTTS object with slower speech for clarity
            tts = gTTS(text=letter_name, lang='en', slow=True)
            tts.save(filepath)
            print(f"  ✓ Saved {filename}")
        except Exception as e:
            print(f"  ✗ Error generating {filename}: {e}")

    print(f"\n✓ Generated {len(GREEK_LETTERS)} audio files in {audio_dir}")

if __name__ == "__main__":
    generate_audio_files()
