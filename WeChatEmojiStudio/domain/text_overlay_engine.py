import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

class TextOverlayEngine:
    """
    微信表情本地高清文字覆写与纠错排版引擎
    彻底解决 AI 绘图大模型中文错别字(如少益少糖、难得期涂)以及文字被截断问题！
    """

    @staticmethod
    def get_chinese_font(font_size=24):
        """
        获取 Windows 系统中预装的优质中文字体 (优先黑体、微软雅黑、幼圆)
        """
        candidates = [
            "C:/Windows/Fonts/OPPOSans-H.ttf",             # OPPO Sans 特粗 (开源免费商用)
            "C:/Windows/Fonts/HarmonyOS_Sans_SC_Bold.ttf", # 华为鸿蒙粗黑 (开源免费商用)
            "C:/Windows/Fonts/Alibaba-PuHuiTi-Bold.otf",   # 阿里巴巴普惠体 (开源免费商用)
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",          # 思源黑体 (SIL 开源商用)
            "C:/Windows/Fonts/Noto Sans SC Bold (TrueType).otf",
            "C:/Windows/Fonts/Source Han Serif SC Heavy (TrueType).ttf",
            "C:/Windows/Fonts/msyhbd.ttc",                 # 微软雅黑粗体
            "C:/Windows/Fonts/msyh.ttc",                   # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",                 # 黑体
        ]
        for f in candidates:
            if os.path.exists(f):
                try:
                    return ImageFont.truetype(f, font_size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @staticmethod
    def draw_text_with_outline(
        draw: ImageDraw.ImageDraw,
        text: str,
        pos: tuple,
        font,
        text_color=(0, 0, 0),
        outline_color=(255, 255, 255),
        outline_width=3
    ):
        """
        绘制带有高对比度白色描边的微信爆款字体
        确保深浅聊天背景下均 100% 清晰可见
        """
        x, y = pos
        # 绘制四周描边
        for ox in range(-outline_width, outline_width + 1):
            for oy in range(-outline_width, outline_width + 1):
                if ox * ox + oy * oy <= outline_width * outline_width:
                    draw.text((x + ox, y + oy), text, font=font, fill=outline_color)
        # 绘制中心文字
        draw.text((x, y), text, font=font, fill=text_color)

    @classmethod
    def replace_gif_text(
        cls,
        gif_path: str,
        correct_text: str,
        out_path: str = None,
        erase_top_height: int = 50, # 擦除顶部原 AI 错字的高度区域
        font_size: int = 22
    ) -> bool:
        """
        清除原有画面顶部的 AI 模糊错别字，覆写上 100% 正确且带白色描边的标准大字！
        """
        if not os.path.exists(gif_path):
            return False

        if out_path is None:
            out_path = gif_path

        im = Image.open(gif_path)
        w, h = im.size
        font = cls.get_chinese_font(font_size)

        temp_dir = os.path.join(os.path.dirname(os.path.abspath(out_path)), f"tmp_text_{os.getpid()}_{os.path.basename(gif_path)}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            frames_count = im.n_frames
            durations = []
            
            for i in range(frames_count):
                im.seek(i)
                durations.append(im.info.get("duration", 100))
                frame = im.convert("RGBA")

                draw = ImageDraw.Draw(frame)

                # 1. 擦除顶部原本的错别字区域 (用透明清除)
                erase_box = (0, 0, w, erase_top_height)
                draw.rectangle(erase_box, fill=(0, 0, 0, 0))

                # 2. 测量正确文字尺寸并居中排版 (留出四周安全边距，绝不切断)
                # 如果字太长（>8字），分两行排版
                lines = []
                if len(correct_text) > 8 and "，" in correct_text:
                    lines = correct_text.split("，", 1)
                    lines[0] = lines[0] + "，"
                elif len(correct_text) > 8 and "," in correct_text:
                    lines = correct_text.split(",", 1)
                    lines[0] = lines[0] + ","
                elif len(correct_text) > 7:
                    mid = len(correct_text) // 2
                    lines = [correct_text[:mid], correct_text[mid:]]
                else:
                    lines = [correct_text]

                # 计算总文字高度与垂直居中位置
                line_heights = []
                line_widths = []
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_widths.append(bbox[2] - bbox[0])
                    line_heights.append(bbox[3] - bbox[1])

                total_text_h = sum(line_heights) + (len(lines) - 1) * 4
                start_y = max(4, (erase_top_height - total_text_h) // 2)

                # 绘制每一行文字并严格水平居中
                cur_y = start_y
                for j, line in enumerate(lines):
                    tw = line_widths[j]
                    tx = max(8, (w - tw) // 2) # 水平居中并留出 8px 安全内边距
                    cls.draw_text_with_outline(draw, line, (tx, cur_y), font, text_color=(20, 20, 20), outline_color=(255, 255, 255), outline_width=3)
                    cur_y += line_heights[j] + 4

                frame.save(os.path.join(temp_dir, f"frame_{i:04d}.png"))

            # 用 FFmpeg 重新合成带正确文字的高清透明 GIF
            target_fps = 10
            vf = (
                f"fps={target_fps},split[s0][s1];"
                f"[s0]palettegen=max_colors=80:reserve_transparent=1[p];"
                f"[s1][p]paletteuse=dither=bayer:bayer_scale=3"
            )
            cmd = [
                "ffmpeg", "-y", "-framerate", str(target_fps),
                "-i", os.path.join(temp_dir, "frame_%04d.png"),
                "-vf", vf, "-loop", "0", out_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        finally:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
