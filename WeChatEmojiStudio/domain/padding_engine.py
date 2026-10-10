import os
from PIL import Image

class SafePaddingEngine:
    """
    15 宫格到 16:9 视频底图的防裁剪安全呼吸垫算法
    彻底根治 AI 视频大模型上下运镜/居中裁剪导致的人物耳朵、头顶、文字截断问题！
    """

    @staticmethod
    def generate_safe_16x9_image(
        input_image_path: str,
        output_image_path: str,
        vertical_safe_percent: float = 0.08, # 上下各留 8% 呼吸安全垫
        target_resolution: tuple = (1280, 720)
    ) -> dict:
        """
        为 15 宫格图片添加自适应防截断安全边框，并拓展为标准的 16:9 尺寸 (1280x720 或 1920x1080)
        返回包含精确网格区域的元数据，用于后续视频自动逆向切片
        """
        img = Image.open(input_image_path).convert("RGBA")
        orig_w, orig_h = img.size

        # 采样四角像素来智能获取背景底色
        corners = [
            img.getpixel((0, 0)),
            img.getpixel((orig_w - 1, 0)),
            img.getpixel((0, orig_h - 1)),
            img.getpixel((orig_w - 1, orig_h - 1))
        ]
        # 取最频繁的背景色，默认白色
        bg_color = max(set(corners), key=corners.count)

        # 1. 目标 16:9 比例 (16 / 9 = 1.7778)
        target_aspect = 16.0 / 9.0

        # 计算加上下呼吸垫之后的高度
        pad_top = int(orig_h * vertical_safe_percent)
        pad_bottom = int(orig_h * vertical_safe_percent)
        padded_h = orig_h + pad_top + pad_bottom

        # 按照 16:9 比例计算对应的总宽度
        ideal_w = int(padded_h * target_aspect)
        if ideal_w < orig_w:
            # 如果原图特别宽，以原图宽度为主，增加上下边距
            ideal_w = orig_w + int(orig_w * 0.04) # 左右各留 2%
            padded_h = int(ideal_w / target_aspect)
            pad_top = int((padded_h - orig_h) / 2)
            pad_bottom = padded_h - orig_h - pad_top

        pad_left = int((ideal_w - orig_w) / 2)
        pad_right = ideal_w - orig_w - pad_left

        # 2. 创建 16:9 画布并填入背景色
        safe_canvas = Image.new("RGBA", (ideal_w, padded_h), bg_color)
        safe_canvas.paste(img, (pad_left, pad_top), img if img.mode == 'RGBA' else None)

        # 3. 规范化为目标分辨率 (如 1280x720)
        final_img = safe_canvas.resize(target_resolution, Image.Resampling.LANCZOS)
        
        # 保存图片
        os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
        if output_image_path.lower().endswith(".jpg") or output_image_path.lower().endswith(".jpeg"):
            final_img.convert("RGB").save(output_image_path, "JPEG", quality=98)
        else:
            final_img.save(output_image_path, "PNG")

        # 4. 计算归一化坐标元数据 (供后续视频自动精准逆向切片)
        scale_x = target_resolution[0] / ideal_w
        scale_y = target_resolution[1] / padded_h

        grid_rect = {
            "x": int(pad_left * scale_x),
            "y": int(pad_top * scale_y),
            "w": int(orig_w * scale_x),
            "h": int(orig_h * scale_y),
            "video_w": target_resolution[0],
            "video_h": target_resolution[1],
            "cols": 5,
            "rows": 3
        }

        return grid_rect
