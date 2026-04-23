import argparse
import math
import os
import shutil
from pathlib import Path

from PIL import Image


FACES = ["b", "d", "f", "l", "r", "u"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Retile Marzipano cube tiles from 512px tiles to 1024px tiles by stitching existing 512 tiles."
    )
    p.add_argument("--src", default="tiles", help="Source tiles directory (default: tiles)")
    p.add_argument("--dst", default="tiles1024", help="Destination tiles directory (default: tiles1024)")
    p.add_argument(
        "--tile-in",
        type=int,
        default=512,
        help="Input tile size in pixels (default: 512)",
    )
    p.add_argument(
        "--tile-out",
        type=int,
        default=1024,
        help="Output tile size in pixels (default: 1024)",
    )
    p.add_argument(
        "--levels",
        default="2,3",
        help="Comma-separated z levels to retile (default: 2,3). Level 1 is copied as-is.",
    )
    p.add_argument("--quality", type=int, default=85, help="JPEG quality for output tiles (default: 85)")
    p.add_argument("--overwrite", action="store_true", help="Overwrite destination if it exists")
    return p.parse_args()


def load_jpg(path: Path) -> Image.Image | None:
    if not path.exists():
        return None
    try:
        img = Image.open(path)
        img.load()
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except Exception:
        return None


def save_jpg(img: Image.Image, path: Path, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=quality, optimize=True)


def retile_level(scene_src: Path, scene_dst: Path, z: str, tile_in: int, tile_out: int, quality: int) -> None:
    if tile_out % tile_in != 0:
        raise ValueError(f"tile-out ({tile_out}) must be a multiple of tile-in ({tile_in})")

    factor = tile_out // tile_in  # e.g. 1024/512 = 2

    for face in FACES:
        face_src = scene_src / z / face
        if not face_src.exists():
            continue

        y_dirs = sorted([p for p in face_src.iterdir() if p.is_dir() and p.name.isdigit()], key=lambda p: int(p.name))
        if not y_dirs:
            continue

        y_max = max(int(p.name) for p in y_dirs)
        n_in = y_max + 1
        n_out = math.ceil(n_in / factor)

        for oy in range(n_out):
            for ox in range(n_out):
                out_img = Image.new("RGB", (tile_out, tile_out), (0, 0, 0))
                any_pasted = False

                for dy in range(factor):
                    for dx in range(factor):
                        iy = oy * factor + dy
                        ix = ox * factor + dx
                        in_path = scene_src / z / face / str(iy) / f"{ix}.jpg"
                        tile = load_jpg(in_path)
                        if tile is None:
                            continue
                        if tile.size != (tile_in, tile_in):
                            tile = tile.resize((tile_in, tile_in), Image.Resampling.BICUBIC)
                        out_img.paste(tile, (dx * tile_in, dy * tile_in))
                        any_pasted = True

                if not any_pasted:
                    continue

                out_path = scene_dst / z / face / str(oy) / f"{ox}.jpg"
                save_jpg(out_img, out_path, quality=quality)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, dst / rel / f)


def main() -> int:
    args = parse_args()
    src = Path(args.src)
    dst = Path(args.dst)

    if not src.exists():
        raise SystemExit(f"Source directory not found: {src}")

    if dst.exists():
        if args.overwrite:
            shutil.rmtree(dst)
        else:
            raise SystemExit(f"Destination already exists: {dst} (use --overwrite)")

    levels = [s.strip() for s in str(args.levels).split(",") if s.strip()]
    if not levels:
        raise SystemExit("--levels is empty")

    scenes = sorted([p for p in src.iterdir() if p.is_dir()])
    if not scenes:
        raise SystemExit(f"No scene folders found in {src}")

    for scene_src in scenes:
        scene_dst = dst / scene_src.name
        scene_dst.mkdir(parents=True, exist_ok=True)

        # Copy preview.jpg if present
        prev = scene_src / "preview.jpg"
        if prev.exists():
            shutil.copy2(prev, scene_dst / "preview.jpg")

        # Copy level 1 as-is (usually size 512, single tile)
        if (scene_src / "1").exists():
            copy_tree(scene_src / "1", scene_dst / "1")

        # Retile specified levels
        for z in levels:
            if not (scene_src / z).exists():
                continue
            retile_level(scene_src, scene_dst, z, args.tile_in, args.tile_out, args.quality)

    print(f"Done. Wrote: {dst}")
    print("Next: open viewer.html?tiles=1024 after updating viewer.html to use tiles1024 + 1024 tileSize for larger levels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

