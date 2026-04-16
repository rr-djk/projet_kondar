#!/usr/bin/env python3
"""Point d'entrée SENTINELLE CNC — Laptop.

Usage:
    python main_laptop.py demo.nc [--camera 0]

Ce fichier est le point d'entrée pour l'exécution sur laptop.
Il initialise le simulateur avec logging JSONL des événements clés
(FSM, obstacles, mute) et gère proprement les erreurs G-code.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


def parse_args():
    """Parse les arguments CLI."""
    parser = argparse.ArgumentParser(
        description="SENTINELLE CNC — Copilote d'autonomie machine"
    )
    parser.add_argument(
        "gcode_file",
        nargs="?",
        default="demo.nc",
        help="Fichier G-code à simuler (default: demo.nc)"
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="Index de la webcam (default: 0)"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="SENTINELLE CNC 1.0.0"
    )
    return parser.parse_args()


def setup_logging() -> tuple[str, object]:
    """Configure le logging JSONL dans sentinelle/logs/.

    Returns:
        Tuple (chemin_fichier, file_handle)
    """
    # Déterminer le répertoire des logs (dans sentinelle/logs/)
    script_dir = Path(__file__).parent
    logs_dir = script_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = int(time.time() * 1000)
    log_path = logs_dir / f"session_{timestamp}.jsonl"
    f = open(log_path, "w")
    return str(log_path), f


def log_event(f, event_type: str, data: dict):
    """Log un événement en JSONL."""
    entry = {
        "type": event_type,
        "ts": int(time.time() * 1000),
        **data
    }
    f.write(json.dumps(entry) + "\n")
    f.flush()


def main():
    """Fonction principale."""
    args = parse_args()
    
    # Setup logging
    log_path, log_file = setup_logging()
    session_start_ts = int(time.time() * 1000)
    
    # Startup log
    log_event(log_file, "session_start", {
        "version": "1.0.0",
        "args": {
            "gcode_file": args.gcode_file,
            "camera": args.camera
        }
    })
    
    # Vérifier fichier G-code
    if not os.path.exists(args.gcode_file):
        error_msg = f"Fichier G-code non trouvé: {args.gcode_file}"
        print(f"Erreur: {error_msg}", file=sys.stderr)
        log_event(log_file, "error", {"message": error_msg})
        log_event(log_file, "session_end", {
            "reason": "gcode_file_not_found",
            "duration_ms": int(time.time() * 1000) - session_start_ts
        })
        log_file.close()
        sys.exit(1)
    
    # Initialiser simulateur
    try:
        from sentinelle.visual.simulator import Simulator
        sim = Simulator(
            gcode_path=args.gcode_file,
            camera_index=args.camera,
            logger=log_file
        )
        
        log_event(log_file, "simulator_init", {
            "gcode_file": args.gcode_file,
            "camera_index": args.camera
        })
        
        # Démarrer
        sim.start()
        log_event(log_file, "simulator_start", {})
        
        # Lancer boucle principale
        sim.run()
        
    except KeyboardInterrupt:
        print("\nArrêt par l'utilisateur")
        log_event(log_file, "session_end", {
            "reason": "keyboard_interrupt",
            "duration_ms": int(time.time() * 1000) - session_start_ts
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Erreur: {error_msg}", file=sys.stderr)
        log_event(log_file, "error", {"message": error_msg})
        log_event(log_file, "session_end", {
            "reason": "exception",
            "duration_ms": int(time.time() * 1000) - session_start_ts
        })
        sys.exit(1)
    finally:
        # Cleanup
        if not log_file.closed:
            log_file.close()
        print(f"Session logguée dans: {log_path}")


if __name__ == "__main__":
    main()
