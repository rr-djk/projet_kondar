# SENTINELLE CNC — Machine Autonomy Copilot

> *What if your CNC machine kept running while you went to lunch?*

---

## The Problem

Every CNC operator knows this moment: a new program, a new part, first run. You set up your clamps, load your stock, launch the program — and then you stand there. Hand near the E-stop. Watching. Waiting. Because the programmer wrote the code in a perfect digital world, and the physical world doesn't always cooperate.

That's 20–30 minutes of lost productivity. Per first run. Every time.

I worked as a CNC operator — nights, 3–4 machines at a time, one programmer who wasn't there when I needed them. I lived this problem. I also watched junior operators miss things that experienced operators catch by sound — a subtle change in cutting tone that signals tool overload before damage accumulates. That knowledge takes years to build. Most shops can't afford to wait.

The tools that exist today (enterprise collision detection systems, acoustic monitoring SaaS) are built for large industrial customers. They cost as much as a machine upgrade. And when they detect a problem, they stop the job.

**SENTINELLE does something different: it routes around the problem.**

---

## The Vision

SENTINELLE is an external, plug-and-play copilot for CNC machines. Two pillars:

**Visual Pillar — Collision Prevention**
A camera watches the real workspace. When the tool's predicted path intersects a physical obstacle (a misplaced clamp, a fixture the programmer didn't know about), SENTINELLE detects the conflict and proposes an alternative path — before the crash happens. The operator confirms, the machine reroutes, the job continues.

**Acoustic Pillar — Cut Health Monitoring**
A microphone listens to the machine. Experienced operators hear when something is wrong. SENTINELLE packages that knowledge: it learns the baseline sound signature of a healthy cut and alerts the operator when the frequency signature shifts — tool overload, wear, or unexpected material resistance.

Together: the machine can run while the operator steps away. The junior operator gets the situational awareness of a senior. The shop doesn't stop every time something unexpected happens.

---

## What Makes This Different

Every competitor stops the machine when something goes wrong.

SENTINELLE is designed to keep the job running.

The operator stays in the loop — the system proposes, the human confirms. That's not a workaround. That's the right design. It keeps liability with the operator, and it keeps the machine productive.

---

## Status

Active development. Visual demo complete and running.

- [x] Acoustic pillar — FFT baseline + anomaly detection, WebSocket server (Raspberry Pi)
- [x] Visual pillar simulator — 2D path replanning demo, A* obstacle avoidance
- [x] Unified interface — pygame dashboard, real-time overlays, FSM-driven alerts
- [x] 51 unit tests, GitHub CI
- [ ] Physical CNC integration (hardware test + demo video)

---

## Quick Start (visual demo, no hardware required)

```bash
pip install -r requirements.txt
python3 -m sentinelle.main_laptop demo.nc
```

The simulator opens at 1280×720. Left panel: G-code toolpath + webcam obstacle detection. Right panel: acoustic pillar status + alerts.

1. Press **BASELINE** to calibrate the acoustic detector (10s capture)
2. Hold an orange object in front of the webcam — the path replans in real-time
3. `SPACE` acknowledges acoustic alerts, `R` resets after emergency stop

To test the acoustic pillar without a Raspberry Pi:
```bash
python3 -m sentinelle.ipc.mock_server  # synthetic acoustic events on ws://localhost:8765
```

---

Design document: [`docs/DESIGN.md`](./docs/DESIGN.md)
Architecture: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)

---

## Target

Small CNC shops. 4–10 people. Machines that work fine and don't need replacing — they need augmenting. The kind of shop that can't justify a $250k machine upgrade to get a feature that should cost a fraction of that.

---

*Built by someone who worked the night shift.*
