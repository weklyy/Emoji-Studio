# 微信表情开放平台官方规格与红线常量
class WeChatSpecs:
    # 表情主图
    MAIN_GIF_WIDTH = 240
    MAIN_GIF_HEIGHT = 240
    MAIN_GIF_MAX_KB = 500
    MAIN_GIF_SAFE_KB = 450  # 软件内置安全控制线，杜绝任何临界超标
    
    # 详情页横幅 (进入专辑详情页展示，严禁文字，严禁纯白底)
    BANNER_WIDTH = 750
    BANNER_HEIGHT = 400
    BANNER_MAX_KB = 500
    BANNER_SAFE_KB = 400
    
    # 表情封面图 (首页展示，必须透明背景)
    COVER_WIDTH = 240
    COVER_HEIGHT = 240
    COVER_MAX_KB = 80
    COVER_SAFE_KB = 75
    
    # 聊天面板图标 (聊天键盘中展示，微距特写)
    ICON_WIDTH = 50
    ICON_HEIGHT = 50
    ICON_MAX_KB = 30
    ICON_SAFE_KB = 25
    
    # 赞赏引导图 (选择赞赏金额页)
    REWARD_GUIDE_WIDTH = 750
    REWARD_GUIDE_HEIGHT = 560
    REWARD_GUIDE_MAX_KB = 100
    REWARD_GUIDE_SAFE_KB = 90
    
    # 赞赏致谢图 (赞赏成功答谢页)
    REWARD_THANKS_WIDTH = 750
    REWARD_THANKS_HEIGHT = 750
    REWARD_THANKS_MAX_KB = 200
    REWARD_THANKS_SAFE_KB = 180

    # 缩略图 (表情面板)
    THUMB_WIDTH = 120
    THUMB_HEIGHT = 120
    THUMB_MAX_KB = 50
