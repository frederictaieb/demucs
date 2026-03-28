#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac"}


def find_audio_files(input_dir: Path) -> list[Path]:
    return sorted(
        [
            p for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )


def run_demucs(input_file: Path, temp_out_dir: Path, device: str = "cpu") -> None:
    """
    Lance Demucs en mode 2 stems:
    - vocals.wav
    - no_vocals.wav
    """
    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "--two-stems",
        "vocals",
        "--out",
        str(temp_out_dir),
        "-d",
        device,
        str(input_file),
    ]

    print(f"\n[INFO] Séparation : {input_file.name}")
    print("[CMD] " + " ".join(cmd))

    subprocess.run(cmd, check=True)


def find_generated_stems(temp_out_dir: Path, original_stem: str) -> tuple[Path, Path]:
    """
    Cherche récursivement vocals.wav et no_vocals.wav produits par Demucs.
    On ne dépend pas trop de la structure exacte des sous-dossiers.
    """
    vocals_candidates = list(temp_out_dir.rglob("vocals.wav"))
    instrumental_candidates = list(temp_out_dir.rglob("no_vocals.wav"))

    if not vocals_candidates:
        raise FileNotFoundError(f"Impossible de trouver vocals.wav pour {original_stem}")
    if not instrumental_candidates:
        raise FileNotFoundError(f"Impossible de trouver no_vocals.wav pour {original_stem}")

    # On essaye d'abord de trouver un chemin contenant le nom du fichier
    vocals = next((p for p in vocals_candidates if original_stem in str(p)), vocals_candidates[0])
    instrumental = next(
        (p for p in instrumental_candidates if original_stem in str(p)),
        instrumental_candidates[0]
    )

    return vocals, instrumental


def move_to_final_structure(
    source_vocals: Path,
    source_instrumental: Path,
    output_dir: Path,
    original_stem: str,
    overwrite: bool = True,
) -> None:
    """
    Crée:
      output/original_stem/voix/voix.wav
      output/original_stem/instruments/instrumental.wav
    """
    target_root = output_dir / original_stem
    voix_dir = target_root / "voice"
    instruments_dir = target_root / "instr"

    if overwrite and target_root.exists():
        shutil.rmtree(target_root)

    voix_dir.mkdir(parents=True, exist_ok=True)
    instruments_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_vocals, voix_dir / f"{original_stem} (voice).wav")
    shutil.copy2(source_instrumental, instruments_dir / f"{original_stem} (instr).wav")

    print(f"[OK] Sortie créée : {target_root}")


def clean_temp_dir(temp_dir: Path) -> None:
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def process_all(input_dir: Path, output_dir: Path, device: str = "cpu") -> None:
    if not input_dir.exists():
        raise FileNotFoundError(f"Le dossier d'entrée n'existe pas : {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    files = find_audio_files(input_dir)
    if not files:
        print("[INFO] Aucun fichier .wav, .mp3 ou .flac trouvé.")
        return

    for audio_file in files:
        stem_name = audio_file.stem
        temp_dir = output_dir / "_demucs_tmp"

        try:
            clean_temp_dir(temp_dir)
            run_demucs(audio_file, temp_dir, device=device)
            vocals_path, instrumental_path = find_generated_stems(temp_dir, stem_name)
            move_to_final_structure(
                vocals_path,
                instrumental_path,
                output_dir,
                stem_name,
                overwrite=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"[ERREUR] Demucs a échoué pour {audio_file.name} : {e}")
        except Exception as e:
            print(f"[ERREUR] {audio_file.name} : {e}")
        finally:
            clean_temp_dir(temp_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sépare les voix et l'instrumental de tous les fichiers audio d'un dossier avec Demucs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./data/input"),
        help="Dossier contenant les fichiers audio (défaut: ./data/input)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/output"),
        help="Dossier de sortie (défaut: ./data/output)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device Demucs: cpu, cuda, cuda:0, mps... (défaut: cpu)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    process_all(
        input_dir=args.input,
        output_dir=args.output,
        device=args.device,
    )


if __name__ == "__main__":
    main()