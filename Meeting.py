import pygame
import time

class MeetingSystem:
    def __init__(self, screen, game_state):
        self.screen = screen
        self.screen_width, self.screen_height = screen.get_size()
        self.game_state = game_state  # Referenz auf dein Hauptspiel (Spieler, Leichen etc.)
        
        # =========================
        # FARBEN & SCHRIFTEN
        # =========================
        self.WHITE = (240, 240, 240)
        self.BLACK = (20, 20, 20)
        self.RED = (200, 50, 50)
        self.GREEN = (0, 200, 0)
        self.BLUE = (80, 120, 255)
        self.GRAY = (150, 150, 150)
        self.DARK_GRAY = (50, 50, 50)
        
        self.font = pygame.font.SysFont("arial", 25)
        self.big_font = pygame.font.SysFont("arial", 50)
        
        # =========================
        # MEETING FENSTER
        # =========================
        self.window_width = 1000
        self.window_height = 700
        self.window_x = (self.screen_width - self.window_width) // 2
        self.window_y = (self.screen_height - self.window_height) // 2
        
        self.rect = pygame.Rect(self.window_x, self.window_y, self.window_width, self.window_height)
        
        self.chat_rect = pygame.Rect(self.window_x + 30, self.window_y + 100, 450, 500)
        self.vote_rect = pygame.Rect(self.window_x + 520, self.window_y + 100, 450, 500)
        
        # =========================
        # STATUS & TIMER
        # =========================
        self.is_active = False
        self.phase = "IDLE"  # "CHAT_ONLY", "VOTING", "ENDED"
        self.start_time = 0
        self.chat_cooldown = 5  # 15 Sekunden nur Chat
        self.voting_time = 10    # 30 Sekunden zum Abstimmen
        
        # =========================
        # DATEN
        # =========================
        self.chat_log = []
        self.current_input = ""
        self.votes = {}       # Wer hat wie viele Stimmen? {player_id: anzahl}
        self.has_voted = []   # Welche Spieler haben schon abgestimmt?
        self.alive_players = []

    def trigger_meeting(self, caller_name, reason="BUTTON"):
        """
        Wird aufgerufen, wenn jemand den Notfallknopf drückt oder eine Leiche meldet.
        reason kann "BUTTON" oder "BODY_REPORTED" sein.
        """
        self.is_active = True
        self.phase = "CHAT_ONLY"
        self.start_time = time.time()
        
        self.chat_log = [f"--- MEETING GESTARTET VON {caller_name} ({reason}) ---"]
        self.current_input = ""
        self.votes = {}
        self.has_voted = []
        
        # 1. Aktive Tasks abbrechen & Spieler zum Spawn teleportieren
        for player in self.game_state.players:
            player.active_task = None  # Task abbrechen
            player.x = player.spawn_x  # Zum Spawn teleportieren
            player.y = player.spawn_y
            
            if player.is_alive:
                self.votes[player.name] = 0
                self.alive_players.append(player)
                
        # "Skip Vote" Option hinzufügen
        self.votes["SKIP"] = 0
                
        # 2. Alle Leichen löschen
        self.game_state.bodies.clear()

    def update(self):
        if not self.is_active:
            return
            
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Phasen-Wechsel
        if self.phase == "CHAT_ONLY" and elapsed >= self.chat_cooldown:
            self.phase = "VOTING"
            self.chat_log.append("--- ABSTIMMUNG FREIGEGEBEN ---")
            
        elif self.phase == "VOTING" and elapsed >= (self.chat_cooldown + self.voting_time):
            self.end_meeting()

    def handle_event(self, event):
        if not self.is_active:
            return

        # =========================
        # CHAT EINGABE
        # =========================
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.current_input.strip() != "":
                    # Eigene Nachricht senden (Hier: "Du" als Platzhalter für den lokalen Spieler)
                    self.chat_log.append(f"Du: {self.current_input}")
                    self.current_input = ""
            elif event.key == pygame.K_BACKSPACE:
                self.current_input = self.current_input[:-1]
            else:
                self.current_input += event.unicode

        # =========================
        # ABSTIMMEN (Mausklick)
        # =========================
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.phase == "VOTING" and "local_player" not in self.has_voted:
                mouse_pos = pygame.mouse.get_pos()
                
                # Prüfen, ob auf einen Spieler geklickt wurde
                button_y = self.vote_rect.y + 20
                for player_name in self.votes.keys():
                    btn_rect = pygame.Rect(self.vote_rect.x + 20, button_y, 410, 40)
                    
                    if btn_rect.collidepoint(mouse_pos):
                        self.votes[player_name] += 1
                        self.has_voted.append("local_player")
                        self.chat_log.append(f"Du hast für {player_name} gestimmt.")
                        
                        # Prüfen, ob alle abgestimmt haben
                        if len(self.has_voted) >= len(self.alive_players):
                            self.end_meeting()
                        break
                        
                    button_y += 50

    def draw(self):
        if not self.is_active:
            return
            
        # Hintergrund abdunkeln
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Hauptfenster
        pygame.draw.rect(self.screen, self.DARK_GRAY, self.rect, border_radius=15)
        pygame.draw.rect(self.screen, self.WHITE, self.rect, width=3, border_radius=15)
        
        # Titel & Timer
        elapsed = time.time() - self.start_time
        
        if self.phase == "CHAT_ONLY":
            time_left = max(0, int(self.chat_cooldown - elapsed))
            title_str = f"MEETING - Nur Chat ({time_left}s)"
            title_color = self.RED
        else:
            time_left = max(0, int((self.chat_cooldown + self.voting_time) - elapsed))
            title_str = f"ABSTIMMUNG LÄUFT ({time_left}s)"
            title_color = self.GREEN
            
        title_surf = self.big_font.render(title_str, True, title_color)
        self.screen.blit(title_surf, (self.window_x + 30, self.window_y + 20))

        # =========================
        # CHAT BEREICH
        # =========================
        pygame.draw.rect(self.screen, self.BLACK, self.chat_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.WHITE, self.chat_rect, width=2, border_radius=10)
        
        # Chat-Nachrichten rendern (letzte 15 Nachrichten)
        y_offset = self.chat_rect.y + 10
        for msg in self.chat_log[-15:]:
            msg_surf = self.font.render(msg, True, self.WHITE)
            self.screen.blit(msg_surf, (self.chat_rect.x + 10, y_offset))
            y_offset += 25
            
        # Eingabefeld
        input_rect = pygame.Rect(self.chat_rect.x, self.chat_rect.bottom + 10, self.chat_rect.width, 40)
        pygame.draw.rect(self.screen, self.WHITE, input_rect, border_radius=5)
        input_surf = self.font.render(self.current_input + "|", True, self.BLACK)
        self.screen.blit(input_surf, (input_rect.x + 10, input_rect.y + 5))

        # =========================
        # VOTING BEREICH
        # =========================
        pygame.draw.rect(self.screen, self.BLACK, self.vote_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.WHITE, self.vote_rect, width=2, border_radius=10)
        
        button_y = self.vote_rect.y + 20
        for player_name, vote_count in self.votes.items():
            btn_rect = pygame.Rect(self.vote_rect.x + 20, button_y, 410, 40)
            
            # Farbe ändern, wenn man abstimmen darf
            color = self.BLUE if (self.phase == "VOTING" and "local_player" not in self.has_voted) else self.GRAY
            if player_name == "SKIP": color = self.GRAY
            
            pygame.draw.rect(self.screen, color, btn_rect, border_radius=5)
            
            # Name und Stimmenanzahl (Stimmenanzahl erst zeigen, wenn abgestimmt)
            name_surf = self.font.render(player_name, True, self.WHITE)
            self.screen.blit(name_surf, (btn_rect.x + 10, btn_rect.y + 5))
            
            if "local_player" in self.has_voted or self.phase == "ENDED":
                vote_surf = self.font.render(f"Votes: {vote_count}", True, self.WHITE)
                self.screen.blit(vote_surf, (btn_rect.right - 100, btn_rect.y + 5))
                
            button_y += 50

    def end_meeting(self):
        """
        Wertet das Meeting aus, eliminiert ggf. Spieler und prüft Siegbedingungen.
        """
        self.phase = "ENDED"
        
        # 1. Meiste Votes finden
        max_votes = -1
        eliminated_player = None
        is_tie = False
        
        for name, count in self.votes.items():
            if count > max_votes:
                max_votes = count
                eliminated_player = name
                is_tie = False
            elif count == max_votes:
                is_tie = True  # Gleichstand
                
        # 2. Spieler eliminieren (Gleichstand oder "Skip" = niemand fliegt)
        if is_tie or eliminated_player == "SKIP":
            print("Gleichstand oder geskippt. Niemand wurde eliminiert.")
        else:
            print(f"{eliminated_player} wurde mit {max_votes} Stimmen eliminiert!")
            # Hier den Spieler in deinem GameState auf tot setzen
            for p in self.game_state.players:
                if p.name == eliminated_player:
                    p.is_alive = False
                    
        # 3. Siegbedingung prüfen
        self.check_win_conditions()
        
        # 4. Meeting schließen (kurze Pause, damit Spieler Ergebnis sehen können)
        self.is_active = False

    def check_win_conditions(self):
        """
        Prüft ob Crewmates oder Imposter gewonnen haben
        """
        imposters_alive = sum(1 for p in self.game_state.players if p.is_alive and p.role == "Imposter")
        crewmates_alive = sum(1 for p in self.game_state.players if p.is_alive and p.role == "Crewmate")
        
        if imposters_alive == 0:
            print("CREWMATES GEWINNEN! Alle Imposter wurden eliminiert.")
            # Trigger End Screen
        elif imposters_alive >= crewmates_alive:
            print("IMPOSTER GEWINNEN! Es gibt gleich viele oder mehr Imposter als Crewmates.")
            # Trigger End Screen