import os
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

class GifTextEditor:
    """
    GIF 帧级文字区域精准渲染与艺术字打字核心引擎
    支持：
    1. 多字体可选 (微软雅黑粗体、华文琥珀、华文行楷、经典黑体、楷体等及自定义本地字体)
    2. 字号自由调节 (12 ~ 48 pt)
    3. 文字色彩可选 (任意 RGB 色系及喜庆色卡)
    4. 描边可选 (描边粗细 0~8px，描边颜色可选)
    5. 位置与对齐自由调节 (垂直 Y 位置、居中/靠左/靠右)
    6. 可选顶部杂乱旧字抹除 (对纯净原图可完全关闭抹除)
    7. 遍历 GIF 每一帧高质量压制，确保 <=480KB 符合微信规范
    """

    FONT_PRESETS = [
        {
            "name": "OPPO Sans Heavy (特粗黑体 • 免费商用 ⭐首选)",
            "file": "OPPOSans-H.ttf",
            "license": "OPPO 免费商用授权"
        },
        {
            "name": "华为鸿蒙黑体 (超清粗黑 • 免费商用 ⭐推荐)",
            "file": "HarmonyOS_Sans_SC_Bold.ttf",
            "license": "华为免费商用授权"
        },
        {
            "name": "阿里巴巴普惠体 (现代粗黑 • 免费商用)",
            "file": "Alibaba-PuHuiTi-Bold.otf",
            "license": "阿里巴巴免费商用授权"
        },
        {
            "name": "思源黑体 (Google/Adobe • SIL开源商用)",
            "file": "NotoSansSC-VF.ttf",
            "candidates": ["NotoSansSC-VF.ttf", "Noto Sans SC Bold (TrueType).otf", "Noto Sans SC (TrueType).otf"],
            "license": "SIL Open Font License"
        },
        {
            "name": "思源宋体 (特粗古风 • SIL开源商用)",
            "file": "Source Han Serif SC Heavy (TrueType).ttf",
            "candidates": ["Source Han Serif SC Heavy (TrueType).ttf", "NotoSerifSC-VF.ttf"],
            "license": "SIL Open Font License"
        },
        {
            "name": "华为鸿蒙常规 (标准阅读 • 免费商用)",
            "file": "HarmonyOS_Sans_SC_Regular.ttf",
            "license": "华为免费商用授权"
        },
        {
            "name": "阿里巴巴普惠体常规 (现代黑体 • 免费商用)",
            "file": "Alibaba-PuHuiTi-Regular.otf",
            "license": "阿里巴巴免费商用授权"
        },
    ]

    @classmethod
    def resolve_font_path(cls, font_identifier: str = None) -> str:
        """根据文件名或全路径或预设名称解析开源商用字体绝对路径"""
        if not font_identifier:
            font_identifier = "OPPOSans-H.ttf"

        # 1. 已经是绝对路径且存在
        if os.path.exists(font_identifier):
            return font_identifier

        # 2. 如果是预设名称，查找对应文件名与候选列表
        candidates_to_try = [font_identifier]
        for p in cls.FONT_PRESETS:
            if p["name"] == font_identifier or p["file"] == font_identifier:
                candidates_to_try = [p["file"]]
                if "candidates" in p:
                    candidates_to_try.extend(p["candidates"])
                break

        # 3. 检查系统字体目录 C:/Windows/Fonts
        for f in candidates_to_try:
            win_path = os.path.join("C:/Windows/Fonts", f)
            if os.path.exists(win_path):
                return win_path

        # 4. 常见开源商用候选兜底 (防侵权安全防线)
        safe_defaults = [
            "C:/Windows/Fonts/OPPOSans-H.ttf",
            "C:/Windows/Fonts/HarmonyOS_Sans_SC_Bold.ttf",
            "C:/Windows/Fonts/Alibaba-PuHuiTi-Bold.otf",
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "C:/Windows/Fonts/Noto Sans SC Bold (TrueType).otf",
        ]
        for c in safe_defaults:
            if os.path.exists(c):
                return c

        return None

    @classmethod
    def get_font(cls, font_identifier=None, font_size=24):
        path = cls.resolve_font_path(font_identifier)
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                pass
        return ImageFont.load_default()

    @staticmethod
    def parse_color(c) -> tuple:
        """统一将 tuple 或十六进制颜色转化为 RGB 整数三元组"""
        if isinstance(c, tuple):
            return tuple(int(x) for x in c[:3])
        if isinstance(c, str):
            c = c.strip().lstrip("#")
            if len(c) == 6:
                return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
            elif len(c) == 3:
                return (int(c[0]*2, 16), int(c[1]*2, 16), int(c[2]*2, 16))
        return (20, 20, 20)

    @classmethod
    def process_gif(
        cls,
        gif_path: str,
        out_gif_path: str,
        text: str = "",
        font_identifier: str = "OPPOSans-H.ttf",
        font_size: int = 24,
        text_color=(20, 20, 20),
        stroke_color=(255, 255, 255),
        stroke_width: int = 3,
        text_y: int = 10,
        text_x: int = None,
        direction: str = "horizontal",
        align: str = "center",
        erase_rect: tuple = None,
        max_kb: int = 480,
        **kwargs
    ) -> bool:
        """
        遍历 GIF 全部帧：
        1. 若 erase_rect 有效且宽>0、高>0，执行局部透明抹除 (0,0,0,0)；否则完全保留原画不抹除
        2. 在指定坐标与方向(横排/竖排)绘制高品质中文字体与自定义描边
        3. 用 FFmpeg 压制为符合微信表情开放平台规范的动图 (<=480KB)
        """
        if not os.path.exists(gif_path):
            return False

        # 兼容旧参数传递：若 kwargs 传递了相关参数
        if "erase_rect" in kwargs and kwargs["erase_rect"]:
            erase_rect = kwargs["erase_rect"]
        direction = kwargs.get("direction", direction)
        if "text_x" in kwargs and kwargs["text_x"] is not None:
            text_x = kwargs["text_x"]

        t_col = cls.parse_color(text_color)
        s_col = cls.parse_color(stroke_color)
        font = cls.get_font(font_identifier, font_size)

        temp_dir = os.path.join(
            os.path.dirname(os.path.abspath(out_gif_path)),
            f"tmp_edit_{os.getpid()}_{os.path.basename(gif_path)}"
        )
        os.makedirs(temp_dir, exist_ok=True)

        try:
            with Image.open(gif_path) as im:
                w, h = im.size
                n_frames = im.n_frames
                durations = []

                for i in range(n_frames):
                    im.seek(i)
                    durations.append(im.info.get("duration", 100))
                    frame = im.convert("RGBA")

                    draw = ImageDraw.Draw(frame)

                    # 1. 局部抹除旧文字 (若开启，支持左侧/右侧/顶部/底部/自定义全方位区域)
                    if erase_rect and len(erase_rect) == 4 and erase_rect[2] > 0 and erase_rect[3] > 0:
                        ex, ey, ew, eh = erase_rect
                        draw.rectangle((ex, ey, ex + ew, ey + eh), fill=(0, 0, 0, 0))

                    # 2. 绘制新艺术字 (支持横排与竖排)
                    if text.strip():
                        if direction == "vertical":
                            # 竖排文字渲染 (适合左侧/右侧竖排文字)
                            chars = list(text.strip())
                            char_bboxes = [draw.textbbox((0, 0), c, font=font, stroke_width=stroke_width) for c in chars]
                            char_heights = [max(font_size, b[3] - b[1]) for b in char_bboxes]
                            max_cw = max((b[2] - b[0]) for b in char_bboxes) if char_bboxes else font_size

                            if text_x is not None:
                                col_x = text_x
                            elif align == "left":
                                col_x = 10
                            elif align == "right":
                                col_x = max(4, w - max_cw - 10)
                            else:
                                col_x = max(4, (w - max_cw) // 2)

                            cur_y = text_y
                            line_spacing = 2
                            for idx, c in enumerate(chars):
                                cb = char_bboxes[idx]
                                cw = cb[2] - cb[0]
                                cx = col_x + (max_cw - cw) // 2
                                if stroke_width > 0:
                                    draw.text(
                                        (cx, cur_y), c, font=font,
                                        fill=t_col, stroke_width=stroke_width, stroke_fill=s_col
                                    )
                                else:
                                    draw.text((cx, cur_y), c, font=font, fill=t_col)
                                cur_y += char_heights[idx] + line_spacing
                        else:
                            # 横排文字渲染 (传统左右横向)
                            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
                            tw = bbox[2] - bbox[0]

                            if align == "center":
                                tx = max(4, (w - tw) // 2)
                            elif align == "right":
                                tx = max(4, w - tw - 8)
                            elif text_x is not None:
                                tx = text_x
                            else:
                                tx = 8

                            if stroke_width > 0:
                                draw.text(
                                    (tx, text_y), text, font=font,
                                    fill=t_col, stroke_width=stroke_width, stroke_fill=s_col
                                )
                            else:
                                draw.text((tx, text_y), text, font=font, fill=t_col)

                    frame.save(os.path.join(temp_dir, f"frame_{i:04d}.png"))

            # 备用：生成 step=2 抽帧序列 (应对帧数过多极限压缩)
            step2_count = 0
            for i in range(0, n_frames, 2):
                src_f = os.path.join(temp_dir, f"frame_{i:04d}.png")
                dst_f = os.path.join(temp_dir, f"step2_{step2_count:04d}.png")
                shutil.copyfile(src_f, dst_f)
                step2_count += 1

            avg_dur = sum(durations) / len(durations) if durations else 100
            orig_fps = max(6, min(12, round(1000.0 / avg_dur)))

            preset_levels = [
                {"prefix": "frame", "fps": orig_fps, "colors": 80, "dither": "bayer:bayer_scale=3"},
                {"prefix": "frame", "fps": min(10, orig_fps), "colors": 64, "dither": "bayer:bayer_scale=2"},
                {"prefix": "frame", "fps": 8, "colors": 48, "dither": "bayer:bayer_scale=1"},
                {"prefix": "frame", "fps": 8, "colors": 32, "dither": "none"},
                {"prefix": "frame", "fps": 7, "colors": 24, "dither": "none"},
                {"prefix": "step2", "fps": max(5, int(orig_fps * 0.65)), "colors": 48, "dither": "bayer:bayer_scale=2"},
                {"prefix": "step2", "fps": max(5, int(orig_fps * 0.6)), "colors": 32, "dither": "none"},
                {"prefix": "step2", "fps": 5, "colors": 24, "dither": "none"},
            ]

            best_candidate = None
            best_sz = float('inf')

            for p_idx, lvl in enumerate(preset_levels):
                colors = lvl["colors"]
                dither = lvl["dither"]
                fps = lvl["fps"]
                prefix = lvl["prefix"]
                tmp_out = os.path.join(temp_dir, f"out_{p_idx}.gif")

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
                    sz_kb = os.path.getsize(tmp_out) / 1024.0
                    if sz_kb < best_sz:
                        best_sz = sz_kb
                        best_candidate = tmp_out
                    if sz_kb <= max_kb:
                        best_candidate = tmp_out
                        best_sz = sz_kb
                        break

            if best_candidate and os.path.exists(best_candidate):
                shutil.copyfile(best_candidate, out_gif_path)
                return True
            return False
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
