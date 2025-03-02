import os
import socket
import threading
import time
import json
from collections import defaultdict


class Server:
    def __init__(self, host='', port=6390, max_connections=100, rate_limit=20, ban_time=30):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.rate_limit = rate_limit  # max requests per second
        self.ban_time = ban_time  # time in seconds
        self.running = True

        self.clients = {}
        self.banned_ips = {}
        self.request_counts = defaultdict(int)
        self.lock = threading.Lock()

        self.users = self.load_users()
        self.options = self.load_options()

        # Création automatique d'un admin si aucun utilisateur n'existe
        if not self.users:
            self.create_user("admin", "0001", "adminpass", "admin")
            self.users = self.load_users()
            print("[INFO] Utilisateur 'admin' créé.")

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(self.max_connections)

        print(f"[INFO] Server started on {self.host}:{self.port}")

        threading.Thread(target=self.reset_request_counts, daemon=True).start()

    def load_users(self):
        users = {}
        if not os.path.exists("data/user"):
            os.makedirs("data/user")

        for user_id in os.listdir("data/user"):
            user_path = os.path.join("data/user", user_id, "user.json")
            if os.path.isfile(user_path):
                try:
                    with open(user_path, "r") as f:
                        data = json.load(f)
                        users[data["id_user"]] = data
                except (json.JSONDecodeError, KeyError):
                    print(f"[ERROR] Erreur de lecture du fichier {user_path}")
        print("[INFO] Utilisateurs chargés.")
        return users

    def load_options(self):
        try:
            with open('data/opt.json') as f:
                return json.load(f)
        except FileNotFoundError:
            print("[ERROR] opt.json file not found! Creating an empty options list.")
            return {}
        except json.JSONDecodeError:
            print("[ERROR] Failed to parse opt.json! Check the file format.")
            return {}

    def reset_request_counts(self):
        while self.running:
            time.sleep(5)
            with self.lock:
                self.request_counts.clear()

    def create_user(self, name, id_user, mdp, status, file_profil=None):
        user_dir = f'data/user/{id_user}'
        os.makedirs(user_dir, exist_ok=True)

        with open(f'{user_dir}/user.json', 'w') as f:
            json.dump({'name': name, 'id_user': id_user, 'mdp': mdp, 'status': status, 'points': 0, 'xp': 0}, f)

        profile_path = f'{user_dir}/profil_photo.png'
        if file_profil is None:
            with open("profil_default.png", "rb") as src, open(profile_path, "wb") as dest:
                dest.write(src.read())
        else:
            with open(profile_path, "wb") as dest:
                dest.write(file_profil)

        with open(f"{user_dir}/logs.json", "w") as f:
            json.dump(["CREATION : " + time.strftime("%Y-%m-%d %H:%M:%S")], f)

    def authenticate(self, id_user, password):
        return id_user in self.users and self.users[id_user]['mdp'] == password

    def handle_request(self, request, ip):
        print(f"[REQUEST] From {ip}: {request.strip()}")

        if ip in self.banned_ips:
            return "IP banned."

        try:
            cmd, *args = request.strip().split()
        except ValueError:
            return "Invalid request format."

        if cmd == "GET-USER-DATA":
            id_user, password = args
            if self.authenticate(id_user, password):
                return json.dumps(self.users[id_user])
            return "Invalid username or password."

        if cmd == "GET-PROFIL-PHOTO":
            id_user, password = args
            if self.authenticate(id_user, password):
                return self.send_file(f"data/user/{id_user}/profil_photo.png", ip)
            return "Invalid username or password."

        if cmd == "GET-USER-POINTS":
            id_user, password, target_user = args
            if self.authenticate(id_user, password):
                return str(self.users[target_user]['points'])
            return "Invalid username or password."

        if cmd == "GET-USER-LIST":
            id_user, password = args
            if self.authenticate(id_user, password):
                return "//".join(self.users.keys())
            return "Invalid username or password."

        if cmd == "GET-OPTIONS":
            option = args[0]
            return self.options[option]

        return "Invalid request."

    def accept_clients(self):
        while self.running:
            try:
                client, addr = self.server.accept()
                ip = addr[0]

                if ip in self.banned_ips:
                    client.send(b'Your IP is banned.\n')
                    client.close()
                    continue

                if len(self.clients) >= self.max_connections:
                    print("[WARNING] Server full! Rejecting connection.")
                    client.send(b'Server full.\n')
                    client.close()
                    continue

                self.clients[ip] = client
                threading.Thread(target=self.handle_client, args=(client, ip), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Error accepting clients: {e}")
                break

    def handle_client(self, client, ip):
        if ip in self.banned_ips and time.time() - self.banned_ips[ip] < self.ban_time:
            print(f"[WARNING] Banned IP {ip} attempted to connect.")
            client.send(b'You are banned.\n')
            client.close()
            return

        print(f"[INFO] Client {ip} connected.")

        while self.running:
            try:
                data = client.recv(4096).decode()
                if not data:
                    break

                with self.lock:
                    self.request_counts[ip] += 1
                    if self.request_counts[ip] > self.rate_limit:
                        self.banned_ips[ip] = time.time()
                        print(f"[SECURITY] Banned {ip} for exceeding request limit.")
                        break

                response : str = self.handle_request(data, ip) + "\n"
                client.send(response.encode())
            except Exception as e:
                print(f"[ERROR] Error handling client {ip}: {e}")
                break

        client.close()
        if ip in self.clients:
            del self.clients[ip]
        print(f"[INFO] Client {ip} disconnected.")

    def stop(self):
        print("[INFO] Stopping server...")
        self.running = False

        with self.lock:
            for ip, client in self.clients.items():
                try:
                    client.send(b"SERVER STOP\n")
                    client.close()
                except Exception as e:
                    print(f"[ERROR] Impossible d'envoyer le message à {ip}: {e}")

        self.server.close()
        print("[INFO] Server stopped.")


if __name__ == "__main__":
    server = Server()
    threading.Thread(target=server.accept_clients, daemon=True).start()

    input("Press ENTER to stop the server...\n")
    server.stop()
