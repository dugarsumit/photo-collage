"""Cluster near-duplicate photos via CLIP embeddings and keep the best of each cluster."""

import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import open_clip
import torch
from PIL import Image, ImageOps

SIMILARITY_THRESHOLD = 0.92  # cosine similarity above which two photos count as "near-duplicate"
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"


def load_model():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    model.eval().to(device)
    return model, preprocess, device


def embed_images(paths, model, preprocess, device):
    embeddings = []
    with torch.no_grad():
        for p in paths:
            img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            tensor = preprocess(img).unsqueeze(0).to(device)
            feat = model.encode_image(tensor)
            feat /= feat.norm(dim=-1, keepdim=True)
            embeddings.append(feat.cpu().numpy()[0])
    return np.stack(embeddings)


def sharpness_score(path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return cv2.Laplacian(img, cv2.CV_64F).var()


def quality_score(path):
    with Image.open(path) as img:
        w, h = img.size
    megapixels = (w * h) / 1_000_000
    blur = sharpness_score(path)
    # Normalize blur roughly to a comparable scale with megapixels; sharpness dominates
    # since a blurry 12MP shot is worse than a sharp 8MP one.
    return blur, megapixels


def cluster_by_similarity(paths, sim_matrix, threshold):
    n = len(paths)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                union(i, j)

    clusters = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)
    return list(clusters.values())


def run(input_dir: Path, output_csv: Path):
    paths = sorted(
        p for p in input_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic"}
    )
    if not paths:
        print(f"No images found in {input_dir}")
        return

    print(f"Loading CLIP model ({MODEL_NAME}/{PRETRAINED})...")
    model, preprocess, device = load_model()

    print(f"Embedding {len(paths)} images on {device}...")
    embeddings = embed_images(paths, model, preprocess, device)
    sim_matrix = embeddings @ embeddings.T

    clusters = cluster_by_similarity(paths, sim_matrix, SIMILARITY_THRESHOLD)
    print(f"Found {len(clusters)} cluster(s) from {len(paths)} photos "
          f"({len(paths) - len(clusters)} near-duplicate(s) to drop)")

    rows = []
    for cluster_id, idxs in enumerate(clusters):
        scored = [(i, *quality_score(paths[i])) for i in idxs]
        # pick highest sharpness; break ties with resolution
        best_i = max(scored, key=lambda t: (t[1], t[2]))[0]
        for i, blur, mp in scored:
            rows.append({
                "filename": paths[i].name,
                "cluster_id": cluster_id,
                "cluster_size": len(idxs),
                "sharpness": round(blur, 1),
                "megapixels": round(mp, 2),
                "kept": i == best_i,
            })
        if len(idxs) > 1:
            kept_name = paths[best_i].name
            dropped = [paths[i].name for i in idxs if i != best_i]
            print(f"  cluster {cluster_id}: kept {kept_name!r}, dropped {dropped}")

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    kept_count = sum(1 for r in rows if r["kept"])
    print(f"Wrote {output_csv} — {kept_count}/{len(rows)} photos kept")


if __name__ == "__main__":
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pics")
    output_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/dedup.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    run(input_dir, output_csv)
