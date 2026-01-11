import random
import pygame

# Simple 64x64 vertical shooter implemented with PyGame.
# The game logic runs at an internal 64x64 resolution and is
# scaled up for display. Comments explain key constants,
# data structures, and the main game loop.

# --- Strict 64x64 internal resolution ---
W, H = 64, 64  # internal "real" pixels
SCALE = 10  # window scale factor (display-only)
FPS = 60

# Sprite / collision sizes (in internal pixels)
PLAYER_W, PLAYER_H = 3, 3
ENEMY_W, ENEMY_H = 3, 3
BULLET_W, BULLET_H = 1, 2

# Resources / pickups
# Fuel and ammo mechanics:
#  - Fuel drains over time and affects movement speed.
#  - Ammo is consumed per shot and can be refilled by pickups.
FUEL_CONSUMPTION_PER_SEC = 1.8
# maximum resource capacities (balance these to tune difficulty)
MAX_FUEL = 160.0
MAX_AMMO = 35
# How often (frames) global random pickups may spawn and how fast
# they fall when spawned.
PICKUP_SPAWN_INTERVAL = 240  # frames (more frequent pickups)
PICKUP_SPEED = 0.4
# Colors used for pickups and HUD bars (matching colors improves UX)
FUEL_COLOR = (255, 180, 60)
AMMO_COLOR = (140, 255, 140)
SPREAD_COLOR = (220, 220, 80)

# Pickup effects / tuning
# Values controlling how much pickups restore and how long
# temporary powerups last. Tweak these to balance gameplay.
FUEL_PICKUP_AMOUNT = 60
AMMO_PICKUP_AMOUNT = 12
SPEED_BOOST_MULT = 1.6
SPEED_BOOST_DURATION = 4.0  # seconds
RAPID_FIRE_FACTOR = 0.5
RAPID_FIRE_DURATION = 5.0  # seconds
SPREAD_DURATION = 60.0  # seconds (strewn / spread ammo)
# Particle burst settings for pickup feedback
PARTICLE_COUNT = 10
PARTICLE_TTL = 0.6  # seconds

# Enemy shooting and difficulty tuning
# Controls when enemies begin firing, how often they shoot, and
# the chance/weights of item drops on enemy death.
ENEMY_SHOOT_START_TIME = 20.0  # seconds before enemies start shooting back
# Base enemy fire rate (shots per second per enemy)
ENEMY_FIRE_RATE = 0.08
# Enemy projectile speed (reduced for fairness)
ENEMY_BULLET_SPEED = 0.9
# Leveling system: every LEVEL_DURATION seconds the level increases.
# Use level-based increments to control pacing predictably.
LEVEL_DURATION = 120.0  # seconds per level (2 minutes)
ENEMY_SPEED_PER_LEVEL = 0.06  # speed increase per completed level
# Chance that a killed enemy will drop a pickup and the relative
# weights for fuel / ammo / spread pickups.
DROP_CHANCE_PER_KILL = 0.45  # higher chance to drop a pickup on kill
DROP_WEIGHTS = [
    ("fuel", 0.45),
    ("ammo", 0.45),
    ("spread", 0.10),
]  # distribution of drops


def clamp(v, lo, hi):
    """Clamp value v into the inclusive range [lo, hi].

    Used for keeping positions inside the 64x64 playfield.
    """
    return lo if v < lo else hi if v > hi else v


def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    """Axis-aligned bounding box collision test.

    Returns True when rectangle A (ax,ay,aw,ah) overlaps
    rectangle B (bx,by,bw,bh). Used for bullets, pickups, and
    player/enemy collisions.
    """
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def main():
    pygame.init()
    pygame.display.set_caption("64x64 Vertical Scrolling Shooter (PyGame)")

    # Window is just a scaled view; the *game* is 64x64.
    window = pygame.display.set_mode((W * SCALE, H * SCALE))
    clock = pygame.time.Clock()

    # This is the only surface we draw onto (64x64 RGB).
    screen64 = pygame.Surface((W, H))  # default is RGB

    # Minimal font (rendered onto 64x64 too)
    font = pygame.font.Font(None, 12)

    # --- Player state ---
    # Stored as a dict for simplicity. Keys:
    #  - x,y: integer-ish position in the internal 64x64 world
    #  - fire_cd: frames until next allowed shot
    #  - lives: remaining lives
    #  - fuel / ammo: resource meters
    player = {
        "x": W // 2 - 1,
        "y": H - 10,
        "fire_cd": 0,
        "lives": 3,
        "fuel": MAX_FUEL,
        "ammo": MAX_AMMO,
    }

    # --- Entity lists ---
    # bullets: list of player projectiles
    # enemies: list of enemy ships
    # enemy_bullets: enemy projectiles the player must avoid
    # *_pods: pickup items for fuel/ammo/spread
    # particles: small visual effects for pickups
    bullets = []  # dicts: {x,y,vx,vy}
    enemies = []  # dicts: {x,y,dx}
    enemy_bullets = []  # dicts: {x,y,vx,vy}
    fuel_pods = []  # dicts: {x,y,color}
    ammo_pods = []
    spread_pods = []
    particles = []  # dicts: {x,y,vx,vy,color,ttl}
    score = 0
    frame = 0
    time_s = 0.0

    spawn_interval = 56  # frames (initial, start slower)
    bullet_speed = 2.5  # px/frame upward
    enemy_base_speed = 0.12  # px/frame downward (starts much slower)
    enemy_accel_per_sec = 0.035
    player_base_speed = 1.0  # px/frame
    fire_cooldown_frames = 6  # frames

    running = True
    game_over = False

    while running:
        dt = clock.tick(FPS)
        frame += 1

        # --- Events ---
        # Handle OS/events (window close) and keyboard input.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # `keys` holds current keyboard state. We also accept WASD.
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        # --- Update ---
        # Main game update: handle movement, shooting, spawning, collisions
        if not game_over:
            # Compute directional input: left/right and up/down as -1/0/1
            # Arrow keys or WASD both work.
            dx = (1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0) - (
                1 if (keys[pygame.K_LEFT] or keys[pygame.K_a]) else 0
            )
            dy = (1 if (keys[pygame.K_DOWN] or keys[pygame.K_s]) else 0) - (
                1 if (keys[pygame.K_UP] or keys[pygame.K_w]) else 0
            )

            # update elapsed time in seconds (used to scale difficulty)
            time_s += dt / 1000.0

            # Level-based dynamic difficulty:
            #  - `level` increments every LEVEL_DURATION seconds.
            #  - enemy speed increases per level, and within a level
            #    we interpolate slightly so difficulty ramps smoothly.
            level = int(time_s // LEVEL_DURATION)
            time_in_level = time_s - level * LEVEL_DURATION
            enemy_speed = (
                enemy_base_speed
                + level * ENEMY_SPEED_PER_LEVEL
                + (time_in_level / LEVEL_DURATION) * ENEMY_SPEED_PER_LEVEL
            )
            # spawn interval shortens per level (but clamped)
            spawn_interval = max(20, int(56 - level * 4 - (time_in_level / LEVEL_DURATION) * 2))

            # Player movement is affected by remaining fuel: less fuel
            # means slower movement. A temporary speed boost (from
            # pickups) multiplies the base speed.
            fuel_ratio = max(0.0, min(1.0, player["fuel"] / MAX_FUEL))
            player_speed = player_base_speed * (0.4 + 0.6 * fuel_ratio)
            # temporary speed boost from pickups
            if player.get("speed_boost_time", 0.0) > 0.0:
                player_speed *= SPEED_BOOST_MULT

            player["x"] = clamp(player["x"] + dx * player_speed, 0, W - PLAYER_W)
            player["y"] = clamp(player["y"] + dy * player_speed, 0, H - PLAYER_H)

            if player["fire_cd"] > 0:
                player["fire_cd"] -= 1

            # Firing consumes ammo. If a rapid-fire powerup is active,
            # the cooldown between shots is reduced. If a spread powerup
            # is active, the shot produces three projectiles with slight
            # horizontal velocities to cover a wider area.
            if keys[pygame.K_SPACE] and player["fire_cd"] == 0 and player["ammo"] > 0:
                rapid = player.get("rapid_fire_time", 0.0) > 0.0
                cooldown = max(
                    1, int(fire_cooldown_frames * (RAPID_FIRE_FACTOR if rapid else 1.0))
                )
                player["fire_cd"] = cooldown
                player["ammo"] = max(0, player["ammo"] - 1)

                # Spread shot if active: center + left + right bullets
                if player.get("spread_time", 0.0) > 0.0:
                    # three bullets with small horizontal velocity
                    bullets.append(
                        {
                            "x": float(player["x"] + 1),
                            "y": float(player["y"] - 2),
                            "vx": 0.0,
                            "vy": -bullet_speed,
                        }
                    )
                    bullets.append(
                        {
                            "x": float(player["x"] + 1),
                            "y": float(player["y"] - 2),
                            "vx": -0.6,
                            "vy": -bullet_speed,
                        }
                    )
                    bullets.append(
                        {
                            "x": float(player["x"] + 1),
                            "y": float(player["y"] - 2),
                            "vx": 0.6,
                            "vy": -bullet_speed,
                        }
                    )
                else:
                    bullets.append(
                        {
                            "x": float(player["x"] + 1),
                            "y": float(player["y"] - 2),
                            "vx": 0.0,
                            "vy": -bullet_speed,
                        }
                    )

            # Spawn enemies at a regular interval. As `spawn_interval`
            # decreases over time the game becomes denser/harder.
            if frame % spawn_interval == 0:
                enemies.append(
                    {
                        "x": float(random.randint(0, W - ENEMY_W)),
                        "y": float(-ENEMY_H),
                        "dx": random.choice([-1, 0, 1]),  # tiny wiggle
                    }
                )

            # Occasionally spawn ambient pickups (not from enemy drops).
            # These are independent of drop-on-kill behavior and make the
            # game more forgiving.
            if frame % PICKUP_SPAWN_INTERVAL == 0:
                if random.random() < 0.5:
                    fuel_pods.append(
                        {
                            "x": float(random.randint(0, W - 2)),
                            "y": float(-2),
                            "color": FUEL_COLOR,
                        }
                    )
                else:
                    ammo_pods.append(
                        {
                            "x": float(random.randint(0, W - 2)),
                            "y": float(-2),
                            "color": AMMO_COLOR,
                        }
                    )

            # Update player bullets: apply velocity vector (vx,vy).
            # Most bullets go straight up (-vy). Some powerups add vx.
            for b in bullets:
                b["x"] += b.get("vx", 0.0)
                b["y"] += b.get("vy", -bullet_speed)

            # Move enemies (scrolling)
            for e in enemies:
                e["y"] += enemy_speed
                # small horizontal wiggle every few frames
                if frame % 10 == 0:
                    e["x"] = clamp(e["x"] + e["dx"], 0, W - ENEMY_W)
                    if random.random() < 0.2:
                        e["dx"] = random.choice([-1, 0, 1])

                # Enemy shooting (only after a while)
                # Enemies fire occasional bullets aimed roughly at the
                # player's current x position. This is intentionally
                # simple and occasionally misses to keep gameplay fair.
                if time_s >= ENEMY_SHOOT_START_TIME:
                    # chance to shoot scaled by current level (predictable
                    # difficulty steps). We keep the probability per frame
                    # proportional to `dt` so framerate changes don't affect
                    # firing frequency.
                    shoot_prob = ENEMY_FIRE_RATE * (1.0 + level * 0.12) * (
                        dt / 1000.0
                    )
                    if random.random() < shoot_prob:
                        # aim roughly towards player's current x (with small
                        # inaccuracy)
                        ex = e["x"] + ENEMY_W // 2
                        ey = e["y"] + ENEMY_H
                        vx = (
                            (player["x"] + PLAYER_W // 2 - ex) * 0.05
                            + random.uniform(-0.2, 0.2)
                        )
                        enemy_bullets.append(
                            {
                                "x": float(ex),
                                "y": float(ey),
                                "vx": vx,
                                "vy": ENEMY_BULLET_SPEED,
                            }
                        )

            # Move enemy bullets
            for eb in enemy_bullets:
                eb["x"] += eb.get("vx", 0.0)
                eb["y"] += eb.get("vy", ENEMY_BULLET_SPEED)

            # Move pickups
            for p in fuel_pods:
                p["y"] += PICKUP_SPEED + enemy_speed * 0.2
            for p in ammo_pods:
                p["y"] += PICKUP_SPEED + enemy_speed * 0.2
            for p in spread_pods:
                p["y"] += PICKUP_SPEED + enemy_speed * 0.2

            # Bullet-enemy collisions: check every player bullet against
            # every enemy. On hit, mark both for removal and increase score.
            # There's also a chance the killed enemy will drop a pickup.
            dead_bullets = set()
            dead_enemies = set()
            for bi, b in enumerate(bullets):
                for ei, e in enumerate(enemies):
                    if aabb(
                        b["x"],
                        b["y"],
                        BULLET_W,
                        BULLET_H,
                        e["x"],
                        e["y"],
                        ENEMY_W,
                        ENEMY_H,
                    ):
                        dead_bullets.add(bi)
                        dead_enemies.add(ei)
                        score += 1
                        # Chance to drop a pickup when an enemy dies.
                        if random.random() < DROP_CHANCE_PER_KILL:
                            r = random.random()
                            cum = 0.0
                            for name, w in DROP_WEIGHTS:
                                cum += w
                                if r < cum:
                                    if name == "fuel":
                                        fuel_pods.append(
                                            {
                                                "x": float(e["x"]),
                                                "y": float(e["y"]),
                                                "color": FUEL_COLOR,
                                            }
                                        )
                                    elif name == "ammo":
                                        ammo_pods.append(
                                            {
                                                "x": float(e["x"]),
                                                "y": float(e["y"]),
                                                "color": AMMO_COLOR,
                                            }
                                        )
                                    elif name == "spread":
                                        spread_pods.append(
                                            {
                                                "x": float(e["x"]),
                                                "y": float(e["y"]),
                                                "color": SPREAD_COLOR,
                                            }
                                        )
                                    break
                        break

            # Player-enemy collisions: touching an enemy costs a life
            # and resets the player to a starting position. This is a
            # simple penalty; more complex games might add invulnerability
            # frames or knockback.
            for ei, e in enumerate(enemies):
                if aabb(
                    player["x"],
                    player["y"],
                    PLAYER_W,
                    PLAYER_H,
                    e["x"],
                    e["y"],
                    ENEMY_W,
                    ENEMY_H,
                ):
                    dead_enemies.add(ei)
                    player["lives"] -= 1
                    player["x"] = W // 2 - 1
                    player["y"] = H - 10
                    if player["lives"] <= 0:
                        game_over = True
                    break

            # Enemy bullet -> player collision: simple point-sized bullets
            # damage the player in the same way as touching an enemy.
            dead_enemy_bullets = set()
            for bi, eb in enumerate(enemy_bullets):
                if aabb(
                    player["x"], player["y"], PLAYER_W, PLAYER_H, eb["x"], eb["y"], 1, 1
                ):
                    dead_enemy_bullets.add(bi)
                    player["lives"] -= 1
                    player["x"] = W // 2 - 1
                    player["y"] = H - 10
                    if player["lives"] <= 0:
                        game_over = True
            enemy_bullets = [
                eb
                for i, eb in enumerate(enemy_bullets)
                if i not in dead_enemy_bullets and eb["y"] < H + 2
            ]

            # Player-pickup collisions: when the player touches a pickup
            # it grants its effect (refill or powerup) and spawns a
            # short-lived particle burst for feedback.
            dead_fuel = set()
            for pi, p in enumerate(fuel_pods):
                if aabb(
                    player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2
                ):
                    # refill partially and give a temporary speed boost
                    player["fuel"] = min(MAX_FUEL, player["fuel"] + FUEL_PICKUP_AMOUNT)
                    player.setdefault("speed_boost_time", 0.0)
                    player["speed_boost_time"] = SPEED_BOOST_DURATION
                    score += 0  # could add pickup points
                    # spawn particles
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append(
                            {
                                "x": p["x"],
                                "y": p["y"],
                                "vx": vx,
                                "vy": vy,
                                "color": p["color"],
                                "ttl": PARTICLE_TTL,
                            }
                        )
                    dead_fuel.add(pi)
            fuel_pods = [p for i, p in enumerate(fuel_pods) if i not in dead_fuel]

            dead_ammo = set()
            for pi, p in enumerate(ammo_pods):
                if aabb(
                    player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2
                ):
                    # refill partially and give a temporary rapid-fire
                    player["ammo"] = min(MAX_AMMO, player["ammo"] + AMMO_PICKUP_AMOUNT)
                    player.setdefault("rapid_fire_time", 0.0)
                    player["rapid_fire_time"] = RAPID_FIRE_DURATION
                    score += 0
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append(
                            {
                                "x": p["x"],
                                "y": p["y"],
                                "vx": vx,
                                "vy": vy,
                                "color": p["color"],
                                "ttl": PARTICLE_TTL,
                            }
                        )
                    dead_ammo.add(pi)
            ammo_pods = [p for i, p in enumerate(ammo_pods) if i not in dead_ammo]

            dead_spread = set()
            for pi, p in enumerate(spread_pods):
                if aabb(
                    player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2
                ):
                    # grant spread (strewn / spread ammo) for a duration
                    player.setdefault("spread_time", 0.0)
                    player["spread_time"] = SPREAD_DURATION
                    score += 0
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append(
                            {
                                "x": p["x"],
                                "y": p["y"],
                                "vx": vx,
                                "vy": vy,
                                "color": p["color"],
                                "ttl": PARTICLE_TTL,
                            }
                        )
                    dead_spread.add(pi)
            spread_pods = [p for i, p in enumerate(spread_pods) if i not in dead_spread]

            # Cleanup offscreen
            bullets = [
                b
                for i, b in enumerate(bullets)
                if i not in dead_bullets and b["y"] > -BULLET_H
            ]
            enemies = [
                e
                for i, e in enumerate(enemies)
                if i not in dead_enemies and e["y"] < H + ENEMY_H
            ]
            fuel_pods = [p for p in fuel_pods if p["y"] < H + 2]
            ammo_pods = [p for p in ammo_pods if p["y"] < H + 2]

            # Move particles and cleanup
            # Particles are purely visual and have a TTL (time-to-live).
            # They drift with a small gravity-like effect for flair.
            new_particles = []
            for part in particles:
                part["x"] += part["vx"]
                part["y"] += part["vy"]
                part["vy"] += 0.02  # gravity-ish
                part["ttl"] -= dt / 1000.0
                if part["ttl"] > 0:
                    new_particles.append(part)
            particles[:] = new_particles

            # Consume fuel over time
            player["fuel"] = max(
                0.0, player["fuel"] - FUEL_CONSUMPTION_PER_SEC * (dt / 1000.0)
            )

            # Update powerup timers
            if player.get("rapid_fire_time", 0.0) > 0.0:
                player["rapid_fire_time"] = max(
                    0.0, player["rapid_fire_time"] - dt / 1000.0
                )
            if player.get("speed_boost_time", 0.0) > 0.0:
                player["speed_boost_time"] = max(
                    0.0, player["speed_boost_time"] - dt / 1000.0
                )
            if player.get("spread_time", 0.0) > 0.0:
                player["spread_time"] = max(0.0, player["spread_time"] - dt / 1000.0)

        # --- Render (ONLY onto 64x64) ---
        # All drawing happens on the 64x64 surface and then is
        # scaled up to the window size. Keep rendering cheap and
        # avoid anti-aliasing to preserve the pixel aesthetic.
        # Simple scrolling-star background (still 64x64)
        screen64.fill((0, 0, 0))
        # deterministic tiny stars (gives a sense of vertical motion)
        for i in range(18):
            sx = (i * 13 + 7) % W
            sy = (i * 19 + frame) % H
            screen64.set_at((sx, sy), (40, 40, 40))

        # Draw player bullets (white). Use integer positions to avoid
        # blurring when scaling up.
        for b in bullets:
            pygame.draw.rect(
                screen64,
                (255, 255, 255),
                (int(b["x"]), int(b["y"]), BULLET_W, BULLET_H),
            )

        # Draw enemies (red)
        for e in enemies:
            pygame.draw.rect(
                screen64, (220, 60, 60), (int(e["x"]), int(e["y"]), ENEMY_W, ENEMY_H)
            )

        # Draw enemy bullets (smaller, orange)
        for eb in enemy_bullets:
            pygame.draw.rect(
                screen64, (240, 140, 80), (int(eb["x"]), int(eb["y"]), 1, 1)
            )

        # Draw player (cyan)
        pygame.draw.rect(
            screen64,
            (60, 220, 220),
            (int(player["x"]), int(player["y"]), PLAYER_W, PLAYER_H),
        )

        # Draw particles (on top). We fade them by multiplying RGB by
        # alpha derived from remaining TTL.
        for part in particles:
            alpha = max(0.0, part["ttl"] / PARTICLE_TTL)
            c = part["color"]
            col = (int(c[0] * alpha), int(c[1] * alpha), int(c[2] * alpha))
            screen64.set_at((int(part["x"]), int(part["y"])), col)

        # Draw pickups (fuel, ammo, spread) — small 2x2 colored squares.
        for p in fuel_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))
        for p in ammo_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))
        for p in spread_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))

        # HUD (tiny)

        # HUD (tiny): score and lives at top-left
        hud = font.render(f"{score}  L{player['lives']}", True, (200, 200, 200))
        screen64.blit(hud, (1, 1))

        # Resource bars at bottom: fuel (left) and ammo (right).
        # Bars are small to keep the UI unobtrusive but still readable
        # at the 64x64 resolution.
        pad = 2
        total_w = W - pad * 2
        half_w = (total_w - 2) // 2
        bar_h = 4
        # Fuel bar (left)
        fx = pad
        fy = H - bar_h - 1
        pygame.draw.rect(screen64, (30, 30, 30), (fx, fy, half_w, bar_h))
        fuel_w = int(half_w * (player["fuel"] / MAX_FUEL))
        pygame.draw.rect(screen64, FUEL_COLOR, (fx, fy, fuel_w, bar_h))
        # Ammo bar (right)
        ax = pad + half_w + 2
        ay = fy
        pygame.draw.rect(screen64, (30, 30, 30), (ax, ay, half_w, bar_h))
        ammo_w = int(half_w * (player["ammo"] / MAX_AMMO))
        pygame.draw.rect(screen64, AMMO_COLOR, (ax, ay, ammo_w, bar_h))

        # Powerup timers (small bars above resource bars)
        # Show remaining duration for active temporary effects.
        tpad = 1
        pt_h = 2
        # Speed boost timer (fuel pickup)
        if player.get("speed_boost_time", 0.0) > 0.0:
            pct = player["speed_boost_time"] / SPEED_BOOST_DURATION
            w = int(half_w * pct)
            pygame.draw.rect(
                screen64, (20, 20, 20), (fx, fy - pt_h - tpad, half_w, pt_h)
            )
            pygame.draw.rect(screen64, FUEL_COLOR, (fx, fy - pt_h - tpad, w, pt_h))
        # Rapid-fire timer (ammo pickup)
        if player.get("rapid_fire_time", 0.0) > 0.0:
            pct = player["rapid_fire_time"] / RAPID_FIRE_DURATION
            w = int(half_w * pct)
            pygame.draw.rect(
                screen64, (20, 20, 20), (ax, ay - pt_h - tpad, half_w, pt_h)
            )
            pygame.draw.rect(screen64, AMMO_COLOR, (ax, ay - pt_h - tpad, w, pt_h))
        # Spread timer (strewn / spread ammo)
        if player.get("spread_time", 0.0) > 0.0:
            pct = player["spread_time"] / SPREAD_DURATION
            w = int(half_w * pct)
            # draw centered between the two bars
            sx = fx + half_w // 2 + 1
            pygame.draw.rect(
                screen64, (20, 20, 20), (sx, fy - pt_h - tpad, half_w, pt_h)
            )
            pygame.draw.rect(screen64, SPREAD_COLOR, (sx, fy - pt_h - tpad, w, pt_h))

        # Game over text shown in the center when lives hit zero
        if game_over:
            t1 = font.render("GAME OVER", True, (255, 255, 255))
            t2 = font.render("ESC", True, (200, 200, 200))
            screen64.blit(t1, (W // 2 - t1.get_width() // 2, H // 2 - 6))
            screen64.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 4))

        # --- Present: scale up without adding new detail ---
        # Scale the 64x64 surface using pygame's transform and blit to
        # the real display. This preserves the low-resolution look.
        scaled = pygame.transform.scale(screen64, (W * SCALE, H * SCALE))
        window.blit(scaled, (0, 0))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
