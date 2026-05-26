import pygame
import random
import math

pygame.init()

# =========================================
# BOOK SORT TASK (Among Us Style)
# =========================================
class BookSortTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.RED = (200, 50, 50)
        self.BLUE = (80, 120, 255)
        self.YELLOW = (255, 220, 0)
        self.BROWN = (120, 80, 40)
        self.PURPLE = (171, 0, 255)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont("arial", 40)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # REGALE
        # =========================

        self.left_shelf = pygame.Rect(
            self.window_x + 120,
            self.window_y + 190,
            300,
            400
        )

        self.right_shelf = pygame.Rect(
            self.window_x + 680,
            self.window_y + 190,
            300,
            400
        )

        # =========================
        # BÜCHER
        # =========================

        self.books = []
        self.create_books()

        # =========================
        # DRAG & DROP
        # =========================

        self.selected_book = None
        self.offset_x = 0
        self.offset_y = 0

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_books(self):

        colors = [
            self.RED,
            self.BLUE,
            self.GREEN,
            self.YELLOW,
            self.BROWN,
            self.PURPLE
        ]

        for i in range(len(colors)):

            rect = pygame.Rect(
                random.randint(
                    self.left_shelf.x + 30,
                    self.left_shelf.x + 180
                ),

                random.randint(
                    self.left_shelf.y + 30,
                    self.left_shelf.y + 250
                ),

                80,
                110
            )

            self.books.append({
                "rect": rect,
                "color": colors[i]
            })

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        # Schwarzer Rand
        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "SORT BOOKS",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 340,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Ziehe alle Bücher ins rechte Regal",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 250,
                self.window_y + 90
            )
        )

        # =========================
        # REGALE
        # =========================

        pygame.draw.rect(
            self.screen,
            self.BROWN,
            self.left_shelf,
            8
        )

        pygame.draw.rect(
            self.screen,
            self.BROWN,
            self.right_shelf,
            8
        )

        # Regal Texte

        left_text = self.font.render(
            "UNSORTIERT",
            True,
            self.BLACK
        )

        right_text = self.font.render(
            "SORTIERT",
            True,
            self.BLACK
        )

        self.screen.blit(
            left_text,
            (
                self.left_shelf.x + 40,
                self.left_shelf.y - 50
            )
        )

        self.screen.blit(
            right_text,
            (
                self.right_shelf.x + 70,
                self.right_shelf.y - 50
            )
        )

        # =========================
        # BÜCHER
        # =========================

        for book in self.books:

            pygame.draw.rect(
                self.screen,
                book["color"],
                book["rect"],
                border_radius=8
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                book["rect"],
                width=3,
                border_radius=8
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for book in reversed(self.books):

                if book["rect"].collidepoint(mouse_pos):

                    self.selected_book = book

                    self.offset_x = (
                        book["rect"].x - mouse_pos[0]
                    )

                    self.offset_y = (
                        book["rect"].y - mouse_pos[1]
                    )

                    break

        # =========================
        # BUCH BEWEGEN
        # =========================

        elif event.type == pygame.MOUSEMOTION:

            if self.selected_book:

                mouse_pos = pygame.mouse.get_pos()

                self.selected_book["rect"].x = (
                    mouse_pos[0] + self.offset_x
                )

                self.selected_book["rect"].y = (
                    mouse_pos[1] + self.offset_y
                )

        # =========================
        # LOSLASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            self.selected_book = None
            self.check_finished()

    def check_finished(self):

        all_correct = True

        for book in self.books:

            if not self.right_shelf.contains(book["rect"]):
                all_correct = False

        if all_correct:
            self.finished = True

    def is_finished(self):
        return self.finished

class ChairStackTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.BROWN = (120, 80, 40)
        self.LIGHT_BROWN = (170, 120, 70)
        self.BLUE = (80, 120, 255)
        self.GREEN = (0, 200, 0)
        self.RED = (200, 50, 50)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont("arial", 36)
        self.big_font = pygame.font.SysFont("arial", 65)

        # =========================
        # TISCHE
        # =========================

        self.tables = []

        self.create_tables()

        # =========================
        # STÜHLE
        # =========================

        self.chairs = []

        self.create_chairs()

        # =========================
        # DRAG & DROP
        # =========================

        self.selected_chair = None

        self.offset_x = 0
        self.offset_y = 0

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_tables(self):

        # 4 bis 6 Tische
        self.table_count = random.randint(4, 6)

        spacing = 170

        start_x = self.window_x + 120
        y = self.window_y + 320

        for i in range(self.table_count):

            table_rect = pygame.Rect(
                start_x + i * spacing,
                y,
                120,
                80
            )

            self.tables.append({
                "rect": table_rect,
                "occupied": False
            })

    def create_chairs(self):

        for i in range(self.table_count):

            chair_rect = pygame.Rect(
                random.randint(
                    self.window_x + 80,
                    self.window_x + 950
                ),

                random.randint(
                    self.window_y + 470,
                    self.window_y + 580
                ),

                60,
                60
            )

            self.chairs.append({
                "rect": chair_rect,
                "placed": False
            })

    def draw(self):

        # Hintergrund
        self.screen.fill((25, 25, 35))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "STACK CHAIRS",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 320,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Stelle alle Stühle auf die Tische",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 320,
                self.window_y + 100
            )
        )

        # =========================
        # TISCHE ZEICHNEN
        # =========================

        for table in self.tables:

            rect = table["rect"]

            # Tischplatte
            pygame.draw.rect(
                self.screen,
                self.BROWN,
                rect,
                border_radius=10
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                rect,
                width=4,
                border_radius=10
            )

            # Tischbeine
            leg_width = 12
            leg_height = 60

            pygame.draw.rect(
                self.screen,
                self.LIGHT_BROWN,
                (
                    rect.x + 10,
                    rect.y + rect.height,
                    leg_width,
                    leg_height
                )
            )

            pygame.draw.rect(
                self.screen,
                self.LIGHT_BROWN,
                (
                    rect.x + rect.width - 22,
                    rect.y + rect.height,
                    leg_width,
                    leg_height
                )
            )

        # =========================
        # STÜHLE ZEICHNEN
        # =========================

        for chair in self.chairs:

            rect = chair["rect"]

            # Sitzfläche
            pygame.draw.rect(
                self.screen,
                self.BLUE,
                rect,
                border_radius=8
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                rect,
                width=3,
                border_radius=8
            )

            # Lehne
            pygame.draw.rect(
                self.screen,
                self.BLUE,
                (
                    rect.x + 10,
                    rect.y - 20,
                    40,
                    20
                ),
                border_radius=5
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUSKLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for chair in reversed(self.chairs):

                if chair["rect"].collidepoint(mouse_pos):

                    self.selected_chair = chair

                    self.offset_x = (
                        chair["rect"].x - mouse_pos[0]
                    )

                    self.offset_y = (
                        chair["rect"].y - mouse_pos[1]
                    )

                    break

        # =========================
        # STUHL BEWEGEN
        # =========================

        elif event.type == pygame.MOUSEMOTION:

            if self.selected_chair:

                mouse_pos = pygame.mouse.get_pos()

                self.selected_chair["rect"].x = (
                    mouse_pos[0] + self.offset_x
                )

                self.selected_chair["rect"].y = (
                    mouse_pos[1] + self.offset_y
                )

        # =========================
        # LOSLASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            if self.selected_chair:

                self.snap_chair_to_table(
                    self.selected_chair
                )

            self.selected_chair = None

            self.check_finished()

    def snap_chair_to_table(self, chair):

        for table in self.tables:

            table_rect = table["rect"]

            # Prüfen ob Stuhl auf Tisch
            if table_rect.colliderect(chair["rect"]):

                # Nur wenn Tisch frei
                if not table["occupied"]:

                    chair["rect"].centerx = table_rect.centerx
                    chair["rect"].bottom = table_rect.top + 25

                    chair["placed"] = True
                    table["occupied"] = True

                    return

    def check_finished(self):

        all_done = True

        for chair in self.chairs:

            if not chair["placed"]:
                all_done = False

        if all_done:
            self.finished = True

    def is_finished(self):
        return self.finished

class WindowTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.BLUE = (120, 180, 255)
        self.GRAY = (120, 120, 120)
        self.DARK_GRAY = (70, 70, 70)
        self.BROWN = (120, 80, 40)
        self.GREEN = (0, 200, 0)
        self.RED = (200, 50, 50)
        self.YELLOW = (255, 220, 0)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont("arial", 38)
        self.big_font = pygame.font.SysFont("arial", 65)

        # =========================
        # MODUS
        # =========================

        # True = Fenster öffnen
        # False = Fenster schließen

        self.must_open = random.choice([True, False])

        # =========================
        # FENSTER
        # =========================

        self.windows = []

        self.create_windows()

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_windows(self):

        start_x = self.window_x + 120
        start_y = self.window_y + 180

        spacing_x = 260
        spacing_y = 220

        for row in range(2):

            for col in range(3):

                rect = pygame.Rect(
                    start_x + col * spacing_x,
                    start_y + row * spacing_y,
                    160,
                    140
                )

                # Zufälliger Zustand
                opened = random.choice([True, False])

                self.windows.append({
                    "rect": rect,
                    "open": opened
                })

    def draw(self):

        # Hintergrund
        self.screen.fill((25, 25, 35))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "WINDOW TASK",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 320,
                self.window_y + 20
            )
        )

        # =========================
        # AUFGABE
        # =========================

        if self.must_open:

            task_text = "Öffne alle Fenster"

        else:

            task_text = "Schließe alle Fenster"

        info = self.font.render(
            task_text,
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 370,
                self.window_y + 100
            )
        )

        # =========================
        # FENSTER ZEICHNEN
        # =========================

        for window in self.windows:

            rect = window["rect"]

            # Rahmen
            pygame.draw.rect(
                self.screen,
                self.BROWN,
                rect,
                border_radius=8
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                rect,
                width=4,
                border_radius=8
            )

            # Zustand
            if window["open"]:

                # Geöffnet
                pygame.draw.rect(
                    self.screen,
                    self.BLUE,
                    (
                        rect.x + 15,
                        rect.y + 15,
                        rect.width - 30,
                        rect.height - 30
                    ),
                    border_radius=5
                )

                # Offener Flügel
                pygame.draw.line(
                    self.screen,
                    self.DARK_GRAY,
                    (
                        rect.centerx,
                        rect.y + 15
                    ),
                    (
                        rect.right - 20,
                        rect.bottom - 20
                    ),
                    6
                )

                state_text = self.font.render(
                    "OFFEN",
                    True,
                    self.GREEN
                )

            else:

                # Geschlossen
                pygame.draw.rect(
                    self.screen,
                    self.GRAY,
                    (
                        rect.x + 15,
                        rect.y + 15,
                        rect.width - 30,
                        rect.height - 30
                    ),
                    border_radius=5
                )

                # Kreuz
                pygame.draw.line(
                    self.screen,
                    self.DARK_GRAY,
                    (
                        rect.centerx,
                        rect.y + 15
                    ),
                    (
                        rect.centerx,
                        rect.bottom - 15
                    ),
                    5
                )

                pygame.draw.line(
                    self.screen,
                    self.DARK_GRAY,
                    (
                        rect.x + 15,
                        rect.centery
                    ),
                    (
                        rect.right - 15,
                        rect.centery
                    ),
                    5
                )

                state_text = self.font.render(
                    "ZU",
                    True,
                    self.RED
                )

            self.screen.blit(
                state_text,
                (
                    rect.x + 35,
                    rect.y + 150
                )
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUSKLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for window in self.windows:

                if window["rect"].collidepoint(mouse_pos):

                    # Zustand wechseln
                    window["open"] = not window["open"]

                    self.check_finished()

                    break

    def check_finished(self):

        all_correct = True

        for window in self.windows:

            # Alle müssen offen sein
            if self.must_open:

                if not window["open"]:
                    all_correct = False

            # Alle müssen geschlossen sein
            else:

                if window["open"]:
                    all_correct = False

        if all_correct:
            self.finished = True

    def is_finished(self):
        return self.finished

class CleanBoardTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.BROWN = (120, 80, 40)
        self.BOARD_GREEN = (40, 100, 40)
        self.CHALK = (230, 230, 230)
        self.YELLOW = (255, 220, 0)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont("arial", 36)
        self.big_font = pygame.font.SysFont("arial", 65)

        # =========================
        # TAFEL
        # =========================

        self.board_rect = pygame.Rect(
            self.window_x + 180,
            self.window_y + 170,
            820,
            420
        )

        # =========================
        # SCHMUTZ / KREIDE
        # =========================

        self.dirt_spots = []

        self.create_dirt()

        # =========================
        # SCHWAMM
        # =========================

        self.sponge_rect = pygame.Rect(
            self.window_x + 520,
            self.window_y + 620,
            140,
            60
        )

        self.cleaning = False

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_dirt(self):

        for i in range(40):

            x = random.randint(
                self.board_rect.x + 20,
                self.board_rect.right - 20
            )

            y = random.randint(
                self.board_rect.y + 20,
                self.board_rect.bottom - 20
            )

            radius = random.randint(10, 22)

            self.dirt_spots.append({
                "x": x,
                "y": y,
                "radius": radius
            })

    def draw(self):

        # Hintergrund
        self.screen.fill((25, 25, 35))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius = 20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width = 5,
            border_radius = 20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "CLEAN BOARD",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 310,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Lösche die ganze Tafel",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 390,
                self.window_y + 100
            )
        )

        # =========================
        # TAFEL
        # =========================

        pygame.draw.rect(
            self.screen,
            self.BOARD_GREEN,
            self.board_rect,
            border_radius = 10
        )

        pygame.draw.rect(
            self.screen,
            self.BROWN,
            self.board_rect,
            width = 12,
            border_radius = 10
        )

        # =========================
        # KREIDEFLECKEN
        # =========================

        for dirt in self.dirt_spots:

            pygame.draw.circle(
                self.screen,
                self.CHALK,
                (
                    dirt["x"],
                    dirt["y"]
                ),
                dirt["radius"]
            )

        # =========================
        # SCHWAMM
        # =========================

        pygame.draw.rect(
            self.screen,
            self.YELLOW,
            self.sponge_rect,
            border_radius = 10
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.sponge_rect,
            width = 4,
            border_radius = 10
        )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS GEDRÜCKT
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            if self.sponge_rect.collidepoint(mouse_pos):

                self.cleaning = True

        # =========================
        # MAUS LOSGELASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            self.cleaning = False

        # =========================
        # SCHWAMM BEWEGEN
        # =========================

        elif event.type == pygame.MOUSEMOTION:

            if self.cleaning:

                mouse_pos = pygame.mouse.get_pos()

                self.sponge_rect.center = mouse_pos

                self.clean_board()

    def clean_board(self):

        remaining_dirt = []

        for dirt in self.dirt_spots:

            dirt_rect = pygame.Rect(
                dirt["x"] - dirt["radius"],
                dirt["y"] - dirt["radius"],
                dirt["radius"] * 2,
                dirt["radius"] * 2
            )

            if not self.sponge_rect.colliderect(dirt_rect):

                remaining_dirt.append(dirt)

        self.dirt_spots = remaining_dirt

        # Task fertig
        if len(self.dirt_spots) == 0:

            self.finished = True

    def is_finished(self):
        return self.finished

class DownloadDataTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 60, 60)
        self.BLUE = (80, 140, 255)
        self.DARK_BLUE = (30, 50, 90)
        self.GRAY = (120, 120, 120)
        self.DARK_GRAY = (60, 60, 60)
        self.YELLOW = (255, 220, 0)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont("consolas", 36)
        self.big_font = pygame.font.SysFont("consolas", 60)

        # =========================
        # PC
        # =========================

        self.monitor_rect = pygame.Rect(
            self.window_x + 250,
            self.window_y + 170,
            700,
            350
        )

        self.screen_rect = pygame.Rect(
            self.window_x + 280,
            self.window_y + 200,
            640,
            290
        )

        # =========================
        # DOWNLOAD BUTTON
        # =========================

        self.download_button = pygame.Rect(
            self.window_x + 450,
            self.window_y + 570,
            320,
            80
        )

        # =========================
        # DOWNLOAD STATUS
        # =========================

        self.downloading = False

        self.progress = 0

        self.finished = False

        self.last_update = pygame.time.get_ticks()

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "DOWNLOAD DATA",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 260,
                self.window_y + 30
            )
        )

        # =========================
        # PC MONITOR
        # =========================

        pygame.draw.rect(
            self.screen,
            self.DARK_GRAY,
            self.monitor_rect,
            border_radius=15
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.monitor_rect,
            width=6,
            border_radius=15
        )

        # Bildschirm
        pygame.draw.rect(
            self.screen,
            self.DARK_BLUE,
            self.screen_rect,
            border_radius=10
        )

        # =========================
        # DOWNLOAD TEXT
        # =========================

        if self.downloading and not self.finished:
            status = self.font.render(
                "Downloading files...",
                True,
                self.GREEN
            )

        elif self.finished:
            status = self.font.render(
                "Download Complete!",
                True,
                self.GREEN
            )

        else:
            status = self.font.render(
                "Ready to download",
                True,
                self.YELLOW
            )

        self.screen.blit(
            status,
            (
                self.screen_rect.x + 140,
                self.screen_rect.y + 40
            )
        )

        # =========================
        # PROGRESS BAR
        # =========================

        bar_x = self.screen_rect.x + 70
        bar_y = self.screen_rect.y + 140
        bar_width = 500
        bar_height = 45

        # Hintergrund
        pygame.draw.rect(
            self.screen,
            self.GRAY,
            (
                bar_x,
                bar_y,
                bar_width,
                bar_height
            ),
            border_radius=10
        )

        # Fortschritt
        pygame.draw.rect(
            self.screen,
            self.GREEN,
            (
                bar_x,
                bar_y,
                int(bar_width * (self.progress / 100)),
                bar_height
            ),
            border_radius=10
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            (
                bar_x,
                bar_y,
                bar_width,
                bar_height
            ),
            width=4,
            border_radius=10
        )

        # Prozentzahl
        percent_text = self.big_font.render(
            f"{self.progress}%",
            True,
            self.WHITE
        )

        self.screen.blit(
            percent_text,
            (
                self.screen_rect.x + 250,
                self.screen_rect.y + 210
            )
        )

        # =========================
        # DOWNLOAD BUTTON
        # =========================

        if not self.downloading and not self.finished:

            pygame.draw.rect(
                self.screen,
                self.BLUE,
                self.download_button,
                border_radius=15
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                self.download_button,
                width=5,
                border_radius=15
            )

            button_text = self.font.render(
                "START DOWNLOAD",
                True,
                self.WHITE
            )

            self.screen.blit(
                button_text,
                (
                    self.download_button.x + 25,
                    self.download_button.y + 20
                )
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def update(self):

        if self.downloading and not self.finished:

            current_time = pygame.time.get_ticks()

            # Alle 80ms Fortschritt erhöhen
            if current_time - self.last_update > 80:

                self.progress += 1

                self.last_update = current_time

                if self.progress >= 100:

                    self.progress = 100

                    self.finished = True

                    self.downloading = False

    def handle_event(self, event):

        if self.finished:
            return

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            if (self.download_button.collidepoint(mouse_pos) and not self.downloading):
                self.downloading = True
                self.progress = 0
                self.last_update = pygame.time.get_ticks()

    def is_finished(self):
        return self.finished

class ProjectorWiresTask:
    def __init__(self, screen):

        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)

        self.RED = (220, 60, 60)
        self.BLUE = (60, 120, 255)
        self.GREEN = (60, 200, 100)
        self.YELLOW = (255, 220, 0)

        self.GRAY = (120, 120, 120)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont(
            "arial",
            40
        )

        self.big_font = pygame.font.SysFont(
            "arial",
            70
        )

        # =========================
        # KABEL
        # =========================

        self.left_points = []
        self.right_points = []

        self.create_wire_points()

        # Verbindungslinien
        self.connections = []

        # Aktuelles Kabel
        self.selected_wire = None

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_wire_points(self):

        colors = [
            self.RED,
            self.BLUE,
            self.GREEN,
            self.YELLOW
        ]

        # LINKE SEITE
        for i in range(4):

            x = self.window_x + 220
            y = self.window_y + 220 + (i * 110)

            self.left_points.append({
                "pos": (x, y),
                "color": colors[i],
                "connected": False
            })

        # RECHTE SEITE (gemischt)

        shuffled = colors.copy()
        random.shuffle(shuffled)

        for i in range(4):

            x = self.window_x + 950
            y = self.window_y + 220 + (i * 110)

            self.right_points.append({
                "pos": (x, y),
                "color": shuffled[i],
                "connected": False
            })

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "CONNECT PROJECTOR",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 250,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Verbinde die richtigen Kabel",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 320,
                self.window_y + 100
            )
        )

        # =========================
        # PROJEKTOR
        # =========================

        projector_rect = pygame.Rect(
            self.window_x + 870,
            self.window_y + 600,
            220,
            90
        )

        pygame.draw.rect(
            self.screen,
            self.GRAY,
            projector_rect,
            border_radius = 15
        )

        projector_text = self.font.render(
            "PROJECTOR",
            True,
            self.BLACK
        )

        self.screen.blit(
            projector_text,
            (
                projector_rect.x + 10,
                projector_rect.y + 20
            )
        )

        # =========================
        # PC
        # =========================

        pc_rect = pygame.Rect(
            self.window_x + 120,
            self.window_y + 600,
            180,
            90
        )

        pygame.draw.rect(
            self.screen,
            self.GRAY,
            pc_rect,
            border_radius=15
        )

        pc_text = self.font.render(
            "PC",
            True,
            self.BLACK
        )

        self.screen.blit(
            pc_text,
            (
                pc_rect.x + 60,
                pc_rect.y + 20
            )
        )

        # =========================
        # VERBINDUNGEN
        # =========================

        for connection in self.connections:

            pygame.draw.line(
                self.screen,
                connection["color"],
                connection["start"],
                connection["end"],
                8
            )

        # =========================
        # AKTUELLES KABEL
        # =========================

        if self.selected_wire:

            mouse_pos = pygame.mouse.get_pos()

            pygame.draw.line(
                self.screen,
                self.selected_wire["color"],
                self.selected_wire["pos"],
                mouse_pos,
                8
            )

        # =========================
        # PUNKTE
        # =========================

        for point in self.left_points:

            pygame.draw.circle(
                self.screen,
                point["color"],
                point["pos"],
                25
            )

            pygame.draw.circle(
                self.screen,
                self.BLACK,
                point["pos"],
                25,
                4
            )

        for point in self.right_points:

            pygame.draw.circle(
                self.screen,
                point["color"],
                point["pos"],
                25
            )

            pygame.draw.circle(
                self.screen,
                self.BLACK,
                point["pos"],
                25,
                4
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for point in self.left_points:

                distance = math.hypot(
                    mouse_pos[0] - point["pos"][0],
                    mouse_pos[1] - point["pos"][1]
                )

                if distance < 25 and not point["connected"]:

                    self.selected_wire = point
                    break

        # =========================
        # LOSLASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            if self.selected_wire:

                mouse_pos = pygame.mouse.get_pos()

                for point in self.right_points:

                    distance = math.hypot(
                        mouse_pos[0] - point["pos"][0],
                        mouse_pos[1] - point["pos"][1]
                    )

                    if distance < 25:

                        # Richtige Farbe?
                        if (
                            point["color"]
                            ==
                            self.selected_wire["color"]
                            and
                            not point["connected"]
                        ):

                            self.connections.append({
                                "start": self.selected_wire["pos"],
                                "end": point["pos"],
                                "color": point["color"]
                            })

                            self.selected_wire["connected"] = True
                            point["connected"] = True

                            break

                self.selected_wire = None
                self.check_finished()

    def check_finished(self):

        all_connected = True

        for point in self.left_points:

            if not point["connected"]:
                all_connected = False

        if all_connected:
            self.finished = True

    def is_finished(self):
        return self.finished

class VirusScanTask:
    def __init__(self, screen):

        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)

        self.RED = (220, 60, 60)
        self.GREEN = (60, 200, 100)
        self.BLUE = (80, 120, 255)

        self.GRAY = (100, 100, 100)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont(
            "arial",
            25
        )

        self.big_font = pygame.font.SysFont(
            "arial",
            65
        )

        # =========================
        # DATEIEN
        # =========================

        self.files = []

        self.create_files()

        # =========================
        # STATUS
        # =========================

        self.finished = False

        self.virus_count = 0

        for file in self.files:
            if file["virus"]:
                self.virus_count += 1

    def create_files(self):

        names = [
            "Münzwurf.js",
            "Tutorial_Docker2.pdf",
            "HuRenRef.exe",
            "PasswortManager2.pdf",
            "Free_Robux.exe",
            "Energieschema.png",
            "Schöne_Frau.jpg.exe",
            "Hacker_Tool.exe",
            "AA_Hexenverfolgung.docx",
            "Passwörter.txt"
        ]

        virus_files = []

        for y in range(6):
            virus_files.append(names[random.randint(0, len(names) - 1)])       

        start_x = self.window_x + 120
        start_y = self.window_y + 180

        index = 0

        for row in range(2):

            for col in range(5):

                name = names[index]

                rect = pygame.Rect(
                    start_x + (col * 210),
                    start_y + (row * 240),
                    140,
                    140
                )

                self.files.append({
                    "name": name,
                    "rect": rect,
                    "virus": name in virus_files,
                    "removed": False
                })

                index += 1

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "VIRUS SCAN",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 360,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Entferne alle verdächtigen Dateien",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 280,
                self.window_y + 100
            )
        )

        # =========================
        # PC RAHMEN
        # =========================

        monitor_rect = pygame.Rect(
            self.window_x + 70,
            self.window_y + 150,
            1060,
            500
        )

        pygame.draw.rect(
            self.screen,
            (40, 40, 50),
            monitor_rect,
            border_radius=15
        )

        # =========================
        # DATEIEN
        # =========================

        for file in self.files:

            if file["removed"]:
                continue

            # Datei Icon

            pygame.draw.rect(
                self.screen,
                self.BLUE,
                file["rect"],
                border_radius = 10
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                file["rect"],
                width = 3,
                border_radius = 10
            )

            # Datei Text

            text = self.font.render(
                file["name"],
                True,
                self.WHITE
            )

            text_rect = text.get_rect(
                center=(
                    file["rect"].centerx,
                    file["rect"].bottom + 25
                )
            )

            self.screen.blit(
                text,
                text_rect
            )

            # Warnsymbol für Virus-Dateien

            if file["virus"]:

                pygame.draw.circle(
                    self.screen,
                    self.RED,
                    (
                        file["rect"].right - 15,
                        file["rect"].y + 15
                    ),
                    12
                )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for file in self.files:

                if file["removed"]:
                    continue

                if file["rect"].collidepoint(mouse_pos):

                    # Nur Virus-Dateien entfernen

                    if file["virus"]:

                        file["removed"] = True

                        self.check_finished()

                    break

    def check_finished(self):

        removed_count = 0

        for file in self.files:

            if file["virus"] and file["removed"]:
                removed_count += 1

        if removed_count >= self.virus_count:
            self.finished = True

    def is_finished(self):
        return self.finished

class PrinterPaperTask:
    def __init__(self, screen):

        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)

        self.GRAY = (110, 110, 110)
        self.DARK_GRAY = (60, 60, 60)

        self.GREEN = (60, 200, 100)
        self.BLUE = (90, 130, 255)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont(
            "arial",
            40
        )

        self.big_font = pygame.font.SysFont(
            "arial",
            70
        )

        # =========================
        # DRUCKER
        # =========================

        self.printer_rect = pygame.Rect(
            self.window_x + 650,
            self.window_y + 180,
            380,
            350
        )

        # Papierfach

        self.paper_slot = pygame.Rect(
            self.window_x + 760,
            self.window_y + 390,
            150,
            90
        )

        # =========================
        # PAPIER
        # =========================

        self.paper_stack = pygame.Rect(
            self.window_x + 180,
            self.window_y + 340,
            140,
            80
        )

        self.paper_inserted = False

        # =========================
        # DRAG & DROP
        # =========================

        self.dragging = False

        self.offset_x = 0
        self.offset_y = 0

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "REFILL PRINTER",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 280,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Setze den Papierstapel richtig ein",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 260,
                self.window_y + 100
            )
        )

        # =========================
        # DRUCKER
        # =========================

        pygame.draw.rect(
            self.screen,
            self.GRAY,
            self.printer_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.printer_rect,
            width=5,
            border_radius=20
        )

        # Drucker Display

        display_rect = pygame.Rect(
            self.printer_rect.x + 90,
            self.printer_rect.y + 50,
            200,
            60
        )

        pygame.draw.rect(
            self.screen,
            self.DARK_GRAY,
            display_rect,
            border_radius=10
        )

        if not self.paper_inserted:

            display_text = self.font.render(
                "NO PAPER",
                True,
                (255, 80, 80)
            )

        else:

            display_text = self.font.render(
                "READY",
                True,
                self.GREEN
            )

        self.screen.blit(
            display_text,
            (
                display_rect.x + 25,
                display_rect.y + 10
            )
        )

        # =========================
        # PAPIERFACH
        # =========================

        pygame.draw.rect(
            self.screen,
            self.DARK_GRAY,
            self.paper_slot,
            border_radius=10
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.paper_slot,
            width=4,
            border_radius=10
        )

        slot_text = self.font.render(
            "TRAY",
            True,
            self.WHITE
        )

        self.screen.blit(
            slot_text,
            (
                self.paper_slot.x + 35,
                self.paper_slot.y + 20
            )
        )

        # =========================
        # PAPIERSTAPEL
        # =========================

        if not self.paper_inserted:

            for i in range(6):

                paper_rect = pygame.Rect(
                    self.paper_stack.x,
                    self.paper_stack.y - i * 3,
                    self.paper_stack.width,
                    self.paper_stack.height
                )

                pygame.draw.rect(
                    self.screen,
                    self.WHITE,
                    paper_rect,
                    border_radius=4
                )

                pygame.draw.rect(
                    self.screen,
                    self.BLACK,
                    paper_rect,
                    width=2,
                    border_radius=4
                )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            if (
                self.paper_stack.collidepoint(mouse_pos)
                and
                not self.paper_inserted
            ):

                self.dragging = True

                self.offset_x = (
                    self.paper_stack.x - mouse_pos[0]
                )

                self.offset_y = (
                    self.paper_stack.y - mouse_pos[1]
                )

        # =========================
        # BEWEGEN
        # =========================

        elif event.type == pygame.MOUSEMOTION:

            if self.dragging:

                mouse_pos = pygame.mouse.get_pos()

                self.paper_stack.x = (
                    mouse_pos[0] + self.offset_x
                )

                self.paper_stack.y = (
                    mouse_pos[1] + self.offset_y
                )

        # =========================
        # LOSLASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            if self.dragging:

                self.dragging = False

                # Papier korrekt eingesetzt?

                if self.paper_slot.colliderect(
                    self.paper_stack
                ):

                    self.paper_stack.x = (
                        self.paper_slot.x + 5
                    )

                    self.paper_stack.y = (
                        self.paper_slot.y + 5
                    )

                    self.paper_inserted = True

                    self.check_finished()

    def check_finished(self):

        if self.paper_inserted:
            self.finished = True

    def is_finished(self):
        return self.finished

class BunsenBurnerTask:
    def __init__(self, screen):

        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1200
        self.window_height = 750

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)

        self.RED = (220, 60, 60)
        self.GREEN = (60, 200, 100)
        self.BLUE = (70, 120, 255)

        self.GRAY = (120, 120, 120)
        self.DARK_GRAY = (60, 60, 60)

        self.ORANGE = (255, 140, 0)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont(
            "arial",
            40
        )

        self.big_font = pygame.font.SysFont(
            "arial",
            70
        )

        # =========================
        # TEMPERATUR
        # =========================

        self.temperature = 20

        self.min_temp = 45
        self.max_temp = 65

        # =========================
        # REGLER
        # =========================

        self.slider_rect = pygame.Rect(
            self.window_x + 220,
            self.window_y + 580,
            700,
            12
        )

        self.knob_rect = pygame.Rect(
            self.slider_rect.x,
            self.slider_rect.y - 14,
            30,
            40
        )

        self.dragging = False

        # =========================
        # STATUS
        # =========================

        self.finished = False

        self.hold_timer = 0
        self.required_hold_time = 180

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "BUNSEN BURNER",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 240,
                self.window_y + 20
            )
        )

        info = self.font.render(
            "Halte die Temperatur im grünen Bereich",
            True,
            self.BLACK
        )

        self.screen.blit(
            info,
            (
                self.window_x + 220,
                self.window_y + 100
            )
        )

        # =========================
        # TEMPERATUR ANZEIGE
        # =========================

        temp_text = self.big_font.render(
            f"{int(self.temperature)}°C",
            True,
            self.BLACK
        )

        self.screen.blit(
            temp_text,
            (
                self.window_x + 470,
                self.window_y + 170
            )
        )

        # =========================
        # THERMOMETER
        # =========================

        thermometer_rect = pygame.Rect(
            self.window_x + 120,
            self.window_y + 180,
            60,
            320
        )

        pygame.draw.rect(
            self.screen,
            self.GRAY,
            thermometer_rect,
            border_radius=20
        )

        # Temperaturfüllung

        fill_height = int(
            (self.temperature / 100) * 300
        )

        fill_rect = pygame.Rect(
            thermometer_rect.x + 10,
            thermometer_rect.bottom - fill_height - 10,
            40,
            fill_height
        )

        # Farbe je nach Temperatur

        if self.min_temp <= self.temperature <= self.max_temp:
            temp_color = self.GREEN
        elif self.temperature < self.min_temp:
            temp_color = self.BLUE
        else:
            temp_color = self.RED

        pygame.draw.rect(
            self.screen,
            temp_color,
            fill_rect,
            border_radius=10
        )

        # =========================
        # GRÜNER BEREICH
        # =========================

        green_zone_y = (
            thermometer_rect.bottom
            -
            int((self.max_temp / 100) * 300)
        )

        green_zone_height = int(
            ((self.max_temp - self.min_temp) / 100)
            * 300
        )

        pygame.draw.rect(
            self.screen,
            (100, 255, 100),
            (
                thermometer_rect.x - 15,
                green_zone_y,
                90,
                green_zone_height
            ),
            width=4,
            border_radius=10
        )

        # =========================
        # BRENNER
        # =========================

        burner_rect = pygame.Rect(
            self.window_x + 500,
            self.window_y + 330,
            160,
            180
        )

        pygame.draw.rect(
            self.screen,
            self.DARK_GRAY,
            burner_rect,
            border_radius=20
        )

        # Flamme

        flame_height = int(
            self.temperature * 2
        )

        flame_color = temp_color

        flame_points = [
            (
                burner_rect.centerx,
                burner_rect.y - flame_height
            ),

            (
                burner_rect.x + 35,
                burner_rect.y
            ),

            (
                burner_rect.right - 35,
                burner_rect.y
            )
        ]

        pygame.draw.polygon(
            self.screen,
            flame_color,
            flame_points
        )

        # =========================
        # SLIDER
        # =========================

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.slider_rect,
            border_radius=10
        )

        # Grüner Bereich am Slider

        green_x = (
            self.slider_rect.x
            +
            int((self.min_temp / 100)
            * self.slider_rect.width)
        )

        green_width = int(
            ((self.max_temp - self.min_temp) / 100)
            * self.slider_rect.width
        )

        pygame.draw.rect(
            self.screen,
            self.GREEN,
            (
                green_x,
                self.slider_rect.y - 4,
                green_width,
                20
            ),
            border_radius=10
        )

        # Regler

        pygame.draw.rect(
            self.screen,
            self.ORANGE,
            self.knob_rect,
            border_radius=10
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.knob_rect,
            width=3,
            border_radius=10
        )

        # =========================
        # PROGRESS
        # =========================

        progress = int(
            (self.hold_timer / self.required_hold_time)
            * 100
        )

        progress_text = self.font.render(
            f"Stabilisieren: {progress}%",
            True,
            self.BLACK
        )

        self.screen.blit(
            progress_text,
            (
                self.window_x + 400,
                self.window_y + 640
            )
        )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def update(self):

        if self.finished:
            return

        # =========================
        # TEMPERATUR CHECK
        # =========================

        if (
            self.min_temp
            <=
            self.temperature
            <=
            self.max_temp
        ):

            self.hold_timer += 1

        else:

            self.hold_timer = 0

        # Task geschafft?

        if self.hold_timer >= self.required_hold_time:

            self.finished = True

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            if self.knob_rect.collidepoint(mouse_pos):

                self.dragging = True

        # =========================
        # MAUS BEWEGEN
        # =========================

        elif event.type == pygame.MOUSEMOTION:

            if self.dragging:

                mouse_x = pygame.mouse.get_pos()[0]

                # Slider Begrenzung

                min_x = self.slider_rect.x
                max_x = (
                    self.slider_rect.right
                    - self.knob_rect.width
                )

                self.knob_rect.x = max(
                    min_x,
                    min(mouse_x, max_x)
                )

                # Temperatur berechnen

                percent = (
                    (self.knob_rect.x - min_x)
                    /
                    (max_x - min_x)
                )

                self.temperature = percent * 100

        # =========================
        # LOSLASSEN
        # =========================

        elif event.type == pygame.MOUSEBUTTONUP:

            self.dragging = False

    def is_finished(self):
        return self.finished

class ChemicalMixTask:
    def __init__(self, screen):

        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================

        self.window_width = 1250
        self.window_height = 760

        self.window_x = (
            self.screen_width - self.window_width
        ) // 2

        self.window_y = (
            self.screen_height - self.window_height
        ) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================

        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)

        self.RED = (220, 60, 60)
        self.BLUE = (60, 120, 255)
        self.YELLOW = (255, 220, 0)

        self.GREEN = (60, 200, 100)
        self.PURPLE = (170, 0, 255)
        self.ORANGE = (255, 140, 0)

        self.GRAY = (120, 120, 120)

        # =========================
        # SCHRIFT
        # =========================

        self.font = pygame.font.SysFont(
            "arial",
            30
        )

        self.big_font = pygame.font.SysFont(
            "arial",
            65
        )

        # =========================
        # REZEPT
        # =========================

        self.recipes = [
            {
                "result_name": "GREEN",
                "result_color": self.GREEN,
                "needed": ["BLUE", "YELLOW"]
            },

            {
                "result_name": "PURPLE",
                "result_color": self.PURPLE,
                "needed": ["RED", "BLUE"]
            },

            {
                "result_name": "ORANGE",
                "result_color": self.ORANGE,
                "needed": ["RED", "YELLOW"]
            }
        ]

        self.current_recipe = random.choice(
            self.recipes
        )

        # =========================
        # CHEMIKALIEN
        # =========================

        self.chemicals = []

        self.create_chemicals()

        # =========================
        # MISCHBECHER
        # =========================

        self.cauldron_rect = pygame.Rect(
            self.window_x + 500,
            self.window_y + 260,
            240,
            220
        )

        self.inserted = []

        # =========================
        # STATUS
        # =========================

        self.finished = False

    def create_chemicals(self):

        chemicals_data = [

            {
                "name": "RED",
                "color": self.RED,
                "x": self.window_x + 120
            },

            {
                "name": "BLUE",
                "color": self.BLUE,
                "x": self.window_x + 120
            },

            {
                "name": "YELLOW",
                "color": self.YELLOW,
                "x": self.window_x + 120
            }
        ]

        for i, chem in enumerate(chemicals_data):

            rect = pygame.Rect(
                chem["x"],
                self.window_y + 220 + (i * 150),
                120,
                120
            )

            self.chemicals.append({

                "name": chem["name"],
                "color": chem["color"],
                "rect": rect,
                "used": False
            })

    def draw(self):

        # Hintergrund
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================

        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL
        # =========================

        title = self.big_font.render(
            "CHEMICAL MIX",
            True,
            self.BLACK
        )

        self.screen.blit(
            title,
            (
                self.window_x + 330,
                self.window_y + 20
            )
        )

        # =========================
        # AUFGABE
        # =========================

        recipe_text = self.font.render(
            f"Erstelle: {self.current_recipe['result_name']}",
            True,
            self.BLACK
        )

        self.screen.blit(
            recipe_text,
            (
                self.window_x + 390,
                self.window_y + 100
            )
        )

        # Zielfarbe

        pygame.draw.circle(
            self.screen,
            self.current_recipe["result_color"],
            (
                self.window_x + 830,
                self.window_y + 120
            ),
            35
        )

        pygame.draw.circle(
            self.screen,
            self.BLACK,
            (
                self.window_x + 830,
                self.window_y + 120
            ),
            35,
            4
        )

        # =========================
        # CHEMIKALIEN
        # =========================

        for chem in self.chemicals:

            if chem["used"]:
                continue

            pygame.draw.rect(
                self.screen,
                chem["color"],
                chem["rect"],
                border_radius=15
            )

            pygame.draw.rect(
                self.screen,
                self.BLACK,
                chem["rect"],
                width=4,
                border_radius=15
            )

            text = self.font.render(
                chem["name"],
                True,
                self.WHITE
            )

            text_rect = text.get_rect(
                center=chem["rect"].center
            )

            self.screen.blit(
                text,
                text_rect
            )

        # =========================
        # MISCHBECHER
        # =========================

        pygame.draw.rect(
            self.screen,
            self.GRAY,
            self.cauldron_rect,
            border_radius=20
        )

        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.cauldron_rect,
            width=5,
            border_radius=20
        )

        cauldron_text = self.font.render(
            "MIXER",
            True,
            self.BLACK
        )

        self.screen.blit(
            cauldron_text,
            (
                self.cauldron_rect.x + 55,
                self.cauldron_rect.y + 20
            )
        )

        # =========================
        # EINGEFÜLLTE CHEMIKALIEN
        # =========================

        for i, chem in enumerate(self.inserted):

            pygame.draw.circle(
                self.screen,
                chem["color"],
                (
                    self.cauldron_rect.centerx,
                    self.cauldron_rect.y + 90 + (i * 50)
                ),
                25
            )

            pygame.draw.circle(
                self.screen,
                self.BLACK,
                (
                    self.cauldron_rect.centerx,
                    self.cauldron_rect.y + 90 + (i * 50)
                ),
                25,
                3
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):

        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================

        if event.type == pygame.MOUSEBUTTONDOWN:

            mouse_pos = pygame.mouse.get_pos()

            for chem in self.chemicals:

                if chem["used"]:
                    continue

                if chem["rect"].collidepoint(mouse_pos):

                    chem["used"] = True

                    self.inserted.append(chem)

                    self.check_mix()

                    break

    def check_mix(self):

        # Schon genug Zutaten?

        if len(self.inserted) < 2:
            return

        inserted_names = []

        for chem in self.inserted:

            inserted_names.append(
                chem["name"]
            )

        inserted_names.sort()

        needed = self.current_recipe["needed"].copy()
        needed.sort()

        # Richtige Mischung?

        if inserted_names == needed:

            self.finished = True

        else:

            # Falsche Mischung -> Reset

            for chem in self.chemicals:
                chem["used"] = False

            self.inserted.clear()

    def is_finished(self):
        return self.finished

class PencilCaseTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.DESK_COLOR = (220, 200, 170) # Helles Holz für den Schreibtisch-Hintergrund
        
        # Farben für das Schreibzubehör
        self.PENCIL_YELLOW = (245, 210, 80)
        self.MARKER_NEON = (235, 255, 0)
        self.ERASER_PINK = (255, 140, 160)
        self.RULER_BLUE = (100, 180, 240)
        self.CASE_PURPLE = (120, 60, 180) # Farbe des Federmäppchens

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 35)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # FEDERMÄPPCHEN (Das Ziel-Areal)
        # =========================
        # Ein großes Mäppchen auf der rechten Seite
        self.pencil_case = pygame.Rect(
            self.window_x + 600,
            self.window_y + 200,
            420,
            400
        )

        # =========================
        # SCHULZUBEHÖR (Items)
        # =========================
        self.items = []
        self.create_items()

        # =========================
        # DRAG & DROP
        # =========================
        self.selected_item = None
        self.offset_x = 0
        self.offset_y = 0

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_items(self):
        # Definition der verschiedenen Gegenstände (Name, Breite, Höhe, Farbe)
        item_templates = [
            {"name": "Bleistift 1", "w": 25, "h": 180, "color": self.PENCIL_YELLOW},
            {"name": "Bleistift 2", "w": 25, "h": 180, "color": self.PENCIL_YELLOW},
            {"name": "Textmarker", "w": 45, "h": 130, "color": self.MARKER_NEON},
            {"name": "Radiergummi", "w": 65, "h": 40, "color": self.ERASER_PINK},
            {"name": "Lineal", "w": 35, "h": 220, "color": self.RULER_BLUE}
        ]

        # Bereich auf der linken Seite des Tisches, wo die Sachen herumliegen
        spawn_zone_x_start = self.window_x + 50
        spawn_zone_x_end = self.window_x + 450
        spawn_zone_y_start = self.window_y + 200
        spawn_zone_y_end = self.window_y + 550

        for temp in item_templates:
            # Zufällige Position auf der linken Tischseite generieren
            rect = pygame.Rect(
                random.randint(spawn_zone_x_start, spawn_zone_x_end - temp["w"]),
                random.randint(spawn_zone_y_start, spawn_zone_y_end - temp["h"]),
                temp["w"],
                temp["h"]
            )

            self.items.append({
                "name": temp["name"],
                "rect": rect,
                "color": temp["color"]
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Schreibtisch-Optik)
        # =========================
        pygame.draw.rect(
            self.screen,
            self.DESK_COLOR,
            self.task_rect,
            border_radius=20
        )

        # Schwarzer Rand um das Minigame-Fenster
        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render(
            "PACK YOUR BAG",
            True,
            self.BLACK
        )
        self.screen.blit(title, (self.window_x + 300, self.window_y + 20))

        info = self.font.render(
            "Räume alle Schulsachen ins Federmäppchen!",
            True,
            self.BLACK
        )
        self.screen.blit(info, (self.window_x + 230, self.window_y + 100))

        # =========================
        # FEDERMÄPPCHEN ZEICHNEN
        # =========================
        # Das Innere/Öffnung des Mäppchens
        pygame.draw.rect(
            self.screen,
            (60, 30, 90), # Dunkleres Lila für das Innere
            self.pencil_case,
            border_radius=15
        )
        # Die dicke Außenseite des Mäppchens
        pygame.draw.rect(
            self.screen,
            self.CASE_PURPLE,
            self.pencil_case,
            width=12,
            border_radius=15
        )

        # Text auf dem Mäppchen
        case_text = self.font.render(
            "FEDERMÄPPCHEN",
            True,
            self.WHITE
        )
        self.screen.blit(
            case_text,
            (
                self.pencil_case.x + 80,
                self.pencil_case.y + 20
            )
        )

        # =========================
        # GEGENSTÄNDE ZEICHNEN
        # =========================
        # Zuerst alle unselektierten Items zeichnen
        for item in self.items:
            if item != self.selected_item:
                self.draw_single_item(item)
                
        # Das aktuell gezogene Item ganz oben zeichnen
        if self.selected_item:
            self.draw_single_item(self.selected_item)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            # Text mit dunklem Hintergrund hinterlegen für bessere Lesbarkeit
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def draw_single_item(self, item):
        # Gegenstand Körper
        pygame.draw.rect(
            self.screen,
            item["color"],
            item["rect"],
            border_radius=5
        )
        # Gegenstand Umrandung
        pygame.draw.rect(
            self.screen,
            self.BLACK,
            item["rect"],
            width=3,
            border_radius=5
        )

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Item greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            # reversed(), damit man das oberste Item greift, wenn sie übereinander liegen
            for item in reversed(self.items):
                if item["rect"].collidepoint(mouse_pos):
                    self.selected_item = item
                    self.offset_x = item["rect"].x - mouse_pos[0]
                    self.offset_y = item["rect"].y - mouse_pos[1]
                    break

        # =========================
        # ITEM BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_item:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_item["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_item["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.selected_item:
                self.selected_item = None
                self.check_finished()

    def check_finished(self):
        # Prüfen, ob alle Gegenstände komplett im Federmäppchen liegen
        all_inside = True

        for item in self.items:
            if not self.pencil_case.contains(item["rect"]):
                all_inside = False
                break

        if all_inside:
            self.finished = True

    def is_finished(self):
        return self.finished

class KeyboardCleanTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.GREY = (180, 185, 190)       # Tastatur-Gehäuse
        self.KEY_GREY = (220, 225, 230)   # Normale Tasten
        self.CRUMB_BROWN = (100, 70, 40)   # Farbe der lästigen Krümel

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 35)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # TASTATUR & TASTEN (Areal)
        # =========================
        # Das graue Tastaturgehäuse unten mittig
        self.keyboard_rect = pygame.Rect(
            self.window_x + 100,
            self.window_y + 220,
            900,
            400
        )

        # Die Leertaste (Spacebar) als zentrales Element im Fokus
        self.spacebar_rect = pygame.Rect(
            self.keyboard_rect.x + 250,
            self.keyboard_rect.y + 280,
            400,
            70
        )

        # =========================
        # KRÜMEL (Crumbs)
        # =========================
        self.crumbs = []
        self.create_crumbs()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_crumbs(self):
        # Wir spawnen 12 Krümel. 
        # Damit es Sinn macht, spawnen die meisten direkt auf oder ganz nah an der Leertaste.
        num_crumbs = 12
        
        for _ in range(num_crumbs):
            # Größe des Krümels (zufällig zwischen 15 und 25 Pixeln, damit sie unregelmäßig wirken)
            size = random.randint(15, 25)
            
            # Suchbereich um die Leertaste herum eingrenzen
            # Krümel können direkt auf der Leertaste oder im direkten Umkreis liegen
            rect = pygame.Rect(
                random.randint(self.spacebar_rect.x - 40, self.spacebar_rect.x + self.spacebar_rect.width + 20),
                random.randint(self.spacebar_rect.y - 60, self.spacebar_rect.y + self.spacebar_rect.height + 20),
                size,
                size
            )
            
            self.crumbs.append({
                "rect": rect,
                "color": self.CRUMB_BROWN
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================
        pygame.draw.rect(
            self.screen,
            self.WHITE,
            self.task_rect,
            border_radius=20
        )

        # Schwarzer Rand um das Minigame-Fenster
        pygame.draw.rect(
            self.screen,
            self.BLACK,
            self.task_rect,
            width=5,
            border_radius=20
        )

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render(
            "CLEAN KEYBOARD",
            True,
            self.BLACK
        )
        self.screen.blit(title, (self.window_x + 260, self.window_y + 20))

        info = self.font.render(
            "Klicke die Krümel weg, bevor die Leertaste stecken bleibt!",
            True,
            self.BLACK
        )
        self.screen.blit(info, (self.window_x + 150, self.window_y + 110))

        # =========================
        # TASTATUR ZEICHNEN
        # =========================
        # Gehäuse
        pygame.draw.rect(self.screen, self.GREY, self.keyboard_rect, border_radius=15)
        pygame.draw.rect(self.screen, self.BLACK, self.keyboard_rect, width=4, border_radius=15)

        # Ein paar "Fake"-Tasten in den oberen Reihen andeuten, damit es wie eine Tastatur aussieht
        for row in range(3):
            for col in range(10):
                fake_key = pygame.Rect(
                    self.keyboard_rect.x + 40 + (col * 85),
                    self.keyboard_rect.y + 30 + (row * 75),
                    70,
                    55
                )
                # Nur zeichnen, wenn es nicht mit der Leertaste unten kollidiert
                if not fake_key.colliderect(self.spacebar_rect):
                    pygame.draw.rect(self.screen, self.KEY_GREY, fake_key, border_radius=8)
                    pygame.draw.rect(self.screen, self.BLACK, fake_key, width=2, border_radius=8)

        # Die echte Leertaste zeichnen
        pygame.draw.rect(self.screen, self.KEY_GREY, self.spacebar_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, self.spacebar_rect, width=4, border_radius=10)

        # =========================
        # KRÜMEL ZEICHNEN
        # =========================
        for crumb in self.crumbs:
            # Krümel als unregelmäßige "Kreise" zeichnen (sieht natürlicher aus als Boxen)
            pygame.draw.ellipse(
                self.screen,
                crumb["color"],
                crumb["rect"]
            )
            # Kleiner schwarzer Rand für den Kontrast
            pygame.draw.ellipse(
                self.screen,
                self.BLACK,
                crumb["rect"],
                width=2
            )

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render(
                "TASK FINISHED",
                True,
                self.GREEN
            )
            
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Krümel entfernen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            # Wir gehen die Liste rückwärts durch, um den getroffenen Krümel zu löschen
            for crumb in reversed(self.crumbs):
                if crumb["rect"].collidepoint(mouse_pos):
                    self.crumbs.remove(crumb) # Krümel wird aus der Liste gelöscht!
                    self.check_finished()
                    break # Loop abbrechen, damit man nur einen Krümel pro Klick erwischt

    def check_finished(self):
        # Wenn die Liste der Krümel leer ist, ist die Tastatur sauber!
        if len(self.crumbs) == 0:
            self.finished = True

    def is_finished(self):
        return self.finished

class MicroscopeFocusTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.MICROSCOPE_BODY = (190, 200, 210) # Labor-Grau
        self.LENS_BG = (220, 240, 255)         # Hellblaues Licht im Objektiv
        self.KNOB_COLOR = (80, 85, 90)         # Dunkelgrau für das Rad

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 35)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # MIKROSKOP STRUKTUR
        # =========================
        # Das runde Sichtfenster des Mikroskops (Objektiv)
        self.lens_center = (self.window_x + 400, self.window_y + 420)
        self.lens_radius = 200

        # Das drehbare Fokusrad auf der rechten Seite
        self.knob_rect = pygame.Rect(
            self.window_x + 850,
            self.window_y + 350,
            100,
            140
        )

        # =========================
        # FOKUS LOGIK & WERTE
        # =========================
        # Der Regler-Y-Wert bestimmt den aktuellen Fokus. Er startet ganz oben (unscharf).
        self.knob_y = self.knob_rect.y + 10
        
        # Der perfekte Fokuspunkt liegt genau in der Mitte des Rades
        self.perfect_focus_y = self.knob_rect.y + (self.knob_rect.height // 2)
        
        self.is_dragging_knob = False

        # =========================
        # ZELLEN GENERIEREN (Das mikroskopische Bild)
        # =========================
        self.cells = []
        self.create_cells()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_cells(self):
        # Wir generieren zufällige Pflanzenzellen-Kreise, die innerhalb der Linse liegen
        for _ in range(25):
            # Polarkoordinaten nutzen, damit die Zellen schön im Kreis bleiben
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, self.lens_radius - 30)
            
            x = self.lens_center[0] + int(distance * math.cos(angle))
            y = self.lens_center[1] + int(distance * math.sin(angle))
            radius = random.randint(15, 30)
            
            # Grüntöne für organische Pflanzenzellen
            color = (random.randint(40, 100), random.randint(160, 220), random.randint(40, 100))
            
            self.cells.append({
                "pos": (x, y),
                "base_radius": radius,
                "color": color
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================
        pygame.draw.rect(self.screen, self.WHITE, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("FOCUS MICROSCOPE", True, self.BLACK)
        self.screen.blit(title, (self.window_x + 210, self.window_y + 20))

        info = self.font.render("Drehe das Rad rechts, bis das Bild im Objektiv scharf ist!", True, self.BLACK)
        self.screen.blit(info, (self.window_x + 150, self.window_y + 110))

        # =========================
        # MIKROSKOP GEHÄUSE ZEICHNEN
        # =========================
        # Große Trägerplatte im Hintergrund des Objektivs
        bg_plate = pygame.Rect(self.lens_center[0] - 240, self.lens_center[1] - 240, 480, 480)
        pygame.draw.rect(self.screen, self.MICROSCOPE_BODY, bg_plate, border_radius=30)
        pygame.draw.rect(self.screen, self.BLACK, bg_plate, width=4, border_radius=30)

        # Das beleuchtete Innere des Objektivs
        pygame.draw.circle(self.screen, self.LENS_BG, self.lens_center, self.lens_radius)

        # =========================
        # UNZULÄNGLICHKEIT / UNSCHÄRFE BERECHNEN & ZEICHNEN
        # =========================
        # Wie weit ist der Spieler vom perfekten Fokus entfernt?
        distance_from_focus = abs(self.knob_y - self.perfect_focus_y)
        
        # Unschärfe-Faktor (0 = perfekt scharf, höhere Werte = extrem verschwommen)
        blur_factor = distance_from_focus / 10.0

        # Erstelle eine temporäre Oberfläche für Alpha-Transparenz-Effekte der Zellen
        # Das erlaubt es uns, den "Verschwommen"-Effekt durch Transparenz zu verstärken
        for cell in self.cells:
            # Wenn unscharf: Zellen werden größer und transparenter gezeichnet
            current_radius = int(cell["base_radius"] + (blur_factor * 2))
            
            # Alpha berechnen (je unschärfer, desto durchsichtiger)
            alpha = max(30, 255 - int(blur_factor * 12))
            
            # Oberfläche für die einzelne Zelle erzeugen
            cell_surf = pygame.Surface((current_radius * 2, current_radius * 2), pygame.SRCALPHA)
            
            # Zelle auf die temporäre Oberfläche zeichnen
            cell_color_with_alpha = (cell["color"][0], cell["color"][1], cell["color"][2], alpha)
            pygame.draw.circle(cell_surf, cell_color_with_alpha, (current_radius, current_radius), current_radius)
            
            # Zellkern zeichnen
            kernel_radius = max(2, int(current_radius * 0.3))
            pygame.draw.circle(cell_surf, (0, 0, 0, alpha), (current_radius, current_radius), kernel_radius, width=2)
            
            # Maskierung: Nur zeichnen, wenn die Zelle noch in der Linse sichtbar wäre
            # (Einfachheitshalber blitten wir sie zentriert auf ihre Position)
            self.screen.blit(cell_surf, (cell["pos"][0] - current_radius, cell["pos"][1] - current_radius))

        # Schwarzer dicker Rand des Objektivs (wird ÜBER den Zellen gezeichnet, um sie sauber zu begrenzen)
        pygame.draw.circle(self.screen, self.BLACK, self.lens_center, self.lens_radius, width=8)

        # =========================
        # FOKUSRAD (KNOB) ZEICHNEN
        # =========================
        # Das Gehäuse/Halterung des Rades
        pygame.draw.rect(self.screen, self.BLACK, self.knob_rect, width=4, border_radius=5)
        
        # Die Linien/Rillen des Rades zur Zierde
        for i in range(5):
            line_y = self.knob_rect.y + 20 + (i * 25)
            pygame.draw.line(self.screen, self.BLACK, (self.knob_rect.x, line_y), (self.knob_rect.x + self.knob_rect.width, line_y), 2)

        # Der bewegliche Greif-Indikator auf dem Rad
        indicator_rect = pygame.Rect(
            self.knob_rect.x - 10,
            self.knob_y - 15,
            self.knob_rect.width + 20,
            30
        )
        pygame.draw.rect(self.screen, self.KNOB_COLOR, indicator_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.BLACK, indicator_rect, width=3, border_radius=5)
        # Kleiner roter Strich auf dem Regler
        pygame.draw.line(self.screen, (255, 0, 0), (indicator_rect.x + 5, self.knob_y), (indicator_rect.x + indicator_rect.width - 5, self.knob_y), 3)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Rad greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            
            # Prüfen, ob auf den Regler-Indikator geklickt wurde
            indicator_click_zone = pygame.Rect(self.knob_rect.x - 10, self.knob_y - 15, self.knob_rect.width + 20, 30)
            if indicator_click_zone.collidepoint(mouse_pos):
                self.is_dragging_knob = True

        # =========================
        # REGLER BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging_knob:
                mouse_pos = pygame.mouse.get_pos()
                
                # Regler entlang der Y-Achse bewegen, aber innerhalb der Grenzen des Rades halten
                self.knob_y = max(self.knob_rect.y + 15, min(mouse_pos[1], self.knob_rect.y + self.knob_rect.height - 15))

        # =========================
        # LOSLASSEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.is_dragging_knob:
                self.is_dragging_knob = False
                self.check_finished()

    def check_finished(self):
        # Wenn der Regler ganz nah am perfekten Fokuspunkt losgelassen wird (Toleranz von 6 Pixeln)
        if abs(self.knob_y - self.perfect_focus_y) <= 6:
            # Regler schnappt exakt auf die Mitte ein
            self.knob_y = self.perfect_focus_y
            self.finished = True

    def is_finished(self):
        return self.finished

class RepairCurcuit:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.PANEL_GREY = (50, 55, 60) # Dunkles Schaltkasten-Grau

        # Kabel-Farben
        self.COLOR_RED = (230, 50, 50)
        self.COLOR_BLUE = (50, 120, 240)
        self.COLOR_YELLOW = (240, 200, 30)
        self.COLOR_PINK = (240, 80, 150)

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 35)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # KABEL INITIALISIERUNG
        # =========================
        self.left_wires = []
        self.right_wires = []
        
        # Aktuell gezogenes Kabel
        self.selected_wire = None
        self.current_mouse_pos = (0, 0)

        self.create_wires()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_wires(self):
        colors = [self.COLOR_RED, self.COLOR_BLUE, self.COLOR_YELLOW, self.COLOR_PINK]
        
        # Farben für links und rechts unabhängig voneinander durchmischen
        left_colors = colors.copy()
        right_colors = colors.copy()
        random.shuffle(left_colors)
        random.shuffle(right_colors)

        # Abstände für die 4 Kabelpositionen berechnen
        start_y = self.window_y + 200
        spacing_y = 110

        for i in range(4):
            # Linke Kontakte (Startpunkte)
            left_rect = pygame.Rect(
                self.window_x + 80,
                start_y + (i * spacing_y),
                60,
                40
            )
            self.left_wires.append({
                "rect": left_rect,
                "color": left_colors[i],
                "connected_to": None # Speichert, mit welchem rechten Wire-Index es verbunden ist
            })

            # Rechte Kontakte (Zielpunkte)
            right_rect = pygame.Rect(
                self.window_x + self.window_width - 140,
                start_y + (i * spacing_y),
                60,
                40
            )
            self.right_wires.append({
                "rect": right_rect,
                "color": right_colors[i],
                "is_occupied": False # Ob schon ein Kabel hier festsitzt
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Schaltkasten)
        # =========================
        pygame.draw.rect(self.screen, self.PANEL_GREY, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("FIX WIRING", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 380, self.window_y + 20))

        info = self.font.render("Verbinde die Kabel mit den gleichfarbigen Kontakten!", True, self.WHITE)
        self.screen.blit(info, (self.window_x + 200, self.window_y + 110))

        # =========================
        # BEREITS VERBUNDENE KABEL ZEICHNEN
        # =========================
        for wire in self.left_wires:
            if wire["connected_to"] is not None:
                target_wire = self.right_wires[wire["connected_to"]]
                # Dicke Linie von links nach rechts zeichnen
                start_pos = (wire["rect"].right, wire["rect"].centery)
                end_pos = (target_wire["rect"].left, target_wire["rect"].centery)
                pygame.draw.line(self.screen, wire["color"], start_pos, end_pos, 14)

        # =========================
        # AKTUELL GEZOGENES KABEL ZEICHNEN
        # =========================
        if self.selected_wire:
            start_pos = (self.selected_wire["rect"].right, self.selected_wire["rect"].centery)
            pygame.draw.line(self.screen, self.selected_wire["color"], start_pos, self.current_mouse_pos, 14)

        # =========================
        # KONTAKTE / STREIFEN ZEICHNEN
        # =========================
        # Linke Kontakte zeichnen
        for wire in self.left_wires:
            pygame.draw.rect(self.screen, wire["color"], wire["rect"], border_radius=4)
            pygame.draw.rect(self.screen, self.BLACK, wire["rect"], width=3, border_radius=4)

        # Rechte Kontakte zeichnen
        for wire in self.right_wires:
            pygame.draw.rect(self.screen, wire["color"], wire["rect"], border_radius=4)
            pygame.draw.rect(self.screen, self.BLACK, wire["rect"], width=3, border_radius=4)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Kabel greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            for wire in self.left_wires:
                # Man kann ein Kabel nur greifen, wenn es noch nicht verbunden ist
                if wire["rect"].collidepoint(mouse_pos) and wire["connected_to"] is None:
                    self.selected_wire = wire
                    self.current_mouse_pos = mouse_pos
                    break

        # =========================
        # MAUS BEWEGUNG (Kabel ziehen)
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_wire:
                self.current_mouse_pos = pygame.mouse.get_pos()

        # =========================
        # LOSLASSEN (Verbindung prüfen)
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.selected_wire:
                mouse_pos = pygame.mouse.get_pos()
                connected = False

                # Prüfen, ob wir über einem rechten Kontakt losgelassen haben
                for idx, r_wire in enumerate(self.right_wires):
                    if r_wire["rect"].collidepoint(mouse_pos):
                        # Stimmt die Farbe überein und ist der Kontakt noch frei?
                        if r_wire["color"] == self.selected_wire["color"] and not r_wire["is_occupied"]:
                            # Verbindung einrasten lassen!
                            self.selected_wire["connected_to"] = idx
                            r_wire["is_occupied"] = True
                            connected = True
                        break

                # Falls nicht korrekt verbunden, schnappt das Kabel zurück
                self.selected_wire = None
                self.check_finished()

    def check_finished(self):
        # Prüfen, ob alle 4 linken Kabel eine Verbindung besitzen
        all_connected = True
        for wire in self.left_wires:
            if wire["connected_to"] is None:
                all_connected = False
                break

        if all_connected:
            self.finished = True

    def is_finished(self):
        return self.finished

class BallCollectTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.GYM_FLOOR = (235, 170, 110) # Typischer Holz-Hallenboden
        self.CRATE_COLOR = (150, 110, 70) # Holz-Kisten

        # Ballfarben
        self.BASKETBALL_ORANGE = (220, 90, 30)
        self.TENNIS_NEON = (190, 230, 50)
        self.SOCCER_WHITE = (255, 255, 255)

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 28)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # DIE KISTEN (Ziel-Areale)
        # =========================
        # Drei Kisten nebeneinander im oberen Bereich der Task
        self.crates = {
            "soccer": pygame.Rect(self.window_x + 150, self.window_y + 180, 200, 150),
            "basketball": pygame.Rect(self.window_x + 450, self.window_y + 180, 200, 150),
            "tennis": pygame.Rect(self.window_x + 750, self.window_y + 180, 200, 150)
        }

        # =========================
        # BÄLLE INITIALISIERUNG
        # =========================
        self.balls = []
        self.selected_ball = None
        self.offset_x = 0
        self.offset_y = 0

        self.create_balls()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_balls(self):
        # Balltypen mit Radius und Typbezeichnung
        ball_types = [
            {"type": "soccer", "radius": 35, "color": self.SOCCER_WHITE},
            {"type": "soccer", "radius": 35, "color": self.SOCCER_WHITE},
            {"type": "basketball", "radius": 40, "color": self.BASKETBALL_ORANGE},
            {"type": "basketball", "radius": 40, "color": self.BASKETBALL_ORANGE},
            {"type": "tennis", "radius": 18, "color": self.TENNIS_NEON},
            {"type": "tennis", "radius": 18, "color": self.TENNIS_NEON}
        ]

        # Unterer Hallenbereich zum Spawnen
        spawn_x_start = self.window_x + 100
        spawn_x_end = self.window_x + self.window_width - 100
        spawn_y_start = self.window_y + 420
        spawn_y_end = self.window_y + self.window_height - 80

        for ball in ball_types:
            r = ball["radius"]
            # Damit die Klick-Abfrage wie bei deinen alten Tasks über ein pygame.Rect läuft,
            # bekommt jeder Ball eine quadratische Hitbox spendiert.
            rect = pygame.Rect(
                random.randint(spawn_x_start, spawn_x_end - (r * 2)),
                random.randint(spawn_y_start, spawn_y_end - (r * 2)),
                r * 2,
                r * 2
            )

            self.balls.append({
                "type": ball["type"],
                "radius": r,
                "rect": rect,
                "color": ball["color"]
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Turnhallen-Boden)
        # =========================
        pygame.draw.rect(self.screen, self.GYM_FLOOR, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # Spielfeldlinien als Deko auf dem Boden ziehen
        pygame.draw.line(self.screen, (255, 255, 255), (self.window_x, self.window_y + 400), (self.window_x + self.window_width, self.window_y + 400), 4)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("SORT THE BALLS", True, self.BLACK)
        self.screen.blit(title, (self.window_x + 280, self.window_y + 20))

        info = self.font.render("Sortiere die Sportbälle in die richtigen Kisten!", True, self.BLACK)
        self.screen.blit(info, (self.window_x + 300, self.window_y + 110))

        # =========================
        # KISTEN ZEICHNEN
        # =========================
        for key, crate_rect in self.crates.items():
            # Kisten-Körper
            pygame.draw.rect(self.screen, self.CRATE_COLOR, crate_rect, border_radius=10)
            pygame.draw.rect(self.screen, self.BLACK, crate_rect, width=4, border_radius=10)

            # Beschriftung der Kisten
            label_text = key.upper()
            text_surf = self.font.render(label_text, True, self.WHITE)
            text_rect = text_surf.get_rect(center=(crate_rect.centerx, crate_rect.centery))
            self.screen.blit(text_surf, text_rect)

        # =========================
        # BÄLLE ZEICHNEN
        # =========================
        # Zuerst unselektierte Bälle zeichnen
        for ball in self.balls:
            if ball != self.selected_ball:
                self.draw_single_ball(ball)

        # Ausgewählten Ball ganz oben zeichnen
        if self.selected_ball:
            self.draw_single_ball(self.selected_ball)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_single_ball(self, ball):
        cx = ball["rect"].centerx
        cy = ball["rect"].centery
        r = ball["radius"]

        # Basis-Kreis für den Ball
        pygame.draw.circle(self.screen, ball["color"], (cx, cy), r)
        pygame.draw.circle(self.screen, self.BLACK, (cx, cy), r, width=3)

        # Ball-Details einzeichnen, damit sie echt aussehen
        if ball["type"] == "basketball":
            # Kreuzlinien für Basketball
            pygame.draw.line(self.screen, self.BLACK, (cx - r, cy), (cx + r, cy), 2)
            pygame.draw.line(self.screen, self.BLACK, (cx, cy - r), (cx, cy + r), 2)
            # Seitliche geschwungene Linien andeuten
            pygame.draw.circle(self.screen, self.BLACK, (cx, cy), int(r * 0.7), width=2)
            
        elif ball["type"] == "tennis":
            # Die typische geschwungene Tennisball-Linie
            pygame.draw.arc(self.screen, self.WHITE, (cx - r, cy - int(r*0.5), r*2, r), 0, 3.14, 2)

        elif ball["type"] == "soccer":
            # Ein paar Flecken andeuten (kleine schwarze Kreise/Polygone im Inneren)
            pygame.draw.circle(self.screen, self.BLACK, (cx, cy), int(r * 0.3))
            pygame.draw.circle(self.screen, self.BLACK, (cx - int(r*0.5), cy - int(r*0.4)), int(r * 0.15))
            pygame.draw.circle(self.screen, self.BLACK, (cx + int(r*0.5), cy - int(r*0.4)), int(r * 0.15))
            pygame.draw.circle(self.screen, self.BLACK, (cx - int(r*0.5), cy + int(r*0.4)), int(r * 0.15))
            pygame.draw.circle(self.screen, self.BLACK, (cx + int(r*0.5), cy + int(r*0.4)), int(r * 0.15))

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Ball greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            for ball in reversed(self.balls):
                if ball["rect"].collidepoint(mouse_pos):
                    self.selected_ball = ball
                    self.offset_x = ball["rect"].x - mouse_pos[0]
                    self.offset_y = ball["rect"].y - mouse_pos[1]
                    break

        # =========================
        # BALL BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_ball:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_ball["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_ball["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.selected_ball:
                self.selected_ball = None
                self.check_finished()

    def check_finished(self):
        # Prüfen, ob jeder Ball in SEINER korrekten Kiste liegt
        all_correct = True

        for ball in self.balls:
            target_crate_rect = self.crates[ball["type"]]
            
            # Schaut nach, ob die Hitbox des Balls komplett in der Zielkiste liegt
            if not target_crate_rect.contains(ball["rect"]):
                all_correct = False
                break

        if all_correct:
            self.finished = True

    def is_finished(self):
        return self.finished

class MatStackTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.GYM_FLOOR = (215, 160, 100) # Etwas dunklerer Hallenboden
        self.WAGON_GREY = (100, 105, 110) # Metallwagen

        # Typische blaue Turnmatten-Farben (leicht abgestuft, damit man sie erkennt)
        self.MAT_COLORS = [
            (30, 90, 200),  # Matte 0 (Größte)
            (45, 110, 220), # Matte 1
            (60, 130, 240), # Matte 2
            (80, 150, 255)  # Matte 3 (Kleinste)
        ]

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 30)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # TRANSPORTWAGEN (Ziel-Areal)
        # =========================
        # Der Wagen steht auf der rechten Seite
        self.wagon_rect = pygame.Rect(
            self.window_x + 650,
            self.window_y + 250,
            380,
            350
        )

        # =========================
        # MATTEN INITIALISIERUNG
        # =========================
        self.mats = []
        self.selected_mat = None
        self.offset_x = 0
        self.offset_y = 0

        self.create_mats()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_mats(self):
        # 4 Matten mit abnehmenden Größen (Breite, Höhe)
        # ID 0 ist die größte Matte, ID 3 die kleinste.
        mat_sizes = [
            (320, 70),  # ID 0: Riesig
            (260, 65),  # ID 1: Groß
            (200, 60),  # ID 2: Mittel
            (140, 55)   # ID 3: Klein
        ]

        # Linker Hallenbereich für das Chaos beim Start
        spawn_x_start = self.window_x + 50
        spawn_x_end = self.window_x + 500
        spawn_y_start = self.window_y + 200
        spawn_y_end = self.window_y + self.window_height - 100

        for i in range(len(mat_sizes)):
            width, height = mat_sizes[i]
            
            rect = pygame.Rect(
                random.randint(spawn_x_start, spawn_x_end - width),
                random.randint(spawn_y_start, spawn_y_end - height),
                width,
                height
            )

            self.mats.append({
                "id": i, # Bestimmt die Größe (0 = unten/zuerst, 3 = oben/zuletzt)
                "rect": rect,
                "color": self.MAT_COLORS[i]
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Turnhalle)
        # =========================
        pygame.draw.rect(self.screen, self.GYM_FLOOR, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("STACK THE MATS", True, self.BLACK)
        self.screen.blit(title, (self.window_x + 280, self.window_y + 20))

        info = self.font.render("Staple die Matten von groß nach klein auf den Wagen!", True, self.BLACK)
        self.screen.blit(info, (self.window_x + 230, self.window_y + 100))

        # =========================
        # WAGEN ZEICHNEN
        # =========================
        # Ladefläche des Wagens
        pygame.draw.rect(self.screen, self.WAGON_GREY, self.wagon_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.BLACK, self.wagon_rect, width=4, border_radius=5)
        
        # Räder des Wagens andeuten
        pygame.draw.circle(self.screen, self.BLACK, (self.wagon_rect.left + 60, self.wagon_rect.bottom + 15), 20)
        pygame.draw.circle(self.screen, self.BLACK, (self.wagon_rect.right - 60, self.wagon_rect.bottom + 15), 20)

        # Text auf dem Wagen
        wagon_text = self.font.render("MATTENWAGEN", True, self.WHITE)
        self.screen.blit(wagon_text, (self.wagon_rect.x + 90, self.wagon_rect.y + 10))

        # =========================
        # MATTEN ZEICHNEN
        # =========================
        # Wir zeichnen die Matten standardmäßig nach ihrer ID (0 zuerst, also die größte unten).
        # Dadurch verdecken kleinere Matten die größeren, wenn sie korrekt gestapelt sind.
        for mat in self.mats:
            if mat != self.selected_mat:
                self.draw_single_mat(mat)

        # Die gehaltene Matte schwebt immer ganz oben über dem Rest
        if self.selected_mat:
            self.draw_single_mat(self.selected_mat)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_single_mat(self, mat):
        # Matten-Körper
        pygame.draw.rect(self.screen, mat["color"], mat["rect"], border_radius=12)
        pygame.draw.rect(self.screen, self.BLACK, mat["rect"], width=3, border_radius=12)
        
        # Angedeutete Griffe oder Eckenschützer an den Seiten für den "Turnmatten-Look"
        pygame.draw.rect(self.screen, self.BLACK, (mat["rect"].x, mat["rect"].y, 15, mat["rect"].height), width=2, border_radius=3)
        pygame.draw.rect(self.screen, self.BLACK, (mat["rect"].right - 15, mat["rect"].y, 15, mat["rect"].height), width=2, border_radius=3)

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Matte greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            # reversed() sorgt dafür, dass man die optisch oberste/kleinste Matte zuerst greift
            for mat in reversed(self.mats):
                if mat["rect"].collidepoint(mouse_pos):
                    self.selected_mat = mat
                    self.offset_x = mat["rect"].x - mouse_pos[0]
                    self.offset_y = mat["rect"].y - mouse_pos[1]
                    break

        # =========================
        # MATTE BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_mat:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_mat["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_mat["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.selected_mat:
                self.selected_mat = None
                self.check_finished()

    def check_finished(self):
        # 1. Schritt: Sind alle Matten auf dem Wagen?
        for mat in self.mats:
            if not self.wagon_rect.contains(mat["rect"]):
                return

        # 2. Schritt: Reihenfolge von unten nach oben prüfen.
        # Wenn wir die Matten nach ihrer Y-Position auf dem Bildschirm sortieren (von oben nach unten),
        # muss die kleinste Matte (ID 3) am weitesten oben stehen, gefolgt von 2, 1 und am Ende 0.
        # Das bedeutet: Je größer das Y (weiter unten), desto kleiner muss die ID sein.
        sorted_by_y = sorted(self.mats, key=lambda m: m["rect"].y)

        # Die IDs müssen in der Y-Sortierung genau rückwärts laufen: [3, 2, 1, 0]
        # (ID 3 ganz oben = kleinster Y-Wert, ID 0 ganz unten = größter Y-Wert)
        for index in range(len(sorted_by_y)):
            expected_id = 3 - index
            if sorted_by_y[index]["id"] != expected_id:
                return  # Falsch gestapelt! (z.B. eine große Matte auf eine kleine gelegt)

        # Wenn beide Bedingungen erfüllt sind, ist der Stapel perfekt!
        self.finished = True

    def is_finished(self):
        return self.finished

class TraySortingTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 200, 0)
        self.BACKGROUND_BROWN = (200, 150, 110) # Mensatisch
        self.TRAY_GREY = (80, 90, 100)          # Kunststoff-Tablett
        self.SLOT_DARK = (55, 60, 65)           # Eingeprägte Schablonen

        # Geschirrfarben
        self.COLOR_PLATE = (250, 250, 250)
        self.COLOR_CUP = (230, 80, 80)
        self.COLOR_SILVER = (180, 185, 190)

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 30)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # ZIEL-SCHABLONEN (Auf dem Tablett)
        # =========================
        # Das Tablett liegt mittig im Fenster
        self.tray_rect = pygame.Rect(self.window_x + 100, self.window_y + 180, 900, 460)

        # Die festen Positionen, wo das Geschirr hinmuss
        self.slots = {
            "plate": pygame.Rect(self.tray_rect.x + 300, self.tray_rect.y + 80, 300, 300),
            "cup": pygame.Rect(self.tray_rect.x + 680, self.tray_rect.y + 80, 120, 120),
            "fork": pygame.Rect(self.tray_rect.x + 120, self.tray_rect.y + 100, 50, 260),
            "knife": pygame.Rect(self.tray_rect.x + 200, self.tray_rect.y + 100, 40, 260)
        }

        # =========================
        # GEGENSTÄNDE INITIALISIERUNG
        # =========================
        self.items = []
        self.selected_item = None
        self.offset_x = 0
        self.offset_y = 0

        self.create_items()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_items(self):
        # Definition der beweglichen Teile mit ihren Startgrößen
        item_defs = [
            {"type": "plate", "w": 300, "h": 300, "color": self.COLOR_PLATE},
            {"type": "cup", "w": 120, "h": 120, "color": self.COLOR_CUP},
            {"type": "fork", "w": 50, "h": 260, "color": self.COLOR_SILVER},
            {"type": "knife", "w": 40, "h": 260, "color": self.COLOR_SILVER}
        ]

        # Um das Tablett herum ungeordnet platzieren (im oberen/seitlichen Bereich)
        for definition in item_defs:
            # Zufällige Platzierung im oberen Bereich des Fensters vor dem Sortieren
            rx = random.randint(self.window_x + 50, self.window_x + self.window_width - definition["w"] - 50)
            ry = random.randint(self.window_y + 140, self.window_y + 160) # Leicht über dem Tablett gestreut

            rect = pygame.Rect(rx, ry, definition["w"], definition["h"])
            self.items.append({
                "type": definition["type"],
                "rect": rect,
                "color": definition["color"]
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Mensatisch)
        # =========================
        pygame.draw.rect(self.screen, self.BACKGROUND_BROWN, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("CLEAN YOUR TRAY", True, self.BLACK)
        self.screen.blit(title, (self.window_x + 280, self.window_y + 15))

        info = self.font.render("Räume das Geschirr auf die passenden Schablonen!", True, self.BLACK)
        self.screen.blit(info, (self.window_x + 240, self.window_y + 95))

        # =========================
        # TABLETT & SCHABLONEN ZEICHNEN
        # =========================
        # Das graue Kunststoff-Tablett
        pygame.draw.rect(self.screen, self.TRAY_GREY, self.tray_rect, border_radius=15)
        pygame.draw.rect(self.screen, self.BLACK, self.tray_rect, width=6, border_radius=15)

        # Dunkle Vertiefungen (Schablonen) auf dem Tablett einzeichnen
        for key, slot_rect in self.slots.items():
            if key == "plate" or key == "cup":
                # Runde Schablonen für Teller und Becher
                pygame.draw.circle(self.screen, self.SLOT_DARK, slot_rect.center, slot_rect.width // 2)
                pygame.draw.circle(self.screen, self.BLACK, slot_rect.center, slot_rect.width // 2, width=3)
            else:
                # Eckige Schablonen für Besteck
                pygame.draw.rect(self.screen, self.SLOT_DARK, slot_rect, border_radius=5)
                pygame.draw.rect(self.screen, self.BLACK, slot_rect, width=3, border_radius=5)

        # =========================
        # GEGENSTÄNDE ZEICHNEN
        # =========================
        # Unselektierte Teile zuerst
        for item in self.items:
            if item != self.selected_item:
                self.draw_single_item(item)

        # Das aktiv gehaltene Teil ganz oben zeichnen
        if self.selected_item:
            self.draw_single_item(self.selected_item)

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_single_item(self, item):
        rect = item["rect"]
        cx, cy = rect.center

        if item["type"] == "plate":
            # Großer Essteller mit innerem Rand
            pygame.draw.circle(self.screen, item["color"], (cx, cy), rect.width // 2)
            pygame.draw.circle(self.screen, self.BLACK, (cx, cy), rect.width // 2, width=3)
            pygame.draw.circle(self.screen, (230, 230, 230), (cx, cy), rect.width // 3, width=2) # Innerer Tiefenring

        elif item["type"] == "cup":
            # Becher von oben gesehen (Außenwand und Loch)
            pygame.draw.circle(self.screen, item["color"], (cx, cy), rect.width // 2)
            pygame.draw.circle(self.screen, self.BLACK, (cx, cy), rect.width // 2, width=3)
            pygame.draw.circle(self.screen, (150, 40, 40), (cx, cy), rect.width // 2 - 12) # Innenseite

        elif item["type"] == "fork":
            # Gabel-Stiel
            pygame.draw.rect(self.screen, item["color"], (rect.x + 18, rect.y + 100, 14, 150), border_radius=3)
            # Gabel-Kopf Basis
            pygame.draw.rect(self.screen, item["color"], (rect.x + 10, rect.y + 30, 30, 70), border_radius=2)
            # Zinken reinschneiden (durch Linien)
            pygame.draw.rect(self.screen, self.BLACK, (rect.x, rect.y, rect.width, rect.height), width=2, border_radius=5)
            # Detailschliffe
            pygame.draw.line(self.screen, self.BLACK, (rect.x + 17, rect.y + 30), (rect.x + 17, rect.y + 75), 2)
            pygame.draw.line(self.screen, self.BLACK, (rect.x + 25, rect.y + 30), (rect.x + 25, rect.y + 75), 2)
            pygame.draw.line(self.screen, self.BLACK, (rect.x + 33, rect.y + 30), (rect.x + 33, rect.y + 75), 2)

        elif item["type"] == "knife":
            # Messer-Griff (Dunkler)
            pygame.draw.rect(self.screen, (140, 145, 150), (rect.x + 12, rect.y + 120, 16, 130), border_radius=4)
            # Klinge (Heller)
            pygame.draw.rect(self.screen, item["color"], (rect.x + 12, rect.y + 15, 16, 110), border_radius=4)
            pygame.draw.rect(self.screen, self.BLACK, (rect.x, rect.y, rect.width, rect.height), width=2, border_radius=5)

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Teil greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            # reversed(), damit man das optisch oberste Teil greift
            for item in reversed(self.items):
                if item["rect"].collidepoint(mouse_pos):
                    self.selected_item = item
                    self.offset_x = item["rect"].x - mouse_pos[0]
                    self.offset_y = item["rect"].y - mouse_pos[1]
                    break

        # =========================
        # TEIL BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_item:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_item["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_item["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN (Snap-to-Slot Logik)
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.selected_item:
                target_slot = self.slots[self.selected_item["type"]]
                
                # Toleranzprüfung: Wenn das Teil nah genug an der Schablone gelassen wird (Zentren liegen nah beieinander)
                dist_x = abs(self.selected_item["rect"].centerx - target_slot.centerx)
                dist_y = abs(self.selected_item["rect"].centery - target_slot.centery)
                
                if dist_x < 50 and dist_y < 50:
                    # Perfekt eingerastet! Position exakt auf den Slot setzen
                    self.selected_item["rect"].x = target_slot.x
                    self.selected_item["rect"].y = target_slot.y
                
                self.selected_item = None
                self.check_finished()

    def check_finished(self):
        # Prüfen, ob alle Gegenstände exakt auf ihrer Schablone liegen
        all_snapped = True
        for item in self.items:
            target_slot = self.slots[item["type"]]
            if item["rect"].x != target_slot.x or item["rect"].y != target_slot.y:
                all_snapped = False
                break

        if all_snapped:
            self.finished = True

    def is_finished(self):
        return self.finished

class MilkFillTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 40, 40)
        self.CAFETERIA_BG = (100, 140, 160) # Blaugraue Wandkacheln
        self.TABLE_COLOR = (180, 130, 90)   # Holztisch
        
        # Milch- & Glasfarben
        self.COLOR_MILK = (255, 255, 255)
        self.COLOR_GLASS = (200, 220, 240, 120) # Leicht transparentes Glasblau

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 30)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # GLAS- UND FÜLL-GEOMETRIE
        # =========================
        # Das Glas steht auf dem Tisch
        self.glass_width = 200
        self.glass_height = 350
        self.glass_x = self.window_x + (self.window_width - self.glass_width) // 2
        self.glass_y = self.window_y + 250
        self.glass_rect = pygame.Rect(self.glass_x, self.glass_y, self.glass_width, self.glass_height)

        # Füllstand-Variablen (0.0 bis 100.0 Prozent)
        self.fill_level = 0.0
        self.fill_speed = 0.6 # Wie schnell die Milch steigt
        self.is_filling = False

        # Die Zielmarkierung (80% bis 88% des Glases sind die perfekte Füllung)
        self.target_min = 80.0
        self.target_max = 88.0

        # =========================
        # STATUS
        # =========================
        self.finished = False
        self.overflowed = False
        self.overflow_timer = 0 # Zeigt den Fehler kurz an

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Mensa-Hintergrund)
        # =========================
        # Obere Wandkacheln
        pygame.draw.rect(self.screen, self.CAFETERIA_BG, self.task_rect, border_radius=20)
        # Unterer Tischbereich
        table_rect = pygame.Rect(self.window_x, self.glass_y + self.glass_height - 20, self.window_width, self.window_height - self.glass_height)
        pygame.draw.rect(self.screen, self.TABLE_COLOR, table_rect, border_bottom_left_radius=20, border_bottom_right_radius=20)
        
        # Rahmen um das Taskfenster
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("FILL THE MILK", True, self.BLACK)
        self.screen.blit(title, (self.window_x + 330, self.window_y + 20))

        status_text = "HALTEN zum Befüllen! Stoppe an der Markierung."
        if self.overflowed:
            status_text = "ÜBERLAUFEN! Versuche es noch einmal."
        info = self.font.render(status_text, True, self.RED if self.overflowed else self.BLACK)
        self.screen.blit(info, (self.window_x + 290, self.window_y + 110))

        # =========================
        # STRÖMENDE MILCH (Animation)
        # =========================
        if self.is_filling and not self.finished and not self.overflowed:
            # Strahl von oben in das Glas zeichnen
            stream_rect = pygame.Rect(self.glass_rect.centerx - 10, self.window_y + 150, 20, self.glass_rect.bottom - self.window_y - 150)
            pygame.draw.rect(self.screen, self.COLOR_MILK, stream_rect)

        # =========================
        # ZIELMARKIERUNG ZEICHNEN
        # =========================
        # Berechnen, wo das grüne Band auf dem Glas liegt
        mark_top_y = self.glass_rect.bottom - (self.glass_height * (self.target_max / 100.0))
        mark_height = self.glass_height * ((self.target_max - self.target_min) / 100.0)
        mark_rect = pygame.Rect(self.glass_rect.x - 25, mark_top_y, self.glass_width + 50, mark_height)
        
        # Das grüne Zielband links und rechts neben dem Glas andeuten
        pygame.draw.rect(self.screen, self.GREEN, mark_rect, width=4, border_radius=3)
        
        # Kleiner Pfeil-Indikator
        arrow_text = self.font.render("< MATCH", True, self.GREEN)
        self.screen.blit(arrow_text, (mark_rect.right + 10, mark_rect.centery - 15))

        # =========================
        # MILCH IM GLAS ZEICHNEN
        # =========================
        if self.fill_level > 0:
            milk_h = self.glass_height * (self.fill_level / 100.0)
            milk_rect = pygame.Rect(
                self.glass_rect.x + 6,
                self.glass_rect.bottom - milk_h - 6,
                self.glass_rect.width - 12,
                milk_h
            )
            pygame.draw.rect(self.screen, self.COLOR_MILK, milk_rect, border_bottom_left_radius=10, border_bottom_right_radius=10)

        # =========================
        # GLAS ZEICHNEN (Über der Milch)
        # =========================
        # Eine transparente Oberfläche für den Glas-Look erstellen
        glass_surf = pygame.Surface((self.glass_width, self.glass_height), pygame.SRCALPHA)
        glass_surf.fill(self.COLOR_GLASS)
        self.screen.blit(glass_surf, (self.glass_x, self.glass_y))
        
        # Dicker schwarzer Rahmen für die Glas-Kontur (oben offen)
        pygame.draw.lines(self.screen, self.BLACK, False, [
            (self.glass_rect.left, self.glass_rect.top),
            (self.glass_rect.left, self.glass_rect.bottom),
            (self.glass_rect.right, self.glass_rect.bottom),
            (self.glass_rect.right, self.glass_rect.top)
        ], width=6)

        # =========================
        # ENGINE LOGIK (FÜLLPROZESS)
        # =========================
        self.update_game_logic()

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def update_game_logic(self):
        if self.finished:
            return

        # Wenn überlaufen, animation abwarten und zurücksetzen
        if self.overflowed:
            self.overflow_timer -= 1
            if self.overflow_timer <= 0:
                self.overflowed = False
                self.fill_level = 0.0
            return

        # Füllstand erhöhen, wenn gedrückt gehalten wird
        if self.is_filling:
            self.fill_level += self.fill_speed
            
            # Hat der Spieler den absoluten Rand gesprengt? (100%)
            if self.fill_level >= 96.0: # 96% sieht optisch wie Randvoll aus
                self.overflowed = True
                self.is_filling = False
                self.overflow_timer = 90 # 90 Frames (~1.5 Sek) Schockmoment zeigen

    def handle_event(self, event):
        if self.finished or self.overflowed:
            return

        # Aktivieren bei Mausklick oder Leertaste
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.is_filling = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.is_filling = True

        # Deaktivieren beim Loslassen -> Prüfen ob gewonnen!
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_filling:
                self.is_filling = False
                self.check_finished()
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            if self.is_filling:
                self.is_filling = False
                self.check_finished()

    def check_finished(self):
        # Befindet sich der aktuelle Füllstand im grünen Bereich?
        if self.target_min <= self.fill_level <= self.target_max:
            self.finished = True
        else:
            # Zu früh losgelassen? Milch bleibt auf dem Stand, man kann weitertippen!
            pass

    def is_finished(self):
        return self.finished

class PizzaCutTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 40, 40)
        
        # Pizza- & Brettfarben
        self.WOOD_BOARD = (210, 155, 100)  # Rundes Holzbrett
        self.PIZZA_CRUST = (220, 130, 50)  # Knuspriger Rand
        self.PIZZA_CHEESE = (245, 210, 70) # Käse
        self.TOMATO_RED = (190, 40, 30)    # Salami / Sauce

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 28)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # PIZZA-GEOMETRIE
        # =========================
        # Die Pizza liegt exakt in der Mitte der Task
        self.pizza_center = (self.window_x + self.window_width // 2, self.window_y + self.window_height // 2 + 30)
        self.pizza_radius = 200

        # Schnitt-Speicherung
        # Jeder Schnitt ist ein Tupel aus (Startpunkt, Endpunkt, Winkel_im_Bogenmaß)
        self.cuts = [] 
        
        # Aktueller Zieh-Vorgang
        self.drawing_start = None
        self.current_mouse_pos = (0, 0)

        # Ziel: 3 Schnitte für 6 Stücke
        self.required_cuts = 3

        # =========================
        # STATUS
        # =========================
        self.finished = False
        self.failed_attempt = False
        self.feedback_timer = 0

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Küchentisch)
        # =========================
        pygame.draw.rect(self.screen, (60, 65, 70), self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # SCHNEIDEBRETT ZEICHNEN
        # =========================
        pygame.draw.circle(self.screen, self.WOOD_BOARD, self.pizza_center, self.pizza_radius + 40)
        pygame.draw.circle(self.screen, self.BLACK, self.pizza_center, self.pizza_radius + 40, width=4)

        # =========================
        # PIZZA ZEICHNEN
        # =========================
        # Teigrand
        pygame.draw.circle(self.screen, self.PIZZA_CRUST, self.pizza_center, self.pizza_radius)
        pygame.draw.circle(self.screen, self.BLACK, self.pizza_center, self.pizza_radius, width=2)
        
        # Käsefläche
        pygame.draw.circle(self.screen, self.PIZZA_CHEESE, self.pizza_center, self.pizza_radius - 20)

        # Ein paar Salamischeiben als Deko
        salami_offsets = [(-80, -60), (70, -70), (-40, 80), (80, 50), (0, -110), (-90, 20), (50, 100), (0, 0)]
        for offset in salami_offsets:
            sal_x = self.pizza_center[0] + offset[0]
            sal_y = self.pizza_center[1] + offset[1]
            pygame.draw.circle(self.screen, self.TOMATO_RED, (sal_x, sal_y), 22)
            pygame.draw.circle(self.screen, (150, 30, 20), (sal_x, sal_y), 22, width=2)

        # =========================
        # EXISTING CUTS ZEICHNEN
        # =========================
        for cut in self.cuts:
            pygame.draw.line(self.screen, self.WHITE, cut[0], cut[1], 5)
            pygame.draw.line(self.screen, self.BLACK, cut[0], cut[1], 1) # Messer-Spur in der Mitte

        # =========================
        # AKTUELLER SCHNITT (Vorschau)
        # =========================
        if self.drawing_start:
            pygame.draw.line(self.screen, (255, 255, 255, 150), self.drawing_start, self.current_mouse_pos, 4)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("SLICE THE PIZZA", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 300, self.window_y + 15))

        # Dynamischer Informationstext
        if self.finished:
            info_text = "Perfekt geschnitten! Guten Appetit."
            info_color = self.GREEN
        elif self.failed_attempt:
            info_text = "Ungenau geschnitten! Die Pizza wird zurückgesetzt..."
            info_color = self.RED
        else:
            info_text = f"Ziehe {self.required_cuts - len(self.cuts)} gerade Schnitte sauber durch die Mitte!"
            info_color = self.WHITE

        info = self.font.render(info_text, True, info_color)
        self.screen.blit(info, (self.window_x + 280, self.window_y + 95))

        # =========================
        # TIMER-LOGIK FÜR FEHLER
        # =========================
        if self.failed_attempt:
            self.feedback_timer -= 1
            if self.feedback_timer <= 0:
                self.failed_attempt = False
                self.cuts.clear()

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):
        if self.finished or self.failed_attempt:
            return

        # =========================
        # MESSER ANSETZEN
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = pygame.mouse.get_pos()
            
            # Man muss den Schnitt in der Nähe der Pizza ansetzen
            dist = math.hypot(mouse_pos[0] - self.pizza_center[0], mouse_pos[1] - self.pizza_center[1])
            if dist <= self.pizza_radius + 30:
                self.drawing_start = mouse_pos
                self.current_mouse_pos = mouse_pos

        # =========================
        # MESSER ZIEHEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.drawing_start:
                self.current_mouse_pos = pygame.mouse.get_pos()

        # =========================
        # SCHNITT BEENDEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drawing_start:
                end_pos = pygame.mouse.get_pos()
                
                # Prüfen, ob der Schnitt lang genug war
                cut_length = math.hypot(end_pos[0] - self.drawing_start[0], end_pos[1] - self.drawing_start[1])
                
                if cut_length > self.pizza_radius:
                    # Winkel des aktuellen Schnitts berechnen (im Bogenmaß)
                    angle = math.atan2(end_pos[1] - self.drawing_start[1], end_pos[0] - self.drawing_start[0]) % math.pi
                    
                    # Schnitt zur Liste hinzufügen
                    self.cuts.append((self.drawing_start, end_pos, angle))
                    
                    # Wenn 3 Schnitte erreicht sind, Geometrie auswerten
                    if len(self.cuts) == self.required_cuts:
                        self.check_pizza_geometry()
                
                self.drawing_start = None

    def check_pizza_geometry(self):
        # 1. PRÜFUNG: Laufen die Linien nah genug am Mittelpunkt vorbei?
        # Abstand Punkt zu Linie Formel
        for cut in self.cuts:
            x1, y1 = cut[0]
            x2, y2 = cut[1]
            px, py = self.pizza_center
            
            # Zähler und Nenner für den Abstand des Pizza-Zentrums von der Schnittlinie
            numerator = abs((x2 - x1) * (y1 - py) - (x1 - px) * (y2 - y1))
            denominator = math.hypot(x2 - x1, y2 - y1)
            
            distance_to_center = numerator / denominator if denominator != 0 else 999
            
            # Toleranz: Der Schnitt darf maximal 35 Pixel am echten Zentrum vorbeilaufen
            if distance_to_center > 35:
                self.trigger_failure()
                return

        # 2. PRÜFUNG: Sind die Winkel gleichmäßig verteilt?
        # Wir sortieren die Schnitte nach ihrem Winkel (0 bis Pi)
        sorted_cuts = sorted(self.cuts, key=lambda c: c[2])
        
        # Berechne die Winkeldifferenzen zwischen aufeinanderfolgenden Schnitten
        diff1 = sorted_cuts[1][2] - sorted_cuts[0][2]
        diff2 = sorted_cuts[2][2] - sorted_cuts[1][2]
        diff3 = (sorted_cuts[0][2] + math.pi) - sorted_cuts[2][2] # Zyklischer Übergang

        # Der optimale Winkel bei 3 Schnitten ist 60 Grad (bzw. rad(60) ≈ 1.047)
        optimal_angle = math.pi / 3 
        tolerance = 0.25 # Großzügige Toleranz im Bogenmaß (~14 Grad Abweichung erlaubt)

        if (abs(diff1 - optimal_angle) > tolerance or 
            abs(diff2 - optimal_angle) > tolerance or 
            abs(diff3 - optimal_angle) > tolerance):
            self.trigger_failure()
        else:
            self.finished = True

    def trigger_failure(self):
        self.failed_attempt = True
        self.feedback_timer = 90 # Zeige Fehlermeldung für 1.5 Sekunden (bei ~60 FPS)

    def is_finished(self):
        return self.finished

class VendingMachineTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        # Fenster mittig
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        # Task Bildschirm
        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 40, 40)
        self.DARK_RED = (140, 20, 20)
        
        # Automaten-Farben
        self.VENDING_BODY = (40, 45, 50)     # Dunkles Anthrazit
        self.GLASS_BG = (25, 35, 45)         # Innenleben hinter Glas
        self.COIN_GOLD = (230, 180, 40)      # Münzen
        self.SNACK_CRISP = (210, 50, 50)     # Rote Chipstüte
        self.SHADOW_BLACK = (10, 10, 12)     # Ausgabeschacht

        # =========================
        # SCHRIFT
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.btn_font = pygame.font.SysFont("arial", 30, bold=True)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # INTERAKTIONS-ELEMENTE
        # =========================
        # 1. Der Münzschlitz (Ziel-Areal)
        self.slot_rect = pygame.Rect(self.window_x + 850, self.window_y + 220, 40, 70)
        
        # 2. Der Push-Button zum Rütteln
        self.btn_rect = pygame.Rect(self.window_x + 820, self.window_y + 350, 110, 70)

        # 3. Der verklemmte Snack (Chipstüte)
        # Startposition: Hängt oben rechts in der Spirale fest
        self.snack_start_y = self.window_y + 240
        self.snack_rect = pygame.Rect(self.window_x + 400, self.snack_start_y, 110, 140)
        
        # 4. Der Ausgabeschacht (Endziel für die Chips)
        self.drop_zone_y = self.window_y + 510

        # Münzen initialisieren
        self.coins = []
        self.selected_coin = None
        self.offset_x = 0
        self.offset_y = 0
        self.coins_inserted = 0
        self.required_coins = 3
        
        self.create_coins()

        # Rüttel-Mechanik
        self.shake_clicks = 0
        self.required_clicks = 5
        self.shake_offset_x = 0  # Für den visuellen Rüttel-Effekt

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_coins(self):
        # Spawne 3 Münzen im linken Bereich auf dem Boden/Ablage
        spawn_x_start = self.window_x + 60
        spawn_x_end = self.window_x + 220
        spawn_y_start = self.window_y + 450
        spawn_y_end = self.window_y + 600

        for i in range(self.required_coins):
            cx = random.randint(spawn_x_start, spawn_x_end)
            cy = random.randint(spawn_y_start, spawn_y_end)
            # Jede Münze bekommt eine quadratische Hitbox (Radius 20 -> 40x40)
            rect = pygame.Rect(cx, cy, 40, 40)
            self.coins.append({
                "rect": rect,
                "inserted": False
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # Rüttel-Effekt auf das Innenleben anwenden, wenn geklopft wird
        current_snack_x = self.snack_rect.x + self.shake_offset_x
        # Der Rüttel-Effekt flacht automatisch jede Frame wieder ab
        if self.shake_offset_x > 0: self.shake_offset_x -= 1
        elif self.shake_offset_x < 0: self.shake_offset_x += 1

        # =========================
        # TASK WINDOW (Snackautomat)
        # =========================
        pygame.draw.rect(self.screen, self.VENDING_BODY, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # Glasfront (Innenraum für Snacks)
        glass_rect = pygame.Rect(self.window_x + 300, self.window_y + 180, 480, 320)
        pygame.draw.rect(self.screen, self.GLASS_BG, glass_rect)
        pygame.draw.rect(self.screen, self.BLACK, glass_rect, width=4)

        # Ausgabeschacht unten
        dispenser_rect = pygame.Rect(self.window_x + 330, self.window_y + 530, 420, 110)
        pygame.draw.rect(self.screen, self.SHADOW_BLACK, dispenser_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, dispenser_rect, width=3, border_radius=10)

        # =========================
        # TITEL & ANLEITUNG
        # =========================
        title = self.big_font.render("VENDING MACHINE", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 240, self.window_y + 20))

        # Dynamischer Anweisungstext
        if self.coins_inserted < self.required_coins:
            info_text = f"Wirf Münzen ein: {self.coins_inserted}/{self.required_coins}"
        elif not self.finished:
            info_text = "Der Snack klemmt! Drücke mehrmals PUSH zum Rütteln!"
        else:
            info_text = "Snack befreit! Task erfolgreich beendet."
            
        info = self.font.render(info_text, True, self.WHITE if not self.finished else self.GREEN)
        self.screen.blit(info, (self.window_x + 300, self.window_y + 115))

        # =========================
        # COIN SLOT (Münzschlitz)
        # =========================
        pygame.draw.rect(self.screen, (100, 105, 110), self.slot_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.BLACK, self.slot_rect, width=2, border_radius=5)
        # Der eigentliche Schlitz
        pygame.draw.rect(self.screen, self.BLACK, (self.slot_rect.centerx - 4, self.slot_rect.y + 10, 8, 50))

        # =========================
        # PUSH BUTTON (Rüttel-Knopf)
        # =========================
        # Leuchtet erst auf, wenn genug Geld drin ist
        btn_ready = self.coins_inserted >= self.required_coins
        pygame.draw.rect(self.screen, self.RED if btn_ready else self.DARK_RED, self.btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.BLACK, self.btn_rect, width=3, border_radius=8)
        
        btn_text = self.btn_font.render("PUSH", True, self.WHITE if btn_ready else (180, 180, 180))
        btn_text_rect = btn_text.get_rect(center=self.btn_rect.center)
        self.screen.blit(btn_text, btn_text_rect)

        # =========================
        # SPIRALE & SNACK ZEICHNEN
        # =========================
        # Die Metallspirale andeuten (Reihe von Ellipsen)
        for i in range(5):
            sp_x = self.window_x + 340 + (i * 65)
            pygame.draw.ellipse(self.screen, (160, 165, 170), (sp_x, self.window_y + 300, 80, 40), width=3)

        # Die verklemmte Knabbertüte zeichnen
        pygame.draw.rect(self.screen, self.SNACK_CRISP, (current_snack_x, self.snack_rect.y, self.snack_rect.width, self.snack_rect.height), border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, (current_snack_x, self.snack_rect.y, self.snack_rect.width, self.snack_rect.height), width=3, border_radius=10)
        # Deko auf der Tüte (Chips-Symbol)
        pygame.draw.circle(self.screen, self.COIN_GOLD, (current_snack_x + 55, self.snack_rect.y + 70), 25)
        snack_label = self.font.render("CRISPS", True, self.WHITE)
        self.screen.blit(snack_label, (current_snack_x + 18, self.snack_rect.y + 15))

        # =========================
        # MÜNZEN ZEICHNEN
        # =========================
        for coin in self.coins:
            if not coin["inserted"] and coin != self.selected_coin:
                self.draw_single_coin(coin["rect"])

        # Gehaltene Münze ganz oben zeichnen
        if self.selected_coin:
            self.draw_single_coin(self.selected_coin["rect"])

        # =========================
        # ENGINE LOGIK (AUTOMATEN-ANIMATION)
        # =========================
        self.update_physics()

        # =========================
        # TASK FINISHED
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_single_coin(self, rect):
        cx, cy = rect.center
        pygame.draw.circle(self.screen, self.COIN_GOLD, (cx, cy), 20)
        pygame.draw.circle(self.screen, self.BLACK, (cx, cy), 20, width=2)
        # Innerer Prägungsring
        pygame.draw.circle(self.screen, (250, 210, 60), (cx, cy), 13, width=1)

    def update_physics(self):
        # Wenn genug geklickt wurde, fällt der Snack stetig nach unten
        if self.shake_clicks >= self.required_clicks and self.snack_rect.y < self.drop_zone_y:
            self.snack_rect.y += 8  # Fall-Geschwindigkeit
            if self.snack_rect.y >= self.drop_zone_y:
                self.snack_rect.y = self.drop_zone_y
                self.finished = True

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = pygame.mouse.get_pos()

            # 1. Münze greifen (nur wenn noch Geld eingeworfen werden muss)
            if self.coins_inserted < self.required_coins:
                for coin in self.coins:
                    if not coin["inserted"] and coin["rect"].collidepoint(mouse_pos):
                        self.selected_coin = coin
                        self.offset_x = coin["rect"].x - mouse_pos[0]
                        self.offset_y = coin["rect"].y - mouse_pos[1]
                        return

            # 2. PUSH-Button drücken (wenn Münzen komplett eingezahlt sind)
            if self.coins_inserted >= self.required_coins:
                if self.btn_rect.collidepoint(mouse_pos):
                    self.shake_clicks += 1
                    # Erzeuge einen zufälligen Ausschlag nach links oder rechts fürs Rütteln
                    self.shake_offset_x = random.choice([-15, 15])
                    
                    # Ein kleiner Trick: Bei jedem legalen Stoß rutscht die Tüte bereits ein kleines Stück nach vorn/unten
                    if self.shake_clicks < self.required_clicks:
                        self.snack_rect.y += 10

        # =========================
        # MÜNZE BEWEGEN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_coin:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_coin["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_coin["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN (Einwurf prüfen)
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.selected_coin:
                # Prüfen, ob die Münze den Münzschlitz berührt
                if self.slot_rect.colliderect(self.selected_coin["rect"]):
                    self.selected_coin["inserted"] = True
                    self.coins_inserted += 1
                
                self.selected_coin = None

    def is_finished(self):
        return self.finished

class BarcodeScanTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (230, 30, 30)
        self.LASER_RED = (255, 50, 50)
        self.DESK_BROWN = (130, 85, 55)

        # Buch-Cover-Farben für optische Abwechslung
        self.BOOK_COLORS = [
            (40, 90, 150),  # Blau
            (160, 60, 130), # Lila
            (45, 125, 80),  # Grün
            (200, 110, 40)  # Orange
        ]

        # =========================
        # SCHRIFTEN
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # SCANNER & LASER LOGIK
        # =========================
        # Das optische Sensorfeld oben in der Mitte
        self.scanner_rect = pygame.Rect(self.window_x + 350, self.window_y + 160, 400, 180)
        
        # Laser-Oszillation (Bewegung auf und ab)
        self.laser_y_offset = 0
        self.laser_speed = 0.05  # Geschwindigkeit des Sinus-Schwungs

        # =========================
        # BÜCHER GENERIEREN
        # =========================
        self.books = []
        self.selected_book = None
        self.offset_x = 0
        self.offset_y = 0
        
        self.scanned_count = 0
        self.required_scans = 4  # Anzahl der Bücher, die gescannt werden müssen
        
        self.create_books()

        # =========================
        # STATUS & FEEDBACK
        # =========================
        self.finished = False
        self.beep_timer = 0  # Lässt den Scanner bei Erfolg kurz grün aufleuchten

    def create_books(self):
        # Wir spawnen die Bücher leicht gestapelt auf der linken Seite (Ablage)
        for i in range(self.required_scans):
            width = 160
            height = 230
            
            # Versetzte Startpositionen auf dem linken Schreibtisch-Bereich
            bx = self.window_x + 80 + (i * 25)
            by = self.window_y + 380 - (i * 15)
            
            rect = pygame.Rect(bx, by, width, height)
            
            # Der Barcode liegt relativ im unteren Viertel des Buch-Covers
            # Format: (Relativer X-Offset, Relativer Y-Offset, Breite, Höhe)
            barcode_local_rect = pygame.Rect(20, 170, 120, 45)

            self.books.append({
                "rect": rect,
                "barcode_local": barcode_local_rect,
                "color": self.BOOK_COLORS[i % len(self.BOOK_COLORS)],
                "scanned": False,
                "beep_active": False
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW (Schreibtisch)
        # =========================
        pygame.draw.rect(self.screen, self.DESK_BROWN, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # RECHTE SEITE: ERLEDIGT-ZONE
        # =========================
        drop_zone = pygame.Rect(self.window_x + 800, self.window_y + 400, 220, 240)
        pygame.draw.rect(self.screen, (105, 70, 45), drop_zone, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, drop_zone, width = 2, border_radius = 10)
        
        lbl = self.font.render("ERLEDIGT", True, (90, 55, 30))
        self.screen.blit(lbl, (drop_zone.centerx - 50, drop_zone.centery - 15))

        # =========================
        # SCANNER-BOX ZEICHNEN
        # =========================
        # Hintergrund des Scanners leuchtet kurz grün auf, wenn ein Buch erfasst wurde
        scanner_bg = (30, 45, 35) if self.beep_timer > 0 else (25, 25, 30)
        pygame.draw.rect(self.screen, scanner_bg, self.scanner_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, self.scanner_rect, width=4, border_radius=10)

        # Glas-Scheibe Andeutung
        pygame.draw.rect(self.screen, (50, 60, 70), self.scanner_rect, width=1, border_radius=10)

        # =========================
        # TEXT-INFOS
        # =========================
        title = self.big_font.render("BARCODE SCANNER", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 240, self.window_y + 20))

        info_text = f"Scanne die Bücher: {self.scanned_count}/{self.required_scans} erfasst"
        if self.finished:
            info_text = "Alle Bücher registriert! Ausgezeichnet."
        
        info = self.font.render(info_text, True, self.WHITE if not self.finished else self.GREEN)
        self.screen.blit(info, (self.window_x + 350, self.window_y + 110))

        # =========================
        # BÜCHER ZEICHNEN (Ungescannte Stapel unten halten)
        # =========================
        # Erst alle unbewegten/ungescannten Bücher zeichnen
        for book in self.books:
            if not book["scanned"] and book != self.selected_book:
                self.draw_book(book)

        # Bereits gescannte Bücher dekorativ auf dem Erledigt-Stapel ablegen
        scanned_stack_y = self.window_y + 580
        for book in self.books:
            if book["scanned"] and book != self.selected_book:
                # Fixiert auf der rechten Seite stapeln
                book["rect"].x = self.window_x + 830
                book["rect"].y = scanned_stack_y
                scanned_stack_y -= 20  # Stapel-Effekt nach oben
                self.draw_book(book)

        # Das aktuell gehaltene Buch über allen anderen zeichnen
        if self.selected_book:
            self.draw_book(self.selected_book)

        # =========================
        # LASER-STRAHL ANIMATION
        # =========================
        # Berechne die auf- und abfahrende Y-Position des Lasers im Scannerfeld via Sinus
        t = pygame.time.get_ticks() * self.laser_speed
        # Normalisiert den Sinus zwischen 0 und 1 und mappt ihn auf die Scannerhöhe
        laser_local_y = (math.sin(t) + 1) / 2 * (self.scanner_rect.height - 20) + 10
        absolute_laser_y = self.scanner_rect.y + laser_local_y

        # Zeichne den glühenden Laserstrahl
        pygame.draw.line(self.screen, self.LASER_RED, (self.scanner_rect.x + 10, absolute_laser_y), (self.scanner_rect.right - 10, absolute_laser_y), 3)
        
        # =========================
        # COLLISION & HITBOX ENGINE
        # =========================
        self.check_laser_collision(absolute_laser_y)

        # Beep Feedback-Timer runterzählen
        if self.beep_timer > 0:
            self.beep_timer -= 1

        # =========================
        # TASK FINISHED OVERLAY
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_book(self, book):
        br = book["rect"]
        # Buch-Körper
        pygame.draw.rect(self.screen, book["color"], br, border_radius=6)
        pygame.draw.rect(self.screen, self.BLACK, br, width=3, border_radius=6)
        
        # Weißes Barcode-Schild auf dem Buch aufbringen
        local_bc = book["barcode_local"]
        global_bc_rect = pygame.Rect(br.x + local_bc.x, br.y + local_bc.y, local_bc.width, local_bc.height)
        pygame.draw.rect(self.screen, (255, 255, 255), global_bc_rect)
        pygame.draw.rect(self.screen, self.BLACK, global_bc_rect, width=1)

        # Die typischen schwarzen Striche im Barcode zeichnen
        for i in range(4, local_bc.width - 4, 6):
            # Variierende Strichstärken simulieren
            line_weight = 3 if (i // 6) % 3 == 0 else 1
            pygame.draw.line(
                self.screen, 
                self.BLACK, 
                (global_bc_rect.x + i, global_bc_rect.y + 4), 
                (global_bc_rect.x + i, global_bc_rect.bottom - 4), 
                line_weight
            )

    def check_laser_collision(self, laser_y):
        if self.finished: return

        for book in self.books:
            # Nur ungescannte Bücher können erfasst werden
            if not book["scanned"]:
                br = book["rect"]
                local_bc = book["barcode_local"]
                # Berechne die absolute Welt-Koordinate des Barcodes auf dem Schirm
                global_bc_rect = pygame.Rect(br.x + local_bc.x, br.y + local_bc.y, local_bc.width, local_bc.height)

                # Prüfschritt 1: Befindet sich der Barcode horizontal komplett im Scannerfeld?
                if self.scanner_rect.contains(global_bc_rect):
                    # Prüfschritt 2: Schneidet die Höhenlinie des Lasers die Barcode-Fläche?
                    if global_bc_rect.top <= laser_y <= global_bc_rect.bottom:
                        # Treffer! Buch erfolgreich registriert
                        book["scanned"] = True
                        self.scanned_count += 1
                        self.beep_timer = 12  # Löst visuelles Aufblitzen für ca. 200ms aus
                        
                        # Wenn das gerade gehaltene Buch gescannt wurde, lassen wir es sofort los
                        if self.selected_book == book:
                            self.selected_book = None
                        
                        if self.scanned_count >= self.required_scans:
                            self.finished = True
                        break

    def handle_event(self, event):
        if self.finished:
            return

        # =========================
        # MAUS KLICK (Buch greifen)
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = pygame.mouse.get_pos()
            
            # Wir gehen die Bücher rückwärts durch, damit man das oberste Buch zuerst greift
            for book in reversed(self.books):
                if not book["scanned"] and book["rect"].collidepoint(mouse_pos):
                    self.selected_book = book
                    self.offset_x = book["rect"].x - mouse_pos[0]
                    self.offset_y = book["rect"].y - mouse_pos[1]
                    break

        # =========================
        # MAUS BEWEGUNG
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_book:
                mouse_pos = pygame.mouse.get_pos()
                self.selected_book["rect"].x = mouse_pos[0] + self.offset_x
                self.selected_book["rect"].y = mouse_pos[1] + self.offset_y

        # =========================
        # LOSLASSEN
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.selected_book = None

    def is_finished(self):
        return self.finished

class LightBulbTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.YELLOW = (255, 230, 100)
        self.DARK_GRAY = (50, 50, 55)
        self.LIGHT_GRAY = (160, 165, 170)
        self.GLASS_OLD = (100, 105, 110) # Trüb/Kaputt
        self.BOX_BLUE = (50, 80, 140)

        # =========================
        # SCHRIFTEN
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # MECHANIK-ELEMENTE
        # =========================
        # Die Lampenfassung (oben in der Mitte)
        self.socket_center = (self.window_x + 550, self.window_y + 220)
        self.socket_rect = pygame.Rect(self.socket_center[0] - 30, self.socket_center[1] - 40, 60, 40)

        # Mülleimer (unten rechts)
        self.bin_rect = pygame.Rect(self.window_x + 850, self.window_y + 450, 150, 180)

        # Box mit neuen Birnen (unten links)
        self.box_rect = pygame.Rect(self.window_x + 100, self.window_y + 480, 180, 140)

        # Zustand der Glühbirne
        # X und Y werden dynamisch berechnet. 'progress' steuert das Gewinde (0 = komplett eingeschraubt, 120 = ganz draußen)
        self.bulb_progress = 0.0 
        
        # Drag & Drop Offsets
        self.offset_x = 0
        self.offset_y = 0

        # Phasen: 
        # "UNSCREW" (Alte Birne lösen)
        # "TRASH_OLD" (Alte Birne wegschmeißen)
        # "GRAB_NEW" (Neue Birne aus Box holen)
        # "SCREW_NEW" (Neue Birne festdrehen)
        self.phase = "UNSCREW"

        # Positionsspeicher für die physikalischen Objekte
        self.old_bulb_pos = list(self.socket_center)
        self.new_bulb_pos = [self.box_rect.centerx, self.box_rect.centery]
        
        self.is_dragging = False
        self.last_angle = None

        self.finished = False

    def draw(self):
        # Raum-Hintergrund (Dunkel, da Licht kaputt)
        bg_color = (15, 15, 20) if not self.finished else (50, 50, 40)
        self.screen.fill(bg_color)

        # =========================
        # TASK WINDOW (Zimmerwand)
        # =========================
        wall_color = (35, 40, 45) if not self.finished else (110, 110, 95)
        pygame.draw.rect(self.screen, wall_color, self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # Lichtkegel zeichnen, wenn fertig
        if self.finished:
            # Ein simpler, transparenter Lichtstrahl-Effekt nach unten
            light_poly = [
                self.socket_center,
                (self.window_x, self.window_y + self.window_height),
                (self.window_x + self.window_width, self.window_y + self.window_height)
            ]
            # Da Pygame Standard-Polygone nicht nativ transparent zeichnet, nutzen wir ein temporäres Surface
            overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            pygame.draw.polygon(overlay, (255, 240, 150, 80), light_poly)
            self.screen.blit(overlay, (0, 0))

        # =========================
        # MÜLLEIMER ZEICHNEN
        # =========================
        pygame.draw.rect(self.screen, self.DARK_GRAY, self.bin_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, self.bin_rect, width=3, border_radius=10)
        # Rillen auf dem Eimer
        for i in range(1, 5):
            rx = self.bin_rect.x + (i * 30)
            pygame.draw.line(self.screen, self.BLACK, (rx, self.bin_rect.y + 10), (rx, self.bin_rect.bottom - 10), 2)

        # =========================
        # SCHACHTEL FÜR NEUE BIRNEN
        # =========================
        pygame.draw.rect(self.screen, self.BOX_BLUE, self.box_rect)
        pygame.draw.rect(self.screen, self.BLACK, self.box_rect, width=3)
        box_lbl = self.font.render("OSRAM", True, self.WHITE)
        self.screen.blit(box_lbl, (self.box_rect.x + 45, self.box_rect.y + 50))

        # =========================
        # FASSUNG (SOCKET) ZEICHNEN
        # =========================
        # Kabel von der Decke
        pygame.draw.line(self.screen, self.BLACK, (self.socket_center[0], self.window_y), (self.socket_center[0], self.socket_rect.y), 6)
        # Die metallische Fassung
        pygame.draw.rect(self.screen, self.LIGHT_GRAY, self.socket_rect, border_radius=3)
        pygame.draw.rect(self.screen, self.BLACK, self.socket_rect, width=3, border_radius=3)

        # =========================
        # TEXT-ANWEISUNGEN
        # =========================
        title = self.big_font.render("LIGHT BULB FIX", True, self.WHITE if not self.finished else self.BLACK)
        self.screen.blit(title, (self.window_x + 320, self.window_y + 20))

        if self.phase == "UNSCREW":
            info_text = "Schraube die alte Glühbirne heraus! (Gegen den Uhrzeigersinn drehen)"
        elif self.phase == "TRASH_OLD":
            info_text = "Wirf die kaputte Birne in den Mülleimer."
        elif self.phase == "GRAB_NEW":
            info_text = "Nimm eine neue Glühbirne aus der Schachtel."
        elif self.phase == "SCREW_NEW":
            info_text = "Setze die neue Birne ein und drehe sie fest! (Im Uhrzeigersinn)"
        else:
            info_text = "Es werde Licht! Hervorragend."

        info = self.font.render(info_text, True, self.WHITE if not self.finished else (20, 80, 20))
        self.screen.blit(info, (self.window_x + 220, self.window_y + 110))

        # =========================
        # DIE GLÜHBIRNEN ZEICHNEN
        # =========================
        if self.phase in ["UNSCREW", "TRASH_OLD"]:
            # Alte Birne bewegt sich beim Schrauben nach unten aus der Fassung
            if self.phase == "UNSCREW":
                self.old_bulb_pos[1] = self.socket_center[1] + int(self.bulb_progress)
            self.draw_bulb(self.old_bulb_pos, is_clean=False, turned_on=False)

        if self.phase in ["GRAB_NEW", "SCREW_NEW", "SUCCESS"]:
            # Neue Birne bewegt sich beim Schrauben nach oben in die Fassung
            if self.phase == "SCREW_NEW":
                self.new_bulb_pos[1] = self.socket_center[1] + int(self.bulb_progress)
            self.draw_bulb(self.new_bulb_pos, is_clean=True, turned_on=self.finished)

        # =========================
        # TASK FINISHED OVERLAY
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_bulb(self, pos, is_clean=True, turned_on=False):
        # pos = (Mitte des Gewindes)
        bx, by = pos

        # 1. Das Metallgewinde
        screw_rect = pygame.Rect(bx - 18, by, 36, 25)
        pygame.draw.rect(self.screen, (130, 135, 140), screw_rect)
        pygame.draw.rect(self.screen, self.BLACK, screw_rect, width=2)
        # Rillen des Gewindes andeuten
        pygame.draw.line(self.screen, self.BLACK, (bx - 18, by + 8), (bx + 18, by + 8), 2)
        pygame.draw.line(self.screen, self.BLACK, (bx - 18, by + 16), (bx + 18, by + 16), 2)

        # 2. Der Glaskörper
        glass_color = self.YELLOW if turned_on else (self.WHITE if is_clean else self.GLASS_OLD)
        glass_center = (bx, by + 60)
        pygame.draw.circle(self.screen, glass_color, glass_center, 35)
        pygame.draw.circle(self.screen, self.BLACK, glass_center, 35, width=3)

        # Verbindungshals zwischen Gewinde und Glaskugel
        neck_rect = pygame.Rect(bx - 18, by + 23, 36, 12)
        pygame.draw.rect(self.screen, glass_color, neck_rect)
        pygame.draw.line(self.screen, self.BLACK, (bx - 18, by + 23), (bx - 18, by + 35), 2)
        pygame.draw.line(self.screen, self.BLACK, (bx + 18, by + 23), (bx + 18, by + 35), 2)

        # Glühdraht im Inneren (nur sichtbar, wenn nicht komplett hell aufleuchtend)
        if not turned_on:
            pygame.draw.lines(self.screen, (200, 100, 40) if is_clean else self.BLACK, False, 
                              [(bx - 10, by + 55), (bx - 5, by + 45), (bx + 5, by + 45), (bx + 10, by + 55)], 2)

    def handle_event(self, event):
        if self.finished:
            return

        mouse_pos = pygame.mouse.get_pos()

        # ========================================================
        # PHASE 1: ALTE GLÜHBIRNE RAUSDREHEN
        # ========================================================
        if self.phase == "UNSCREW":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Prüfen, ob Klick auf die alte Birne erfolgt
                dist = math.hypot(mouse_pos[0] - self.old_bulb_pos[0], mouse_pos[1] - (self.old_bulb_pos[1] + 60))
                if dist < 45:
                    self.is_dragging = True
                    # Mathematischen Startwinkel bestimmen
                    self.last_angle = math.atan2(mouse_pos[1] - (self.old_bulb_pos[1] + 60), mouse_pos[0] - self.old_bulb_pos[0])

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                current_angle = math.atan2(mouse_pos[1] - (self.old_bulb_pos[1] + 60), mouse_pos[0] - self.old_bulb_pos[0])
                angle_diff = current_angle - self.last_angle
                
                # Normalisierung gegen unnatürliche Sprünge beim Quadranten-Wechsel
                if angle_diff > math.pi: angle_diff -= 2 * math.pi
                if angle_diff < -math.pi: angle_diff += 2 * math.pi

                # Wenn gegen den Uhrzeigersinn gedreht wird (negatives Delta im mathematischen System)
                if angle_diff < 0:
                    self.bulb_progress += abs(angle_diff) * 8  # Drehgeschwindigkeit skalieren
                    if self.bulb_progress >= 90.0: # Weit genug herausgedreht!
                        self.phase = "TRASH_OLD"
                        self.is_dragging = False

                self.last_angle = current_angle

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.is_dragging = False

        # ========================================================
        # PHASE 2: ALTE GLÜHBIRNE WEGSCHMEISSEN (Drag & Drop)
        # ========================================================
        elif self.phase == "TRASH_OLD":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dist = math.hypot(mouse_pos[0] - self.old_bulb_pos[0], mouse_pos[1] - (self.old_bulb_pos[1] + 60))
                if dist < 45:
                    self.is_dragging = True
                    self.offset_x = self.old_bulb_pos[0] - mouse_pos[0]
                    self.offset_y = self.old_bulb_pos[1] - mouse_pos[1]

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                self.old_bulb_pos[0] = mouse_pos[0] + self.offset_x
                self.old_bulb_pos[1] = mouse_pos[1] + self.offset_y

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.is_dragging:
                    self.is_dragging = False
                    # Kollision mit Mülleimer prüfen
                    if self.bin_rect.collidepoint(mouse_pos):
                        self.phase = "GRAB_NEW"
                        # Setze Progress zurück für das spätere Eindrehen der neuen Birne
                        self.bulb_progress = 90.0 

        # ========================================================
        # PHASE 3: NEUE GLÜHBIRNE AUS SCHACHTEL HOLEN
        # ========================================================
        elif self.phase == "GRAB_NEW":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Klick in der Box?
                if self.box_rect.collidepoint(mouse_pos):
                    self.is_dragging = True
                    self.new_bulb_pos = list(mouse_pos)
                    self.offset_x = 0
                    self.offset_y = 0

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                self.new_bulb_pos[0] = mouse_pos[0]
                self.new_bulb_pos[1] = mouse_pos[1] - 40 # Versatz, damit man das Gewinde sieht

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.is_dragging:
                    self.is_dragging = False
                    # Prüfen, ob nahe genug an der Fassung losgelassen wurde
                    dist_to_socket = math.hypot(self.new_bulb_pos[0] - self.socket_center[0], self.new_bulb_pos[1] - (self.socket_center[1] + 90))
                    if dist_to_socket < 60:
                        self.phase = "SCREW_NEW"
                        self.new_bulb_pos[0] = self.socket_center[0]

        # ========================================================
        # PHASE 4: NEUE GLÜHBIRNE REINDREHEN
        # ========================================================
        elif self.phase == "SCREW_NEW":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dist = math.hypot(mouse_pos[0] - self.new_bulb_pos[0], mouse_pos[1] - (self.new_bulb_pos[1] + 60))
                if dist < 45:
                    self.is_dragging = True
                    self.last_angle = math.atan2(mouse_pos[1] - (self.new_bulb_pos[1] + 60), mouse_pos[0] - self.new_bulb_pos[0])

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                current_angle = math.atan2(mouse_pos[1] - (self.new_bulb_pos[1] + 60), mouse_pos[0] - self.new_bulb_pos[0])
                angle_diff = current_angle - self.last_angle
                
                if angle_diff > math.pi: angle_diff -= 2 * math.pi
                if angle_diff < -math.pi: angle_diff += 2 * math.pi

                # Im Uhrzeigersinn drehen (positives Delta im mathematischen System)
                if angle_diff > 0:
                    self.bulb_progress -= abs(angle_diff) * 8
                    if self.bulb_progress <= 0.0: # Ganz hineingeschraubt!
                        self.new_bulb_pos[1] = self.socket_center[1]
                        self.phase = "SUCCESS"
                        self.finished = True
                        self.is_dragging = False

                self.last_angle = current_angle

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.is_dragging = False

    def is_finished(self):
        return self.finished

class LockerCleanTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 40, 40)
        
        # Gehäuse-Farben
        self.LOCKER_OUTER = (100, 110, 120)  # Metallgrau außen
        self.LOCKER_INNER = (60, 65, 70)     # Dunkleres Innenleben
        self.SHELF_COLOR = (80, 85, 90)
        self.BIN_GRAY = (40, 40, 45)
        
        # Objekt-Farben
        self.TRASH_CAN = (200, 70, 70)       # Rote Dose
        self.TRASH_PEEL = (220, 200, 50)     # Gelbe Banane
        self.BOOK_COLOR = (40, 100, 180)     # Blaues Buch

        # =========================
        # SCHRIFTEN
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # PHASEN-MANAGEMENT
        # =========================
        # Phasen: "CLEAN_TRASH" -> "ARRANGE_BOOKS" -> "FIX_DOOR" -> "SUCCESS"
        self.phase = "CLEAN_TRASH"
        self.finished = False

        # =========================
        # GEOMETRIE & ZONEN
        # =========================
        # Der geöffnete Spind (zentriert)
        self.locker_rect = pygame.Rect(self.window_x + 350, self.window_y + 140, 320, 480)
        # Das obere Fachbrett (Zielzone für Bücher)
        self.shelf_y = self.locker_rect.y + 150
        self.shelf_target_rect = pygame.Rect(self.locker_rect.x + 10, self.locker_rect.y + 10, 300, 130)

        # Mülleimer rechts neben dem Spind (Zielzone für Müll)
        self.bin_rect = pygame.Rect(self.window_x + 800, self.window_y + 400, 160, 220)

        # Scharnier-Position für Phase 3 (Oben links an der Tür)
        self.screw_center = (self.window_x + 220, self.window_y + 200)
        self.screw_clicks = 0
        self.required_clicks = 3

        # =========================
        # INTERAKTIVE OBJEKTE
        # =========================
        self.dragged_item = None
        self.offset_x = 0
        self.offset_y = 0

        # Müll-Objekte (liegen chaotisch unten im Spind)
        self.trash_items = [
            {"name": "dose", "rect": pygame.Rect(self.locker_rect.x + 40, self.locker_rect.bottom - 60, 40, 50), "color": self.TRASH_CAN, "removed": False},
            {"name": "banane", "rect": pygame.Rect(self.locker_rect.x + 180, self.locker_rect.bottom - 45, 70, 30), "color": self.TRASH_PEEL, "removed": False}
        ]

        # Buch-Objekte (liegen chaotisch unten im Spind, müssen nach oben)
        self.book_items = [
            {"rect": pygame.Rect(self.locker_rect.x + 100, self.locker_rect.bottom - 50, 60, 40), "color": self.BOOK_COLOR, "placed": False}
        ]

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # TASK WINDOW
        # =========================
        pygame.draw.rect(self.screen, (45, 50, 55), self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # MÜLLEIMER ZEICHNEN
        # =========================
        pygame.draw.rect(self.screen, self.BIN_GRAY, self.bin_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, self.bin_rect, width=3, border_radius=10)
        # Mülltonnen-Symbol/Text
        bin_lbl = self.font.render("MÜLL", True, (90, 95, 100))
        self.screen.blit(bin_lbl, (self.bin_rect.centerx - 25, self.bin_rect.y + 20))

        # =========================
        # SPIND ZEICHNEN (INNENLEBEN)
        # =========================
        # Korpus
        pygame.draw.rect(self.screen, self.LOCKER_INNER, self.locker_rect)
        pygame.draw.rect(self.screen, self.LOCKER_OUTER, self.locker_rect, width=6)
        # Fachboden oben
        pygame.draw.line(self.screen, self.LOCKER_OUTER, (self.locker_rect.x, self.shelf_y), (self.locker_rect.right, self.shelf_y), 5)

        # =========================
        # SCHIEFE SPINDTÜR ZEICHNEN (PHASENABHÄNGIG)
        # =========================
        # In Phase 1 & 2 hängt die geöffnete Tür links extrem schief im Raum
        if self.phase in ["CLEAN_TRASH", "ARRANGE_BOOKS"]:
            door_poly = [
                (self.window_x + 220, self.window_y + 150), # Oben links (hängt tiefer)
                (self.locker_rect.x - 5, self.window_y + 190),  # Oben rechts (Verbindung)
                (self.locker_rect.x - 5, self.locker_rect.bottom - 40), # Unten rechts
                (self.window_x + 220, self.locker_rect.bottom + 40) # Unten links
            ]
            pygame.draw.polygon(self.screen, self.LOCKER_OUTER, door_poly)
            pygame.draw.polygon(self.screen, self.BLACK, door_poly, width=3)
        
        elif self.phase == "FIX_DOOR":
            # Tür hängt immer noch leicht schief, fokussiert aber das lose Scharnier
            door_poly = [
                (self.window_x + 220, self.window_y + 180), 
                (self.locker_rect.x - 5, self.window_y + 190),
                (self.locker_rect.x - 5, self.locker_rect.bottom - 40),
                (self.window_x + 220, self.locker_rect.bottom + 10)
            ]
            pygame.draw.polygon(self.screen, self.LOCKER_OUTER, door_poly)
            pygame.draw.polygon(self.screen, self.BLACK, door_poly, width=3)
            
            # Das lose Scharnier (Große kaputte Schraube)
            pygame.draw.circle(self.screen, (130, 135, 140), self.screw_center, 18)
            pygame.draw.circle(self.screen, self.BLACK, self.screw_center, 18, width=2)
            # Der Schraubenschlitz dreht sich visuell bei Klicks
            angle = self.screw_clicks * 45
            rad = math.radians(angle)
            sx = int(math.cos(rad) * 12)
            sy = int(math.sin(rad) * 12)
            pygame.draw.line(self.screen, self.BLACK, (self.screw_center[0] - sx, self.screw_center[1] - sy), (self.screw_center[0] + sx, self.screw_center[1] + sy), 4)

        else: # SUCCESS: Tür steht perfekt gerade geöffnet parallel zum Spind
            door_rect = pygame.Rect(self.locker_rect.x - 160, self.locker_rect.y, 160, self.locker_rect.height)
            pygame.draw.rect(self.screen, self.LOCKER_OUTER, door_rect)
            pygame.draw.rect(self.screen, self.BLACK, door_rect, width=3)

        # =========================
        # OBJEKTE ZEICHNEN
        # =========================
        # Müll-Zeichnung
        for trash in self.trash_items:
            if not trash["removed"] and trash != self.dragged_item:
                pygame.draw.rect(self.screen, trash["color"], trash["rect"], border_radius=4)
                pygame.draw.rect(self.screen, self.BLACK, trash["rect"], width=2, border_radius=4)

        # Bücher-Zeichnung
        for book in self.book_items:
            if book != self.dragged_item:
                pygame.draw.rect(self.screen, book["color"], book["rect"], border_radius=2)
                pygame.draw.rect(self.screen, self.BLACK, book["rect"], width=2, border_radius=2)
                # Buchseiten-Streifen andeuten
                pygame.draw.line(self.screen, self.WHITE, (book["rect"].x + 4, book["rect"].y + 4), (book["rect"].right - 4, book["rect"].y + 4), 2)

        # Gehaltenes Element ganz oben rendern
        if self.dragged_item:
            pygame.draw.rect(self.screen, self.dragged_item["color"], self.dragged_item["rect"], border_radius=4)
            pygame.draw.rect(self.screen, self.BLACK, self.dragged_item["rect"], width=2, border_radius=4)

        # =========================
        # TEXT-ANWEISUNGEN
        # =========================
        title = self.big_font.render("SCHLIESSFACH-PROUTINE", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 200, self.window_y + 20))

        if self.phase == "CLEAN_TRASH":
            info_text = "Räume das Schließfach auf: Wirf den Müll in die Tonne!"
        elif self.phase == "ARRANGE_BOOKS":
            info_text = "Sachen richten: Lege das Schulbuch ordentlich ins obere Fach!"
        elif self.phase == "FIX_DOOR":
            info_text = "Die Tür hängt schief! Klicke auf das obere Scharnier zum Festziehen!"
        else:
            info_text = "Schließfach sauber hinterlassen! Ausgezeichnet."

        info = self.font.render(info_text, True, self.WHITE if not self.finished else self.GREEN)
        self.screen.blit(info, (self.window_x + 180, self.window_y + 100))

        # =========================
        # TASK FINISHED OVERLAY
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def handle_event(self, event):
        if self.finished:
            return

        mouse_pos = pygame.mouse.get_pos()

        # ========================================================
        # PHASE 1: MÜLL ENTFERNEN
        # ========================================================
        if self.phase == "CLEAN_TRASH":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for trash in self.trash_items:
                    if not trash["removed"] and trash["rect"].collidepoint(mouse_pos):
                        self.dragged_item = trash
                        self.offset_x = trash["rect"].x - mouse_pos[0]
                        self.offset_y = trash["rect"].y - mouse_pos[1]
                        break

            elif event.type == pygame.MOUSEMOTION and self.dragged_item:
                self.dragged_item["rect"].x = mouse_pos[0] + self.offset_x
                self.dragged_item["rect"].y = mouse_pos[1] + self.offset_y

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragged_item:
                # Prüfen, ob über Mülleimer abgeworfen
                if self.bin_rect.colliderect(self.dragged_item["rect"]):
                    self.dragged_item["removed"] = True
                
                self.dragged_item = None
                
                # Checken, ob aller Müll weg ist
                if all(t["removed"] for t in self.trash_items):
                    self.phase = "ARRANGE_BOOKS"

        # ========================================================
        # PHASE 2: BÜCHER RICHTEN
        # ========================================================
        elif self.phase == "ARRANGE_BOOKS":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for book in self.book_items:
                    if not book["placed"] and book["rect"].collidepoint(mouse_pos):
                        self.dragged_item = book
                        self.offset_x = book["rect"].x - mouse_pos[0]
                        self.offset_y = book["rect"].y - mouse_pos[1]
                        break

            elif event.type == pygame.MOUSEMOTION and self.dragged_item:
                self.dragged_item["rect"].x = mouse_pos[0] + self.offset_x
                self.dragged_item["rect"].y = mouse_pos[1] + self.offset_y

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragged_item:
                # Prüfen, ob im oberen Fach abgelegt
                if self.shelf_target_rect.contains(self.dragged_item["rect"]):
                    self.dragged_item["placed"] = True
                
                self.dragged_item = None
                
                if all(b["placed"] for b in self.book_items):
                    self.phase = "FIX_DOOR"

        # ========================================================
        # PHASE 3: TÜR REPARIEREN (SCHANIER FESTZIEHEN)
        # ========================================================
        elif self.phase == "FIX_DOOR":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Klick auf die Schraube prüfen
                if math.hypot(mouse_pos[0] - self.screw_center[0], mouse_pos[1] - self.screw_center[1]) < 20:
                    self.screw_clicks += 1
                    if self.screw_clicks >= self.required_clicks:
                        self.phase = "SUCCESS"
                        self.finished = True

    def is_finished(self):
        return self.finished

class TrashDisposalTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.LIGHT_BLUE = (100, 160, 220)
        
        # Umgebungstöne
        self.KITCHEN_WALL = (75, 85, 95)     # Linke Seite: Küche
        self.OUTSIDE_GROUND = (50, 55, 60)   # Rechte Seite: Hof
        self.CONTAINER_GREEN = (25, 110, 60) # Große Mülltonne
        self.TRASH_PLASTIC = (45, 50, 55)    # Dunkle Müllsäcke

        # =========================
        # SCHRIFTEN
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # CONTAINER & CONTAINER-DECKEL
        # =========================
        # Große Zielzone auf der rechten Seite
        self.container_rect = pygame.Rect(self.window_x + 780, self.window_y + 260, 240, 320)
        # Die Luke/Öffnung oben, in die der Müll rein muss
        self.target_zone = pygame.Rect(self.container_rect.x + 20, self.container_rect.y - 20, 200, 80)

        # =========================
        # MÜLLSÄCKE GENERIEREN
        # =========================
        self.bags = []
        self.selected_bag = None
        
        # Trägheits-Zielpunkte für weiche Bewegung (Gewichtssimulation)
        self.target_x = 0
        self.target_y = 0

        self.disposed_count = 0
        self.required_bags = 3
        
        self.create_bags()

        # =========================
        # STATUS
        # =========================
        self.finished = False

    def create_bags(self):
        # Die Säcke stehen gestapelt in der "Küche" unten links
        for i in range(self.required_bags):
            # Versetzte Bodenpositionen
            bx = self.window_x + 90 + (i * 70)
            by = self.window_y + 480 + (i * 15)
            
            # Die Hitbox des Sacks
            rect = pygame.Rect(bx, by, 90, 110)
            
            # Farbnuancen für jeden Sack generieren (Grau-Blau-Töne)
            shade = random.randint(-10, 10)
            color = (self.TRASH_PLASTIC[0] + shade, self.TRASH_PLASTIC[1] + shade, self.TRASH_PLASTIC[2] + shade)

            self.bags.append({
                "rect": rect,
                "color": color,
                "disposed": False,
                "weight_factor": 0.15 - (i * 0.02) # Jeder Sack fühlt sich minimal anders schwer an beim Ziehen
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # =========================
        # ENGINE LOGIK (TRÄGHEIT/PHYSICK)
        # =========================
        self.update_physics()

        # =========================
        # COPTICAL SPLIT (Küche vs. Draußen)
        # =========================
        # Linke Hälfte: Küche
        pygame.draw.rect(self.screen, self.KITCHEN_WALL, (self.window_x, self.window_y, self.window_width // 2, self.window_height), border_top_left_radius=20, border_bottom_left_radius=20)
        # Rechte Hälfte: Draußen
        pygame.draw.rect(self.screen, self.OUTSIDE_GROUND, (self.window_x + self.window_width // 2, self.window_y, self.window_width // 2, self.window_height), border_top_right_radius=20, border_bottom_right_radius=20)
        
        # Trennlinie (Hauswand-Kante)
        pygame.draw.line(self.screen, self.BLACK, (self.window_x + self.window_width // 2, self.window_y), (self.window_x + self.window_width // 2, self.window_y + self.window_height), 4)

        # Rahmen um das gesamte Task-Fenster
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # CONTAINER ZEICHNEN
        # =========================
        # Hauptkörper
        pygame.draw.rect(self.screen, self.CONTAINER_GREEN, self.container_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BLACK, self.container_rect, width=4, border_radius=10)
        
        # Räder unten drunter
        pygame.draw.circle(self.screen, self.BLACK, (self.container_rect.x + 40, self.container_rect.bottom), 18)
        pygame.draw.circle(self.screen, self.BLACK, (self.container_rect.right - 40, self.container_rect.bottom), 18)
        
        # Offene Klappe / Einwurfschacht (Schattiertes Rechteck)
        pygame.draw.rect(self.screen, (15, 20, 15), self.target_zone, border_radius=5)
        pygame.draw.rect(self.screen, self.BLACK, self.target_zone, width=3, border_radius=5)

        # Recycling-Logo (Simpel angedeutetes Dreieck)
        logo_center = (self.container_rect.centerx, self.container_rect.centery + 30)
        pygame.draw.polygon(self.screen, self.WHITE, [
            (logo_center[0], logo_center[1] - 30),
            (logo_center[0] - 25, logo_center[1] + 15),
            (logo_center[0] + 25, logo_center[1] + 15)
        ], width=3)

        # =========================
        # TEXT-INFOS
        # =========================
        title = self.big_font.render("BRING OUT THE TRASH", True, self.WHITE)
        self.screen.blit(title, (self.window_x + 180, self.window_y + 20))

        info_text = f"Bringe die Müllsäcke weg: {self.disposed_count}/{self.required_bags} entsorgt"
        if self.finished:
            info_text = "Hof sauber, Task erledigt! Ab zurück ins Warme."
        
        info = self.font.render(info_text, True, self.WHITE if not self.finished else self.GREEN)
        self.screen.blit(info, (self.window_x + 310, self.window_y + 110))

        # =========================
        # MÜLLSÄCKE RECHTS & LINKS RENDER-QUEUE
        # =========================
        # Unentsorgte Säcke am Boden zeichnen
        for bag in self.bags:
            if not bag["disposed"] and bag != self.selected_bag: # Korrektur: Variable im Scope halten
                if bag != self.selected_bag:
                    self.draw_trash_bag(bag)

        # Gehaltenen, schweren Sack als oberstes Element rendern
        if self.selected_bag:
            self.draw_trash_bag(self.selected_bag)

        # =========================
        # TASK FINISHED OVERLAY
        # =========================
        if self.finished:
            finished = self.big_font.render("TASK FINISHED", True, self.GREEN)
            text_rect = finished.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(finished, text_rect)

    def draw_trash_bag(self, bag):
        r = bag["rect"]
        
        # Hauptkörper des Beutels (Abgerundete organische Ellipsen-Form)
        pygame.draw.ellipse(self.screen, bag["color"], r)
        pygame.draw.ellipse(self.screen, self.BLACK, r, width=3)

        # Der zugeknotete Zipfel oben (Verschluss)
        knot_poly = [
            (r.centerx - 15, r.y + 10),
            (r.centerx, r.y - 12),
            (r.centerx + 15, r.y + 10),
            (r.centerx, r.y + 20)
        ]
        pygame.draw.polygon(self.screen, bag["color"], knot_poly)
        pygame.draw.polygon(self.screen, self.BLACK, knot_poly, width=2)
        
        # Rotes oder blaues Band am Knoten als Detail
        pygame.draw.line(self.screen, (220, 50, 50), (r.centerx - 10, r.y + 12), (r.centerx + 10, r.y + 12), 3)

    def update_physics(self):
        # Wenn ein Sack gegriffen ist, bewegt er sich verzögert (Linear Interpolation) auf die Maus zu
        if self.selected_bag:
            # Berechne Differenz zwischen Wunschposition (Maus) und Ist-Position des Sacks
            dx = self.target_x - self.selected_bag["rect"].centerx
            dy = self.target_y - self.selected_bag["rect"].centery
            
            # Bewege den Sack nur um einen Bruchteil des Weges (Dämpfung)
            # Das erzeugt das visuelle Gefühl von zäher Masse und Gewicht
            self.selected_bag["rect"].x += int(dx * self.selected_bag["weight_factor"])
            self.selected_bag["rect"].y += int(dy * self.selected_bag["weight_factor"])

    def handle_event(self, event):
        if self.finished:
            return

        mouse_pos = pygame.mouse.get_pos()

        # =========================
        # MÜLLSACK GREIFEN
        # =========================
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Rückwärts durchsuchen, damit man den vordersten Sack greift
            for bag in reversed(self.bags):
                if not bag["disposed"] and bag["rect"].collidepoint(mouse_pos):
                    self.selected_bag = bag
                    # Speicher die relative Mausposition im Sack, damit er nicht springt
                    self.target_x = mouse_pos[0]
                    self.target_y = mouse_pos[1]
                    break

        # =========================
        # GEWICHTS-ZIELPUNKT AKTUALISIEREN
        # =========================
        elif event.type == pygame.MOUSEMOTION:
            if self.selected_bag:
                self.target_x = mouse_pos[0]
                self.target_y = mouse_pos[1]

        # =========================
        # LOSLASSEN (EINWURF PRÜFEN)
        # =========================
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.selected_bag:
                # Prüfen, ob der Sack die offene Luke des Containers berührt
                if self.target_zone.colliderect(self.selected_bag["rect"]):
                    self.selected_bag["disposed"] = True
                    self.disposed_count += 1
                    
                    if self.disposed_count >= self.required_bags:
                        self.finished = True
                        
                self.selected_bag = None

    def is_finished(self):
        return self.finished

class PipeLeakTask:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()

        # =========================
        # TASK WINDOW
        # =========================
        self.window_width = 1100
        self.window_height = 700

        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2

        self.task_rect = pygame.Rect(
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height
        )

        # =========================
        # FARBEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.GREEN = (0, 220, 0)
        self.RED = (220, 40, 40)
        
        # Rohr & Wasser
        self.PIPE_BASE = (130, 140, 150)     # Graues Metallrohr
        self.PIPE_SHADOW = (90, 100, 110)
        self.WATER_BLUE = (50, 150, 255)    # Heller, spritzender Wasserstrahl
        self.CLAMP_COLOR = (180, 100, 40)    # Rostbraune/Kupferne Reparaturschellen

        # =========================
        # SCHRIFTEN
        # =========================
        self.font = pygame.font.SysFont("arial", 26)
        self.big_font = pygame.font.SysFont("arial", 70)

        # =========================
        # ROHR-GEOMETRIE
        # =========================
        # Das Rohr verläuft horizontal durch die Mitte des Fensters
        self.pipe_rect = pygame.Rect(self.window_x, self.window_y + 300, self.window_width, 100)

        # =========================
        # LEISTUNG & MECHANIK
        # =========================
        self.water_damage = 0.0              # Startet bei 0%, steigt pro Frame basierend auf offenen Lecks
        self.max_damage = 100.0
        
        self.finished = False
        self.failed = False

        # =========================
        # LEAKS GENERIEREN
        # =========================
        self.leaks = []
        self.total_leaks = 5                 # Anzahl der Lecks, die geflickt werden müssen
        
        self.create_leaks()

    def create_leaks(self):
        # Generiert zufällige Bruchstellen entlang des Rohres
        segment_width = self.window_width // (self.total_leaks + 1)
        
        for i in range(self.total_leaks):
            # Berechne X-Position mit leichtem Zufall innerhalb des Segments
            lx = self.window_x + segment_width * (i + 1) + random.randint(-40, 40)
            # Y-Position liegt auf dem Rohr
            ly = self.pipe_rect.y + random.randint(20, 70)
            
            # Jedes Leck spritzt in eine leicht andere Richtung
            angle = random.randint(-45, 45) # Winkel der Partikel
            
            self.leaks.append({
                "pos": (lx, ly),
                "radius": 22,               # Klick-Hitbox
                "fixed": False,
                "angle": angle,
                "particle_timer": 0          # Für die Animation des Wasserstrahls
            })

    def draw(self):
        # Hintergrund außerhalb der Task
        self.screen.fill((20, 20, 30))

        # Update-Logik für Wasserschaden (wird direkt im Draw-Cycle für die Animation berechnet)
        self.update_task_logic()

        # =========================
        # TASK WINDOW
        # =========================
        pygame.draw.rect(self.screen, (40, 45, 50), self.task_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.BLACK, self.task_rect, width=5, border_radius=20)

        # =========================
        # METALLROHR ZEICHNEN
        # =========================
        # Rohr-Körper mit einfacher Schattierung für 3D-Look
        pygame.draw.rect(self.screen, self.PIPE_SHADOW, self.pipe_rect)
        pygame.draw.rect(self.screen, self.PIPE_BASE, (self.pipe_rect.x, self.pipe_rect.y, self.pipe_rect.width, 70))
        pygame.draw.line(self.screen, self.WHITE, (self.pipe_rect.x, self.pipe_rect.y + 10), (self.pipe_rect.right, self.pipe_rect.y + 10), 3) # Highlight-Kante

        # =========================
        # WASSERSTRAHLEN & REPARATURSCHELLEN
        # =========================
        for leak in self.leaks:
            lx, ly = leak["pos"]
            
            if not leak["fixed"]:
                # Animierter Wasserstrahl (Mehrere Kreise/Linien, die nach unten wegspritzen)
                leak["particle_timer"] += 1
                for j in range(4):
                    # Simpler Partikeleffekt basierend auf Zeit
                    offset = (leak["particle_timer"] * 4 + j * 15) % 80
                    rad = math.radians(90 + leak["angle"])
                    
                    wx = lx + int(math.cos(rad) * offset)
                    wy = ly + int(math.sin(rad) * offset)
                    
                    # Wasser wird feiner und transparenter, je weiter es wegfliegt
                    p_radius = max(2, 10 - (offset // 10))
                    pygame.draw.circle(self.screen, self.WATER_BLUE, (wx, wy), p_radius)
                
                # Das Loch/Riss im Rohr selbst
                pygame.draw.ellipse(self.screen, (20, 20, 20), (lx - 10, ly - 5, 20, 10))
            else:
                # Reparierte Stelle: Eine Metallschelle wird über das Loch gelegt
                clamp_rect = pygame.Rect(lx - 25, self.pipe_rect.y - 4, 50, self.pipe_rect.height + 8)
                pygame.draw.rect(self.screen, self.CLAMP_COLOR, clamp_rect, border_radius=4)
                pygame.draw.rect(self.screen, self.BLACK, clamp_rect, width=2, border_radius=4)
                # Schrauben auf der Schelle andeuten
                pygame.draw.circle(self.screen, self.WHITE, (lx, self.pipe_rect.y + 15), 4)
                pygame.draw.circle(self.screen, self.WHITE, (lx, self.pipe_rect.bottom - 15), 4)

        # =========================
        # WASSERSTANDS-ANZEIGE (HUD)
        # =========================
        # Schadensbalken Hintergrund
        bar_rect = pygame.Rect(self.window_x + 300, self.window_y + 140, 500, 30)
        pygame.draw.rect(self.screen, (30, 30, 30), bar_rect, border_radius=5)
        
        # Dynamischer roter Füllstand
        fill_width = int((self.water_damage / self.max_damage) * 500)
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)
            pygame.draw.rect(self.screen, self.RED, fill_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.BLACK, bar_rect, width=3, border_radius=5)

        # =========================
        # TEXT-INFOS
        # =========================
        title = self.big_font.render("ROHRBRUCH!", True, self.WHITE if not self.failed else self.RED)
        self.screen.blit(title, (self.window_x + 360, self.window_y + 20))

        # Schadens-Prozent-Text
        lbl_damage = self.font.render(f"Wasserschaden: {int(self.water_damage)}%", True, self.WHITE)
        self.screen.blit(lbl_damage, (bar_rect.x, bar_rect.y - 35))

        remaining = sum(1 for l in self.leaks if not l["fixed"])
        info_text = f"Klicke auf die Lecks, um sie zu dichten! ({remaining} offen)"
        
        if self.finished:
            info_text = "Alles trocken! Das Rohr hält vorerst wieder."
        elif self.failed:
            info_text = "Raum überflutet! Task fehlgeschlagen."

        info = self.font.render(info_text, True, self.WHITE if not (self.finished or self.failed) else (self.GREEN if self.finished else self.RED))
        self.screen.blit(info, (self.window_x + 280, self.window_y + 190))

        # =========================
        # OVERLAY (SUCCESS / GAME OVER)
        # =========================
        if self.finished or self.failed:
            overlay_text = "TASK FINISHED" if self.finished else "TASK FAILED"
            color = self.GREEN if self.finished else self.RED
            
            rendered_text = self.big_font.render(overlay_text, True, color)
            text_rect = rendered_text.get_rect(center=(self.window_x + self.window_width // 2, self.window_y + self.window_height // 2))
            bg_rect = text_rect.inflate(40, 20)
            
            pygame.draw.rect(self.screen, self.BLACK, bg_rect, border_radius=10)
            self.screen.blit(rendered_text, text_rect)

    def update_task_logic(self):
        if self.finished or self.failed:
            return

        # Zähle offene Lecks
        active_leaks = sum(1 for l in self.leaks if not l["fixed"])
        
        if active_leaks == 0:
            self.finished = True
            return

        # Schaden skaliert mit der Anzahl der offenen Lecks (z.B. 0.05% pro Leck pro Frame)
        self.water_damage += active_leaks * 0.06
        
        if self.water_damage >= self.max_damage:
            self.water_damage = self.max_damage
            self.failed = True

    def handle_event(self, event):
        if self.finished or self.failed:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = pygame.mouse.get_pos()

            # Überprüfe, ob der Spieler ein offenes Leck getroffen hat
            for leak in self.leaks:
                if not leak["fixed"]:
                    lx, ly = leak["pos"]
                    # Mathematische Distanzprüfung (Kreis-Kollision)
                    distance = math.hypot(mouse_pos[0] - lx, mouse_pos[1] - ly)
                    
                    if distance <= leak["radius"]:
                        leak["fixed"] = True
                        break # Nur ein Leck pro Klick dichten

    def is_finished(self):
        return self.finished

    def is_failed(self):
        return self.failed

# =========================================
# TEST
# =========================================
if __name__ == "__main__":

    info = pygame.display.Info()
    screen_width, screen_height = info.current_w, info.current_h
    screen = pygame.display.set_mode(size = (screen_width, screen_height), flags = pygame.FULLSCREEN | pygame.SCALED)

    pygame.display.set_caption("Among Us School Task")

    clock = pygame.time.Clock()

    task = PipeLeakTask(screen)

    running = True

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            task.handle_event(event)

        task.draw()

        pygame.display.update()
        clock.tick(60)

    pygame.quit()