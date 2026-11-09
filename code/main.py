import pygame as pg
import sys
from settings import *
from map import *
from player import *
from raycasting import *
from object_renderer import *
from sprite_object import *
from object_handler import *
from weapon import *
from sound import *
from pathfinding import *


class Game:
    def __init__(self):
        pg.init()
        pg.mouse.set_visible(False)
        self.screen = pg.display.set_mode(RES)
        pg.event.set_grab(True)
        self.clock = pg.time.Clock()
        self.delta_time = 1
        self.global_trigger = False
        self.global_event = pg.USEREVENT + 0
        pg.time.set_timer(self.global_event, 40)
        self.font = pg.font.SysFont("comicsansms", 50)
        # Distance, ID V
        self.closest_to_player = []
        self.text = self.font.render(str(self.closest_to_player), True, (255, 255, 255))
        self.new_game()

    def new_game(self):
        self.map = Map(self)
        self.player = Player(self)
        self.object_renderer = ObjectRenderer(self)
        self.raycasting = RayCasting(self)
        # built before the object handler so NPCs can reach the graph on spawn
        self.pathfinding = PathFinding(self)
        self.object_handler = ObjectHandler(self)
        self.weapon = Weapon(self)
        self.sound = Sound(self)
        pg.mixer.music.play(-1)

    def update(self):
        self.player.update()
        self.raycasting.update()
        # refresh the cost layer and flow field before the NPCs read them
        self.pathfinding.update()
        self.object_handler.update()
        self.weapon.update()
        pg.display.flip()
        self.delta_time = self.clock.tick(FPS)
        pg.display.set_caption(f'{self.clock.get_fps() :.1f}')

    def draw(self):
        # self.screen.fill('black')
        self.text = self.font.render(str(self.closest_to_player), True, (255, 255, 255))
        self.object_renderer.draw()
        self.weapon.draw()
        self.screen.blit(self.text, (50, 8))
        # self.map.draw()
        # self.player.draw()

    def check_events(self):
        self.global_trigger = False
        for event in pg.event.get():
            if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                pg.quit()
                sys.exit()
            elif event.type == pg.KEYDOWN and event.key == pg.K_r and self.weapon.reserve > 0:
                self.player.reload_event()
            elif event.type == self.global_event:
                self.global_trigger = True
            self.player.single_fire_event(event)

    def distance_update(self):
        self.closest_to_player.sort(key=lambda unit: unit[0])


    def run(self):
        while True:
            self.check_events()
            self.update()
            self.draw()
            self.closest_to_player = []


if __name__ == '__main__':
    game = Game()
    game.run()
