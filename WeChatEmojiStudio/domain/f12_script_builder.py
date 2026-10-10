import json

class F12ScriptBuilder:
    """
    全自动生成微信表情开放平台提交页面的 F12 控制台脚本
    用户在审核上传页面按 F12 粘贴回车，全页面字段瞬间秒级自动填满并触发响应事件
    """

    @staticmethod
    def build_script(
        title: str,
        intro: str,
        reward_text: str,
        meanings: list,
        tags: list = None
    ) -> str:
        """
        生成一键自动填表的 JavaScript 脚本代码
        """
        title_json = json.dumps(title, ensure_ascii=False)
        intro_json = json.dumps(intro, ensure_ascii=False)
        reward_json = json.dumps(reward_text, ensure_ascii=False)
        meanings_json = json.dumps(meanings, ensure_ascii=False)
        tags_json = json.dumps(tags or ["日常", "问候"], ensure_ascii=False)

        js_code = f"""(function autoFillWeChatEmoji() {{
    console.log("%c[WeChatEmojiStudio] 开始全自动填写微信表情提审表单...", "color: #07C160; font-size: 14px; font-weight: bold;");

    const data = {{
        title: {title_json},
        intro: {intro_json},
        reward: {reward_json},
        tags: {tags_json},
        meanings: {meanings_json}
    }};

    // 辅助工具：向输入框填值并触发 React / Vue 内部状态更新
    function setInputValue(el, val) {{
        if (!el) return false;
        el.focus();
        // 尝试通过原生 prototype setter 设置，绕过受控组件劫持
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, "value"
        )?.set;
        const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, "value"
        )?.set;

        if (el.tagName === "TEXTAREA" && nativeTextAreaValueSetter) {{
            nativeTextAreaValueSetter.call(el, val);
        }} else if (nativeInputValueSetter) {{
            nativeInputValueSetter.call(el, val);
        }} else {{
            el.value = val;
        }}

        el.dispatchEvent(new Event("input", {{ bubbles: true, cancelable: true }}));
        el.dispatchEvent(new Event("change", {{ bubbles: true, cancelable: true }}));
        el.blur();
        return true;
    }}

    // 1. 填写表情专辑名称 (不超过 8 个字)
    let titleInput = document.querySelector('input[placeholder*="名称"]') 
        || Array.from(document.querySelectorAll('input')).find(i => {{
            const p = i.closest('.weui-desktop-form__control') || i.parentElement;
            return p && (p.textContent.includes('名称') || p.previousElementSibling?.textContent.includes('名称'));
        }});
    if (titleInput && setInputValue(titleInput, data.title)) {{
        console.log("✔ 表情名称已填入:", data.title);
    }}

    // 2. 填写表情介绍 (不超过 100 个字)
    let introInput = document.querySelector('textarea') 
        || document.querySelector('textarea[placeholder*="介绍"]')
        || document.querySelector('input[placeholder*="介绍"]');
    if (introInput && setInputValue(introInput, data.intro)) {{
        console.log("✔ 专辑介绍已填入:", data.intro);
    }}

    // 3. 填写赞赏引导语 (不超过 15 个字)
    let rewardInput = document.querySelector('input[placeholder*="引导语"]')
        || Array.from(document.querySelectorAll('input')).find(i => {{
            const p = i.closest('.weui-desktop-form__control') || i.parentElement;
            return p && p.textContent.includes('引导') || p?.previousElementSibling?.textContent.includes('赞赏');
        }});
    if (rewardInput && setInputValue(rewardInput, data.reward)) {{
        console.log("✔ 赞赏引导语已填入:", data.reward);
    }}

    // 4. 自动填写 15 个表情含义输入框
    const meaningInputs = Array.from(document.querySelectorAll('input[placeholder*="含义"]'));
    let filledCount = 0;
    meaningInputs.forEach((inp, idx) => {{
        if (data.meanings[idx]) {{
            setInputValue(inp, data.meanings[idx]);
            filledCount++;
        }}
    }});
    console.log(`✔ 成功填入 ${{filledCount}} / ${{data.meanings.length}} 个表情含义输入框！`);

    // 5. 自动勾选通用合规选项 (如果存在对应 label 或 checkbox)
    function checkRadioOrCheckbox(labelKeyword) {{
        const labels = Array.from(document.querySelectorAll('label, .weui-desktop-radio, .weui-desktop-checkbox'));
        for (const lbl of labels) {{
            if (lbl.textContent.includes(labelKeyword)) {{
                const input = lbl.querySelector('input[type="radio"], input[type="checkbox"]') || lbl;
                if (input) {{
                    input.click();
                    return true;
                }}
            }}
        }}
        return false;
    }}

    checkRadioOrCheckbox("个人原创作品");
    checkRadioOrCheckbox("中国大陆");
    checkRadioOrCheckbox("免费");
    checkRadioOrCheckbox("开通赞赏");

    alert(`🎉 恭喜！WeChatEmojiStudio 已为您自动填满全页面所有内容：\\n1. 表情名称：${{data.title}}\\n2. 专辑介绍：已填写\\n3. 赞赏引导语：${{data.reward}}\\n4. 表情含义：${{filledCount}} 个全部填满！`);
}})();"""
        return js_code
