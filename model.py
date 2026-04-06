import pandas as pd
import numpy as np
import ast, json, os
from sklearn.metrics.pairwise import cosine_similarity

# ─── Configuración ────────────────────────────────────────────────────
CSV_METADATA  = os.path.join(os.path.dirname(__file__), "movies_metadata.csv")
CSV_RATINGS   = os.path.join(os.path.dirname(__file__), "ratings_small.csv")
JSON_MEMBERS  = os.path.join(os.path.dirname(__file__), "members_data.json")
TOP_N         = 10
TOP_SIMILARES = 5

GENEROS_VALIDOS = {
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "Foreign",
    "History", "Horror", "Music", "Mystery", "Romance",
    "Science Fiction", "TV Movie", "Thriller", "War", "Western"
}
GENEROS_LISTA = sorted(GENEROS_VALIDOS)
PESO_DECLARADO = 1.0
PESO_INFERIDO  = 0.5

# ─── Estado global (se carga una sola vez) ───────────────────────────
_modelo_cargado  = False
_R_real          = None
_Q               = None
_user_genre_matrix = None
_id_titulo       = {}
_poster_path_map = {}   # movie_id → poster_path

def _cargar_modelo():
    global _modelo_cargado, _R_real, _Q, _user_genre_matrix, _id_titulo, _poster_path_map

    if _modelo_cargado:
        return

    print("[Recomendador] Cargando modelo...")

    # 1. Metadata
    df_meta = pd.read_csv(CSV_METADATA, low_memory=False)
    df_meta["id_num"] = pd.to_numeric(df_meta["id"], errors="coerce")
    df_meta = df_meta.dropna(subset=["id_num"])
    df_meta["id_num"] = df_meta["id_num"].astype(int)

    def filtrar_genres(valor):
        try:
            return [g["name"] for g in ast.literal_eval(valor) if g["name"] in GENEROS_VALIDOS]
        except Exception:
            return []

    df_meta["genres_clean"] = df_meta["genres"].apply(filtrar_genres)
    df_meta = df_meta[df_meta["genres_clean"].apply(len) > 0]
    _id_titulo       = dict(zip(df_meta["id_num"], df_meta["title"]))
    _poster_path_map = dict(zip(df_meta["id_num"], df_meta["poster_path"].fillna("")))

    # 2. Ratings + join
    df_ratings = pd.read_csv(CSV_RATINGS)
    df_merged  = df_ratings.merge(
        df_meta[["id_num", "genres_clean"]],
        left_on="movieId", right_on="id_num", how="inner"
    )

    # 3. Matriz R real
    _R_real = df_merged.pivot_table(index="userId", columns="movieId", values="rating")

    # 4. Matriz Q
    movie_ids       = _R_real.columns.tolist()
    peliculas_unicas = df_merged[["movieId","genres_clean"]].drop_duplicates("movieId")
    _Q = pd.DataFrame(0, index=movie_ids, columns=GENEROS_LISTA)
    for _, row in peliculas_unicas.iterrows():
        for g in row["genres_clean"]:
            if g in _Q.columns:
                _Q.loc[row["movieId"], g] = 1

    # 5. Vector de géneros por usuario (basado en sus ratings reales)
    _user_genre_matrix = pd.DataFrame(0.0, index=_R_real.index, columns=GENEROS_LISTA)
    for user_id in _R_real.index:
        rated = _R_real.loc[user_id].dropna()
        for movie_id, rating in rated.items():
            if movie_id in _Q.index:
                _user_genre_matrix.loc[user_id] += _Q.loc[movie_id].values * rating
        n = len(rated)
        if n > 0:
            _user_genre_matrix.loc[user_id] /= n

    _modelo_cargado = True
    print("[Recomendador] Modelo listo.")


def obtener_recomendaciones(member):
    """
    Recibe un dict de perfil con 'genres' y 'genres_inferidos'.
    Devuelve lista de dicts: [{"title": ..., "poster_path": ..., "score": ...}, ...]
    """
    _cargar_modelo()

    # Construir vector P del perfil
    p_vec = np.zeros(len(GENEROS_LISTA))
    for g in member.get("genres", []):
        if g in GENEROS_LISTA:
            p_vec[GENEROS_LISTA.index(g)] = PESO_DECLARADO
    for g in member.get("genres_inferidos", []):
        if g in GENEROS_LISTA:
            idx = GENEROS_LISTA.index(g)
            if p_vec[idx] < PESO_INFERIDO:
                p_vec[idx] = PESO_INFERIDO

    # Similitud coseno contra todos los usuarios de ratings_small
    similitudes   = cosine_similarity(p_vec.reshape(1, -1), _user_genre_matrix.values)[0]
    sim_series    = pd.Series(similitudes, index=_R_real.index).sort_values(ascending=False)
    top_similares = sim_series.head(TOP_SIMILARES)

    # Recopilar películas bien calificadas por usuarios similares
    candidatas = {}
    for user_id, sim_score in top_similares.items():
        rated = _R_real.loc[user_id].dropna()
        buenas = rated[rated >= 3.5]
        for movie_id, rating in buenas.items():
            if movie_id not in candidatas:
                candidatas[movie_id] = []
            candidatas[movie_id].append(rating * sim_score)

    # Score final y ordenar
    scores = {mid: float(np.mean(v)) for mid, v in candidatas.items()}
    top_ids = sorted(scores, key=scores.get, reverse=True)[:TOP_N]

    return [
        {
            "title":       _id_titulo.get(mid, f"ID {mid}"),
            "poster_path": _poster_path_map.get(mid, ""),
            "score":       round(scores[mid], 2),
            "movie_id":    mid,
        }
        for mid in top_ids
    ]


# ─── Modo standalone (python "sistema de recomendacion.py") ──────────
if __name__ == "__main__":
    _cargar_modelo()

    if not os.path.exists(JSON_MEMBERS):
        print("⚠️  members_data.json no encontrado.")
    else:
        with open(JSON_MEMBERS, "r", encoding="utf-8") as f:
            members = json.load(f)

        for member in members:
            recomendaciones = obtener_recomendaciones(member)
            print(f"\n👤 {member['name']}")
            print(f"   Géneros declarados : {', '.join(member.get('genres', []))}")
            print(f"   Géneros inferidos  : {', '.join(member.get('genres_inferidos', []))}")
            print(f"   Top {TOP_N} recomendaciones:")
            for r in recomendaciones:
                print(f"      • {r['title']:<45} score: {r['score']}")