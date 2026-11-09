import math

# game settings
RES = WIDTH, HEIGHT = 1600, 900
# RES = WIDTH, HEIGHT = 1920, 1080
HALF_WIDTH = WIDTH // 2
HALF_HEIGHT = HEIGHT // 2
FPS = 0

PLAYER_POS = 1.5, 5  # mini_map
PLAYER_ANGLE = 0
PLAYER_SPEED = 0.004
PLAYER_ROT_SPEED = 0.002
PLAYER_SIZE_SCALE = 60
PLAYER_MAX_HEALTH = 100

MOUSE_SENSITIVITY = 0.0003
MOUSE_MAX_REL = 40
MOUSE_BORDER_LEFT = 100
MOUSE_BORDER_RIGHT = WIDTH - MOUSE_BORDER_LEFT

FLOOR_COLOR = (30, 30, 30)

FOV = math.pi / 3
HALF_FOV = FOV / 2
NUM_RAYS = WIDTH // 2
HALF_NUM_RAYS = NUM_RAYS // 2
DELTA_ANGLE = FOV / NUM_RAYS
MAX_DEPTH = 30

SCREEN_DIST = HALF_WIDTH / math.tan(HALF_FOV)
SCALE = WIDTH // NUM_RAYS

TEXTURE_SIZE = 256
HALF_TEXTURE_SIZE = TEXTURE_SIZE // 2

# pathfinding
ASTAR_MAX_EXPANSIONS = 4000     # safety cap on a single A* search
PATH_REFRESH_MS = 350           # how long a cached path stays valid
PATH_RETRY_MS = 500             # cooldown after a failed (unreachable) search
PATH_SMOOTH_LOOKAHEAD = 8       # waypoints considered by line-of-sight smoothing
FLOW_FIELD_REFRESH_MS = 200     # rebuild cadence for the shared flow field
FLOW_PATH_LIMIT = 24            # waypoints pulled out of the flow field at a time

# pathfinding cost layer
CROWD_COST = 3.0                # cost added to a tile an NPC is standing on
CROWD_SPILL_COST = 1.0          # cost added to the ring around that tile
DANGER_COST = 2.5               # peak cost inside the cone the player faces
DANGER_CONE = math.pi / 4       # half-angle of that cone
DANGER_RANGE = 8                # tiles over which the danger cost falls to zero

# npc perception and behaviour
NPC_RADIUS = 0.3                # body radius in tiles, used for collision and LOS
NPC_SIGHT_RANGE = 20            # tiles an NPC can see with clear line of sight
NPC_HEARING_RANGE = 12          # tiles at which an NPC notices a gunshot
NPC_SEARCH_DURATION = 6000      # ms an NPC keeps hunting a last known position
NPC_PATROL_POINTS = 4           # waypoints generated per NPC patrol route
NPC_PATROL_RADIUS = 6           # tiles around the spawn those waypoints sit in
NPC_SEARCH_RADIUS = 4           # tiles around the last known position to sweep
NPC_STUCK_MS = 600              # ms of no progress before pushing past a blocker