"""Simulateur visuel SENTINELLE CNC avec intégration pilier acoustique.

Boucle pygame 60fps avec layout split-screen:
- Panel visuel gauche (768×720): Trajectoire G-code, obstacles webcam, point outil
- Panel données droit (512×720): FFT live, alertes, badges état, boutons
"""

from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pygame

from sentinelle import config
from sentinelle.ipc.ws_client import AcousticLink
from sentinelle.protocol import AcousticEvent
from sentinelle.state import AppState, Event, State
from sentinelle.visual.gcode_parser import Segment, parse_gcode
from sentinelle.visual.obstacle import BoundingBox, detect_obstacle
from sentinelle.visual.planner import find_path

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
        self._gcode_error = None
        if gcode_path:
            if os.path.exists(gcode_path):
                self.segments = parse_gcode(gcode_path)
            else:
                print(f"[WARN] G-code file not found: {gcode_path}")
                self.segments = []
                self._gcode_error = f"Fichier non trouvé:\n{gcode_path}"
        else:
            self.segments = []
            self._gcode_error = "Aucun fichier G-code"

        # Path planning state
        self.original_segments = self.segments.copy()
        self.current_path = []
        self.last_planner_ts = 0
        self.planner_throttle_ms = config.PLANNER_THROTTLE_MS

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

    def _mm_to_pixel(self, x_mm: float, y_mm: float) -> tuple[int, int]:
        """Convertit coordonnées mm en pixels dans le panel visuel."""
        scale_x = VISUAL_PANEL_WIDTH / config.WORKSPACE_MM[0]
        scale_y = SCREEN_HEIGHT / config.WORKSPACE_MM[1]
        px = int(x_mm * scale_x)
        py = int((config.WORKSPACE_MM[1] - y_mm) * scale_y)
        return (px, py)

    def _bbox_to_obstacle_set(self, bbox: BoundingBox) -> set[tuple[int, int]]:
        """Convertit BoundingBox en ensemble de cellules grille (50×50)."""
        cols, rows = config.GRID_SIZE
        cw, ch = config.WEBCAM_MAX_RES
        blocked: set[tuple[int, int]] = set()

        x1 = int(bbox.x / cw * cols)
        y1 = int(bbox.y / ch * rows)
        x2 = int((bbox.x + bbox.w) / cw * cols)
        y2 = int((bbox.y + bbox.h) / ch * rows)

        x1 = max(0, min(x1, cols - 1))
        y1 = max(0, min(y1, rows - 1))
        x2 = max(0, min(x2, cols - 1))
        y2 = max(0, min(y2, rows - 1))

        for gx in range(x1, x2 + 1):
            for gy in range(y1, y2 + 1):
                blocked.add((gx, gy))

        return blocked

    def _update_path_planning(self) -> None:
        """Détecte obstacles et recalcule path si nécessaire."""
        try:
            frame = self._frame_queue.get_nowait()
        except queue.Empty:
            return

        bbox = detect_obstacle(frame, allow_aruco=True)

        if bbox is None:
            if self._fsm.path_blocked:
                self._fsm.transition(Event.PATH_FOUND)
            self.segments = self.original_segments.copy()
            self.current_path = []
            return

        obstacle_set = self._bbox_to_obstacle_set(bbox)

        if not self.segments:
            return

        start_mm = (self.original_segments[0].start.x, self.original_segments[0].start.y)
        end_mm = (self.original_segments[-1].end.x, self.original_segments[-1].end.y)

        path = find_path(start_mm, end_mm, [bbox])

        if path is None:
            if not self._fsm.path_blocked:
                self._fsm.transition(Event.PATH_BLOCKED)
            self.current_path = []
        else:
            if self._fsm.path_blocked:
                self._fsm.transition(Event.PATH_FOUND)
            self.current_path = [(p.x, p.y) for p in path]

    def _update_fsm(self, events: list[dict]) -> None:
        """Met à jour la FSM, gère throttle A*.

        Args:
            events: Liste des events acoustiques reçus.
        """
        for evt in events:
            if evt.get("type") == "acoustic":
                severity = evt.get("severity")
                if severity == "warn":
                    try:
                        self._fsm.transition(Event.ACOUSTIC_WARN)
                    except Exception:
                        pass
                elif severity == "critical":
                    try:
                        self._fsm.transition(Event.ACOUSTIC_CRITICAL)
                    except Exception:
                        pass

        now = time.time()
        if now - self.last_planner_ts >= self.planner_throttle_ms / 1000:
            self._update_path_planning()
            self.last_planner_ts = now

    def _draw_grid(self, surface: pygame.Surface) -> None:
        """Dessine grille légère sur le panel."""
        for x in range(0, VISUAL_PANEL_WIDTH, 50):
            pygame.draw.line(surface, (0x33, 0x33, 0x44), (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, 50):
            pygame.draw.line(surface, (0x33, 0x33, 0x44), (0, y), (VISUAL_PANEL_WIDTH, y))

    def _draw_segments(self, surface: pygame.Surface, segments: list[Segment], color: tuple) -> None:
        """Dessine segments G-code."""
        for seg in segments:
            start_px = self._mm_to_pixel(seg.start.x, seg.start.y)
            end_px = self._mm_to_pixel(seg.end.x, seg.end.y)
            pygame.draw.line(surface, color, start_px, end_px, 3)

    def _draw_path(self, surface: pygame.Surface, path: list[tuple], color: tuple) -> None:
        """Dessine path A* (liste de coordonnées grille)."""
        if len(path) < 2:
            return

        points = []
        for grid_x, grid_y in path:
            x_mm = grid_x * (config.WORKSPACE_MM[0] / config.GRID_SIZE[0])
            y_mm = grid_y * (config.WORKSPACE_MM[1] / config.GRID_SIZE[1])
            px, py = self._mm_to_pixel(x_mm, y_mm)
            points.append((px, py))

        pygame.draw.lines(surface, color, False, points, 3)

    def _draw_path_blocked_overlay(self, surface: pygame.Surface) -> None:
        """Overlay 'CHEMIN IMPOSSIBLE' en magenta."""
        font = pygame.font.Font(None, 64)
        text = font.render("CHEMIN IMPOSSIBLE", True, COLOR_MAGENTA)
        rect = text.get_rect(center=(VISUAL_PANEL_WIDTH // 2, SCREEN_HEIGHT // 2))
        surface.blit(text, rect)

        pygame.draw.rect(surface, COLOR_SURFACE, (300, 400, 168, 40))
        font_small = pygame.font.Font(None, 32)
        text_btn = font_small.render("Réessayer", True, COLOR_TEXT)
        rect_btn = text_btn.get_rect(center=(384, 420))
        surface.blit(text_btn, rect_btn)

    def _draw_webcam_preview(self, surface: pygame.Surface) -> None:
        """Affiche preview webcam 160×120 en coin inférieur droit."""
        try:
            frame = self._frame_queue.get_nowait()
            small = cv2.resize(frame, (160, 120))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            preview = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
            surface.blit(preview, (VISUAL_PANEL_WIDTH - 170, SCREEN_HEIGHT - 130))
        except queue.Empty:
            pygame.draw.rect(surface, (0x33, 0x33, 0x33),
                           (VISUAL_PANEL_WIDTH - 170, SCREEN_HEIGHT - 130, 160, 120))
            font = pygame.font.Font(None, 24)
            text = font.render("No camera", True, COLOR_TEXT)
            surface.blit(text, (VISUAL_PANEL_WIDTH - 150, SCREEN_HEIGHT - 80))

    def _render_visual_panel(self, surface: pygame.Surface) -> None:
        """Rend le panel visuel gauche (768×720) avec G-code, obstacles, path."""
        surface.fill(COLOR_SURFACE)

        self._draw_grid(surface)

        if hasattr(self, '_gcode_error') and self._gcode_error:
            font = pygame.font.Font(None, 32)
            lines = self._gcode_error.split('\n')
            for i, line in enumerate(lines):
                text = font.render(line, True, COLOR_ALERT)
                surface.blit(text, (20, 20 + i * 40))
            return

        if not self._fsm.path_blocked:
            self._draw_segments(surface, self.original_segments, COLOR_ALERT)

        if self.current_path:
            self._draw_path(surface, self.current_path, COLOR_PRIMARY)

        if self.segments:
            start_px = self._mm_to_pixel(self.segments[0].start.x, self.segments[0].start.y)
            pygame.draw.circle(surface, COLOR_PRIMARY, start_px, 8)

        if self._fsm.path_blocked and not self.current_path:
            self._draw_path_blocked_overlay(surface)

        self._draw_webcam_preview(surface)

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
