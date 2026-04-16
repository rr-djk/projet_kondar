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

        # État baseline
        self._baseline_capturing = False
        self._baseline_progress = 0.0  # 0.0 à 1.0
        self._baseline_start_ts: float | None = None
        self._baseline_ready = False  # Pour badge "Baseline active"

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

        # État acoustique (T-3.3)
        self._last_acoustic_ts = time.time()  # Dernier event reçu
        self._critical_start_ts = None  # Quand l'alerte critical a commencé
        self._acoustic_offline_timeout = 5.0  # Secondes avant badge OFFLINE

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
        """Gère événements pygame."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._running = False

                elif event.key == pygame.K_SPACE:
                    # Acquittement pour ALERT_CRITICAL ou PAUSED_ACOUSTIC
                    if self._fsm.state in (
                        State.ALERT_CRITICAL, State.PAUSED_ACOUSTIC
                    ):
                        # Vérifier que 3s se sont écoulées
                        if self._critical_start_ts:
                            elapsed = time.time() - self._critical_start_ts
                            if elapsed >= 3.0:
                                self._fsm.transition(Event.DISMISS)
                                self._critical_start_ts = None

                elif event.key == pygame.K_r:
                    # Reset d'EMERGENCY_STOP
                    if self._fsm.state == State.EMERGENCY_STOP:
                        self._fsm.transition(Event.RESET)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Clic gauche
                    mouse_pos = event.pos
                    self._handle_mouse_click(mouse_pos)

    def _consume_queue(self) -> list[AcousticEvent]:
        """Lit la queue WebSocket et parse les events.

        Returns:
            Liste des AcousticEvent reçus.
        """
        from sentinelle.protocol import from_json

        events = []
        while True:
            msg = self._acoustic.get_event()
            if msg is None:
                break
            if isinstance(msg, str):
                try:
                    event = from_json(msg)
                    events.append(event)
                    self._last_acoustic_ts = time.time()
                except Exception as e:
                    print(f"Warning: Invalid message: {e}")
            elif isinstance(msg, dict) and msg.get("type") == "status":
                self._acoustic_connected = msg.get("connected", False)
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

    def _handle_mouse_click(self, pos: tuple[int, int]) -> None:
        """Gère les clics souris sur boutons."""
        # Vérifier clic sur bouton BASELINE
        # Bouton à (20, 250) dans panel droit qui commence à x=768
        button_rect = pygame.Rect(768 + 20, 250, 120, 40)

        if button_rect.collidepoint(pos):
            self._start_baseline()

    def _start_baseline(self) -> None:
        """Démarre la capture de baseline."""
        # Vérifier état autorisé
        if self._fsm.state not in (State.IDLE, State.RUNNING_NORMAL):
            print("Cannot start baseline: invalid state", self._fsm.state)
            return

        if self._baseline_capturing or self._baseline_ready:
            print("Baseline already captured or in progress")
            return

        # Démarrer capture
        self._baseline_capturing = True
        self._baseline_progress = 0.0
        self._baseline_start_ts = time.time()

        # Transition FSM
        self._fsm.transition(Event.START)
        print("Baseline capture started")

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

    def _update_fsm(self, events: list[AcousticEvent]) -> None:
        """Met à jour FSM et gère baseline."""
        now = time.time()

        # Gestion baseline capture
        if self._baseline_capturing and self._baseline_start_ts is not None:
            elapsed = now - self._baseline_start_ts
            duration = config.BASELINE_DURATION_S  # 10s

            self._baseline_progress = min(1.0, elapsed / duration)

            if elapsed >= duration:
                # Capture terminée
                self._baseline_capturing = False
                self._baseline_ready = True
                self._baseline_progress = 1.0

                # Transition FSM
                self._fsm.transition(Event.BASELINE_DONE)
                print("Baseline capture completed")

        # Traiter events acoustiques
        for event in events:
            if event.severity == "warn":
                if self._fsm.state not in (
                    State.ALERT_WARN, State.ALERT_CRITICAL,
                    State.PAUSED_ACOUSTIC, State.AUTO_OPTIMIZE
                ):
                    try:
                        self._fsm.transition(Event.ACOUSTIC_WARN)
                    except Exception:
                        pass

            elif event.severity == "critical":
                if self._fsm.state not in (
                    State.ALERT_CRITICAL, State.PAUSED_ACOUSTIC, State.EMERGENCY_STOP
                ):
                    try:
                        self._fsm.transition(Event.ACOUSTIC_CRITICAL)
                        self._critical_start_ts = now  # Pour le 3s d'attente
                    except Exception:
                        pass

        # Gestion AUTO_OPTIMIZE: retour à RUNNING_NORMAL après 5s sans alerte
        if self._fsm.state == State.AUTO_OPTIMIZE:
            if now - self._last_acoustic_ts > 5.0:
                try:
                    self._fsm.transition(Event.OPTIMIZE_COMPLETE)
                except Exception:
                    pass

        # Path planning (existant)
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
        """Rend le panel droit avec données acoustiques et bouton BASELINE."""
        surface.fill(COLOR_SURFACE)

        # Titre
        font_title = pygame.font.Font(None, 36)
        title = font_title.render("Pilier Acoustique", True, COLOR_TEXT)
        surface.blit(title, (20, 20))

        # Bouton BASELINE
        self._draw_baseline_button(surface)

        # Badge "Baseline active" si applicable
        if self._baseline_ready:
            self._draw_baseline_active_badge(surface)

        # Badge ACOUSTIC OFFLINE si pas d'event depuis 5s
        now = time.time()
        if now - self._last_acoustic_ts > self._acoustic_offline_timeout:
            self._draw_offline_badge(surface)
        else:
            self._draw_online_badge(surface)

        # Affichage état FSM
        font_state = pygame.font.Font(None, 28)
        state_text = f"État: {self._fsm.state.value}"
        color = COLOR_TEXT
        if self._fsm.state == State.ALERT_CRITICAL:
            color = COLOR_ALERT
        elif self._fsm.state == State.ALERT_WARN:
            color = (0xFF, 0xCC, 0x00)  # Jaune
        text = font_state.render(state_text, True, color)
        surface.blit(text, (20, 110))

        # Overlay si alerte active
        if self._fsm.state == State.ALERT_CRITICAL:
            self._draw_critical_overlay(surface)
        elif self._fsm.state == State.ALERT_WARN:
            self._draw_warn_overlay(surface)
        elif self._fsm.state == State.EMERGENCY_STOP:
            self._draw_emergency_overlay(surface)
        elif self._fsm.state == State.AUTO_OPTIMIZE:
            self._draw_optimize_overlay(surface)

    def _draw_offline_badge(self, surface: pygame.Surface) -> None:
        """Badge rouge 'ACOUSTIC OFFLINE'."""
        pygame.draw.rect(surface, COLOR_ALERT, (20, 60, 200, 30))
        font = pygame.font.Font(None, 24)
        text = font.render("ACOUSTIC OFFLINE", True, (0xFF, 0xFF, 0xFF))
        surface.blit(text, (30, 67))

    def _draw_online_badge(self, surface: pygame.Surface) -> None:
        """Badge vert 'ACOUSTIC ONLINE'."""
        pygame.draw.rect(surface, (0x44, 0xFF, 0x44), (20, 60, 200, 30))
        font = pygame.font.Font(None, 24)
        text = font.render("ACOUSTIC ONLINE", True, (0x00, 0x00, 0x00))
        surface.blit(text, (30, 67))

    def _draw_critical_overlay(self, surface: pygame.Surface) -> None:
        """Indicateur alerte critical dans panel droit."""
        font = pygame.font.Font(None, 48)
        text = font.render("CRITIQUE", True, COLOR_ALERT)
        surface.blit(text, (20, 150))

        # Compte à rebours 3s
        if self._critical_start_ts:
            elapsed = time.time() - self._critical_start_ts
            remaining = max(0, 3.0 - elapsed)
            font2 = pygame.font.Font(None, 32)
            countdown = font2.render(
                f"Attendre {remaining:.1f}s", True, COLOR_TEXT
            )
            surface.blit(countdown, (20, 200))

            if remaining <= 0:
                ok_text = font2.render("Appuyer ESPACE", True, COLOR_PRIMARY)
                surface.blit(ok_text, (20, 230))

    def _draw_warn_overlay(self, surface: pygame.Surface) -> None:
        """Indicateur alerte warn (jaune)."""
        font = pygame.font.Font(None, 36)
        text = font.render("AVERTISSEMENT", True, (0xFF, 0xCC, 0x00))
        surface.blit(text, (20, 150))

    def _draw_emergency_overlay(self, surface: pygame.Surface) -> None:
        """Overlay EMERGENCY STOP."""
        font_big = pygame.font.Font(None, 48)
        text = font_big.render("ARRET D'URGENCE", True, COLOR_ALERT)
        surface.blit(text, (20, 150))

        font_small = pygame.font.Font(None, 28)
        instr = font_small.render("Appuyer 'R' pour reset", True, COLOR_TEXT)
        surface.blit(instr, (20, 210))

    def _draw_optimize_overlay(self, surface: pygame.Surface) -> None:
        """Overlay AUTO_OPTIMIZE."""
        font = pygame.font.Font(None, 32)
        text = font.render("AUTO-OPTIMISATION", True, COLOR_PRIMARY)
        surface.blit(text, (20, 150))

        font2 = pygame.font.Font(None, 24)
        sub = font2.render("Feed rate -20%", True, COLOR_TEXT)
        surface.blit(sub, (20, 190))

    def _draw_baseline_button(self, surface: pygame.Surface) -> None:
        """Dessine le bouton BASELINE avec état."""
        # Position: sous le titre, x=20, y=250
        button_rect = pygame.Rect(20, 250, 120, 40)

        # Couleur selon état
        if self._baseline_capturing:
            # En cours: fond gris
            color = (0x66, 0x66, 0x66)
        elif self._baseline_ready:
            # Déjà capturé: vert
            color = (0x44, 0xAA, 0x44)
        elif self._fsm.state in (State.IDLE, State.RUNNING_NORMAL):
            # Actif: cyan
            color = COLOR_PRIMARY
        else:
            # Désactivé: gris foncé
            color = (0x44, 0x44, 0x44)

        # Dessiner bouton
        pygame.draw.rect(surface, color, button_rect, border_radius=4)
        pygame.draw.rect(surface, COLOR_TEXT, button_rect, 2, border_radius=4)

        # Texte
        font = pygame.font.Font(None, 24)
        if self._baseline_capturing:
            text = font.render("CAPTURE...", True, COLOR_TEXT)
        elif self._baseline_ready:
            text = font.render("BASELINE ✓", True, COLOR_TEXT)
        else:
            text = font.render("BASELINE", True, (0x00, 0x00, 0x00))

        text_rect = text.get_rect(center=button_rect.center)
        surface.blit(text, text_rect)

        # Barre de progression si capture en cours
        if self._baseline_capturing:
            self._draw_baseline_progress(surface, button_rect)

    def _draw_baseline_progress(self, surface: pygame.Surface, button_rect: pygame.Rect) -> None:
        """Barre de progression sous le bouton."""
        progress_width = 200
        progress_height = 10
        x = button_rect.x
        y = button_rect.bottom + 10

        # Fond
        pygame.draw.rect(surface, (0x33, 0x33, 0x33), (x, y, progress_width, progress_height))

        # Remplissage
        fill_width = int(progress_width * self._baseline_progress)
        pygame.draw.rect(surface, COLOR_PRIMARY, (x, y, fill_width, progress_height))

        # Pourcentage
        font = pygame.font.Font(None, 20)
        pct = font.render(f"{int(self._baseline_progress * 100)}%", True, COLOR_TEXT)
        surface.blit(pct, (x + progress_width + 10, y))

    def _draw_baseline_active_badge(self, surface: pygame.Surface) -> None:
        """Badge vert 'Baseline active'."""
        pygame.draw.rect(surface, (0x44, 0xAA, 0x44), (150, 250, 140, 30))
        font = pygame.font.Font(None, 20)
        text = font.render("Baseline active", True, COLOR_TEXT)
        surface.blit(text, (160, 257))

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

            # Overlay rouge prioritaire si critical/emergency
            if self._fsm.state in (State.ALERT_CRITICAL, State.EMERGENCY_STOP):
                overlay = pygame.Surface(
                    (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA
                )
                overlay.fill((0xFF, 0x52, 0x52, 128))  # Rouge 50% alpha
                self._screen.blit(overlay, (0, 0))

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
