from sprite_object import *


class Weapon(AnimatedSprite):
    def __init__(self, game, path='images/sprites/weapon/shotgun/0.png', scale=0.4, animation_time=90):
        super().__init__(game=game, path=path, scale=scale, animation_time=animation_time)
        self.images = deque(
            [pg.transform.smoothscale(img, (self.image.get_width() * scale, self.image.get_height() * scale))
             for img in self.images])
        self.weapon_pos = (HALF_WIDTH - self.images[0].get_width() // 2, HEIGHT - self.images[0].get_height())
        self.shot_fired = False
        self.reloading = False
        self.num_images = len(self.images)
        self.frame_counter = 0
        self.ammo = 5
        self.max_ammo = 5
        self.reserve = 25
        self.damage = 150
        # Reload state. Timed in milliseconds rather than frames so the
        # cadence is identical on every machine; FPS is uncapped, so the old
        # per-frame counter made reloading slower the slower the game ran.
        self.reload_started = 0
        self.shell_delay = RELOAD_FIRST_SHELL_MS
        # Shotgun fire model. player.single_fire_event() resets pellets to 8 on
        # each trigger pull and NPC.check_hit_in_npc() spends them per target,
        # so a single blast can be split across several NPCs.
        self.current_weapon = 'Shotgun'
        self.pellets = 8
        self.spread = SHOTGUN_SPREAD

    def animate_shot(self):
        if self.shot_fired:
            self.game.player.shot = False
            if self.animation_trigger:
                self.images.rotate(-1)
                self.image = self.images[0]
                self.frame_counter += 1
                if self.frame_counter == self.num_images:
                    self.shot_fired = False
                    self.frame_counter = 0

    def begin_reload(self):
        """Start a reload, if one is possible and not already running.

        Safe to call repeatedly: an in-progress reload is left alone rather
        than restarted, so firing a shell mid-reload no longer cancels it.
        """
        if self.reloading or self.ammo >= self.max_ammo or self.reserve <= 0:
            return
        self.reloading = True
        self.reload_started = pg.time.get_ticks()
        self.shell_delay = RELOAD_FIRST_SHELL_MS

    def load(self):
        if self.ammo < self.max_ammo and self.reserve > 0:
            self.ammo += 1
            self.reserve -= 1
            self.game.sound.load.play()
        if self.ammo >= self.max_ammo or self.reserve <= 0:
            self.reloading = False

    def update_reload(self):
        if not self.reloading:
            return
        if self.ammo >= self.max_ammo or self.reserve <= 0:
            self.reloading = False
            return
        now = pg.time.get_ticks()
        if now - self.reload_started >= self.shell_delay:
            self.load()
            self.reload_started = now
            self.shell_delay = RELOAD_SHELL_MS

    def draw(self):
        self.game.screen.blit(self.images[0], self.weapon_pos)

    def update(self):
        self.check_animation_time()
        self.animate_shot()
        self.update_reload()