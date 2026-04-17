# TILTFIRE — Boss Training

A fast-paced, 1v1 top-down arena shooter built with Python and Pygame where you face off against an adaptive AI boss across a split arena.

---

## Overview

TILTFIRE drops you into a divided arena separated by an invisible horizontal wall. You control the bottom half; the Boss owns the top. Neither side can cross the divider — positioning, timing, and charge management are everything.

The Boss isn't scripted. It has a randomly assigned **personality**, learns from your play style, and adapts its aggression mid-fight. Every run feels different.

---

## Gameplay

### Core Loop

1. **Move** around your half of the arena using WASD with momentum-based ("tilt") physics.
2. **Aim** with your mouse — your ship rotates to face the cursor.
3. **Charge** a shot by holding Space or Left Mouse Button. Release to fire.
4. **Survive** the Boss's projectiles while whittling its health down to zero.

### Charge System

Charging is the heart of the game. How long you hold determines everything:

| Charge Level | Effect |
|---|---|
| Low | Small, fast projectile, low damage, costs 1 ammo |
| Medium | Balanced size, speed, and damage |
| Full | Large, high-damage projectile — costs up to full magazine |

Charge also scales **ammo consumption** — a fully charged shot can burn multiple bullets at once. Run out mid-fight and you're defenseless until the reload cycle completes.

### Ammo & Reloading

- You carry **7 bullets** (same as the Boss).
- Bullets reload **one at a time** (~0.66 seconds per bullet).
- Reloading starts automatically after 2.5 seconds of inactivity, or instantly when your mag hits zero.
- Press **R** to manually trigger a reload at any time.
- You can still charge during a reload — any bullets that have already reloaded are available immediately.

---

## The Boss AI

The Boss is the centerpiece of the game. It runs a full state machine with personality traits and adaptive learning.

### Personalities (randomly assigned each run)

| Personality | Preferred Range | Behavior |
|---|---|---|
| **Sniper** | Far (340px) | Hangs back, fires precise long-range shots |
| **Brawler** | Close (220px) | Rushes in, fires frequently, high aggression |
| **Trickster** | Medium (280px) | Mixes fake charges with real ones to bait you |
| **Adaptive** | Medium (260px) | Balanced — shifts behavior based on your accuracy |

### AI Behaviors

- **Comfort band movement** — the Boss always tries to stay at its preferred distance from you. Inside the band it drifts laterally; outside it closes or retreats.
- **Predictive aiming** — the Boss leads its shots based on your current velocity, not just your position.
- **Fake charges** — a visual wind-up that fires nothing, designed to make you dodge at the wrong moment.
- **Panic mode** — when ammo drops to ≤ 2 bullets, the Boss fires faster and more desperately.
- **Proactive retreat** — the Boss periodically disengages to reset spacing, mimicking human hesitation.
- **Adaptive aggression** — if you land more than 50% of your shots, the Boss dials back aggression; if you miss, it escalates. This learning runs continuously throughout the fight.

### Difficulty Modifiers

| Difficulty | Boss HP | Move Speed | Aggression |
|---|---|---|---|
| Easy | 240 | ×0.9 | ×0.85 |
| Normal | 300 | ×1.0 | ×1.0 |
| Hard | 420 | ×1.2 | ×1.2 |

---

## Controls

| Input | Action |
|---|---|
| `W A S D` | Move (momentum-based) |
| Mouse | Aim |
| Hold `LMB` or `Space` | Charge shot |
| Release `LMB` or `Space` | Fire |
| `R` | Manual reload |
| `Esc` | Quit |

---

## Visual Feedback

- **Charge ring** — a purple glow ring around your ship grows as charge builds.
- **Hit flash** — your screen flashes red when you take damage; the Boss shakes and flickers on hit.
- **Particle bursts** — purple particles on boss hits, orange/red on player hits.
- **Boss health bar** — color-coded (green → yellow → red) displayed at the top center.
- **Ammo HUD** — live ammo count and per-bullet reload progress for both you and the Boss.
- **Divider flash** — the arena wall flashes at game start to orient you.

---

## Requirements

```
Python 3.8+
pygame
numpy  (optional — enables procedural sound effects)
```

Install dependencies:

```bash
pip install pygame numpy
```

---

## Running the Game

```bash
python titlfire.py
```

---

## Project Structure

```
tiltfire/
├── titlfire.py        # Main game (single-file)
├── assets/
│   └── energy_vfx.png
└── README.md
```

---

## Tips

- **Don't spam shots** — a fully charged blast does up to 8× the damage of a tap shot.
- **Watch the Boss's ring** — a growing red ring means it's about to fire; a fake charge peaks and disappears without a shot.
- **Strafe laterally** — the Boss's predictive aim punishes straight-line movement.
- **Keep ammo above zero** — an empty mag leaves you completely unable to retaliate for over a second per bullet needed.
- **Hard mode Boss has 420 HP** — you'll need near-perfect charge discipline to win.
