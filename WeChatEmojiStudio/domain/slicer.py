import os
import subprocess
from PIL import Image
from domain.compressor import ImageCompressor
from domain.specs import WeChatSpecs

class VideoGridSlicer:
    """
    16:9 视频 5x3 (15宫格) 自动智能切片器
    内置【安全视口缩放 (Safe Viewport Padding)】：
    自动将每格画面等比内缩 5%~10% 并居中透明垫底，彻底根除文字左右/上下被截断问题！
    """

    @staticmethod
    def slice_5x3_video(
        video_path: str,
        output_dir: str,
        grid_metadata: dict = None,
        duration: float = 3.0,
        start_time: float = 0.0,
        make_transparent: bool = True,
        scale_percent: int = 94, # 默认等比内缩至 94%，四周留 3% 呼吸区，彻底防切字
        progress_callback = None
    ) -> list:
        """
        自动将 16:9 视频切片为 15 个合规 GIF (240x240, <=500KB)
        """
        os.makedirs(output_dir, exist_ok=True)
        thumbs_dir = os.path.join(output_dir, "thumbs_120x120")
        os.makedirs(thumbs_dir, exist_ok=True)

        cols, rows = 5, 3

        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", video_path
        ]
        try:
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            w_str, h_str = res.stdout.strip().split(",")
            vid_w, vid_h = int(w_str), int(h_str)
        except Exception:
            vid_w, vid_h = 1280, 720

        if grid_metadata and "w" in grid_metadata and "h" in grid_metadata:
            base_x = grid_metadata.get("x", 0)
            base_y = grid_metadata.get("y", 0)
            grid_w = grid_metadata.get("w", vid_w)
            grid_h = grid_metadata.get("h", vid_h)
        else:
            base_x, base_y = 0, 0
            grid_w, grid_h = vid_w, vid_h

        cell_w = grid_w / cols
        cell_h = grid_h / rows
        square_size = int(min(cell_w, cell_h))
        inner_pad_x = int((cell_w - square_size) / 2)
        inner_pad_y = int((cell_h - square_size) / 2)

        generated_gifs = []
        total = cols * rows

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c + 1
                crop_x = int(base_x + c * cell_w + inner_pad_x)
                crop_y = int(base_y + r * cell_h + inner_pad_y)

                crop_x = max(0, min(vid_w - square_size, crop_x))
                crop_y = max(0, min(vid_h - square_size, crop_y))

                out_gif = os.path.join(output_dir, f"{idx:02d}.gif")
                crop_box = (crop_x, crop_y, square_size, square_size)

                # 压制 240x240 微信 GIF (通过 scale_percent 防切字)
                ImageCompressor.transcode_to_wechat_gif(
                    video_path=video_path,
                    output_gif=out_gif,
                    crop_box=crop_box,
                    duration=duration,
                    start_time=start_time,
                    max_kb=WeChatSpecs.MAIN_GIF_SAFE_KB,
                    make_transparent=make_transparent,
                    scale_percent=scale_percent
                )
                generated_gifs.append(out_gif)

                # 提取 120x120 缩略图 PNG
                out_thumb = os.path.join(thumbs_dir, f"{idx:02d}.png")
                thumb_im = Image.open(out_gif)
                thumb_im.seek(0)
                thumb_png = thumb_im.convert("RGBA").resize((120, 120), Image.Resampling.LANCZOS)
                thumb_png.save(out_thumb, "PNG")
                ImageCompressor.compress_png(out_thumb, max_kb=WeChatSpecs.THUMB_MAX_KB)

                if progress_callback:
                    progress_callback(idx, total)

        return generated_gifs
