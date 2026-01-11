# Vertical Vanguard

A compact 64×64 retro vertical shooter built with Python and Pygame.

## Description

Vertical Vanguard is a classic vertical scrolling shooter game with a minimalist aesthetic. The game runs at a fixed internal resolution of 64×64 pixels and scales up for display, creating a distinctive retro look. Battle through waves of enemies, collect powerups, and manage your resources to achieve the highest score possible.

## Features

- **Retro 64×64 Graphics**: Authentic pixel-perfect rendering scaled up for modern displays
- **Dynamic Difficulty**: Level-based progression system that increases enemy speed and spawn rates over time
- **Resource Management**: 
  - Fuel: Drains over time and affects movement speed
  - Ammo: Required for shooting, refilled by pickups
  - Health: Prevents instant death, allowing for tactical gameplay
- **Powerup System**:
  - Speed Boost: Temporary movement speed increase
  - Rapid Fire: Faster shooting rate
  - Spread Shot: Triple-bullet attack pattern
  - Health Restoration: Recover hit points
- **Enemy AI**: Enemies fire back after 20 seconds, with increasing difficulty
- **Lives System**: Start with 3 lives, lose one when health depletes
- **Particle Effects**: Visual feedback for explosions and pickups

## Installation

### Requirements

- Python 3.x
- Pygame

### Setup

1. Clone the repository:
```bash
git clone https://github.com/SimonWaldherr/VerticalVanguardPygame.git
cd VerticalVanguardPygame
```

2. Install Pygame:
```bash
pip install pygame
```

## Usage

Run the game with:
```bash
python VerticalVanguard.py
```

## Controls

- **Arrow Keys** or **WASD**: Move the player ship
- **Spacebar**: Fire bullets (consumes ammo)
- **ESC**: Quit the game

## Gameplay

### Objective
Survive as long as possible while destroying enemy ships to increase your score.

### Resources
- **Ammo** (Green bar): Required to shoot. Collect green pickups to refill.
- **Fuel** (Orange bar): Drains constantly. Low fuel reduces movement speed. Collect orange pickups to refill and gain speed boost.
- **Health** (Red bar): Prevents instant death. Collect red pickups to restore health.

### Powerups
- **Green Pods**: Restore ammo + grant rapid fire
- **Orange Pods**: Restore fuel + grant speed boost
- **Yellow Pods**: Grant spread shot (triple bullets)
- **Red Pods**: Restore health

### Difficulty Progression
- Every 2 minutes, the level increases
- Enemy speed increases per level
- Enemy spawn rate increases
- Enemies start shooting back after 20 seconds

## Technical Details

- **Resolution**: 64×64 internal, 640×640 display (10× scale)
- **Frame Rate**: 60 FPS
- **Game Engine**: Pygame
- **Collision Detection**: Axis-aligned bounding box (AABB)

## License

See repository for license details.

## Credits

Created by Simon Waldherr
