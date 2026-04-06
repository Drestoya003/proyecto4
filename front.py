import tkinter as tk
from tkinter import ttk, messagebox
import json, os, ast, random, threading, urllib.request, io
from PIL import Image, ImageTk, ImageDraw
import pandas as pd

# ─── Importar sistema de recomendación ───────────────────────────────
import importlib.util, sys

def _importar_recomendador():
    ruta = os.path.join(os.path.dirname(__file__), "model.py")
    if not os.path.exists(ruta):
        return None
    spec   = importlib.util.spec_from_file_location("recomendador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo

recomendador = _importar_recomendador()

# ─── CSV de películas ─────────────────────────────────────────────────
CSV_PATH  = os.path.join(os.path.dirname(__file__), "movies_metadata.csv")
TMDB_BASE = "https://image.tmdb.org/t/p/w342"

def cargar_peliculas():
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
        GENEROS_SET = {
            "Action","Adventure","Animation","Comedy","Crime",
            "Documentary","Drama","Family","Fantasy","Foreign",
            "History","Horror","Music","Mystery","Romance",
            "Science Fiction","TV Movie","Thriller","War","Western"
        }
        def filtrar(v):
            try:
                return [g["name"] for g in ast.literal_eval(v) if g["name"] in GENEROS_SET]
            except Exception:
                return []
        df["genres_clean"] = df["genres"].apply(filtrar)
        df = df[df["genres_clean"].apply(len) > 0].copy()
        return df[["title","poster_path","genres_clean"]].reset_index(drop=True)
    except Exception as e:
        print(f"[CSV] Error: {e}")
        return None

DF_MOVIES = cargar_peliculas()

# ─── Paleta de colores ────────────────────────────────────────────────
BG_MAIN      = "#F0F2F7"
BG_CARD      = "#FFFFFF"
BG_HEADER    = "#FFFFFF"
TEXT_TITLE   = "#1A2B4A"
TEXT_NAME    = "#1A56A0"
TEXT_BODY    = "#555E6D"
TEXT_META    = "#8A93A3"
ACCENT_BLUE  = "#1A56A0"
BADGE_ACTIVE = ("#D1FAE5", "#065F46")
BADGE_PEND   = ("#FEF3C7", "#92400E")
BADGE_INACT  = ("#F3F4F6", "#6B7280")
SHADOW       = "#E2E5EC"
SEARCH_BG    = "#FFFFFF"

FONT_TITLE   = ("Georgia", 26, "bold")
FONT_SUBTITLE= ("Helvetica", 10)
FONT_NAME    = ("Helvetica", 14, "bold")
FONT_DESC    = ("Helvetica", 10)
FONT_META    = ("Helvetica", 9)
FONT_BADGE   = ("Helvetica", 8, "bold")
FONT_SEARCH  = ("Helvetica", 11)
FONT_BTN     = ("Helvetica", 12, "bold")

COLS   = 3
CARD_W = 280
CARD_H = 230

# ─── Datos ────────────────────────────────────────────────────────────
DEFAULT_MEMBERS = [
    {"name": "Elena Rostova",  "role": "Lead architectural designer specializing in modular structural systems and sustainable urban development.", "meta": "📍 Stockholm, SE",   "status": "ACTIVE"},
    {"name": "Marcus Chen",    "role": "Interaction specialist focusing on the intersection of human psychology and digital interfaces.",             "meta": "✉ m.chen@atelier.io","status": "PENDING"},
    {"name": "Sarah Jenkins",  "role": "Senior visual storyteller crafting narrative-driven brand identities for global technology startups.",        "meta": "🎨 Brand Strategy",  "status": "ACTIVE"},
    {"name": "David Thorne",   "role": "Data visualization engineer bridging the gap between complex analytics and intuitive design.",               "meta": "📍 Berlin, DE",      "status": "ACTIVE"},
    {"name": "Aiko Tanaka",    "role": "UX researcher uncovering deep behavioral patterns to shape next-generation product experiences.",            "meta": "📍 Tokyo, JP",       "status": "INACTIVE"},
    {"name": "Lucas Ferreira", "role": "Full-stack developer crafting scalable cloud-native architectures for high-growth startups.",                "meta": "✉ l.ferreira@dev.io","status": "ACTIVE"},
]

DATA_FILE = os.path.join(os.path.dirname(__file__), "members_data.json")

def load_members():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_MEMBERS[:]

def save_members(members):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)

# ─── Helpers de imagen ────────────────────────────────────────────────
AVATAR_COLORS = [
    ("#4F46E5","#FFFFFF"),("#0891B2","#FFFFFF"),("#059669","#FFFFFF"),
    ("#D97706","#FFFFFF"),("#DC2626","#FFFFFF"),("#7C3AED","#FFFFFF"),
    ("#DB2777","#FFFFFF"),("#0284C7","#FFFFFF"),
]

def make_avatar(name, size=64):
    idx    = sum(ord(c) for c in name) % len(AVATAR_COLORS)
    bg, fg = AVATAR_COLORS[idx]
    img    = Image.new("RGBA", (size, size), (0,0,0,0))
    draw   = ImageDraw.Draw(img)
    draw.ellipse([0,0,size-1,size-1], fill=bg)
    initials = "".join(p[0].upper() for p in name.split()[:2])
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size//3)
        bbox = draw.textbbox((0,0), initials, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    except Exception:
        font, tw, th = None, size//3, size//3
    draw.text(((size-tw)//2,(size-th)//2-2), initials, fill=fg, font=font)
    return ImageTk.PhotoImage(img)

GENEROS_VALIDOS = sorted([
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Foreign",
    "History", "Horror", "Music", "Mystery", "Romance",
    "Science Fiction", "TV Movie", "Thriller", "War", "Western"
])

# ─── Diálogo agregar/editar ───────────────────────────────────────────
class MemberDialog(tk.Toplevel):
    def __init__(self, parent, member=None):
        super().__init__(parent)
        self.result = None
        self.title("Nuevo Miembro" if member is None else "Editar Miembro")
        self.resizable(False, False)
        self.configure(bg=BG_CARD)
        self.grab_set()
        pad = {"padx":16,"pady":6}

        tk.Label(self, text="Nombre completo", bg=BG_CARD, fg=TEXT_BODY, font=FONT_META
                 ).grid(row=0, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar(value=member["name"] if member else "")
        tk.Entry(self, textvariable=self.name_var, font=FONT_DESC, width=36,
                 relief="solid", bd=1).grid(row=1, column=0, **pad)

        tk.Label(self, text="Escoger géneros (máximo 3)", bg=BG_CARD, fg=TEXT_BODY, font=FONT_META
                 ).grid(row=2, column=0, sticky="w", **pad)

        # Contenedor con grid de checkboxes (4 columnas)
        genres_frame = tk.Frame(self, bg=BG_CARD)
        genres_frame.grid(row=3, column=0, **pad, sticky="w")

        selected_genres  = set(member.get("genres", []) if member else [])
        self.genre_vars  = {}
        self.genre_count = tk.IntVar(value=len(selected_genres))
        self.genre_lbl   = tk.Label(self, text=f"{len(selected_genres)} / 3 seleccionados",
                                    bg=BG_CARD, fg=TEXT_META, font=FONT_META)
        self.genre_lbl.grid(row=2, column=0, sticky="e", padx=16)

        def on_toggle(genre, var):
            if var.get():
                if self.genre_count.get() >= 3:
                    var.set(False)   # revertir
                    return
                self.genre_count.set(self.genre_count.get() + 1)
            else:
                self.genre_count.set(self.genre_count.get() - 1)
            self.genre_lbl.config(text=f"{self.genre_count.get()} / 3 seleccionados")

        for i, genre in enumerate(GENEROS_VALIDOS):
            var = tk.BooleanVar(value=genre in selected_genres)
            self.genre_vars[genre] = var
            tk.Checkbutton(genres_frame, text=genre, variable=var,
                           bg=BG_CARD, fg=TEXT_BODY, font=FONT_META,
                           activebackground=BG_CARD, selectcolor=BG_CARD,
                           cursor="hand2",
                           command=lambda g=genre, v=var: on_toggle(g, v)
                           ).grid(row=i//4, column=i%4, sticky="w", padx=4, pady=2)

        tk.Label(self, text="Info adicional (ciudad, email, etc.)", bg=BG_CARD,
                 fg=TEXT_BODY, font=FONT_META).grid(row=4, column=0, sticky="w", **pad)
        self.meta_var = tk.StringVar(value=member.get("meta","") if member else "")
        tk.Entry(self, textvariable=self.meta_var, font=FONT_DESC, width=36,
                 relief="solid", bd=1).grid(row=5, column=0, **pad)

        bf = tk.Frame(self, bg=BG_CARD)
        bf.grid(row=6, column=0, pady=12)
        tk.Button(bf, text="Cancelar", command=self.destroy,
                  bg=SHADOW, fg=TEXT_BODY, font=FONT_META,
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=8)
        tk.Button(bf, text="Guardar", command=self._save,
                  bg=ACCENT_BLUE, fg="white", font=FONT_META,
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=8)

        self.update_idletasks()
        x = parent.winfo_x()+(parent.winfo_width()-self.winfo_width())//2
        y = parent.winfo_y()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Campo requerido","El nombre es obligatorio.",parent=self)
            return
        genres_seleccionados = [g for g, var in self.genre_vars.items() if var.get()]
        self._datos_base = {"name": name,
                            "genres": genres_seleccionados,
                            "meta": self.meta_var.get().strip()}
        self.withdraw()   # ocultamos el formulario
        picker = MoviePickerDialog(self, genres_seleccionados, self._on_picker_done)
        self.wait_window(picker)

    def _on_picker_done(self, peliculas_elegidas):
        # Géneros que el usuario eligió manualmente
        genres_perfil = set(self._datos_base["genres"])

        # Géneros de las películas seleccionadas
        genres_peliculas = set()
        for titulo, datos in peliculas_elegidas.items() if isinstance(peliculas_elegidas, dict) else []:
            for g in datos.get("genres_clean", []):
                genres_peliculas.add(g)

        # Géneros nuevos inferidos de las películas (sin los que ya eligió)
        genres_inferidos = sorted(genres_peliculas - genres_perfil)

        self.result = self._datos_base
        self.result["favorite_movies"]   = list(peliculas_elegidas.keys()) if isinstance(peliculas_elegidas, dict) else peliculas_elegidas
        self.result["genres_inferidos"]  = genres_inferidos
        self.destroy()

# ─── Selector de películas favoritas ─────────────────────────────────
class MoviePickerDialog(tk.Toplevel):
    MAX_SEL   = 5
    POSTER_W  = 130
    POSTER_H  = 195

    def __init__(self, parent, genres, on_done):
        super().__init__(parent)
        self.on_done   = on_done
        self.genres    = genres
        self.selected  = {}   # title → datos
        self._img_refs = []
        self.title("Elige tus 5 películas favoritas")
        self.geometry("900x580")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)
        self.grab_set()

        # Centrar
        self.update_idletasks()
        rx = parent.winfo_x() + (parent.winfo_width()  - 900) // 2
        ry = parent.winfo_y() + (parent.winfo_height() - 580) // 2
        self.geometry(f"900x580+{rx}+{ry}")

        # Películas filtradas por géneros elegidos (muestra 10 al azar)
        self.peliculas = self._get_peliculas(genres)

        self._build()

    def _get_peliculas(self, genres):
        if DF_MOVIES is None or len(DF_MOVIES) == 0:
            return []
        mask     = DF_MOVIES["genres_clean"].apply(
            lambda gs: any(g in gs for g in genres))
        coinciden = DF_MOVIES[mask]
        sample    = coinciden.sample(min(10, len(coinciden)), random_state=None)
        return sample.to_dict("records")

    def _build(self):
        # ── Header ──
        header = tk.Frame(self, bg=BG_HEADER, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="Escoge hasta 5 películas que te gusten",
                 bg=BG_HEADER, fg=TEXT_TITLE, font=FONT_NAME).pack(side="left", padx=24)

        # Botón "Ver otras" en esquina superior derecha
        tk.Button(header, text="🔀  Ver otras", command=self._refresh,
                  bg=SHADOW, fg=TEXT_BODY, font=FONT_META,
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="right", padx=12)

        self.counter_lbl = tk.Label(header, text="0 / 5 seleccionadas",
                                    bg=BG_HEADER, fg=TEXT_META, font=FONT_META)
        self.counter_lbl.pack(side="right", padx=8)

        tk.Frame(self, bg=SHADOW, height=1).pack(fill="x")

        # ── Grid de pósters (contenedor fijo) ──
        canvas = tk.Canvas(self, bg=BG_MAIN, highlightthickness=0)
        sb     = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self.grid_f = tk.Frame(canvas, bg=BG_MAIN)
        win = canvas.create_window((0,0), window=self.grid_f, anchor="nw")
        self.grid_f.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Renderizar pósters iniciales
        self._render_posters()

        # ── Footer ──
        footer = tk.Frame(self, bg=BG_HEADER, pady=10)
        footer.pack(fill="x", side="bottom")
        tk.Frame(self, bg=SHADOW, height=1).pack(fill="x", side="bottom")
        tk.Button(footer, text="Confirmar selección", command=self._confirm,
                  bg=ACCENT_BLUE, fg="white", font=FONT_BTN,
                  relief="flat", padx=20, pady=8, cursor="hand2").pack(side="right", padx=24)
        tk.Button(footer, text="Omitir", command=lambda: self.on_done({}),
                  bg=SHADOW, fg=TEXT_BODY, font=FONT_META,
                  relief="flat", padx=14, pady=8, cursor="hand2").pack(side="right", padx=8)

    def _render_posters(self):
        """Limpia el grid y renderiza las películas actuales."""
        for w in self.grid_f.winfo_children():
            w.destroy()
        self._img_refs = []
        for i, pelicula in enumerate(self.peliculas):
            self._make_poster_card(self.grid_f, pelicula, i)

    def _refresh(self):
        """Carga 10 películas distintas al azar manteniendo las ya seleccionadas."""
        self.peliculas = self._get_peliculas(self.genres)
        self._render_posters()

    def _make_poster_card(self, parent, pelicula, idx):
        col = idx % 5
        row = idx // 5

        frame = tk.Frame(parent, bg=BG_CARD,
                         highlightbackground=SHADOW, highlightthickness=2,
                         cursor="hand2", width=self.POSTER_W+8, height=self.POSTER_H+40)
        frame.grid(row=row, column=col, padx=10, pady=12)
        frame.grid_propagate(False)

        # Placeholder mientras carga
        ph = Image.new("RGB", (self.POSTER_W, self.POSTER_H), "#D1D5DB")
        ph_draw = ImageDraw.Draw(ph)
        ph_draw.text((10,80), "Cargando...", fill="#9CA3AF")
        ph_photo = ImageTk.PhotoImage(ph)
        self._img_refs.append(ph_photo)

        img_lbl = tk.Label(frame, image=ph_photo, bg=BG_CARD)
        img_lbl.place(x=4, y=4)

        title_lbl = tk.Label(frame, text=pelicula["title"], bg=BG_CARD,
                             fg=TEXT_BODY, font=("Helvetica",8),
                             wraplength=self.POSTER_W, justify="center")
        title_lbl.place(x=4, y=self.POSTER_H+6, width=self.POSTER_W)

        # Overlay de selección
        overlay = tk.Label(frame, text="✓", bg="#1A56A0", fg="white",
                           font=("Helvetica",28,"bold"))

        def toggle(e, t=pelicula["title"], f=frame, o=overlay):
            if t in self.selected:
                del self.selected[t]
                f.config(highlightbackground=SHADOW)
                o.place_forget()
            else:
                if len(self.selected) >= self.MAX_SEL:
                    messagebox.showinfo("Límite alcanzado",
                                        "Solo puedes elegir 5 películas.", parent=self)
                    return
                self.selected[t] = pelicula
                f.config(highlightbackground=ACCENT_BLUE)
                o.place(relx=0.5, rely=0.4, anchor="center")
            self.counter_lbl.config(text=f"{len(self.selected)} / 5 seleccionadas")

        for w in (frame, img_lbl, title_lbl):
            w.bind("<Button-1>", toggle)

        # Cargar poster desde CSV + TMDb
        poster_path = pelicula.get("poster_path", "")
        if poster_path and str(poster_path) != "nan":
            url = TMDB_BASE + str(poster_path)
            def load(u=url, lbl=img_lbl, title=pelicula["title"]):
                try:
                    req = urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = r.read()
                    img   = Image.open(io.BytesIO(data)).resize(
                                (self.POSTER_W, self.POSTER_H), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self._img_refs.append(photo)
                    if self.winfo_exists():
                        lbl.config(image=photo)
                except Exception:
                    if self.winfo_exists():
                        ph2 = Image.new("RGB",(self.POSTER_W,self.POSTER_H),"#374151")
                        d   = ImageDraw.Draw(ph2)
                        d.text((10,80), title[:30], fill="#E5E7EB")
                        p2  = ImageTk.PhotoImage(ph2)
                        self._img_refs.append(p2)
                        lbl.config(image=p2)
            threading.Thread(target=load, daemon=True).start()
        else:
            ph2 = Image.new("RGB",(self.POSTER_W,self.POSTER_H),"#374151")
            d   = ImageDraw.Draw(ph2)
            d.text((10,80), pelicula["title"][:30], fill="#E5E7EB")
            p2  = ImageTk.PhotoImage(ph2)
            self._img_refs.append(p2)
            img_lbl.config(image=p2)

    def _confirm(self):
        self.on_done(self.selected)   # dict completo: título → datos
        self.destroy()


# ─── Tarjeta ──────────────────────────────────────────────────────────
class MemberCard(tk.Frame):
    def __init__(self, parent, member, on_edit, on_delete, on_open, **kwargs):
        super().__init__(parent, bg=BG_CARD, relief="flat",
                         highlightbackground=SHADOW, highlightthickness=1, **kwargs)
        self.member      = member
        self._avatar_ref = None

        avatar_img = make_avatar(member["name"], size=60)
        self._avatar_ref = avatar_img
        av_lbl = tk.Label(self, image=avatar_img, bg=BG_CARD, cursor="hand2")
        av_lbl.place(x=16, y=16)

        name_lbl = tk.Label(self, text=member["name"], bg=BG_CARD, fg=TEXT_NAME,
                             font=FONT_NAME, cursor="hand2",
                             wraplength=CARD_W-24, justify="left")
        name_lbl.place(x=16, y=88)

        desc = tk.Label(self, text=", ".join(member.get("genres", [])), bg=BG_CARD, fg=TEXT_BODY,
                        font=FONT_DESC, wraplength=CARD_W-24, justify="left")
        desc.place(x=16, y=112)

        tk.Frame(self, bg=SHADOW, height=1).place(x=16, y=CARD_H-48, width=CARD_W-32)
        tk.Label(self, text=member.get("meta",""), bg=BG_CARD,
                 fg=TEXT_META, font=FONT_META).place(x=16, y=CARD_H-36)

        btn_del = tk.Label(self, text="✕", bg=BG_CARD, fg="#CBD5E0",
                           font=("Helvetica",13), cursor="hand2")
        btn_del.place(relx=1.0, x=-12, rely=1.0, y=-12, anchor="se")
        btn_del.bind("<Button-1>", lambda e: on_delete(member))
        btn_del.bind("<Enter>", lambda e: btn_del.config(fg="#DC2626"))
        btn_del.bind("<Leave>", lambda e: btn_del.config(fg="#CBD5E0"))

        btn_edit = tk.Label(self, text="✎", bg=BG_CARD, fg="#CBD5E0",
                            font=("Helvetica",13), cursor="hand2")
        btn_edit.place(relx=1.0, x=-32, rely=1.0, y=-12, anchor="se")
        btn_edit.bind("<Button-1>", lambda e: on_edit(member))
        btn_edit.bind("<Enter>", lambda e: btn_edit.config(fg=ACCENT_BLUE))
        btn_edit.bind("<Leave>", lambda e: btn_edit.config(fg="#CBD5E0"))

        for w in (self, av_lbl, name_lbl, desc):
            w.bind("<Button-1>", lambda e: on_open(member))
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, _):
        self.config(highlightbackground=ACCENT_BLUE)
    def _on_leave(self, _):
        self.config(highlightbackground=SHADOW)


# ─── Colores placeholder para las tarjetas de película ───────────────
MOVIE_COLORS = [
    "#1E3A5F", "#2D4A1E", "#4A1E2D", "#3D3000", "#1E2D4A",
    "#4A2D1E", "#1E4A3D", "#3D1E4A", "#4A3D1E", "#1E4A2D",
]

# ─── Ventana de detalle ───────────────────────────────────────────────
class DetailWindow(tk.Toplevel):
    W, H = 960, 620

    def __init__(self, parent, member):
        super().__init__(parent)
        self.title(member["name"])
        self.resizable(False, False)
        self.configure(bg="#12181F")
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()  - self.W) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.H) // 2
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self._build(member)

    def _build(self, member):
        self._img_refs = []
        BG = "#12181F"

        # ── Área scrollable ──
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb     = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        inner = tk.Frame(canvas, bg=BG)
        win   = canvas.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        # ── Sección: Películas favoritas ──
        favorite_titles = member.get("favorite_movies", [])
        self._favorites_row(inner, "🎬  Películas favoritas", favorite_titles)

        # ── Sección: Recomendadas para ti ──
        self._placeholder_row(inner, member)

    def _favorites_row(self, parent, section_title, titles):
        """Fila con los 5 pósters de las películas favoritas del miembro."""
        BG     = "#12181F"
        CARD_W = 160
        CARD_H = 240

        tk.Label(parent, text=section_title, bg=BG, fg="white",
                 font=("Helvetica", 13, "bold")).pack(
                 anchor="w", padx=24, pady=(28, 10))

        row_frame = tk.Frame(parent, bg=BG)
        row_frame.pack(anchor="w", padx=24)

        if not titles:
            tk.Label(row_frame, text="Este usuario no seleccionó películas favoritas.",
                     bg=BG, fg="#6B7280", font=("Helvetica", 10)).pack(pady=20)
            return

        for i, title in enumerate(titles[:5]):
            # Buscar datos de la película en el CSV
            pelicula = None
            if DF_MOVIES is not None:
                match = DF_MOVIES[DF_MOVIES["title"] == title]
                if len(match) > 0:
                    pelicula = match.iloc[0]

            card = tk.Frame(row_frame, bg="#1E2535", width=CARD_W, height=CARD_H,
                            highlightbackground="#2A3A4A", highlightthickness=1)
            card.grid(row=0, column=i, padx=8, pady=4)
            card.grid_propagate(False)

            ph = Image.new("RGB", (CARD_W, CARD_H-36), "#2D3748")
            ph_photo = ImageTk.PhotoImage(ph)
            self._img_refs.append(ph_photo)
            img_lbl = tk.Label(card, image=ph_photo, bg="#1E2535")
            img_lbl.place(x=0, y=0)

            tk.Label(card, text=title, bg="#1E2535", fg="#E2E8F0",
                     font=("Helvetica", 8), wraplength=CARD_W-8,
                     justify="center").place(x=4, y=CARD_H-34, width=CARD_W-8)

            # Cargar poster si existe
            poster_path = pelicula["poster_path"] if pelicula is not None else None
            if poster_path and str(poster_path) != "nan":
                url = TMDB_BASE + str(poster_path)
                def load_poster(u=url, lbl=img_lbl, t=title, cw=CARD_W, ch=CARD_H):
                    try:
                        req = urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=8) as r:
                            data = r.read()
                        img   = Image.open(io.BytesIO(data)).resize(
                                    (cw, ch-36), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self._img_refs.append(photo)
                        if self.winfo_exists():
                            lbl.config(image=photo)
                    except Exception:
                        self._sin_poster(lbl, t, cw, ch-36)
                threading.Thread(target=load_poster, daemon=True).start()
            else:
                self._sin_poster(img_lbl, title, CARD_W, CARD_H-36)

    def _sin_poster(self, lbl, title, w, h):
        """Muestra el título sobre fondo oscuro cuando no hay poster."""
        img  = Image.new("RGB", (w, h), "#374151")
        draw = ImageDraw.Draw(img)
        # Texto centrado línea a línea
        words, lines, line = title.split(), [], ""
        for word in words:
            if len(line + word) < 18:
                line += word + " "
            else:
                lines.append(line.strip())
                line = word + " "
        lines.append(line.strip())
        y = h//2 - len(lines)*8
        for l in lines:
            draw.text((w//2 - len(l)*3, y), l, fill="#E5E7EB")
            y += 18
        photo = ImageTk.PhotoImage(img)
        self._img_refs.append(photo)
        if self.winfo_exists():
            lbl.config(image=photo)

    def _placeholder_row(self, parent, member):
        """Fila de recomendaciones reales desde el sistema de recomendación."""
        BG     = "#12181F"
        CARD_W = 160
        CARD_H = 240

        tk.Label(parent, text="🎯  Recomendadas para ti", bg=BG, fg="white",
                 font=("Helvetica", 13, "bold")).pack(
                 anchor="w", padx=24, pady=(20, 10))

        outer    = tk.Frame(parent, bg=BG)
        outer.pack(fill="x", padx=24)
        h_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, height=CARD_H+20)
        h_sb     = ttk.Scrollbar(outer, orient="horizontal", command=h_canvas.xview)
        h_canvas.configure(xscrollcommand=h_sb.set)
        h_sb.pack(side="bottom", fill="x")
        h_canvas.pack(fill="x")

        row_frame = tk.Frame(h_canvas, bg=BG)
        h_canvas.create_window((0,0), window=row_frame, anchor="nw")
        row_frame.bind("<Configure>", lambda e: h_canvas.configure(
            scrollregion=h_canvas.bbox("all")))

        # Mostrar placeholders mientras carga
        placeholders = []
        for i in range(10):
            color = MOVIE_COLORS[i % len(MOVIE_COLORS)]
            card  = tk.Frame(row_frame, bg=color, width=CARD_W, height=CARD_H,
                             highlightbackground="#2A3A4A", highlightthickness=1)
            card.grid(row=0, column=i, padx=6, pady=6)
            card.grid_propagate(False)
            ph    = Image.new("RGB", (CARD_W, CARD_H-36), color)
            ph_ph = ImageTk.PhotoImage(ph)
            self._img_refs.append(ph_ph)
            img_lbl = tk.Label(card, image=ph_ph, bg=color)
            img_lbl.place(x=0, y=0)
            tk.Label(card, text="Cargando...", bg=color, fg="#CBD5E0",
                     font=("Helvetica", 8), wraplength=140).place(
                     relx=0.5, rely=0.85, anchor="center")
            placeholders.append((card, img_lbl))

        # Cargar recomendaciones en hilo separado
        def cargar():
            try:
                if recomendador is None:
                    return
                recomendaciones = recomendador.obtener_recomendaciones(member)
                if self.winfo_exists():
                    self.after(0, lambda: self._poblar_recomendaciones(
                        row_frame, placeholders, recomendaciones, CARD_W, CARD_H))
            except Exception as e:
                print(f"[Recomendador] Error: {e}")

        threading.Thread(target=cargar, daemon=True).start()

    def _poblar_recomendaciones(self, row_frame, placeholders, recomendaciones, CARD_W, CARD_H):
        """Rellena las tarjetas placeholder con las recomendaciones reales."""
        for i, rec in enumerate(recomendaciones[:10]):
            if i >= len(placeholders):
                break
            card, img_lbl = placeholders[i]

            # Actualizar título
            for w in card.winfo_children():
                if isinstance(w, tk.Label) and w.cget("text") == "Cargando...":
                    w.config(text=rec["title"])

            # Cambiar fondo a oscuro
            card.config(bg="#1E2535")
            img_lbl.config(bg="#1E2535")

            # Cargar poster
            poster_path = rec.get("poster_path", "")
            titulo      = rec["title"]
            if poster_path and str(poster_path) != "nan" and poster_path != "":
                url = TMDB_BASE + str(poster_path)
                def load(u=url, lbl=img_lbl, t=titulo, cw=CARD_W, ch=CARD_H):
                    try:
                        req = urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=8) as r:
                            data = r.read()
                        img   = Image.open(io.BytesIO(data)).resize((cw, ch-36), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self._img_refs.append(photo)
                        if self.winfo_exists():
                            lbl.config(image=photo, bg="#1E2535")
                    except Exception:
                        self._sin_poster(lbl, t, cw, ch-36)
                threading.Thread(target=load, daemon=True).start()
            else:
                self._sin_poster(img_lbl, titulo, CARD_W, CARD_H-36)


# ─── App principal ────────────────────────────────────────────────────
class MemberDirectoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Member Directory")
        self.geometry("1000x680")
        self.minsize(700, 500)
        self.configure(bg=BG_MAIN)
        self.members = load_members()
        self._build_ui()
        self._render_cards()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG_HEADER, pady=20)
        header.pack(fill="x")

        left = tk.Frame(header, bg=BG_HEADER)
        left.pack(side="left", padx=32)
        tk.Label(left, text="Member Directory", bg=BG_HEADER, fg=TEXT_TITLE,
                 font=FONT_TITLE).pack(anchor="w")
        tk.Label(left, text="Curating and managing the creative network with precision and clarity.",
                 bg=BG_HEADER, fg=TEXT_META, font=FONT_SUBTITLE).pack(anchor="w")

        right = tk.Frame(header, bg=BG_HEADER)
        right.pack(side="right", padx=32)

        sf = tk.Frame(right, bg=SEARCH_BG, highlightbackground=SHADOW, highlightthickness=1)
        sf.pack(side="left", padx=(0,12))
        tk.Label(sf, text="🔍", bg=SEARCH_BG, fg=TEXT_META,
                 font=("Helvetica",12)).pack(side="left", padx=(10,4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_cards())
        tk.Entry(sf, textvariable=self.search_var, font=FONT_SEARCH,
                 relief="flat", bg=SEARCH_BG, fg=TEXT_BODY, width=22,
                 insertbackground=ACCENT_BLUE).pack(side="left", pady=8, padx=(0,10))

        tk.Button(right, text="＋  Agregar", command=self._add_member,
                  bg=ACCENT_BLUE, fg="white", font=FONT_BTN,
                  relief="flat", padx=18, pady=8, cursor="hand2",
                  activebackground="#134080", activeforeground="white").pack(side="left")

        tk.Frame(self, bg=SHADOW, height=1).pack(fill="x")

        container = tk.Frame(self, bg=BG_MAIN)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = tk.Frame(self.canvas, bg=BG_MAIN)
        self.canvas_win = self.canvas.create_window((0,0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_win, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def _render_cards(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        query   = self.search_var.get().lower().strip()
        visible = [m for m in self.members
                   if query in m["name"].lower() or
                   any(query in g.lower() for g in m.get("genres", []))]
        for i, member in enumerate(visible):
            row, col = divmod(i, COLS)
            card = MemberCard(self.grid_frame, member,
                              on_edit=self._edit_member,
                              on_delete=self._delete_member,
                              on_open=self._open_detail,
                              width=CARD_W, height=CARD_H)
            card.grid(row=row, column=col, padx=16, pady=16, sticky="nw")
            card.grid_propagate(False)
        if not visible:
            msg = ("No hay perfiles aún.\nHaz clic en  ＋ Agregar  para crear el primero."
                   if not self.members else "Sin resultados para tu búsqueda 🔍")
            tk.Label(self.grid_frame, text=msg, bg=BG_MAIN, fg=TEXT_META,
                     font=("Helvetica",13), justify="center"
                     ).grid(row=0, column=0, columnspan=3, padx=40, pady=80)

    def _open_detail(self, member):
        DetailWindow(self, member)

    def _add_member(self):
        dlg = MemberDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.members.append(dlg.result)
            save_members(self.members)
            self._render_cards()

    def _edit_member(self, member):
        dlg = MemberDialog(self, member)
        self.wait_window(dlg)
        if dlg.result:
            self.members[self.members.index(member)] = dlg.result
            save_members(self.members)
            self._render_cards()

    def _delete_member(self, member):
        if messagebox.askyesno("Eliminar", f"¿Eliminar a {member['name']}?", parent=self):
            self.members.remove(member)
            save_members(self.members)
            self._render_cards()


if __name__ == "__main__":
    app = MemberDirectoryApp()
    app.mainloop()