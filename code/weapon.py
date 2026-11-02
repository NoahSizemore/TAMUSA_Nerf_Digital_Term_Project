from sprite_object import *


class Weapon(AnimatedSprite):
    def __init__(self, game, path='resources/sprites/weapon/shotgun/0.png', scale=0.4, animation_time=90):
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
        self.reload_time = 80
        self.x = 0
        self.damage = 150

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

    def load(self):
        if self.ammo < self.max_ammo:
            self.ammo += 1
            self.reserve -= 1
            self.game.sound.load.play()
        if self.ammo == self.max_ammo:
            self.reloading = False



    def draw(self):
        self.game.screen.blit(self.images[0], self.weapon_pos)

    def update(self):
        self.check_animation_time()
        self.animate_shot()
        if self.reloading:
            self.x += 1
            if self.x == self.reload_time and self.reserve > 0:
                self.load()
                self.x = 0
                self.reload_time = 60