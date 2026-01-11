import random
import pygame

# --- Strict 64x64 internal resolution ---
W, H = 64, 64          # internal "real" pixels
SCALE = 10             # window scale factor (display-only)
FPS = 60

PLAYER_W, PLAYER_H = 3, 3
ENEMY_W, ENEMY_H = 3, 3
BULLET_W, BULLET_H = 1, 2

# Resources / pickups
FUEL_CONSUMPTION_PER_SEC = 1.8
MAX_FUEL = 160.0
MAX_AMMO = 35
PICKUP_SPAWN_INTERVAL = 240  # frames (more frequent pickups)
PICKUP_SPEED = 0.4
FUEL_COLOR = (255, 180, 60)
AMMO_COLOR = (140, 255, 140)
SPREAD_COLOR = (220, 220, 80)

# Pickup effects / tuning
FUEL_PICKUP_AMOUNT = 60
AMMO_PICKUP_AMOUNT = 12
SPEED_BOOST_MULT = 1.6
SPEED_BOOST_DURATION = 4.0  # seconds
RAPID_FIRE_FACTOR = 0.5
RAPID_FIRE_DURATION = 5.0   # seconds
SPREAD_DURATION = 60.0  # seconds (Streumnunition)
PARTICLE_COUNT = 10
PARTICLE_TTL = 0.6  # seconds

# Enemy shooting and difficulty tuning
ENEMY_SHOOT_START_TIME = 20.0  # seconds before enemies start shooting back
ENEMY_FIRE_RATE = 0.12  # shots per second per enemy (scales with time)
ENEMY_BULLET_SPEED = 1.8
DROP_CHANCE_PER_KILL = 0.45  # higher chance to drop a pickup on kill
DROP_WEIGHTS = [("fuel", 0.45), ("ammo", 0.45), ("spread", 0.10)]  # distribution of drops

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

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

    player = {
        "x": W // 2 - 1,
        "y": H - 10,
        "fire_cd": 0,
        "lives": 3,
        "fuel": MAX_FUEL,
        "ammo": MAX_AMMO
    }

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

    spawn_interval = 56       # frames (initial, start slower)
    bullet_speed = 2.5        # px/frame upward
    enemy_base_speed = 0.12   # px/frame downward (starts much slower)
    enemy_accel_per_sec = 0.035
    player_base_speed = 1.0   # px/frame
    fire_cooldown_frames = 6  # frames

    running = True
    game_over = False

    while running:
        dt = clock.tick(FPS)
        frame += 1

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        # --- Update ---
        if not game_over:
            dx = (1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0) - (1 if (keys[pygame.K_LEFT] or keys[pygame.K_a]) else 0)
            dy = (1 if (keys[pygame.K_DOWN]  or keys[pygame.K_s]) else 0) - (1 if (keys[pygame.K_UP]   or keys[pygame.K_w]) else 0)

            # update time
            time_s += dt / 1000.0

            # dynamic speeds: start slower, accelerate over time
            enemy_speed = enemy_base_speed + time_s * enemy_accel_per_sec
            # spawn interval gradually shortens (to a gentler limit)
            spawn_interval = max(20, int(56 - time_s * 0.2))

            # player speed depends on fuel level (no fuel -> much slower)
            fuel_ratio = max(0.0, min(1.0, player["fuel"] / MAX_FUEL))
            player_speed = player_base_speed * (0.4 + 0.6 * fuel_ratio)
            # temporary speed boost from pickups
            if player.get("speed_boost_time", 0.0) > 0.0:
                player_speed *= SPEED_BOOST_MULT

            player["x"] = clamp(player["x"] + dx * player_speed, 0, W - PLAYER_W)
            player["y"] = clamp(player["y"] + dy * player_speed, 0, H - PLAYER_H)

            if player["fire_cd"] > 0:
                player["fire_cd"] -= 1

            # Firing consumes ammo; only fire if ammo available
            if keys[pygame.K_SPACE] and player["fire_cd"] == 0 and player["ammo"] > 0:
                rapid = player.get("rapid_fire_time", 0.0) > 0.0
                cooldown = max(1, int(fire_cooldown_frames * (RAPID_FIRE_FACTOR if rapid else 1.0)))
                player["fire_cd"] = cooldown
                player["ammo"] = max(0, player["ammo"] - 1)

                # spread shot if active
                if player.get("spread_time", 0.0) > 0.0:
                    # three bullets with small horizontal velocity
                    bullets.append({"x": float(player["x"] + 1), "y": float(player["y"] - 2), "vx": 0.0, "vy": -bullet_speed})
                    bullets.append({"x": float(player["x"] + 1), "y": float(player["y"] - 2), "vx": -0.6, "vy": -bullet_speed})
                    bullets.append({"x": float(player["x"] + 1), "y": float(player["y"] - 2), "vx": 0.6, "vy": -bullet_speed})
                else:
                    bullets.append({"x": float(player["x"] + 1), "y": float(player["y"] - 2), "vx": 0.0, "vy": -bullet_speed})

            # Spawn enemies
            if frame % spawn_interval == 0:
                enemies.append({
                    "x": float(random.randint(0, W - ENEMY_W)),
                    "y": float(-ENEMY_H),
                    "dx": random.choice([-1, 0, 1])  # tiny wiggle
                })

            # Spawn pickups occasionally (color matches HUD bars)
            if frame % PICKUP_SPAWN_INTERVAL == 0:
                if random.random() < 0.5:
                    fuel_pods.append({"x": float(random.randint(0, W - 2)), "y": float(-2), "color": FUEL_COLOR})
                else:
                    ammo_pods.append({"x": float(random.randint(0, W - 2)), "y": float(-2), "color": AMMO_COLOR})

            # Move bullets (player)
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
                if time_s >= ENEMY_SHOOT_START_TIME:
                    # chance to shoot scaled by time (keeps game increasing difficulty)
                    shoot_prob = ENEMY_FIRE_RATE * min(2.5, 0.5 + time_s / 30.0) * (dt / 1000.0)
                    if random.random() < shoot_prob:
                        # aim roughly towards player's current x (with small inaccuracy)
                        ex = e["x"] + ENEMY_W // 2
                        ey = e["y"] + ENEMY_H
                        vx = (player["x"] + PLAYER_W//2 - ex) * 0.05 + random.uniform(-0.2, 0.2)
                        enemy_bullets.append({"x": float(ex), "y": float(ey), "vx": vx, "vy": ENEMY_BULLET_SPEED})

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

            # Bullet-enemy collisions
            dead_bullets = set()
            dead_enemies = set()
            for bi, b in enumerate(bullets):
                for ei, e in enumerate(enemies):
                    if aabb(b["x"], b["y"], BULLET_W, BULLET_H, e["x"], e["y"], ENEMY_W, ENEMY_H):
                        dead_bullets.add(bi)
                        dead_enemies.add(ei)
                        score += 1
                        # 1/4 chance to drop a pickup
                        if random.random() < DROP_CHANCE_PER_KILL:
                            r = random.random()
                            cum = 0.0
                            for name, w in DROP_WEIGHTS:
                                cum += w
                                if r < cum:
                                    if name == "fuel":
                                        fuel_pods.append({"x": float(e["x"]), "y": float(e["y"]), "color": FUEL_COLOR})
                                    elif name == "ammo":
                                        ammo_pods.append({"x": float(e["x"]), "y": float(e["y"]), "color": AMMO_COLOR})
                                    elif name == "spread":
                                        spread_pods.append({"x": float(e["x"]), "y": float(e["y"]), "color": SPREAD_COLOR})
                                    break
                        break

            # Player-enemy collisions
            for ei, e in enumerate(enemies):
                if aabb(player["x"], player["y"], PLAYER_W, PLAYER_H, e["x"], e["y"], ENEMY_W, ENEMY_H):
                    dead_enemies.add(ei)
                    player["lives"] -= 1
                    player["x"] = W // 2 - 1
                    player["y"] = H - 10
                    if player["lives"] <= 0:
                        game_over = True
                    break

            # Enemy bullet -> player collision
            dead_enemy_bullets = set()
            for bi, eb in enumerate(enemy_bullets):
                if aabb(player["x"], player["y"], PLAYER_W, PLAYER_H, eb["x"], eb["y"], 1, 1):
                    dead_enemy_bullets.add(bi)
                    player["lives"] -= 1
                    player["x"] = W // 2 - 1
                    player["y"] = H - 10
                    if player["lives"] <= 0:
                        game_over = True
            enemy_bullets = [eb for i, eb in enumerate(enemy_bullets) if i not in dead_enemy_bullets and eb["y"] < H + 2]

            # Player-pickup collisions
            dead_fuel = set()
            for pi, p in enumerate(fuel_pods):
                if aabb(player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2):
                    # refill partially and give a temporary speed boost
                    player["fuel"] = min(MAX_FUEL, player["fuel"] + FUEL_PICKUP_AMOUNT)
                    player.setdefault("speed_boost_time", 0.0)
                    player["speed_boost_time"] = SPEED_BOOST_DURATION
                    score += 0  # could add pickup points
                    # spawn particles
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append({"x": p["x"], "y": p["y"], "vx": vx, "vy": vy, "color": p["color"], "ttl": PARTICLE_TTL})
                    dead_fuel.add(pi)
            fuel_pods = [p for i, p in enumerate(fuel_pods) if i not in dead_fuel]

            dead_ammo = set()
            for pi, p in enumerate(ammo_pods):
                if aabb(player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2):
                    # refill partially and give a temporary rapid-fire
                    player["ammo"] = min(MAX_AMMO, player["ammo"] + AMMO_PICKUP_AMOUNT)
                    player.setdefault("rapid_fire_time", 0.0)
                    player["rapid_fire_time"] = RAPID_FIRE_DURATION
                    score += 0
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append({"x": p["x"], "y": p["y"], "vx": vx, "vy": vy, "color": p["color"], "ttl": PARTICLE_TTL})
                    dead_ammo.add(pi)
            ammo_pods = [p for i, p in enumerate(ammo_pods) if i not in dead_ammo]

            dead_spread = set()
            for pi, p in enumerate(spread_pods):
                if aabb(player["x"], player["y"], PLAYER_W, PLAYER_H, p["x"], p["y"], 2, 2):
                    # grant spread (Streumnunition)
                    player.setdefault("spread_time", 0.0)
                    player["spread_time"] = SPREAD_DURATION
                    score += 0
                    for _ in range(PARTICLE_COUNT):
                        vx = random.uniform(-0.9, 0.9)
                        vy = random.uniform(-0.9, 0.3)
                        particles.append({"x": p["x"], "y": p["y"], "vx": vx, "vy": vy, "color": p["color"], "ttl": PARTICLE_TTL})
                    dead_spread.add(pi)
            spread_pods = [p for i, p in enumerate(spread_pods) if i not in dead_spread]

            # Cleanup offscreen
            bullets = [b for i, b in enumerate(bullets) if i not in dead_bullets and b["y"] > -BULLET_H]
            enemies = [e for i, e in enumerate(enemies) if i not in dead_enemies and e["y"] < H + ENEMY_H]
            fuel_pods = [p for p in fuel_pods if p["y"] < H + 2]
            ammo_pods = [p for p in ammo_pods if p["y"] < H + 2]

            # Move particles and cleanup
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
            player["fuel"] = max(0.0, player["fuel"] - FUEL_CONSUMPTION_PER_SEC * (dt / 1000.0))

            # Update powerup timers
            if player.get("rapid_fire_time", 0.0) > 0.0:
                player["rapid_fire_time"] = max(0.0, player["rapid_fire_time"] - dt / 1000.0)
            if player.get("speed_boost_time", 0.0) > 0.0:
                player["speed_boost_time"] = max(0.0, player["speed_boost_time"] - dt / 1000.0)
            if player.get("spread_time", 0.0) > 0.0:
                player["spread_time"] = max(0.0, player["spread_time"] - dt / 1000.0)

        # --- Render (ONLY onto 64x64) ---
        # Simple scrolling-star background (still 64x64)
        screen64.fill((0, 0, 0))
        # deterministic tiny stars
        for i in range(18):
            sx = (i * 13 + 7) % W
            sy = (i * 19 + frame) % H
            screen64.set_at((sx, sy), (40, 40, 40))

        # Draw bullets (white)
        for b in bullets:
            pygame.draw.rect(screen64, (255, 255, 255), (int(b["x"]), int(b["y"]), BULLET_W, BULLET_H))

        # Draw enemies (red)
        for e in enemies:
            pygame.draw.rect(screen64, (220, 60, 60), (int(e["x"]), int(e["y"]), ENEMY_W, ENEMY_H))

        # Draw enemy bullets
        for eb in enemy_bullets:
            pygame.draw.rect(screen64, (240, 140, 80), (int(eb["x"]), int(eb["y"]), 1, 1))

        # Draw player (cyan)
        pygame.draw.rect(screen64, (60, 220, 220), (int(player["x"]), int(player["y"]), PLAYER_W, PLAYER_H))

        # Draw particles (on top)
        for part in particles:
            alpha = max(0.0, part["ttl"] / PARTICLE_TTL)
            c = part["color"]
            col = (int(c[0]*alpha), int(c[1]*alpha), int(c[2]*alpha))
            screen64.set_at((int(part["x"]), int(part["y"])), col)

        # Draw pickups (fuel, ammo, spread)
        for p in fuel_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))
        for p in ammo_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))
        for p in spread_pods:
            pygame.draw.rect(screen64, p["color"], (int(p["x"]), int(p["y"]), 2, 2))

        # HUD (tiny)

        # HUD (tiny)
        hud = font.render(f"{score}  L{player['lives']}", True, (200, 200, 200))
        screen64.blit(hud, (1, 1))

        # Resource bars at bottom: fuel (left) and ammo (right)
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
        tpad = 1
        pt_h = 2
        # Speed boost timer (fuel pickup)
        if player.get("speed_boost_time", 0.0) > 0.0:
            pct = player["speed_boost_time"] / SPEED_BOOST_DURATION
            w = int(half_w * pct)
            pygame.draw.rect(screen64, (20, 20, 20), (fx, fy - pt_h - tpad, half_w, pt_h))
            pygame.draw.rect(screen64, FUEL_COLOR, (fx, fy - pt_h - tpad, w, pt_h))
        # Rapid-fire timer (ammo pickup)
        if player.get("rapid_fire_time", 0.0) > 0.0:
            pct = player["rapid_fire_time"] / RAPID_FIRE_DURATION
            w = int(half_w * pct)
            pygame.draw.rect(screen64, (20, 20, 20), (ax, ay - pt_h - tpad, half_w, pt_h))
            pygame.draw.rect(screen64, AMMO_COLOR, (ax, ay - pt_h - tpad, w, pt_h))
        # Spread timer (Streumnunition)
        if player.get("spread_time", 0.0) > 0.0:
            pct = player["spread_time"] / SPREAD_DURATION
            w = int(half_w * pct)
            # draw centered between the two bars
            sx = fx + half_w // 2 + 1
            pygame.draw.rect(screen64, (20, 20, 20), (sx, fy - pt_h - tpad, half_w, pt_h))
            pygame.draw.rect(screen64, SPREAD_COLOR, (sx, fy - pt_h - tpad, w, pt_h))

        if game_over:
            t1 = font.render("GAME OVER", True, (255, 255, 255))
            t2 = font.render("ESC", True, (200, 200, 200))
            screen64.blit(t1, (W // 2 - t1.get_width() // 2, H // 2 - 6))
            screen64.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 4))

        # --- Present: scale up without adding new detail ---
        scaled = pygame.transform.scale(screen64, (W * SCALE, H * SCALE))
        window.blit(scaled, (0, 0))
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()

