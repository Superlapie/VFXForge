"""Deterministic software preview renderer used by the CLI and quality gate.

Godot remains the authoritative runtime renderer. This small Pillow renderer is
deliberately dependency-light and gives AI agents a stable PNG snapshot even
when a Godot binary is not installed on the authoring machine.
"""

from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .errors import ExportError
from .validation import estimate_metrics


def _color(value: Any, fallback: tuple[int, int, int, int] = (180, 140, 255, 255)) -> tuple[int, int, int, int]:
    if not isinstance(value, str):
        return fallback
    text = value.strip().lstrip("#")
    if len(text) == 6:
        text += "FF"
    if len(text) != 8:
        return fallback
    try:
        return tuple(int(text[index : index + 2], 16) for index in range(0, 8, 2))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _mix(first: tuple[int, int, int, int], second: tuple[int, int, int, int], amount: float) -> tuple[int, int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))  # type: ignore[return-value]


def _curve(value: Any, position: float, default: float = 1.0) -> float:
    if not isinstance(value, dict) or not isinstance(value.get("points"), list):
        return default
    points = value["points"]
    if not points:
        return 0.0
    normalized = max(0.0, min(1.0, position))
    parsed = [
        (float(point.get("x", 0.0)), float(point.get("y", 0.0)))
        for point in points
        if isinstance(point, dict) and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float))
    ]
    if not parsed:
        return default
    parsed.sort(key=lambda item: item[0])
    if normalized <= parsed[0][0]:
        return parsed[0][1]
    if normalized >= parsed[-1][0]:
        return parsed[-1][1]
    for (x0, y0), (x1, y1) in zip(parsed, parsed[1:]):
        if x0 <= normalized <= x1:
            ratio = 0.0 if x1 == x0 else (normalized - x0) / (x1 - x0)
            return y0 + (y1 - y0) * ratio
    return parsed[-1][1]


def _gradient(value: Any, position: float, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if not isinstance(value, list):
        return fallback
    stops = []
    for stop in value:
        if isinstance(stop, dict) and isinstance(stop.get("position"), (int, float)):
            stops.append((float(stop["position"]), _color(stop.get("color"), fallback)))
    if not stops:
        return fallback
    stops.sort(key=lambda item: item[0])
    normalized = max(0.0, min(1.0, position))
    if normalized <= stops[0][0]:
        return stops[0][1]
    if normalized >= stops[-1][0]:
        return stops[-1][1]
    for (x0, c0), (x1, c1) in zip(stops, stops[1:]):
        if x0 <= normalized <= x1:
            ratio = 0.0 if x1 == x0 else (normalized - x0) / (x1 - x0)
            return _mix(c0, c1, ratio)
    return stops[-1][1]


def _stable_seed(*parts: Any) -> int:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def _project(point: tuple[float, float, float], camera: str, width: int, height: int, scale: float = 70.0) -> tuple[float, float]:
    x, y, z = point
    if camera == "top":
        return width * 0.5 + x * scale, height * 0.52 + z * scale
    if camera == "side":
        return width * 0.5 + z * scale, height * 0.72 - y * scale
    if camera == "mmo":
        return width * 0.5 + (x - z) * scale * 0.7, height * 0.68 - y * scale + (x + z) * scale * 0.28
    return width * 0.5 + x * scale, height * 0.72 - y * scale - z * scale * 0.12


def _additive(base: Image.Image, overlay: Image.Image) -> Image.Image:
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    return ImageChops.add(base, overlay, scale=1.0, offset=0).convert("RGBA")


def _draw_glow(target: Image.Image, point: tuple[float, float], radius: float, color: tuple[int, int, int, int], strength: float = 1.0) -> None:
    width, height = target.size
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    r = max(1.0, radius)
    alpha = int(max(0, min(255, color[3] * strength)))
    draw.ellipse((point[0] - r, point[1] - r, point[0] + r, point[1] + r), fill=(color[0], color[1], color[2], alpha))
    target.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(1, int(r * 0.65)))))
    core = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core)
    core_draw.ellipse((point[0] - r * 0.35, point[1] - r * 0.35, point[0] + r * 0.35, point[1] + r * 0.35), fill=(color[0], color[1], color[2], alpha))
    target.alpha_composite(core)


def _layer_color(layer: dict[str, Any], position: float = 0.5) -> tuple[int, int, int, int]:
    properties = layer.get("properties", {})
    fallback = _color(properties.get("color"), _color(layer.get("material", {}).get("tint")))
    if isinstance(properties.get("color"), str) and properties.get("color"):
        gradient_color = _gradient(layer.get("gradient"), position, (255, 255, 255, fallback[3]))
        return (fallback[0], fallback[1], fallback[2], int(fallback[3] * gradient_color[3] / 255.0))
    return _gradient(layer.get("gradient"), position, fallback)


def _draw_grid(image: Image.Image, camera: str) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    horizon = int(height * 0.72)
    if camera == "top":
        for x in range(0, width, 40):
            draw.line((x, 0, x, height), fill=(90, 110, 140, 30), width=1)
        for y in range(0, height, 40):
            draw.line((0, y, width, y), fill=(90, 110, 140, 30), width=1)
    else:
        draw.line((0, horizon, width, horizon), fill=(110, 130, 160, 70), width=1)
        for offset in range(-8, 9):
            x = width * 0.5 + offset * 80
            draw.line((width * 0.5, horizon, x, height), fill=(90, 110, 140, 26), width=1)


def _draw_particle_layer(
    image: Image.Image,
    layer: dict[str, Any],
    effect_time: float,
    effect_seed: int,
    camera: str,
) -> None:
    props = layer.get("properties", {})
    start = float(layer.get("start", 0.0))
    duration = max(0.001, float(layer.get("duration", props.get("lifetime", 1.0))))
    local_time = effect_time - start
    if local_time < 0.0:
        return
    lifetime = max(0.001, float(props.get("lifetime", duration)))
    count = max(0, min(6000, int(props.get("amount", 0))))
    one_shot = bool(props.get("one_shot", True))
    shape = props.get("emission_shape", "point")
    gravity = props.get("gravity", [0.0, -2.0, 0.0])
    direction = props.get("direction", [0.0, 1.0, 0.0])
    spread = math.radians(float(props.get("spread", 35.0)))
    velocity_min = float(props.get("initial_velocity_min", 1.0))
    velocity_max = float(props.get("initial_velocity_max", 2.0))
    for index in range(count):
        rng = random.Random(_stable_seed(effect_seed, layer.get("id"), index))
        birth = rng.random() * lifetime if one_shot else (index / max(1, count)) * lifetime
        if not one_shot:
            birth = (birth + start) % lifetime
        age = local_time - birth
        if age < 0.0 or age > lifetime:
            continue
        normalized = age / lifetime
        theta = rng.random() * math.tau
        phi = rng.random() * math.pi
        if shape in {"sphere", "sphere_surface"}:
            radius = float(props.get("emission_radius", 0.5)) * (1.0 if shape == "sphere_surface" else rng.random() ** (1.0 / 3.0))
            origin = (math.cos(theta) * math.sin(phi) * radius, math.cos(phi) * radius, math.sin(theta) * math.sin(phi) * radius)
        elif shape == "ring":
            radius = float(props.get("emission_radius", 0.5))
            origin = (math.cos(theta) * radius, 0.0, math.sin(theta) * radius)
        elif shape == "disc":
            radius = float(props.get("emission_radius", 0.5)) * math.sqrt(rng.random())
            origin = (math.cos(theta) * radius, 0.0, math.sin(theta) * radius)
        elif shape == "line":
            origin = ((rng.random() - 0.5) * float(props.get("emission_height", 0.1)), 0.0, 0.0)
        elif shape == "box":
            extents = props.get("emission_box_extents", [0.25, 0.25, 0.25])
            origin = tuple((rng.random() * 2.0 - 1.0) * float(extents[axis]) for axis in range(3))
        else:
            origin = (0.0, 0.0, 0.0)
        dx, dy, dz = (float(direction[axis]) if isinstance(direction, list) and len(direction) == 3 else (0.0, 1.0, 0.0)[axis] for axis in range(3))
        dx += (rng.random() * 2.0 - 1.0) * math.sin(spread)
        dz += (rng.random() * 2.0 - 1.0) * math.sin(spread)
        length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        speed = velocity_min + (velocity_max - velocity_min) * rng.random()
        velocity = (dx / length * speed, dy / length * speed, dz / length * speed)
        position = tuple(
            origin[axis] + velocity[axis] * age + 0.5 * float(gravity[axis] if isinstance(gravity, list) and len(gravity) == 3 else 0.0) * age * age
            for axis in range(3)
        )
        screen = _project(position, camera, *image.size, scale=62.0)
        scale_value = _curve(layer.get("curves", {}).get("scale"), normalized, 1.0)
        alpha_value = max(0.0, min(1.0, _curve(layer.get("curves", {}).get("alpha"), normalized, 1.0)))
        color = _layer_color(layer, normalized)
        color = (color[0], color[1], color[2], int(color[3] * alpha_value))
        radius = max(1.0, (float(props.get("scale_min", 0.08)) + float(props.get("scale_max", 0.16))) * 0.5 * scale_value * 70.0)
        _draw_glow(image, screen, radius, color, 1.0)


def _draw_beam(image: Image.Image, layer: dict[str, Any], effect_time: float, effect_seed: int, camera: str) -> None:
    props = layer.get("properties", {})
    start_time = float(layer.get("start", 0.0))
    local = effect_time - start_time
    duration = max(0.001, float(layer.get("duration", 1.0)))
    if local < 0.0 or local > duration:
        return
    source = props.get("source", [0.0, 0.0, 0.0])
    target = props.get("target", [0.0, 0.0, -4.0])
    segments = max(2, min(64, int(props.get("segments", 12))))
    rng = random.Random(_stable_seed(effect_seed, layer.get("id")))
    points = []
    for index in range(segments + 1):
        t = index / segments
        jitter = (rng.random() * 2.0 - 1.0) * float(props.get("noise", 0.08)) * math.sin(t * math.pi)
        point = (
            float(source[0]) + (float(target[0]) - float(source[0])) * t + jitter,
            float(source[1]) + (float(target[1]) - float(source[1])) * t + jitter * 0.5,
            float(source[2]) + (float(target[2]) - float(source[2])) * t + jitter,
        )
        points.append(_project(point, camera, *image.size, scale=62.0))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = _layer_color(layer, local / duration)
    fade = max(0.0, min(1.0, _curve(layer.get("curves", {}).get("width"), local / duration, 1.0)))
    alpha = int(color[3] * fade)
    width = max(1, int(float(props.get("thickness", 0.12)) * 62.0))
    for spread, opacity in ((width * 3, 0.12), (width * 1.8, 0.25), (width, 0.95)):
        draw.line(points, fill=(color[0], color[1], color[2], int(alpha * opacity)), width=max(1, int(spread)), joint="curve")
    image.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(max(0, width // 3))))
    image.alpha_composite(overlay)


def _draw_visual_layer(image: Image.Image, layer: dict[str, Any], effect_time: float, camera: str) -> None:
    start = float(layer.get("start", 0.0))
    duration = max(0.001, float(layer.get("duration", 1.0)))
    local = effect_time - start
    if local < 0.0 or local > duration:
        return
    normalized = local / duration
    props = layer.get("properties", {})
    layer_type = layer.get("type")
    center = _project((0.0, 0.15, 0.0), camera, *image.size, scale=62.0)
    alpha = max(0.0, min(1.0, _curve(layer.get("curves", {}).get("alpha"), normalized, 1.0)))
    scale = max(0.0, _curve(layer.get("curves", {}).get("scale"), normalized, 1.0))
    color = _layer_color(layer, normalized)
    color = (color[0], color[1], color[2], int(color[3] * alpha))
    if layer_type == "light":
        energy = _curve(layer.get("curves", {}).get("energy"), normalized, 1.0)
        _draw_glow(image, center, float(props.get("range", 3.0)) * 22.0 * max(0.1, energy), _color(props.get("color"), color), energy)
    elif layer_type in {"sprite", "mesh_effect"}:
        size = props.get("size", [1.0, 1.0])
        radius = (float(size[0]) if isinstance(size, list) and size else 1.0) * 35.0 * scale
        _draw_glow(image, center, radius, color, 1.0)
        draw = ImageDraw.Draw(image, "RGBA")
        if layer_type == "mesh_effect":
            draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=color, width=max(1, int(radius * 0.08)))
        else:
            draw.rectangle((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=color, width=max(1, int(radius * 0.08)))
    elif layer_type == "decal":
        size = props.get("size", [2.0, 2.0])
        rx = float(size[0]) * 28.0 * max(scale, 0.01)
        ry = float(size[1]) * 12.0 * max(scale, 0.01)
        draw = ImageDraw.Draw(image, "RGBA")
        draw.ellipse((center[0] - rx, center[1] - ry, center[0] + rx, center[1] + ry), fill=color, outline=(color[0], color[1], color[2], min(255, color[3] + 40)), width=2)
    elif layer_type == "trail":
        draw = ImageDraw.Draw(image, "RGBA")
        points = []
        for index in range(18):
            t = index / 17.0
            point = _project((math.sin(t * math.pi * 2.0) * 0.8 * (1.0 - t), 0.4 + t * 0.9, -t * 1.8), camera, *image.size, scale=62.0)
            points.append(point)
        draw.line(points, fill=color, width=max(1, int(float(props.get("width", 0.18)) * 60.0)), joint="curve")
    elif layer_type == "beam":
        _draw_beam(image, layer, effect_time, 0, camera)


def render_preview(
    document: dict[str, Any],
    output: str | Path,
    time: float = 0.0,
    camera: str = "mmo",
    width: int = 768,
    height: int = 512,
    background: str = "dark",
    show_grid: bool = True,
) -> dict[str, Any]:
    if width < 64 or height < 64 or width > 4096 or height > 4096:
        raise ExportError("Preview dimensions must be between 64 and 4096 pixels.", "INVALID_PREVIEW_SIZE")
    if camera not in {"front", "side", "top", "mmo"}:
        raise ExportError("Camera must be one of: front, side, top, mmo.", "INVALID_CAMERA")
    if background not in {"dark", "light", "night", "transparent"}:
        raise ExportError("Background must be dark, light, night, or transparent.", "INVALID_BACKGROUND")
    if background == "transparent":
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    else:
        color = {"dark": (12, 16, 25, 255), "light": (220, 225, 232, 255), "night": (5, 8, 18, 255)}[background]
        image = Image.new("RGBA", (width, height), color)
    if show_grid and background != "transparent":
        _draw_grid(image, camera)
    duration = max(0.001, float(document.get("duration", 1.0)))
    sample_time = float(time)
    if document.get("loop"):
        sample_time = sample_time % duration
    else:
        sample_time = max(0.0, min(duration, sample_time))
    for layer in document.get("layers", []):
        if not isinstance(layer, dict) or not layer.get("enabled", True):
            continue
        layer_type = layer.get("type")
        if layer_type in {"particle", "mesh_particle"}:
            _draw_particle_layer(image, layer, sample_time, int(document.get("seed", 0)), camera)
        elif layer_type in {"sprite", "light", "trail", "beam", "decal", "mesh_effect"}:
            _draw_visual_layer(image, layer, sample_time, camera)
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    label = f"{document.get('name', document.get('id', 'effect'))}   {sample_time:0.3f}s / {duration:0.3f}s"
    draw.rounded_rectangle((16, 16, min(width - 16, 16 + max(230, len(label) * 7)), 42), radius=6, fill=(7, 10, 18, 190))
    draw.text((26, 24), label, fill=(228, 235, 247, 230), font=font)
    metrics = estimate_metrics(document)
    metrics_label = f"{metrics['layer_count']} layers  |  ~{metrics['peak_particles_estimate']} particles  |  seed {document.get('seed', 0)}"
    draw.text((18, height - 26), metrics_label, fill=(180, 195, 215, 190), font=font)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        image.save(destination, format="PNG", optimize=False)
    except OSError as exc:
        raise ExportError(f"Could not write preview {destination}: {exc}", "PREVIEW_WRITE", str(destination)) from exc
    return {
        "path": str(destination),
        "time": sample_time,
        "camera": camera,
        "width": width,
        "height": height,
        "background": background,
        "metrics": metrics,
    }
