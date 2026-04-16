"""Simulateur visuel SENTINELLE CNC avec intégration pilier acoustique.

Boucle pygame 60fps avec layout split-screen:
- Panel visuel gauche (768×720): Trajectoire G-code, obstacles webcam, point outil
- Panel données droit (512×720): FFT live, alertes, badges état, boutons
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import cv2
import pygame

from sentinelle import config
from sentinelle.ipc.ws_client import AcousticLink
from sentinelle.protocol import AcousticEvent
from sentinelle.state import AppState, Event, State

# Palette Dashboard Industriel (Mode Sombre)
COLOR_BG = (0x12, 0x12, 0x12)           # Deep Charcoal #121212
COLOR_SURFACE = (0x1E, 0x1E, 0x2E)      # Dark Slate #1E1E2E
COLOR_PRIMARY = (0x00, 0xE5, 0xFF)      # Cyan Électrique #00E5FF
COLOR_ALERT = (0xFF, 0x52, 0x52)        # Rouge Flash #FF5252
COLOR_TEXT = (0xE0, 0xE0, 0xE0)         # Blanc Cassé #E0E0E0
COLOR_MAGENTA = (0xFF, 0x00, 0xFF)      # Magenta #FF00FF (CHEMIN IMPOSSIBLE)

# Layout
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
VISUAL_PANEL_WIDTH = 768  # 60%
DATA_PANEL_WIDTH = 512    # 40%
FPS_TARGET = 60


class Simulator:
    """Simulateur visuel SENTINELLE CNC avec intégration pilier acoustique."""

    def __init__(self, gcode_path: str | None = None, camera_index: int = 0) -> None:
        """Initialise le simulateur pygame, FSM, webcam et AcousticLink."""
        # Pygame
        pygame.init()
        self._screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("SENTINELLE CNC — Simulateur")
        self._clock = pygame.time.Clock()
        self._font = pygame.font.SysFont("monospace", 16)

        # FSM
        self._fsm = AppState()
        self._baseline_ready = False

        # Webcam
        self._camera_index = camera_index
        self._frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._camera_offline = False
        self._running = True
        self._cam_thread: threading.Thread | None = None

        # G-code
        self._gcode_path = gcode_path
        if gcode_path and not Path(gcode_path).exists():
            print(f"[WARN] Fichier G-code introuvable: {gcode_path}")
            self._gcode_path = None

        # AcousticLink
        self._acoustic = AcousticLink()
        self._acoustic_connected = False

        # Threads démarrés dans start() pour permettre import/test sans side effects
        self._started = False

    def start(self) -> None:
        """Démarre les threads webcam et acoustique."""
        if self._started:
            return
        self._started = True
        self._cam_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="webcam-capture",
        )
        self._cam_thread.start()
        self._acoustic.start()

    def _capture_loop(self) -> None:
        """Thread séparé pour capture webcam. Garde uniquement le dernier frame."""
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self._camera_offline = True
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.WEBCAM_MAX_RES[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.WEBCAM_MAX_RES[1])

        while self._running:
            ret, frame = cap.read()
            if ret:
                self._camera_offline = False
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                self._frame_queue.put(frame)
            else:
                self._camera_offline = True

        cap.release()

    def _handle_events(self) -> None:
        """Gère les événements pygame (QUIT, MOUSEBUTTONDOWN, KEYDOWN)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._running = False
                elif event.key == pygame.K_SPACE:
                    if self._fsm.state in (State.PAUSED_ACOUSTIC, State.CONFIRMING):
                        self._fsm.transition(Event.RESUME)

    def _consume_queue(self) -> list[dict]:
        """Lit la queue WebSocket sans bloquer.

        Retourne liste des events reçus depuis dernière frame.
        """
        events = []
        while True:
            event = self._acoustic.get_event()
            if event is None:
                break
            if isinstance(event, AcousticEvent):
                events.append({
                    "type": "acoustic",
                    "severity": event.severity,
                    "ts": event.ts,
                })
            elif isinstance(event, dict) and event.get("type") == "status":
                self._acoustic_connected = event.get("connected", False)
        return events

    def _update_fsm(self, events: list[dict]) -> None:
        """Met à jour la FSM, gère throttle A* (placeholder pour T-3.2).

        Args:
            events: Liste des events acoustiques reçus.
        """
        for evt in events:
            if evt.get("type") == "acoustic":
                severity = evt.get("severity")
                if severity == "warn":
                    try:
                        self._fsm.transition(Event.ACOUSTIC_WARN)
                    except Exception:  # noqa: BLE001
                        pass
                elif severity == "critical":
                    try:
                        self._fsm.transition(Event.ACOUSTIC_CRITICAL)
                    except Exception:  # noqa: BLE001
                        pass

    def _render_visual_panel(self, surface: pygame.Surface) -> None:
        """Rend le panel visuel gauche (768×720).

        Pour T-3.1: juste fond COLOR_SURFACE + grille légère.
        """
        surface.fill(COLOR_SURFACE)

        # Grille légère
        for x in range(0, VISUAL_PANEL_WIDTH, 50):
            pygame.draw.line(surface, (40, 40, 50), (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, 50):
            pygame.draw.line(surface, (40, 40, 50), (0, y), (VISUAL_PANEL_WIDTH, y))

        # Badge CAMERA OFFLINE si webcam indisponible
        if self._camera_offline:
            text = self._font.render("CAMERA OFFLINE", True, COLOR_ALERT)
            rect = text.get_rect(center=(VISUAL_PANEL_WIDTH // 2, 30))
            surface.blit(text, rect)

    def _render_acoustic_panel(self, surface: pygame.Surface) -> None:
        """Rend le panel données droit (512×720).

        Pour T-3.1: juste fond COLOR_SURFACE + texte "Panel Données".
        """
        surface.fill(COLOR_SURFACE)

        # Titre
        title = self._font.render("Panel Données", True, COLOR_PRIMARY)
        surface.blit(title, (20, 20))

        # Statut connexion acoustique
        if not self._acoustic_connected:
            status = self._font.render("ACOUSTIC OFFLINE", True, COLOR_ALERT)
            surface.blit(status, (20, 50))

    def run(self) -> None:
        """Boucle principale 60fps.

        Ordre par frame:
        1. _handle_events()
        2. _consume_queue()
        3. _update_fsm(events)
        4. _render_visual_panel() + _render_acoustic_panel()
        5. pygame.display.flip()
        6. clock.tick(60)
        """
        self.start()
        visual_surface = pygame.Surface((VISUAL_PANEL_WIDTH, SCREEN_HEIGHT))
        acoustic_surface = pygame.Surface((DATA_PANEL_WIDTH, SCREEN_HEIGHT))

        while self._running:
            # 1. Gestion événements
            self._handle_events()

            # 2. Consommation queue WebSocket
            events = self._consume_queue()

            # 3. Mise à jour FSM
            self._update_fsm(events)

            # 4. Rendu
            self._render_visual_panel(visual_surface)
            self._render_acoustic_panel(acoustic_surface)

            # Blit sur écran principal
            self._screen.fill(COLOR_BG)
            self._screen.blit(visual_surface, (0, 0))
            self._screen.blit(acoustic_surface, (VISUAL_PANEL_WIDTH, 0))

            # 5. Flip display
            pygame.display.flip()

            # 6. Limitation 60fps
            self._clock.tick(FPS_TARGET)

        # Cleanup
        self._running = False
        self._acoustic.stop()
        if self._cam_thread:
            self._cam_thread.join(timeout=1.0)
        pygame.quit()
