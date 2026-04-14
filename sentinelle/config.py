"""Constantes globales SENTINELLE CNC.

Toutes les constantes configurables sont centralisées ici.
Ne jamais hardcoder ces valeurs dans les modules métier.
"""

# Espace de travail simulé (mm)
WORKSPACE_MM = (300, 200)

# Grille A* pour path planning
GRID_SIZE = (50, 50)

# Audio
AUDIO_SR = 44100              # Sample rate
FFT_WINDOW_SAMPLES = 512      # Taille fenêtre FFT en samples (512 @ 44.1kHz ≈ 11.6ms)
FFT_OVERLAP = 0.5             # Overlap 50%
AUDIO_BLOCKSIZE = 4096        # Blocs sounddevice (~93ms @ 44.1kHz)
BASELINE_DURATION_S = 10      # Durée capture baseline
ANOMALY_WARN_SIGMA = 2.0      # Seuil alerte jaune
ANOMALY_CRITICAL_SIGMA = 3.0  # Seuil alerte rouge + pause

# WebSocket IPC
WS_HOST = "raspberrypi.local"
WS_PORT = 8765
WS_RECONNECT_BACKOFF = (1, 2, 5)  # secondes, plafonné à 5s

# Vision
HSV_ORANGE_LOW = (5, 100, 100)
HSV_ORANGE_HIGH = (25, 255, 255)
CAMERA_INDEX = 0              # Override CLI: --camera N
WEBCAM_MAX_RES = (640, 480)   # Résolution max webcam
ARUCO_THROTTLE_MS = 100       # Throttle ArUco fallback
PLANNER_THROTTLE_MS = 200     # Throttle A* (max 5Hz)
