import heapq
import math
from random import choice

import pygame as pg

from settings import *

SQRT2 = math.sqrt(2)
INF = math.inf

# (dx, dy, step_cost, is_diagonal)
MOVES = (
    (-1, 0, 1.0, False),
    (1, 0, 1.0, False),
    (0, -1, 1.0, False),
    (0, 1, 1.0, False),
    (-1, -1, SQRT2, True),
    (1, -1, SQRT2, True),
    (1, 1, SQRT2, True),
    (-1, 1, SQRT2, True),
)


class PathFinding:
    """Weighted A* plus a shared Dijkstra flow field, with line-of-sight smoothing.

    Three layers:
      * graph       static 8-connected grid, diagonals priced at sqrt(2) and
                    forbidden when they would cut a wall corner.
      * cost_layer  per-frame additive tile costs (NPC crowding, and the wedge
                    the player is currently aiming down). Always >= 0, so the
                    octile heuristic stays admissible.
      * flow_field  one Dijkstra expansion outward from the player gives every
                    NPC an O(1) next hop, instead of one search per NPC.
    """

    def __init__(self, game):
        self.game = game
        self.map = game.map.mini_map
        self.rows = game.map.rows
        self.cols = game.map.cols

        self.graph = {}
        self.get_graph()

        # per-frame cost layer
        self.cost_layer = {}

        # shared flow field
        self.flow_field = {}
        self.flow_dist = {}
        self.flow_goal = None
        self.flow_built_at = -INF

        # metrics, handy for before/after numbers
        self.nodes_expanded = 0
        self.searches = 0
        self.flow_builds = 0

    # ------------------------------------------------------------------ graph

    def walkable(self, tile):
        x, y = tile
        if not (0 <= x < self.cols and 0 <= y < self.rows):
            return False
        return tile not in self.game.map.world_map

    def get_next_nodes(self, x, y):
        nodes = []
        for dx, dy, cost, diagonal in MOVES:
            nxt = (x + dx, y + dy)
            if not self.walkable(nxt):
                continue
            # no corner cutting: a diagonal needs both orthogonals open
            if diagonal and not (self.walkable((x + dx, y)) and self.walkable((x, y + dy))):
                continue
            nodes.append((nxt, cost))
        return tuple(nodes)

    def get_graph(self):
        for y in range(self.rows):
            for x in range(self.cols):
                if self.walkable((x, y)):
                    self.graph[(x, y)] = self.get_next_nodes(x, y)

    def nearest_walkable(self, tile):
        """Snap a tile that has ended up inside geometry back onto the graph."""
        if tile in self.graph:
            return tile
        x, y = tile
        for ring in (1, 2):
            best, best_d = None, INF
            for dy in range(-ring, ring + 1):
                for dx in range(-ring, ring + 1):
                    n = (x + dx, y + dy)
                    if n not in self.graph:
                        continue
                    d = dx * dx + dy * dy
                    if d < best_d:
                        best, best_d = n, d
            if best is not None:
                return best
        return None

    # ------------------------------------------------------------- cost layer

    def update_cost_layer(self):
        """Rebuild the additive cost layer for this frame."""
        layer = {}
        graph = self.graph

        # Crowding: an NPC makes its own tile expensive and its ring slightly so,
        # which routes the rest of the pack around it instead of walling them off.
        for tile in self.game.object_handler.npc_positions:
            layer[tile] = layer.get(tile, 0.0) + CROWD_COST
            x, y = tile
            for dx, dy, _cost, _diagonal in MOVES:
                n = (x + dx, y + dy)
                if n in graph:
                    layer[n] = layer.get(n, 0.0) + CROWD_SPILL_COST

        # Danger: the cone the player is looking down, falling off with distance,
        # so approaches drift toward the flanks and back instead of the muzzle.
        px, py = self.game.player.pos
        angle = self.game.player.angle
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        cone = math.cos(DANGER_CONE)
        rng = int(DANGER_RANGE)
        ptx, pty = int(px), int(py)
        for ty in range(pty - rng, pty + rng + 1):
            for tx in range(ptx - rng, ptx + rng + 1):
                tile = (tx, ty)
                if tile not in graph:
                    continue
                vx = tx + 0.5 - px
                vy = ty + 0.5 - py
                dist = math.hypot(vx, vy)
                if dist < 1e-6 or dist > DANGER_RANGE:
                    continue
                if (vx * cos_a + vy * sin_a) / dist > cone:
                    layer[tile] = layer.get(tile, 0.0) + DANGER_COST * (1.0 - dist / DANGER_RANGE)

        self.cost_layer = layer

    def tile_cost(self, tile):
        return 1.0 + self.cost_layer.get(tile, 0.0)

    # ------------------------------------------------------------- flow field

    def update(self):
        """Called once per frame, before the NPCs update."""
        self.update_cost_layer()
        now = pg.time.get_ticks()
        goal = self.game.player.map_pos
        if goal != self.flow_goal or now - self.flow_built_at >= FLOW_FIELD_REFRESH_MS:
            self.build_flow_field(goal)
            self.flow_built_at = now

    def build_flow_field(self, goal):
        """One Dijkstra expansion outward from the player over the cost layer.

        Stores, for every reachable tile, the neighbour that leads toward the
        player. The graph is symmetric, so expanding from the goal and then
        following flow_field forward is equivalent to a per-NPC search.
        """
        goal = self.nearest_walkable(goal)
        self.flow_goal = goal
        self.flow_builds += 1
        if goal is None:
            self.flow_field, self.flow_dist = {}, {}
            return

        graph = self.graph
        layer = self.cost_layer
        dist = {goal: 0.0}
        field = {}
        heap = [(0.0, goal)]
        push, pop = heapq.heappush, heapq.heappop

        while heap:
            d, cur = pop(heap)
            if d > dist.get(cur, INF):
                continue
            for nxt, step in graph[cur]:
                nd = d + step * (1.0 + layer.get(nxt, 0.0))
                if nd < dist.get(nxt, INF):
                    dist[nxt] = nd
                    field[nxt] = cur
                    push(heap, (nd, nxt))

        self.flow_field, self.flow_dist = field, dist

    def flow_path(self, start, limit=FLOW_PATH_LIMIT):
        """Walk the flow field from start. Returns the tiles after start, or None."""
        start = self.nearest_walkable(start)
        if start is None or self.flow_goal is None:
            return None
        if start == self.flow_goal:
            return []
        field = self.flow_field
        path = []
        cur = start
        while cur != self.flow_goal and len(path) < limit:
            cur = field.get(cur)
            if cur is None:
                return None
            path.append(cur)
        return path

    def flow_cost(self, tile):
        """Cost-to-player for a tile, or None if unreachable. Doubles as a
        reachability test."""
        return self.flow_dist.get(tile)

    # --------------------------------------------------------------------- A*

    @staticmethod
    def heuristic(a, b):
        """Octile distance. The minimum edge cost is 1.0, so this never
        overestimates and A* stays optimal."""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return (dx + dy) + (SQRT2 - 2.0) * min(dx, dy)

    def astar(self, start, goal, max_expansions=ASTAR_MAX_EXPANSIONS):
        """Weighted A* over graph + cost layer. Returns tiles after start, or None."""
        start = self.nearest_walkable(start)
        goal = self.nearest_walkable(goal)
        if start is None or goal is None:
            return None
        if start == goal:
            return []

        self.searches += 1
        graph = self.graph
        layer = self.cost_layer
        heuristic = self.heuristic

        came_from = {start: None}
        g_score = {start: 0.0}
        heap = [(heuristic(start, goal), start)]
        closed = set()
        push, pop = heapq.heappush, heapq.heappop
        expansions = 0

        while heap:
            _, cur = pop(heap)
            if cur in closed:
                continue
            if cur == goal:
                self.nodes_expanded += expansions
                return self.rebuild_path(came_from, start, goal)
            closed.add(cur)
            expansions += 1
            if expansions > max_expansions:
                break
            g = g_score[cur]
            for nxt, step in graph[cur]:
                if nxt in closed:
                    continue
                tentative = g + step * (1.0 + layer.get(nxt, 0.0))
                if tentative < g_score.get(nxt, INF):
                    g_score[nxt] = tentative
                    came_from[nxt] = cur
                    push(heap, (tentative + heuristic(nxt, goal), nxt))

        self.nodes_expanded += expansions
        return None

    @staticmethod
    def rebuild_path(came_from, start, goal):
        path = []
        step = goal
        while step is not None and step != start:
            path.append(step)
            step = came_from[step]
        path.reverse()
        return path

    # --------------------------------------------- line of sight and smoothing

    def line_of_sight(self, x0, y0, x1, y1, radius=0.0):
        """Clear straight walk between two world points. With a radius, the
        centre ray plus two offset rays are tested so corners are not clipped."""
        if radius > 0.0:
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            if length > 1e-9:
                ox = -dy / length * radius
                oy = dx / length * radius
                return (self.ray_clear(x0, y0, x1, y1)
                        and self.ray_clear(x0 + ox, y0 + oy, x1 + ox, y1 + oy)
                        and self.ray_clear(x0 - ox, y0 - oy, x1 - ox, y1 - oy))
        return self.ray_clear(x0, y0, x1, y1)

    def ray_clear(self, x0, y0, x1, y1):
        """Amanatides and Woo grid traversal: visits every tile the segment
        crosses, so diagonal wall seams block correctly."""
        world_map = self.game.map.world_map
        tx, ty = int(x0), int(y0)
        if (tx, ty) in world_map:
            return False
        end = (int(x1), int(y1))
        if (tx, ty) == end:
            return True

        dx, dy = x1 - x0, y1 - y0
        if dx > 0:
            step_x, t_max_x, t_delta_x = 1, (tx + 1 - x0) / dx, 1.0 / dx
        elif dx < 0:
            step_x, t_max_x, t_delta_x = -1, (tx - x0) / dx, -1.0 / dx
        else:
            step_x, t_max_x, t_delta_x = 0, INF, INF
        if dy > 0:
            step_y, t_max_y, t_delta_y = 1, (ty + 1 - y0) / dy, 1.0 / dy
        elif dy < 0:
            step_y, t_max_y, t_delta_y = -1, (ty - y0) / dy, -1.0 / dy
        else:
            step_y, t_max_y, t_delta_y = 0, INF, INF

        while True:
            if abs(t_max_x - t_max_y) <= 1e-9:
                # The segment passes exactly through a lattice corner. Advance
                # both axes together so the walk is direction independent, and
                # apply the same no-corner-cutting rule the graph uses, so
                # smoothing can never produce a shortcut a body cannot walk.
                if t_max_x > 1.0:
                    return True
                if (tx + step_x, ty) in world_map or (tx, ty + step_y) in world_map:
                    return False
                tx += step_x
                ty += step_y
                t_max_x += t_delta_x
                t_max_y += t_delta_y
            elif t_max_x < t_max_y:
                if t_max_x > 1.0:
                    return True
                tx += step_x
                t_max_x += t_delta_x
            else:
                if t_max_y > 1.0:
                    return True
                ty += step_y
                t_max_y += t_delta_y
            if (tx, ty) in world_map:
                return False
            if (tx, ty) == end:
                return True

    def smooth_path(self, x, y, path, radius=0.0, lookahead=PATH_SMOOTH_LOOKAHEAD):
        """String pulling: drop any waypoint we can already see past.

        Only the first `lookahead` waypoints are considered, searched furthest
        first, so the common case costs a single visibility test.
        """
        if not path:
            return path
        limit = min(len(path), lookahead)
        for i in range(limit - 1, -1, -1):
            cx = path[i][0] + 0.5
            cy = path[i][1] + 0.5
            if self.line_of_sight(x, y, cx, cy, radius):
                return path[i:]
        return path

    # ----------------------------------------------------------------- helpers

    def random_walkable_near(self, tile, radius):
        """A random walkable tile within radius, preferring ones the flow field
        marks as connected to the player."""
        x, y = tile
        reachable = self.flow_dist
        connected, fallback = [], []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                n = (x + dx, y + dy)
                if n == tile or n not in self.graph:
                    continue
                (connected if n in reachable else fallback).append(n)
        pool = connected or fallback
        return choice(pool) if pool else None
