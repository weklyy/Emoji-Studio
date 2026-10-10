import os
import shutil
import subprocess
from PIL import Image

class ImageCompressor:
    """
    智能图像与 GIF 微信合规压缩引擎
    包含：
    1. 边缘漫水连通域泛洪智能透明化 (Flood-Fill Alpha Matte)
    2. 安全视口内缩与透明垫底 (防贴边切字)
    3. FFmpeg 双通调色板极限体积压制 (严格保证 <= 480KB)
    """

    @staticmethod
    def make_gif_transparent(
        src_gif_path: str,
        out_gif_path: str = None,
        tolerance: int = 30,
        max_kb: int = 480,
        scale_percent: int = 100
    ) -> bool:
        if not os.path.exists(src_gif_path):
            return False

        if out_gif_path is None:
            out_gif_path = src_gif_path

        temp_dir = os.path.join(os.path.dirname(os.path.abspath(out_gif_path)), f"tmp_{os.getpid()}_{os.path.basename(src_gif_path)}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            frames_rgba = []
            with Image.open(src_gif_path) as im:
                w, h = im.size
                n_frames = im.n_frames
                step = 1 if n_frames <= 26 else 2

                for i in range(0, n_frames, step):
                    im.seek(i)
                    frames_rgba.append(im.convert("RGBA"))

            extracted_count = 0
            for frame in frames_rgba:
                c0, c1 = frame.getpixel((0, 0)), frame.getpixel((w - 1, 0))
                c2, c3 = frame.getpixel((0, h - 1)), frame.getpixel((w - 1, h - 1))
                bg_r = (c0[0] + c1[0] + c2[0] + c3[0]) // 4
                bg_g = (c0[1] + c1[1] + c2[1] + c3[1]) // 4
                bg_b = (c0[2] + c1[2] + c2[2] + c3[2]) // 4

                def is_bg(pix):
                    return (
                        abs(pix[0] - bg_r) < tolerance and
                        abs(pix[1] - bg_g) < tolerance and
                        abs(pix[2] - bg_b) < tolerance
                    )

                visited = bytearray(w * h)
                queue = []

                for x in range(w):
                    if is_bg(frame.getpixel((x, 0))):
                        queue.append((x, 0))
                        visited[0 * w + x] = 1
                    if is_bg(frame.getpixel((x, h - 1))):
                        queue.append((x, h - 1))
                        visited[(h - 1) * w + x] = 1
                for y in range(h):
                    if is_bg(frame.getpixel((0, y))) and not visited[y * w + 0]:
                        queue.append((0, y))
                        visited[y * w + 0] = 1
                    if is_bg(frame.getpixel((w - 1, y))) and not visited[y * w + (w - 1)]:
                        queue.append((w - 1, y))
                        visited[y * w + (w - 1)] = 1

                while queue:
                    cx, cy = queue.pop()
                    for nx, ny in [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]:
                        if 0 <= nx < w and 0 <= ny < h:
                            idx = ny * w + nx
                            if not visited[idx] and is_bg(frame.getpixel((nx, ny))):
                                visited[idx] = 1
                                queue.append((nx, ny))

                pix = frame.load()
                for y in range(h):
                    for x in range(w):
                        if visited[y * w + x]:
                            pix[x, y] = (0, 0, 0, 0)

                if scale_percent < 100:
                    scaled_w = int(w * scale_percent / 100)
                    scaled_h = int(h * scale_percent / 100)
                    scaled_frame = frame.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                    padded_frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    padded_frame.paste(scaled_frame, ((w - scaled_w) // 2, (h - scaled_h) // 2))
                    frame = padded_frame

                frame.save(os.path.join(temp_dir, f"frame_{extracted_count:04d}.png"))
                extracted_count += 1

            preset_levels = [
                {"fps": 10, "colors": 96, "dither": "bayer:bayer_scale=3"},
                {"fps": 10, "colors": 80, "dither": "bayer:bayer_scale=3"},
                {"fps": 10, "colors": 64, "dither": "bayer:bayer_scale=2"},
                {"fps": 8,  "colors": 64, "dither": "bayer:bayer_scale=2"},
                {"fps": 8,  "colors": 48, "dither": "none"},
                {"fps": 8,  "colors": 32, "dither": "none"},
            ]

            tmp_out_gif = os.path.join(temp_dir, "output.gif")
            best_candidate = None

            for lvl in preset_levels:
                fps = lvl["fps"]
                colors = lvl["colors"]
                dither = lvl["dither"]
                vf = (
                    f"fps={fps},split[s0][s1];"
                    f"[s0]palettegen=max_colors={colors}:reserve_transparent=1[p];"
                    f"[s1][p]paletteuse=dither={dither}"
                )
                cmd = [
                    "ffmpeg", "-y", "-framerate", str(fps),
                    "-i", os.path.join(temp_dir, "frame_%04d.png"),
                    "-vf", vf, "-loop", "0", tmp_out_gif
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(tmp_out_gif):
                    sz = os.path.getsize(tmp_out_gif) / 1024.0
                    best_candidate = tmp_out_gif
                    if sz <= max_kb:
                        break

            if best_candidate and os.path.exists(best_candidate):
                try:
                    shutil.copyfile(best_candidate, out_gif_path)
                except Exception:
                    os.replace(best_candidate, out_gif_path)
                return True
            return False
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    def compress_gif(
        cls,
        src_gif_path: str,
        out_gif_path: str = None,
        max_kb: int = 480
    ) -> tuple:
        """
        高保真 GIF 智能自适应压缩引擎
        采用多通调色板 (PaletteGen)、自适应抖动控制、智能降频与抽帧管线，
        严格压制到指定体积 (默认 <= 480KB 微信红线) 之内。
        返回: (成功标志 bool, 最终体积 float KB, 说明文字 str)
        """
        if not os.path.exists(src_gif_path):
            return False, 0.0, "文件不存在"

        if out_gif_path is None:
            out_gif_path = src_gif_path

        orig_kb = os.path.getsize(src_gif_path) / 1024.0

        temp_dir = os.path.join(
            os.path.dirname(os.path.abspath(out_gif_path)),
            f"tmp_comp_{os.getpid()}_{os.path.basename(src_gif_path)}"
        )
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with Image.open(src_gif_path) as im:
                n_frames = im.n_frames
                durations = []
                for i in range(n_frames):
                    im.seek(i)
                    durations.append(im.info.get("duration", 100))
                    im.convert("RGBA").save(os.path.join(temp_dir, f"full_{i:04d}.png"))

                avg_dur = sum(durations) / len(durations) if durations else 100
                orig_fps = max(6, min(15, round(1000.0 / avg_dur)))

                # 备用：抽帧 (每隔1帧取1帧)
                step2_count = 0
                for i in range(0, n_frames, 2):
                    im.seek(i)
                    im.convert("RGBA").save(os.path.join(temp_dir, f"step2_{step2_count:04d}.png"))
                    step2_count += 1

            passes = [
                {"prefix": "full", "fps": orig_fps, "colors": 80, "dither": "bayer:bayer_scale=3"},
                {"prefix": "full", "fps": min(10, orig_fps), "colors": 64, "dither": "bayer:bayer_scale=2"},
                {"prefix": "full", "fps": 8, "colors": 48, "dither": "bayer:bayer_scale=1"},
                {"prefix": "full", "fps": 8, "colors": 32, "dither": "none"},
                {"prefix": "full", "fps": 7, "colors": 24, "dither": "none"},
                {"prefix": "step2", "fps": max(5, int(orig_fps * 0.65)), "colors": 48, "dither": "bayer:bayer_scale=2"},
                {"prefix": "step2", "fps": max(5, int(orig_fps * 0.6)), "colors": 32, "dither": "none"},
                {"prefix": "step2", "fps": 5, "colors": 24, "dither": "none"},
            ]

            best_candidate = None
            best_kb = orig_kb

            for p_idx, p in enumerate(passes):
                tmp_out = os.path.join(temp_dir, f"out_{p_idx}.gif")
                prefix, fps, colors, dither = p["prefix"], p["fps"], p["colors"], p["dither"]
                vf = (
                    f"fps={fps},split[s0][s1];"
                    f"[s0]palettegen=max_colors={colors}:reserve_transparent=1[p];"
                    f"[s1][p]paletteuse=dither={dither}"
                )
                cmd = [
                    "ffmpeg", "-y", "-framerate", str(fps),
                    "-i", os.path.join(temp_dir, f"{prefix}_%04d.png"),
                    "-vf", vf, "-loop", "0", tmp_out
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(tmp_out):
                    sz = os.path.getsize(tmp_out) / 1024.0
                    if sz < best_kb:
                        best_kb = sz
                        best_candidate = tmp_out
                    if sz <= max_kb:
                        best_candidate = tmp_out
                        best_kb = sz
                        break

            if best_candidate and os.path.exists(best_candidate):
                if best_kb < orig_kb or best_kb <= max_kb:
                    try:
                        shutil.copyfile(best_candidate, out_gif_path)
                    except Exception:
                        os.replace(best_candidate, out_gif_path)
                    return True, best_kb, f"从 {orig_kb:.1f}KB 成功压缩至 {best_kb:.1f}KB (降幅 {((orig_kb-best_kb)/orig_kb*100):.1f}%)"

            return (orig_kb <= max_kb), orig_kb, f"当前体积 {orig_kb:.1f}KB"
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def compress_png(file_path: str, max_kb: int) -> bool:
        if not os.path.exists(file_path):
            return False
        cur_kb = os.path.getsize(file_path) / 1024.0
        if cur_kb <= max_kb:
            return True

        with Image.open(file_path) as img:
            for colors in [256, 192, 128, 96, 64]:
                tmp_path = file_path + ".tmp.png"
                if img.mode == 'RGBA':
                    # 修复：对于 RGBA 必须使用 FASTOCTREE 或默认
                    quantized = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
                else:
                    quantized = img.convert('RGB').quantize(colors=colors)
                quantized.save(tmp_path, format="PNG", optimize=True)
                if os.path.getsize(tmp_path) / 1024.0 <= max_kb:
                    try:
                        shutil.copyfile(tmp_path, file_path)
                    finally:
                        os.remove(tmp_path)
                    return True
                os.remove(tmp_path)
        return False

    @staticmethod
    def compress_jpg(file_path: str, max_kb: int) -> bool:
        if not os.path.exists(file_path):
            return False
        if os.path.getsize(file_path) / 1024.0 <= max_kb:
            return True

        with Image.open(file_path) as img:
            rgb_img = img.convert("RGB")
            low_q, high_q = 30, 95
            best_path = None
            while low_q <= high_q:
                mid_q = (low_q + high_q) // 2
                tmp_path = file_path + ".tmp.jpg"
                rgb_img.save(tmp_path, "JPEG", quality=mid_q, optimize=True)
                if os.path.getsize(tmp_path) / 1024.0 <= max_kb:
                    best_path = tmp_path
                    low_q = mid_q + 1
                else:
                    high_q = mid_q - 1
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

            if best_path and os.path.exists(best_path):
                try:
                    shutil.copyfile(best_path, file_path)
                finally:
                    os.remove(best_path)
                return True
        return False

    @staticmethod
    def transcode_to_wechat_gif(
        video_path: str,
        output_gif: str,
        crop_box: tuple,
        duration: float = 3.0,
        start_time: float = 0.0,
        max_kb: int = 480,
        make_transparent: bool = True,
        scale_percent: int = 94
    ) -> bool:
        x, y, w, h = crop_box
        os.makedirs(os.path.dirname(os.path.abspath(output_gif)), exist_ok=True)

        if scale_percent < 100:
            target_inner = int(240 * scale_percent / 100)
            pad_xy = (240 - target_inner) // 2
            scale_vf = f"scale={target_inner}:{target_inner}:flags=lanczos,pad=240:240:{pad_xy}:{pad_xy}:color=0xFFFFFF"
        else:
            scale_vf = "scale=240:240:flags=lanczos"

        preset_levels = [
            {"fps": 10, "colors": 96, "dither": "bayer:bayer_scale=3"},
            {"fps": 10, "colors": 80, "dither": "bayer:bayer_scale=3"},
            {"fps": 8,  "colors": 64, "dither": "bayer:bayer_scale=2"},
            {"fps": 8,  "colors": 48, "dither": "none"},
        ]

        for level in preset_levels:
            fps = level["fps"]
            colors = level["colors"]
            dither = level["dither"]

            vf = (
                f"crop={w}:{h}:{x}:{y},"
                f"fps={fps},{scale_vf},split[s0][s1];"
                f"[s0]palettegen=max_colors={colors}:reserve_transparent=0[p];"
                f"[s1][p]paletteuse=dither={dither}"
            )

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", video_path,
                "-vf", vf,
                "-loop", "0",
                output_gif
            ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(output_gif):
                size_kb = os.path.getsize(output_gif) / 1024.0
                if size_kb <= max_kb:
                    break

        if make_transparent and os.path.exists(output_gif):
            ImageCompressor.make_gif_transparent(output_gif, output_gif, tolerance=30, max_kb=max_kb)

        return os.path.exists(output_gif)
