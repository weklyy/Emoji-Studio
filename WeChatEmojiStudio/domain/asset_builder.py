import os
import shutil
from PIL import Image
from domain.specs import WeChatSpecs
from domain.compressor import ImageCompressor
from domain.f12_script_builder import F12ScriptBuilder

class WeChatAssetPackager:
    """
    微信表情提审物料自动化打包与体积保障服务
    1. 整合 15 个 GIF 与缩略图
    2. 处理横幅、封面、图标、赞赏图并 100% 压缩到微信红线之内
    3. 生成 F12 一键填表脚本与规范对照表
    4. 统一打包归档到指定提审目录
    """

    @staticmethod
    def pack_project(
        project_dir: str,
        export_dir: str,
        title: str,
        intro: str,
        reward_text: str,
        meanings: list,
        tags: list = None
    ) -> str:
        """
        一键打包提审物料
        """
        os.makedirs(export_dir, exist_ok=True)
        
        # 1. 主图文件夹
        target_gifs_dir = os.path.join(export_dir, "01_表情主图_240x240_GIF")
        os.makedirs(target_gifs_dir, exist_ok=True)
        src_gifs_dir = os.path.join(project_dir, "gifs")

        if not os.path.exists(src_gifs_dir) or not [f for f in os.listdir(src_gifs_dir) if f.lower().endswith(".gif")]:
            for root, dirs, files in os.walk(project_dir):
                if os.path.abspath(root).startswith(os.path.abspath(export_dir)):
                    continue
                gifs = [f for f in files if f.lower().endswith(".gif") and not f.endswith(".trans_tmp.gif")]
                if len(gifs) >= 8:
                    src_gifs_dir = root
                    if "01_表情主图" in root or "gifs" in root:
                        break

        if os.path.exists(src_gifs_dir):
            for fname in os.listdir(src_gifs_dir):
                if fname.lower().endswith(".gif") and not fname.endswith(".trans_tmp.gif"):
                    s_file = os.path.join(src_gifs_dir, fname)
                    d_file = os.path.join(target_gifs_dir, fname)
                    shutil.copy2(s_file, d_file)

        # 2. 详情页横幅 750x400
        banner_dst = os.path.join(export_dir, "02_详情页横幅_750x400.png")
        banner_candidates = [
            os.path.join(project_dir, "横幅.png"),
            os.path.join(project_dir, "横幅.jpg"),
            os.path.join(project_dir, "banner.png"),
            os.path.join(project_dir, "banner.jpg")
        ]
        banner_src = next((f for f in banner_candidates if os.path.exists(f)), None)
        if banner_src:
            img = Image.open(banner_src).resize((WeChatSpecs.BANNER_WIDTH, WeChatSpecs.BANNER_HEIGHT), Image.Resampling.LANCZOS)
            img.save(banner_dst, "PNG")
        else:
            # 自动生成备用艺术横幅
            img = Image.new("RGB", (WeChatSpecs.BANNER_WIDTH, WeChatSpecs.BANNER_HEIGHT), (245, 235, 220))
            img.save(banner_dst, "PNG")
        ImageCompressor.compress_png(banner_dst, WeChatSpecs.BANNER_SAFE_KB)

        # 3. 表情封面图 240x240 (必须透明底)
        cover_dst = os.path.join(export_dir, "03_表情封面图_240x240.png")
        cover_candidates = [
            os.path.join(project_dir, "封面图.png"),
            os.path.join(project_dir, "封面.png"),
            os.path.join(project_dir, "cover.png")
        ]
        cover_src = next((f for f in cover_candidates if os.path.exists(f)), None)
        if cover_src:
            img = Image.open(cover_src).convert("RGBA").resize((WeChatSpecs.COVER_WIDTH, WeChatSpecs.COVER_HEIGHT), Image.Resampling.LANCZOS)
            img.save(cover_dst, "PNG")
        else:
            # 若无，从第 1 张表情中自动提取
            first_thumb = os.path.join(project_dir, "gifs", "thumbs_120x120", "01.png")
            if os.path.exists(first_thumb):
                img = Image.open(first_thumb).convert("RGBA").resize((WeChatSpecs.COVER_WIDTH, WeChatSpecs.COVER_HEIGHT), Image.Resampling.LANCZOS)
            else:
                img = Image.new("RGBA", (WeChatSpecs.COVER_WIDTH, WeChatSpecs.COVER_HEIGHT), (255, 255, 255, 0))
            img.save(cover_dst, "PNG")
        ImageCompressor.compress_png(cover_dst, WeChatSpecs.COVER_SAFE_KB)

        # 4. 聊天页图标 50x50
        icon_dst = os.path.join(export_dir, "04_聊天页图标_50x50.png")
        icon_candidates = [
            os.path.join(project_dir, "图标.png"),
            os.path.join(project_dir, "icon.png")
        ]
        icon_src = next((f for f in icon_candidates if os.path.exists(f)), None)
        if icon_src:
            img = Image.open(icon_src).convert("RGBA").resize((WeChatSpecs.ICON_WIDTH, WeChatSpecs.ICON_HEIGHT), Image.Resampling.LANCZOS)
            img.save(icon_dst, "PNG")
        else:
            # 从封面图自动缩放到 50x50
            img = Image.open(cover_dst).convert("RGBA").resize((WeChatSpecs.ICON_WIDTH, WeChatSpecs.ICON_HEIGHT), Image.Resampling.LANCZOS)
            img.save(icon_dst, "PNG")
        ImageCompressor.compress_png(icon_dst, WeChatSpecs.ICON_SAFE_KB)

        # 5. 赞赏引导图 750x560
        reward_guide_dst = os.path.join(export_dir, "05_赞赏引导图_750x560.png")
        guide_candidates = [
            os.path.join(project_dir, "赞赏引导图.png"),
            os.path.join(project_dir, "赞赏引导图.jpg"),
            os.path.join(project_dir, "reward_guide.png")
        ]
        guide_src = next((f for f in guide_candidates if os.path.exists(f)), None)
        if guide_src:
            img = Image.open(guide_src).resize((WeChatSpecs.REWARD_GUIDE_WIDTH, WeChatSpecs.REWARD_GUIDE_HEIGHT), Image.Resampling.LANCZOS)
            img.save(reward_guide_dst, "PNG")
        else:
            img = Image.new("RGB", (WeChatSpecs.REWARD_GUIDE_WIDTH, WeChatSpecs.REWARD_GUIDE_HEIGHT), (250, 240, 230))
            img.save(reward_guide_dst, "PNG")
        ImageCompressor.compress_png(reward_guide_dst, WeChatSpecs.REWARD_GUIDE_SAFE_KB)

        # 6. 赞赏致谢图 750x750
        reward_thanks_dst = os.path.join(export_dir, "06_赞赏致谢图_750x750.png")
        thanks_candidates = [
            os.path.join(project_dir, "赞赏感谢图.png"),
            os.path.join(project_dir, "赞赏感谢图.jpg"),
            os.path.join(project_dir, "赞赏致谢图.png"),
            os.path.join(project_dir, "赞赏致谢图.jpg")
        ]
        thanks_src = next((f for f in thanks_candidates if os.path.exists(f)), None)
        if thanks_src:
            img = Image.open(thanks_src).resize((WeChatSpecs.REWARD_THANKS_WIDTH, WeChatSpecs.REWARD_THANKS_HEIGHT), Image.Resampling.LANCZOS)
            img.save(reward_thanks_dst, "PNG")
        else:
            img = Image.new("RGB", (WeChatSpecs.REWARD_THANKS_WIDTH, WeChatSpecs.REWARD_THANKS_HEIGHT), (250, 240, 230))
            img.save(reward_thanks_dst, "PNG")
        ImageCompressor.compress_png(reward_thanks_dst, WeChatSpecs.REWARD_THANKS_SAFE_KB)

        # 7. 生成微信后台 F12 一键填表脚本
        js_code = F12ScriptBuilder.build_script(title, intro, reward_text, meanings, tags)
        js_path = os.path.join(export_dir, "微信后台_F12一键填表脚本.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_code)

        # 8. 生成文案与使用指南
        guide_text = f"""=======================================================
   微信开放平台 • 表情开放平台全套审核物料对照表与文案
=======================================================

【提审核基本信息】：
- 表情专辑名称：{title} (不超过8字)
- 专辑介绍：{intro} (不超过100字)
- 赞赏引导语：{reward_text} (不超过15字)
- 表情标签：{", ".join(tags or ["日常", "长辈", "问候"])}

【15 个表情含义清单】：
"""
        for i, m in enumerate(meanings, 1):
            guide_text += f"{i:02d}. {m}\n"

        guide_text += """
=======================================================
【F12 极速一键填表秘籍】：
1. 登录微信表情开放平台 (sticker.weixin.qq.com)，进入上传页面。
2. 批量上传 01_表情主图_240x240_GIF/ 内的 15 个 GIF。
3. 对应上传 横幅、封面、图标、赞赏引导图、赞赏致谢图。
4. 按键盘上的【F12】键（或右键网页空白处选择“检查”），点击顶部的【Console (控制台)】。
5. 打开本文件夹下的【微信后台_F12一键填表脚本.js】，全选复制，粘贴进控制台按回车(Enter)！
6. 瞬间搞定：名称、介绍、赞赏语、15个表情含义全部自动填满并勾选原创！
=======================================================
"""
        txt_path = os.path.join(export_dir, "微信提审文案与操作指南.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(guide_text)

        return export_dir
