import pygame
import random
from collections import deque

TILE = 40
COLS, ROWS = 20, 15
WALL, FLOOR, CHEST, KEY, TRAP = 0, 1, 2, 3, 4
SPEED = 3
GUARD_SPEED = 1
TRAP_COUNT = 4


def generate_world():
    grid = [[WALL]*COLS for _ in range(ROWS)]
    rooms = []
    for _ in range(8):
        w = random.randint(3,6)
        h = random.randint(3,5)
        x = random.randint(1, COLS-w-1)
        y = random.randint(1, ROWS-h-1)
        room = pygame.Rect(x, y, w, h)
        overlap = any(room.inflate(2,2).colliderect(r) for r in rooms)
        if not overlap:
            rooms.append(room)
            for ry in range(y, y+h):
                for rx in range(x, x+w):
                    grid[ry][rx] = FLOOR
    for i in range(len(rooms)-1):
        ax, ay = rooms[i].centerx, rooms[i].centery
        bx, by = rooms[i+1].centerx, rooms[i+1].centery
        cx = ax
        while cx != bx:
            grid[ay][cx] = FLOOR
            cx += 1 if bx > cx else -1
        cy = ay
        while cy != by:
            grid[cy][bx] = FLOOR
            cy += 1 if by > cy else -1
    if len(rooms) >= 2:
        cr, ck = rooms[-1], rooms[-2]
        grid[cr.centery][cr.centerx] = CHEST
        grid[ck.centery][ck.centerx] = KEY

    start = rooms[0] if rooms else None

    # Find one guaranteed route from the starting room to the chest.
    # Traps are never placed on this route, so they can never completely
    # block the player's only way to the chest.
    chest_tile = None
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] == CHEST:
                chest_tile = (r, c)
                break
        if chest_tile:
            break

    safe_path = set()
    if start and chest_tile:
        start_tile = (start.centery, start.centerx)
        queue = deque([start_tile])
        previous = {start_tile: None}

        while queue:
            r, c = queue.popleft()
            if (r, c) == chest_tile:
                break

            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue
                if (nr, nc) in previous:
                    continue
                if grid[nr][nc] in (FLOOR, KEY, CHEST):
                    previous[(nr, nc)] = (r, c)
                    queue.append((nr, nc))

        if chest_tile in previous:
            current = chest_tile
            while current is not None:
                safe_path.add(current)
                current = previous[current]

    # Place traps only away from the guaranteed safe route and starting room.
    trap_candidates = []
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] != FLOOR:
                continue
            if start and start.collidepoint(c, r):
                continue
            if (r, c) in safe_path:
                continue
            trap_candidates.append((r, c))

    for r, c in random.sample(trap_candidates, min(TRAP_COUNT, len(trap_candidates))):
        grid[r][c] = TRAP

    return grid, start


COLORS = {
    WALL: (60,50,70),
    FLOOR: (200,190,170),
    CHEST: (200,160,30),
    KEY: (220,220,60),
    TRAP: (170,60,60),
}


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 28, 28)
        self.color = (60,120,220)
        self.has_key = False

    def move(self, keys, grid, rows, cols):
        dx=dy=0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dx=-SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx=SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]: dy=-SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: dy=SPEED
        self._try_move(dx,0,grid,rows,cols)
        self._try_move(0,dy,grid,rows,cols)

    def _try_move(self, dx, dy, grid, rows, cols):
        new = self.rect.move(dx,dy)
        for px,py in [(new.left,new.top),(new.right-1,new.top),(new.left,new.bottom-1),(new.right-1,new.bottom-1)]:
            c,r=px//TILE,py//TILE
            if not(0<=r<rows and 0<=c<cols) or grid[r][c]==WALL:
                return
        self.rect=new

    def draw(self, screen):
        pygame.draw.ellipse(screen, self.color, self.rect)
        if self.has_key:
            pygame.draw.circle(screen, (220,220,60), (self.rect.right-6, self.rect.top+6), 5)


class Guard:
    def __init__(self, patrol_points):
        self.patrol_points = [pygame.Vector2(x, y) for x, y in patrol_points]
        self.target_index = 1
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = self.patrol_points[0]
        self.color = (190, 55, 55)

    def move(self, grid, rows, cols):
        target = self.patrol_points[self.target_index]
        direction = target - pygame.Vector2(self.rect.center)
        distance = direction.length()

        if distance <= GUARD_SPEED:
            self.rect.center = (round(target.x), round(target.y))
            self.target_index = 1 - self.target_index
            return

        if distance:
            direction.scale_to_length(GUARD_SPEED)
            new = self.rect.move(round(direction.x), round(direction.y))
            for px, py in [(new.left, new.top), (new.right - 1, new.top),
                           (new.left, new.bottom - 1), (new.right - 1, new.bottom - 1)]:
                c, r = px // TILE, py // TILE
                if not (0 <= r < rows and 0 <= c < cols) or grid[r][c] == WALL:
                    self.target_index = 1 - self.target_index
                    return
            self.rect = new

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=6)
        pygame.draw.circle(screen, (245, 220, 220), (self.rect.centerx - 5, self.rect.centery - 4), 3)
        pygame.draw.circle(screen, (245, 220, 220), (self.rect.centerx + 5, self.rect.centery - 4), 3)


WIDTH = COLS * TILE
HEIGHT = ROWS * TILE + 50
FPS = 60


class GameEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Treasure Hunt")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 24)
        self.big_font = pygame.font.SysFont("monospace", 40, bold=True)
        self.minimap_tile = 8
        self.minimap_margin = 10
        self.reset()

    def reset(self):
        self.grid, start = generate_world()
        if start:
            sx = start.x * TILE + 6
            sy = start.y * TILE + 6
        else:
            sx, sy = TILE+6, TILE+6
        self.start_pos = (sx, sy)
        self.player = Player(sx, sy)

        # The chest is in the last generated room. Use the floor tiles directly
        # to its left and right as two safe patrol points for the guard.
        chest_tile = None
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] == CHEST:
                    chest_tile = (c, r)
                    break
            if chest_tile:
                break

        if chest_tile:
            cx, cy = chest_tile
            patrol_points = [
                (cx * TILE + TILE // 2 - TILE, cy * TILE + TILE // 2),
                (cx * TILE + TILE // 2 + TILE, cy * TILE + TILE // 2),
            ]
        else:
            patrol_points = [(sx + TILE, sy), (sx + 2 * TILE, sy)]

        self.guard = Guard(patrol_points)
        self.won = False
        self.status = "Find the KEY, then the CHEST!"

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r: self.reset()
        return True

    def update(self):
        if self.won: return
        keys = pygame.key.get_pressed()
        self.player.move(keys, self.grid, ROWS, COLS)
        self.guard.move(self.grid, ROWS, COLS)

        pr = self.player.rect.centery // TILE
        pc = self.player.rect.centerx // TILE
        if 0<=pr<ROWS and 0<=pc<COLS:
            cell = self.grid[pr][pc]
            if cell == TRAP:
                self.player.rect.topleft = self.start_pos
                self.status = "You stepped on a trap! Returned to start."
            elif cell == KEY:
                self.player.has_key = True
                self.grid[pr][pc] = FLOOR
                self.status = "Got the key! Find the CHEST!"
            elif cell == CHEST and self.player.has_key:
                self.won = True
                self.status = "Treasure found!"

        if self.player.rect.colliderect(self.guard.rect):
            self.player.rect.topleft = self.start_pos
            self.status = "The guard caught you! Returned to start."

    def draw_inventory(self):
        # The inventory uses the player's existing has_key state.
        slot = pygame.Rect(8, ROWS * TILE + 5, 40, 40)
        pygame.draw.rect(self.screen, (45, 45, 60), slot)
        pygame.draw.rect(self.screen, (180, 180, 190), slot, 2)

        if self.player.has_key:
            # Simple key icon: ring, shaft, and teeth.
            pygame.draw.circle(
                self.screen, (255, 230, 70),
                (slot.x + 13, slot.y + 14), 7, 3
            )
            pygame.draw.line(
                self.screen, (255, 230, 70),
                (slot.x + 19, slot.y + 14),
                (slot.x + 31, slot.y + 14), 3
            )
            pygame.draw.line(
                self.screen, (255, 230, 70),
                (slot.x + 27, slot.y + 14),
                (slot.x + 27, slot.y + 20), 3
            )
            pygame.draw.line(
                self.screen, (255, 230, 70),
                (slot.x + 31, slot.y + 14),
                (slot.x + 31, slot.y + 18), 3
            )

    def draw_minimap(self):
        # The mini-map is generated directly from the current dungeon grid.
        # This keeps it synchronized with the actual world after every restart.
        map_w = COLS * self.minimap_tile
        map_h = ROWS * self.minimap_tile
        map_x = WIDTH - map_w - self.minimap_margin
        map_y = self.minimap_margin

        # Dark backing makes the small map readable over the game world.
        pygame.draw.rect(
            self.screen, (15, 15, 22),
            (map_x - 4, map_y - 4, map_w + 8, map_h + 8)
        )

        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                if cell == WALL:
                    color = (45, 40, 55)
                else:
                    color = (190, 180, 160)

                rect = pygame.Rect(
                    map_x + c * self.minimap_tile,
                    map_y + r * self.minimap_tile,
                    self.minimap_tile,
                    self.minimap_tile
                )
                pygame.draw.rect(self.screen, color, rect)

        # Mark the player's exact position using their current pixel position.
        player_x = map_x + (self.player.rect.centerx / TILE) * self.minimap_tile
        player_y = map_y + (self.player.rect.centery / TILE) * self.minimap_tile
        pygame.draw.circle(
            self.screen, (60, 120, 220),
            (round(player_x), round(player_y)),
            4
        )

        pygame.draw.rect(
            self.screen, (220, 220, 220),
            (map_x - 1, map_y - 1, map_w + 2, map_h + 2),
            1
        )

    def draw(self):
        self.screen.fill((30,25,40))
        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                rect = pygame.Rect(c*TILE, r*TILE, TILE, TILE)
                pygame.draw.rect(self.screen, COLORS[cell], rect)
                if cell == KEY:
                    pygame.draw.circle(self.screen, (255,240,60),(c*TILE+TILE//2, r*TILE+TILE//2),10)
                elif cell == CHEST:
                    pygame.draw.rect(self.screen,(180,120,20),rect.inflate(-12,-12),border_radius=4)
                elif cell == TRAP:
                    # Simple visible floor trap: dark center with crossing blades.
                    pygame.draw.rect(self.screen,(90,35,35),rect.inflate(-10,-10),border_radius=4)
                    pygame.draw.line(self.screen,(235,120,120),rect.topleft,rect.bottomright,4)
                    pygame.draw.line(self.screen,(235,120,120),rect.topright,rect.bottomleft,4)
        self.guard.draw(self.screen)
        self.player.draw(self.screen)
        self.draw_minimap()
        hud = pygame.Rect(0,ROWS*TILE,WIDTH,50)
        pygame.draw.rect(self.screen,(20,20,35),hud)
        self.draw_inventory()
        st = self.font.render(self.status+"  |  R=Restart", True, (200,200,200))
        self.screen.blit(st,(58,ROWS*TILE+13))
        if self.won:
            ov=pygame.Surface((WIDTH,ROWS*TILE),pygame.SRCALPHA)
            ov.fill((0,0,0,140))
            self.screen.blit(ov,(0,0))
            msg=self.big_font.render("TREASURE FOUND!", True,(220,180,30))
            sub=self.font.render("Press R to Play Again",True,(180,180,180))
            self.screen.blit(msg,(WIDTH//2-msg.get_width()//2,ROWS*TILE//2-30))
            self.screen.blit(sub,(WIDTH//2-sub.get_width()//2,ROWS*TILE//2+20))
        pygame.display.flip()

    def run(self):
        running=True
        while running:
            running=self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    engine = GameEngine()
    engine.run()
