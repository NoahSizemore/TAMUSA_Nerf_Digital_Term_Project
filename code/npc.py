from sprite_object import *
from random import randint, random

# behaviour states
STATE_IDLE = 'idle'
STATE_PATROL = 'patrol'
STATE_CHASE = 'chase'
STATE_SEARCH = 'search'
STATE_ATTACK = 'attack'


class NPC(AnimatedSprite):
    def __init__(self, game, path='images/sprites/npc/soldier/0.png', pos=(10.5, 5.5),
                 scale=0.6, shift=0.38, animation_time=180):
        super().__init__(game, path, pos, scale, shift, animation_time)
        self.attack_images = self.get_images(self.path + '/attack')
        self.death_images = self.get_images(self.path + '/death')
        self.idle_images = self.get_images(self.path + '/idle')
        self.pain_images = self.get_images(self.path + '/pain')
        self.walk_images = self.get_images(self.path + '/walk')

        self.attack_dist = randint(3, 6)
        self.speed = 0.01
        self.radius = NPC_RADIUS
        self.health = 100
        self.attack_damage = 10
        self.accuracy = 0.15
        self.alive = True
        self.pain = False
        self.ray_cast_value = False
        self.player_distance = 0
        self.los = False
        self.frame_counter = 0
        self.ID = 0

        # perception
        self.sight_range = NPC_SIGHT_RANGE
        self.hearing_range = NPC_HEARING_RANGE
        self.search_duration = NPC_SEARCH_DURATION
        self.state = STATE_IDLE
        self.last_known_pos = None
        self.last_seen_time = 0
        self.search_expire = 0
        self.investigate_tile = None

        # patrol route, generated lazily so it can use the pathfinding graph
        self.patrol_points = []
        self.patrol_index = 0
        self.patrol_ready = False

        # path cache, with explicit invalidation
        self.path = []
        self.path_goal = None
        self.path_built_at = -1000000
        self.path_failed_until = 0
        self.stuck_since = pg.time.get_ticks()
        self.prev_pos = (self.x, self.y)

    def update(self):
        self.check_animation_time()
        self.get_sprite()
        self.run_logic()
        # self.draw_ray_cast()

    def check_wall(self, x, y):
        return (x, y) not in self.game.map.world_map

    def check_wall_collision(self, dx, dy):
        """Axis-separated move with a real body radius, so the NPC can travel at
        any angle without clipping into geometry."""
        r = self.radius
        if dx:
            nx = self.x + dx
            edge = nx + r if dx > 0 else nx - r
            if (self.check_wall(int(edge), int(self.y + r))
                    and self.check_wall(int(edge), int(self.y - r))):
                self.x = nx
        if dy:
            ny = self.y + dy
            edge = ny + r if dy > 0 else ny - r
            if (self.check_wall(int(self.x + r), int(edge))
                    and self.check_wall(int(self.x - r), int(edge))):
                self.y = ny

    # ----------------------------------------------------------- perception

    def update_perception(self):
        """Decide what this NPC believes about the player, then pick a state.

        Sight is the raycast plus a range limit. Losing sight does not reset the
        NPC to idle: it keeps the last known position and searches around it
        until the memory expires.
        """
        now = pg.time.get_ticks()

        if self.ray_cast_value and self.dist < self.sight_range:
            self.last_known_pos = self.game.player.pos
            self.last_seen_time = now
            self.search_expire = now + self.search_duration
            self.investigate_tile = None
            self.state = STATE_ATTACK if self.dist < self.attack_dist else STATE_CHASE
            return

        if self.last_known_pos is not None and now < self.search_expire:
            self.state = STATE_SEARCH
            return

        self.last_known_pos = None
        self.investigate_tile = None
        self.state = STATE_PATROL if self.get_patrol_points() else STATE_IDLE

    def alert(self, pos, loudness):
        """Hearing: a gunshot gives an unaware NPC a position to investigate."""
        if not self.alive:
            return
        if math.hypot(pos[0] - self.x, pos[1] - self.y) > loudness:
            return
        now = pg.time.get_ticks()
        self.last_known_pos = pos
        self.search_expire = max(self.search_expire, now + self.search_duration)
        if self.state in (STATE_IDLE, STATE_PATROL):
            self.state = STATE_SEARCH
            self.investigate_tile = None
            self.invalidate_path()

    def get_patrol_points(self):
        """Build a patrol route around the spawn point, once."""
        if self.patrol_ready:
            return self.patrol_points
        pathfinding = getattr(self.game, 'pathfinding', None)
        if pathfinding is None:
            return self.patrol_points
        home = self.map_pos
        points = []
        for _ in range(NPC_PATROL_POINTS):
            tile = pathfinding.random_walkable_near(home, NPC_PATROL_RADIUS)
            if tile and tile not in points:
                points.append(tile)
        self.patrol_points = points
        self.patrol_ready = True
        return points

    # -------------------------------------------------------------- movement

    def current_goal(self):
        """The tile this NPC wants to reach, given its state."""
        if self.state == STATE_CHASE:
            return self.game.player.map_pos
        if self.state == STATE_SEARCH:
            if self.investigate_tile:
                return self.investigate_tile
            if self.last_known_pos:
                return int(self.last_known_pos[0]), int(self.last_known_pos[1])
            return None
        if self.state == STATE_PATROL:
            points = self.get_patrol_points()
            if points:
                return points[self.patrol_index % len(points)]
        return None

    def invalidate_path(self):
        self.path = []
        self.path_goal = None
        self.path_built_at = -1000000
        self.path_failed_until = 0

    def ensure_path(self, goal):
        """Keep a cached path alive, rebuilding it only when it goes stale.

        A chasing NPC reads the shared flow field, so the whole pack costs one
        Dijkstra expansion rather than one search each. Anything else (searching,
        patrolling) gets its own weighted A* search.
        """
        now = pg.time.get_ticks()
        pathfinding = self.game.pathfinding

        if self.path and goal == self.path_goal and now - self.path_built_at < PATH_REFRESH_MS:
            # still fresh, just pull it taut against the walls again
            self.path = pathfinding.smooth_path(self.x, self.y, self.path, self.radius)
            return

        if goal == self.path_goal and now < self.path_failed_until:
            return  # unreachable a moment ago, do not re-search every frame

        start = self.map_pos
        path = None
        if self.state == STATE_CHASE and goal == pathfinding.flow_goal:
            path = pathfinding.flow_path(start)
        if path is None:
            path = pathfinding.astar(start, goal)

        self.path_goal = goal
        self.path_built_at = now

        if path is None:
            # genuinely unreachable: stand still instead of walking into a wall
            self.path = []
            self.path_failed_until = now + PATH_RETRY_MS
            return

        self.path_failed_until = 0
        self.path = pathfinding.smooth_path(self.x, self.y, path, self.radius)

    def movement(self):
        goal = self.current_goal()
        if goal is None:
            return

        self.ensure_path(goal)
        if not self.path:
            self.on_goal_reached()
            return

        target = self.path[0]
        tx, ty = target[0] + 0.5, target[1] + 0.5
        if math.hypot(tx - self.x, ty - self.y) < self.radius + 0.1:
            self.path.pop(0)
            if not self.path:
                self.on_goal_reached()
                return
            target = self.path[0]
            tx, ty = target[0] + 0.5, target[1] + 0.5

        if target in self.game.object_handler.npc_positions and target != self.map_pos:
            # someone is in the way: reroute, and only shove past if we have been
            # stuck long enough that waiting has clearly deadlocked
            self.invalidate_path()
            if pg.time.get_ticks() - self.stuck_since < NPC_STUCK_MS:
                return

        angle = math.atan2(ty - self.y, tx - self.x)
        self.check_wall_collision(math.cos(angle) * self.speed, math.sin(angle) * self.speed)
        self.track_progress()

    def track_progress(self):
        """Reset the stuck timer whenever the NPC actually covers ground."""
        if math.hypot(self.x - self.prev_pos[0], self.y - self.prev_pos[1]) > 0.02:
            self.prev_pos = (self.x, self.y)
            self.stuck_since = pg.time.get_ticks()

    def on_goal_reached(self):
        if self.state == STATE_PATROL:
            points = self.get_patrol_points()
            if points:
                self.patrol_index = (self.patrol_index + 1) % len(points)
            self.invalidate_path()
        elif self.state == STATE_SEARCH:
            # sweep the area instead of standing on the last known position
            pathfinding = self.game.pathfinding
            if self.investigate_tile:
                anchor = self.investigate_tile
            elif self.last_known_pos:
                anchor = int(self.last_known_pos[0]), int(self.last_known_pos[1])
            else:
                anchor = self.map_pos
            self.investigate_tile = pathfinding.random_walkable_near(anchor, NPC_SEARCH_RADIUS)
            self.invalidate_path()

    def attack(self):
        if self.animation_trigger:
            self.game.sound.npc_shot.play()
            if random() < self.accuracy:
                self.game.player.get_damage(self.attack_damage)

    def animate_death(self):
        if not self.alive:
            if self.game.global_trigger and self.frame_counter < len(self.death_images) - 1:
                self.death_images.rotate(-1)
                self.image = self.death_images[0]
                self.frame_counter += 1

    def animate_pain(self):
        self.animate(self.pain_images)
        if self.animation_trigger:
            self.pain = False

    def check_hit_in_npc(self):
        if self.ray_cast_value and self.game.player.shot:

            if HALF_WIDTH - self.sprite_half_width < self.screen_x < HALF_WIDTH + self.sprite_half_width:
                self.game.sound.npc_pain.play()
                self.game.player.shot = False
                self.pain = True
                self.health -= self.game.weapon.damage
                self.check_health()
                return True
        return False

    def check_health(self):
        if self.health < 1:
            self.alive = False
            self.game.sound.npc_death.play()

    def run_logic(self):
        if not self.alive:
            self.animate_death()
            return

        self.ray_cast_value = self.ray_cast_player_npc()
        self.update_perception()

        if self.pain:
            self.animate_pain()
            return

        if self.state == STATE_ATTACK:
            self.animate(self.attack_images)
            self.attack()
        elif self.state in (STATE_CHASE, STATE_SEARCH, STATE_PATROL):
            self.animate(self.walk_images)
            self.movement()
        else:
            self.animate(self.idle_images)


    @property
    def map_pos(self):
        return int(self.x), int(self.y)

    def ray_cast_player_npc(self):
        if self.game.player.map_pos == self.map_pos:
            self.player_distance = 0
            return True

        wall_dist_v, wall_dist_h = 0, 0
        player_dist_v, player_dist_h = 0, 0

        ox, oy = self.game.player.pos
        x_map, y_map = self.game.player.map_pos

        ray_angle = self.theta + 1e-6

        sin_a = math.sin(ray_angle)
        cos_a = math.cos(ray_angle)

        # horizontals
        y_hor, dy = (y_map + 1, 1) if sin_a > 0 else (y_map - 1e-6, -1)

        depth_hor = (y_hor - oy) / sin_a
        x_hor = ox + depth_hor * cos_a

        delta_depth = dy / sin_a
        dx = delta_depth * cos_a

        for i in range(MAX_DEPTH):
            tile_hor = int(x_hor), int(y_hor)
            if tile_hor == self.map_pos:
                player_dist_h = depth_hor
                break
            if tile_hor in self.game.map.world_map:
                wall_dist_h = depth_hor
                break
            x_hor += dx
            y_hor += dy
            depth_hor += delta_depth

        # verticals
        x_vert, dx = (x_map + 1, 1) if cos_a > 0 else (x_map - 1e-6, -1)

        depth_vert = (x_vert - ox) / cos_a
        y_vert = oy + depth_vert * sin_a

        delta_depth = dx / cos_a
        dy = delta_depth * sin_a

        for i in range(MAX_DEPTH):
            tile_vert = int(x_vert), int(y_vert)
            if tile_vert == self.map_pos:
                player_dist_v = depth_vert
                break
            if tile_vert in self.game.map.world_map:
                wall_dist_v = depth_vert
                break
            x_vert += dx
            y_vert += dy
            depth_vert += delta_depth

        player_dist = max(player_dist_v, player_dist_h)
        wall_dist = max(wall_dist_v, wall_dist_h)

        if 0 < player_dist < wall_dist or not wall_dist:
            self.distance_check(player_dist)
            return True
        return False

    def distance_check(self, player_dist):
        self.player_distance = player_dist
        self.game.closest_to_player.append([self.player_distance, self.ID])

    def draw_ray_cast(self):
        pg.draw.circle(self.game.screen, 'red', (100 * self.x, 100 * self.y), 15)
        if self.ray_cast_player_npc():
            pg.draw.line(self.game.screen, 'orange', (100 * self.game.player.x, 100 * self.game.player.y),
                         (100 * self.x, 100 * self.y), 2)


class SoldierNPC(NPC):
    def __init__(self, game, path='images/sprites/npc/soldier/0.png', pos=(10.5, 5.5),
                 scale=0.6, shift=0.38, animation_time=180):
        super().__init__(game, path, pos, scale, shift, animation_time)

class CacoDemonNPC(NPC):
    def __init__(self, game, path='images/sprites/npc/caco_demon/0.png', pos=(10.5, 6.5),
                 scale=0.7, shift=0.27, animation_time=250):
        super().__init__(game, path, pos, scale, shift, animation_time)
        self.attack_dist = 1.0
        self.health = 150
        self.attack_damage = 25
        self.speed = 0.05
        self.accuracy = 0.35

class CyberDemonNPC(NPC):
    def __init__(self, game, path='images/sprites/npc/cyber_demon/0.png', pos=(11.5, 6.0),
                 scale=1.0, shift=0.04, animation_time=210):
        super().__init__(game, path, pos, scale, shift, animation_time)
        self.attack_dist = 6
        self.health = 350
        self.attack_damage = 15
        self.speed = 0.055
        self.accuracy = 0.25





















