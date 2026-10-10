import os
import json
import re

class ProjectManager:
    """
    微信表情包项目与资产管理器
    自动扫描管理工作区目录，维护审核状态、上传时间与方案信息
    """

    DEFAULT_WORKSPACE = r"D:\Work\apps\微信表情包"

    @classmethod
    def list_projects(cls, workspace_dir: str = None) -> list:
        root = workspace_dir or cls.DEFAULT_WORKSPACE
        if not os.path.exists(root):
            return []

        projects = []
        for name in os.listdir(root):
            p_dir = os.path.join(root, name)
            if os.path.isdir(p_dir) and name not in ["WeChatEmojiStudio", "test_auto_slice", ".git", ".gemini"]:
                info = cls.load_project(p_dir)
                projects.append(info)
        return projects

    @classmethod
    def load_project(cls, project_dir: str) -> dict:
        json_path = os.path.join(project_dir, "project.json")
        project_name = os.path.basename(project_dir)

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["dir"] = project_dir
                    # 重新刷新一次 meanings 确保准确
                    scheme_txt = os.path.join(project_dir, "方案.txt")
                    if os.path.exists(scheme_txt):
                        parsed = cls.parse_scheme_file(scheme_txt)
                        if parsed.get("meanings"):
                            data["meanings"] = parsed["meanings"]
                    return data
            except Exception:
                pass

        data = {
            "name": project_name,
            "dir": project_dir,
            "title": project_name,
            "intro": "微信表情包专辑",
            "reward_text": "鼓励一下作者吧",
            "tags": ["日常", "问候"],
            "meanings": [f"表情_{i+1:02d}" for i in range(15)],
            "upload_date": "",
            "status": "draft",
            "created_at": ""
        }

        scheme_files = [os.path.join(project_dir, "方案.txt"), os.path.join(project_dir, "方案.md")]
        for sf in scheme_files:
            if os.path.exists(sf):
                data.update(cls.parse_scheme_file(sf))
                break

        gifs_dir = os.path.join(project_dir, "gifs")
        if os.path.exists(gifs_dir) and len([f for f in os.listdir(gifs_dir) if f.endswith(".gif")]) >= 8:
            data["status"] = "sliced"

        for item in os.listdir(project_dir):
            if "物料包" in item:
                data["status"] = "submitted"
                break

        cls.save_project(data)
        return data

    @staticmethod
    def extract_title_and_index_from_filename(filename: str, fallback_idx: int = 1) -> tuple:
        """
        从文件名智能提取序号与标题
        例如:
        01_你好.gif -> (1, "你好")
        02 谢谢.gif -> (2, "谢谢")
        03.收到.gif -> (3, "收到")
        04-点赞.gif -> (4, "点赞")
        05加油.gif  -> (5, "加油")
        你好.gif    -> (fallback_idx, "你好")
        01_收到_T.gif -> (1, "收到")
        01_T.gif    -> (1, "")
        01.gif      -> (1, "")
        """
        base = os.path.splitext(os.path.basename(filename))[0]
        base = re.sub(r'(_T|_t|_transparent)$', '', base, flags=re.IGNORECASE)
        m = re.match(r'^(?:pic)?0*(\d{1,2})[\s_.\-—]*(.*)$', base, re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            t = m.group(2).strip()
            if t.lower() in ['t', 'transparent', '']:
                t = ''
            return idx, t
        return fallback_idx, base.strip()

    @classmethod
    def save_project(cls, data: dict):
        p_dir = data.get("dir")
        if not p_dir or not os.path.exists(p_dir):
            return
        json_path = os.path.join(p_dir, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 同步写入/更新 方案.txt 保证持久化对齐
        meanings = data.get("meanings")
        if meanings:
            scheme_txt = os.path.join(p_dir, "方案.txt")
            title = data.get("title", data.get("name", "表情专辑"))
            try:
                with open(scheme_txt, "w", encoding="utf-8") as f:
                    f.write(f"【{title}】\n")
                    for i, m in enumerate(meanings, 1):
                        f.write(f"{i:02d}\t{m}\n")
            except Exception:
                pass

    @staticmethod
    def parse_scheme_file(file_path: str) -> dict:
        """
        自动解析方案文件中的标题、介绍与 15 个表情含义 (精确匹配 01~15 序号行)
        """
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        res = {}
        match_title = re.search(r"《(.*?)》", text)
        if match_title:
            res["title"] = match_title.group(1)[:8]

        lines = text.splitlines()
        meanings_dict = {}

        for line in lines:
            line = line.strip()
            # 严格匹配行首序号 01 到 15 (或 1 到 15)
            m = re.match(r"^(0?[1-9]|1[0-5])[\t\s]+([^\t\r\n]+)", line)
            if m:
                idx = int(m.group(1))
                parts = re.split(r"\t+|\s{2,}", line)
                if len(parts) >= 2:
                    word = parts[1].strip()
                    # 避免匹配到表头
                    if word and word not in ["画面大字", "标题", "画面视觉元素"]:
                        meanings_dict[idx] = word[:12]

        if meanings_dict:
            res["meanings"] = [meanings_dict.get(i, f"表情_{i:02d}") for i in range(1, 16)]

        if "为什么这个创新方案能引爆" in text or "痛点" in text:
            intro_lines = [l for l in lines if l and not l.startswith("序号") and not re.match(r"^\d", l)]
            if len(intro_lines) > 2:
                res["intro"] = "".join(intro_lines[1:3])[:90]

        return res
